from typing import Dict, List, Optional, Tuple, Any
import json
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

from utils.numpy_implementation import (
    NumPyReferenceEngine,
    float32_reciprocal,
    get_node_attribute,
)
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


def unblock_vta_output(raw: np.ndarray, shape: Tuple[int, ...], block_size: int = 16) -> np.ndarray:
    """Converts a square VTA block stream to a logical NCHW tensor.

    Args:
        raw: Flat values ordered as ``[row_block, col_block, row, col]``.
        shape: Logical NCHW tensor shape.
        block_size: VTA tensor block dimension.

    Returns:
        Logical tensor cropped to its unpadded dimensions.

    Raises:
        ValueError: If the raw element count does not match the padded shape.
    """
    batch, channels, height, width = shape
    logical_rows = batch * height * width
    padded_rows = ((logical_rows + block_size - 1) // block_size) * block_size
    padded_channels = ((channels + block_size - 1) // block_size) * block_size
    expected_size = padded_rows * padded_channels
    if raw.size != expected_size:
        raise ValueError(f"Expected {expected_size} blocked values, got {raw.size}.")
    blocks = raw.reshape(
        padded_rows // block_size,
        padded_channels // block_size,
        block_size,
        block_size,
    )
    matrix = blocks.transpose(0, 2, 1, 3).reshape(padded_rows, padded_channels)
    logical = matrix[:logical_rows, :channels]
    return logical.reshape(batch, height, width, channels).transpose(0, 3, 1, 2)


def debug_quantized_mismatches(
    node: Any,
    tensors: Dict[str, np.ndarray],
    mismatch_indices: Tuple[np.ndarray, ...],
    max_print: int = 5,
) -> None:
    """Prints embedded-contract intermediates for quantized mismatches.

    Args:
        node: ONNX node whose output differs.
        tensors: Reference-engine tensor mapping, including initializers.
        mismatch_indices: Coordinates of differing output elements.
        max_print: Maximum number of mismatch calculations to print.
    """
    if node.op_type not in {
        "QLinearAdd",
        "QLinearMul",
        "QLinearConcat",
        "QuantizeLinear",
        "QLinearConv",
    }:
        return
    print("     Embedded arithmetic breakdown:")
    for mismatch_idx in range(min(max_print, len(mismatch_indices[0]))):
        coords = tuple(int(dim[mismatch_idx]) for dim in mismatch_indices)
        if node.op_type == "QLinearAdd":
            a = int(tensors[node.input[0]][coords])
            za = int(np.asarray(tensors[node.input[2]]).reshape(()))
            b = int(tensors[node.input[3]][coords])
            zb = int(np.asarray(tensors[node.input[5]]).reshape(()))
            sa = np.float32(tensors[node.input[1]])
            sb = np.float32(tensors[node.input[4]])
            sc = np.float32(tensors[node.input[6]])
            inv_c = float32_reciprocal(sc)
            multiplier_a = np.float32(sa * inv_c)
            multiplier_b = np.float32(sb * inv_c)
            term_a = np.float32((a - za) * multiplier_a)
            term_b = np.float32((b - zb) * multiplier_b)
            scaled = np.float32(term_a + term_b)
            distance = abs(float(scaled - np.floor(scaled)) - 0.5)
            print(
                f"       {coords}: A={a}, B={b}, centered=({a-za},{b-zb}), "
                f"invC={inv_c!r}, multipliers=({multiplier_a!r},{multiplier_b!r}), "
                f"terms=({term_a!r},{term_b!r}), pre-round={scaled!r}, "
                f"distance-to-half={distance:.9g}"
            )
        elif node.op_type == "QLinearMul":
            a = int(np.asarray(tensors[node.input[0]])[coords] if tensors[node.input[0]].size > 1 else np.asarray(tensors[node.input[0]]).reshape(-1)[0])
            b = int(np.asarray(tensors[node.input[3]])[coords] if tensors[node.input[3]].size > 1 else np.asarray(tensors[node.input[3]]).reshape(-1)[0])
            za = int(np.asarray(tensors[node.input[2]]).reshape(()))
            zb = int(np.asarray(tensors[node.input[5]]).reshape(()))
            scale = np.float32(
                np.float32(np.float32(tensors[node.input[1]]) * np.float32(tensors[node.input[4]]))
                / np.float32(tensors[node.input[6]])
            )
            accumulator = (a - za) * (b - zb)
            scaled = float(accumulator) * float(scale)
            print(
                f"       {coords}: centered=({a-za},{b-zb}), accumulator={accumulator}, "
                f"multiplier={scale!r}, pre-round={scaled!r}"
            )
        elif node.op_type == "QLinearConcat":
            output_channel = coords[1]
            branch_start = 0
            inv_scale = float32_reciprocal(tensors[node.input[0]])
            for input_idx in range(2, len(node.input), 3):
                branch = tensors[node.input[input_idx]]
                branch_channels = branch.shape[1]
                if output_channel < branch_start + branch_channels:
                    branch_coords = list(coords)
                    branch_coords[1] -= branch_start
                    branch_coords_tuple = tuple(branch_coords)
                    value = int(branch[branch_coords_tuple])
                    zero_point = int(
                        np.asarray(tensors[node.input[input_idx + 2]]).reshape(())
                    )
                    multiplier = np.float32(
                        np.float32(tensors[node.input[input_idx + 1]]) * inv_scale
                    )
                    scaled = np.float32((value - zero_point) * multiplier)
                    distance = abs(float(scaled - np.floor(scaled)) - 0.5)
                    print(
                        f"       {coords}: branch={(input_idx-2)//3}, value={value}, "
                        f"centered={value-zero_point}, multiplier={multiplier!r}, "
                        f"pre-round={scaled!r}, distance-to-half={distance:.9g}"
                    )
                    break
                branch_start += branch_channels
        elif node.op_type == "QuantizeLinear":
            value = np.float32(tensors[node.input[0]][coords])
            inv_scale = float32_reciprocal(tensors[node.input[1]])
            scaled = np.float32(value * inv_scale)
            distance = abs(float(scaled - np.floor(scaled)) - 0.5)
            print(
                f"       {coords}: value={value!r}, inv-scale={inv_scale!r}, "
                f"pre-round={scaled!r}, distance-to-half={distance:.9g}"
            )
        else:
            print(f"       {coords}: see pre-rescale accumulator comparison above.")


def compare_float_layer_outputs(
    ref_val: np.ndarray,
    sim_val: np.ndarray,
    layer_name: str,
    idx: int,
) -> bool:
    """Compares float32 tensors by IEEE-754 bit patterns, without tolerance.

    Args:
        ref_val: Logical NCHW reference tensor with dtype float32.
        sim_val: Logical NCHW simulator tensor with dtype float32.
        layer_name: Layer identifier used in the printed report.
        idx: Zero-based graph node index.

    Returns:
        True only when every float32 bit pattern agrees, including signed zero
        and NaN payloads. Numerical errors are printed only as diagnostics.
    """
    ref_bits = ref_val.view(np.uint32)
    sim_bits = sim_val.view(np.uint32)
    mismatched = ref_bits != sim_bits
    count = int(np.count_nonzero(mismatched))
    if count == 0:
        print(f"[{idx:02d}] {layer_name:18s}: MATCH (shape: {ref_val.shape}, float32 bits)")
        return True

    # Subtract in float64 for diagnostics; never cast fractional values to
    # integers or apply a tolerance to the actual equality decision.
    with np.errstate(invalid="ignore", over="ignore"):
        abs_diff = np.abs(ref_val.astype(np.float64) - sim_val.astype(np.float64))
    finite_diff = abs_diff[np.isfinite(abs_diff)]
    max_diff = float(np.max(finite_diff)) if finite_diff.size else float("nan")
    print(
        f"[{idx:02d}] {layer_name:18s}: MISMATCH! Shape: {ref_val.shape}, "
        f"float32 bit mismatches: {count}/{ref_val.size}, "
        f"Max finite abs diff: {max_diff:.9g}"
    )
    coordinates = np.where(mismatched)
    for mismatch_idx in range(min(5, count)):
        coords = tuple(int(axis[mismatch_idx]) for axis in coordinates)
        print(
            f"       at NCHW {coords}: "
            f"Ref={float(ref_val[coords]):.9g} (0x{int(ref_bits[coords]):08x}), "
            f"Sim={float(sim_val[coords]):.9g} (0x{int(sim_bits[coords]):08x}), "
            f"abs diff={float(abs_diff[coords]):.9g}"
        )
    return False


def compare_layer_outputs(
    ref_val: np.ndarray,
    sim_val: np.ndarray,
    layer_name: str,
    idx: int,
    node: Any = None,
    input_val: Optional[np.ndarray] = None,
    tensors: Optional[Dict[str, np.ndarray]] = None,
) -> bool:
    """Compares the reference NumPy tensor with the simulator output tensor.

    Args:
        ref_val: Reference output array from NumPy engine.
        sim_val: Simulator output array loaded from binary dump.
        layer_name: Identifier name of the layer.
        idx: Index of the node in the execution graph.
        node: Optional ONNX graph node.
        input_val: Optional input array to this layer.
        tensors: Optional reference tensor mapping used for arithmetic diagnostics.

    Returns:
        bool: True if tensors are bit-exact equal, False otherwise.
    """
    if ref_val.shape != sim_val.shape or ref_val.dtype != sim_val.dtype:
        print(
            f"[{idx:02d}] {layer_name:18s}: MISMATCH! "
            f"Ref shape/dtype={ref_val.shape}/{ref_val.dtype}, "
            f"Sim shape/dtype={sim_val.shape}/{sim_val.dtype}"
        )
        return False
    if ref_val.dtype == np.dtype(np.float32):
        return compare_float_layer_outputs(ref_val, sim_val, layer_name, idx)

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
    if node is not None and tensors is not None:
        debug_quantized_mismatches(node, tensors, mismatch_indices, max_print=5)

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
    # run_pipeline uses this same hardware configuration. Do not assume B=16
    # when decoding the pre-rescale stream of a different VTA configuration.
    with open(os.path.join(standalone_vta_dir, "config/vta_config.json"), encoding="utf-8") as config_file:
        hardware_config = json.load(config_file)
    block_size = 1 << int(hardware_config["LOG_BLOCK"])
    output_bits = 1 << int(hardware_config["LOG_OUT_WIDTH"])

    for idx, node in enumerate(engine.graph.node):
        op_type: str = node.op_type
        layer_name: str = f"{op_type}{idx + 1}"
        output_name: str = node.output[0]

        if output_name not in engine.tensors:
            print(f"[{idx:02d}] {layer_name:18s}: Skipping (node output tensor '{output_name}' not computed)")
            continue

        ref_val: np.ndarray = engine.tensors[output_name]

        if output_name in engine.integer_accumulators:
            raw_acc_path = os.path.join(sim_out_dir, f"output{layer_name}.bin")
            if os.path.exists(raw_acc_path):
                expected_acc = engine.integer_accumulators[output_name]
                rows = ref_val.shape[0] * ref_val.shape[2] * ref_val.shape[3]
                padded_rows = ((rows + block_size - 1) // block_size) * block_size
                padded_channels = ((ref_val.shape[1] + block_size - 1) // block_size) * block_size
                padded_count = padded_rows * padded_channels
                if output_bits == 32 and os.path.getsize(raw_acc_path) == padded_count * np.dtype(np.int32).itemsize:
                    raw_acc = np.fromfile(raw_acc_path, dtype=np.int32)
                    sim_acc = unblock_vta_output(raw_acc, ref_val.shape, block_size)
                    acc_equal = np.array_equal(expected_acc, sim_acc)
                    acc_mismatches = int(np.count_nonzero(expected_acc != sim_acc))
                    status = "MATCH" if acc_equal else f"MISMATCH ({acc_mismatches})"
                    print(f"     Pre-rescale accumulator: {status}")
                    # Saturation can hide an incorrect accumulator in the
                    # int8 result; this check must affect the exit status too.
                    if not acc_equal:
                        all_matched = False
                else:
                    print("     Pre-rescale accumulator: NOT CHECKED (OUT width or dump size)")

        # Retrieve input tensor to this node
        input_tensor_name = node.input[0]
        layer_input_val: Optional[np.ndarray] = engine.tensors.get(input_tensor_name, None)

        # Search for simulator output in simulators_output/ then compiler_output/
        sim_path: str = os.path.join(sim_out_dir, f"fsim_out_{layer_name}.bin")
        if not os.path.exists(sim_path):
            sim_path = os.path.join(output_dir, f"fsim_out_{layer_name}.bin")

        if not os.path.exists(sim_path):
            print(f"[{idx:02d}] {layer_name:18s}: FAILURE: Output file 'fsim_out_{layer_name}.bin' not found.")
            all_matched = False
            continue

        # The file contains NCHW int8 for quantized nodes and NCHW IEEE-754
        # float32 for DequantizeLinear/ConvTranspose. No header is added: the
        # operator fixes the dtype, and the logical tensor fixes its byte count.
        dump_dtype = np.dtype(np.float32 if op_type in {"DequantizeLinear", "ConvTranspose"} else np.int8)
        expected_bytes = ref_val.size * dump_dtype.itemsize
        actual_bytes = os.path.getsize(sim_path)
        if actual_bytes != expected_bytes:
            print(
                f"[{idx:02d}] {layer_name:18s}: FAILURE: dump size "
                f"{actual_bytes} bytes, expected {expected_bytes} ({dump_dtype})."
            )
            all_matched = False
            continue
        sim_val: np.ndarray = np.fromfile(sim_path, dtype=dump_dtype).reshape(ref_val.shape)
        executed_layers_count += 1

        matched: bool = compare_layer_outputs(
            ref_val,
            sim_val,
            layer_name,
            idx,
            node=node,
            input_val=layer_input_val,
            tensors=engine.tensors,
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
