from typing import Dict, List, Optional, Tuple, Any
import os
import sys
import subprocess
import numpy as np

# Retrieve standalone-vta directories dynamically
script_dir: str = os.path.dirname(os.path.abspath(__file__))
standalone_vta_dir: str = os.path.abspath(os.path.join(script_dir, "../../.."))
examples_dir: str = os.path.join(standalone_vta_dir, "examples")
compiler_dir: str = os.path.join(standalone_vta_dir, "src/compiler")

sys.path.append(compiler_dir)

from utils.numpy_implementation import NumPyReferenceEngine, get_node_attribute
from utils.find_project_root import compiler_output_setup, filepath_definition
from utils.read_csv import load_csv_to_dict


def run_pipeline(model_path: str) -> None:
    """Compiles the model and runs functional simulation with layer dumping enabled.

    Args:
        model_path: Absolute path to the ONNX model file.

    Raises:
        RuntimeError: If the compilation or simulation subprocess fails.
    """
    print("Compiling and running functional simulation with layer dumping...", flush=True)
    try:
        subprocess.run(
            [
                "make",
                "-C",
                examples_dir,
                f"ONNX_FILE={model_path}",
                "RUNTIME_FLAGS=--dump-layers",
                "clean",
                "nn_compiler",
                "reference",
                "vta_compiler",
                "fsim_inference",
            ],
            check=True,
            env=os.environ.copy(),
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"VTA compilation or simulation run failed: {e}")


def load_input_tensor(output_dir: str, first_layer_name: str, dep_dict: Dict[str, List[str]]) -> Tuple[np.ndarray, str, List[int]]:
    """Loads the input tensor used by the functional simulator from input_nn.bin.

    Args:
        output_dir: Path to the compiler output directory.
        first_layer_name: Name of the first layer in the network.
        dep_dict: Dictionary parsed from dependency.csv.

    Returns:
        Tuple containing:
            - input_data: NumPy array of shape [1, C, H, W] with dtype int8.
            - real_input_name: ONNX graph input name.
            - input_shape: List representing tensor dimensions [1, C, H, W].

    Raises:
        FileNotFoundError: If input_nn.bin does not exist.
    """
    file_inp_path: str = filepath_definition(output_dir, "input_nn.bin")
    if not os.path.exists(file_inp_path):
        raise FileNotFoundError(f"Input binary file '{file_inp_path}' not found.")

    attributes: List[str] = dep_dict[first_layer_name]
    in_c: int = int(attributes[11])
    in_h: int = int(attributes[12])
    in_w: int = int(attributes[13])
    input_shape: List[int] = [1, in_c, in_h, in_w]

    raw_inp: np.ndarray = np.fromfile(file_inp_path, dtype=np.int8)
    # The reference_onnx script flattens (1, C, H, W) via transpose(0, 2, 3, 1).reshape(-1, C).
    # Reconstruct exact (1, C, H, W) shape matching the raw binary:
    input_data: np.ndarray = raw_inp.reshape(1, in_h, in_w, in_c).transpose(0, 3, 1, 2)
    return input_data, "input", input_shape


def debug_maxpool_mismatches(
    ref_val: np.ndarray,
    sim_val: np.ndarray,
    input_val: Optional[np.ndarray],
    node: Any,
    mismatch_indices: Tuple[np.ndarray, ...],
    max_print: int = 5,
) -> None:
    """Prints a detailed window-by-window pooling inspection for MaxPool mismatches.

    Args:
        ref_val: Reference output array [N, C, H_out, W_out].
        sim_val: Simulator output array [N, C, H_out, W_out].
        input_val: Input array to the MaxPool layer [N, C, H_in, W_in].
        node: ONNX graph node for MaxPool.
        mismatch_indices: Tuple of coordinate arrays where mismatches occur.
        max_print: Maximum number of mismatching windows to print in detail.
    """
    kernel_shape = get_node_attribute(node, "kernel_shape", default=(2, 2))
    strides = get_node_attribute(node, "strides", default=(2, 2))
    pads = get_node_attribute(node, "pads", default=(0, 0, 0, 0))

    kh, kw = kernel_shape[0], kernel_shape[1]
    sh, sw = strides[0], strides[1]
    pad_top, pad_left = pads[0], pads[1]

    print(f"\n     --- Detailed MaxPool Window Breakdown (Kernel={kernel_shape}, Strides={strides}) ---")

    num_to_print = min(max_print, len(mismatch_indices[0]))
    for m_idx in range(num_to_print):
        b = int(mismatch_indices[0][m_idx])
        c = int(mismatch_indices[1][m_idx])
        h_out = int(mismatch_indices[2][m_idx])
        w_out = int(mismatch_indices[3][m_idx])

        r_val = int(ref_val[b, c, h_out, w_out])
        s_val = int(sim_val[b, c, h_out, w_out])

        h_in_start = h_out * sh - pad_top
        w_in_start = w_out * sw - pad_left

        if input_val is not None:
            h_in_end = min(h_in_start + kh, input_val.shape[2])
            w_in_end = min(w_in_start + kw, input_val.shape[3])
            window = input_val[b, c, max(0, h_in_start):h_in_end, max(0, w_in_start):w_in_end]

            window_flat = [int(v) for v in window.flatten()]
            window_str = f"max({', '.join(map(str, window_flat))})" if window_flat else "[]"
            grid_str = str(window.tolist())

            print(f"     Mismatch #{m_idx + 1} at NCHW ({b}, {c}, {h_out}, {w_out}):")
            print(f"       Window input 2D grid (H:[{h_in_start}:{h_in_end}], W:[{w_in_start}:{w_in_end}]): {grid_str}")
            print(f"       Ref evaluation : {window_str} = {r_val}")
            print(f"       Sim output     : {s_val} (Diff: {r_val - s_val:+d})")
        else:
            print(f"     Mismatch #{m_idx + 1} at NCHW ({b}, {c}, {h_out}, {w_out}): Ref = {r_val}, Sim = {s_val} (Diff: {r_val - s_val:+d})")


def compare_layer_outputs(
    ref_val: np.ndarray,
    sim_val: np.ndarray,
    layer_name: str,
    idx: int,
    node: Any = None,
    input_val: Optional[np.ndarray] = None,
) -> bool:
    """Compares the reference NumPy tensor with the simulator output tensor.

    Args:
        ref_val: Reference output array from NumPy engine.
        sim_val: Simulator output array loaded from binary dump.
        layer_name: Identifier name of the layer.
        idx: Index of the node in the execution graph.
        node: Optional ONNX graph node.
        input_val: Optional input array to this layer.

    Returns:
        bool: True if tensors are bit-exact equal, False otherwise.
    """
    is_equal: bool = np.array_equal(ref_val, sim_val)
    if is_equal:
        print(f"[{idx:02d}] {layer_name:18s}: MATCH (shape: {ref_val.shape})")
        return True

    diff: np.ndarray = ref_val.astype(np.int32) - sim_val.astype(np.int32)
    abs_diff: np.ndarray = np.abs(diff)
    max_diff: int = int(np.max(abs_diff))
    mean_diff: float = float(np.mean(abs_diff))
    mismatch_indices: Tuple[np.ndarray, ...] = np.where(abs_diff > 0)
    num_mismatches: int = len(mismatch_indices[0])
    pct_mismatches: float = (num_mismatches / ref_val.size) * 100.0

    print(
        f"[{idx:02d}] {layer_name:18s}: MISMATCH! Shape: {ref_val.shape}, "
        f"Mismatches: {num_mismatches}/{ref_val.size} ({pct_mismatches:.3f}%), "
        f"Max Diff: {max_diff}, Mean Abs Diff: {mean_diff:.4f}"
    )

    # Difference distribution histogram
    unique_diffs, counts = np.unique(abs_diff[abs_diff > 0], return_counts=True)
    diff_dist_str = ", ".join(f"|diff|={d}: {c}" for d, c in zip(unique_diffs[:5], counts[:5]))
    print(f"     Error magnitude breakdown: {diff_dist_str}")

    # Print first few mismatch coordinates
    num_to_print: int = min(5, num_mismatches)
    print(f"     First {num_to_print} mismatches:")
    for m_idx in range(num_to_print):
        coords: Tuple[int, ...] = tuple(int(dim[m_idx]) for dim in mismatch_indices)
        r_val: int = int(ref_val[coords])
        s_val: int = int(sim_val[coords])
        d_val: int = int(diff[coords])
        print(f"       at NCHW {coords}: Ref = {r_val:4d}, Sim = {s_val:4d} (Diff: {d_val:+4d})")

    # If it is a MaxPool layer, print detailed window-by-window breakdown
    if node is not None and node.op_type == "MaxPool":
        debug_maxpool_mismatches(ref_val, sim_val, input_val, node, mismatch_indices, max_print=5)

    return False


def main() -> None:
    """Main execution function to run bit-accuracy layer-by-layer comparison."""
    if len(sys.argv) > 1:
        model_path: str = os.path.abspath(sys.argv[1])
    else:
        model_path: str = os.path.join(examples_dir, "onnx/qyolo_pattern.onnx")

    print(f"Target ONNX model: {model_path}", flush=True)
    if not os.path.exists(model_path):
        print(f"ERROR: Model file '{model_path}' does not exist.", flush=True)
        sys.exit(1)

    # Step 1: Run compilation and simulation
    run_pipeline(model_path)

    # Output directories
    output_dir: str = compiler_output_setup()
    sim_out_dir: str = os.path.join(standalone_vta_dir, "simulators_output")

    # Read dependency metadata
    file_dep_path: str = filepath_definition(output_dir, "dependency.csv")
    dep_dict: Dict[str, List[str]] = load_csv_to_dict(file_dep_path)
    if not dep_dict or "0" not in dep_dict:
        print(f"ERROR: Invalid or missing dependency.csv at '{file_dep_path}'.")
        sys.exit(1)

    first_layer_name: str = dep_dict["0"][2]

    # Step 2: Load input tensor and initialize NumPy Reference Engine
    input_data, _, input_shape = load_input_tensor(output_dir, first_layer_name, dep_dict)
    print(f"Using input tensor shape: {input_shape}")

    engine: NumPyReferenceEngine = NumPyReferenceEngine(model_path)
    real_input_name: str = engine.graph.input[0].name
    engine.run(real_input_name, input_data)

    print("\n" + "=" * 80)
    print("STARTING LAYER-BY-LAYER BIT-ACCURACY COMPARISON (fsim vs NumPy)")
    print("=" * 80)

    all_matched: bool = True
    executed_layers_count: int = 0

    for idx, node in enumerate(engine.graph.node):
        op_type: str = node.op_type
        layer_name: str = f"{op_type}{idx + 1}"
        output_name: str = node.output[0]

        if output_name not in engine.tensors:
            print(f"[{idx:02d}] {layer_name:18s}: Skipping (node output tensor '{output_name}' not computed)")
            continue

        ref_val: np.ndarray = engine.tensors[output_name]

        # Retrieve input tensor to this node
        input_tensor_name = node.input[0]
        layer_input_val: Optional[np.ndarray] = engine.tensors.get(input_tensor_name, None)

        # Search for simulator output in simulators_output/ then compiler_output/
        sim_path: str = os.path.join(sim_out_dir, f"fsim_out_{layer_name}.bin")
        if not os.path.exists(sim_path):
            sim_path = os.path.join(output_dir, f"fsim_out_{layer_name}.bin")

        if not os.path.exists(sim_path):
            print(f"[{idx:02d}] {layer_name:18s}: [WARNING] Output file 'fsim_out_{layer_name}.bin' not found. Skipped.")
            continue

        sim_val: np.ndarray = np.fromfile(sim_path, dtype=np.int8).reshape(ref_val.shape)
        executed_layers_count += 1

        matched: bool = compare_layer_outputs(
            ref_val, sim_val, layer_name, idx, node=node, input_val=layer_input_val
        )
        if not matched:
            all_matched = False

    print("=" * 80)
    if executed_layers_count == 0:
        print("FAILURE: No simulated layer output files were found to compare.")
        sys.exit(1)
    elif all_matched:
        print(f"SUCCESS: All {executed_layers_count} simulated layers match the NumPy reference model bit-for-bit!")
    else:
        print("FAILURE: Mismatches detected in functional simulation layers.")
        sys.exit(1)


if __name__ == "__main__":
    main()
