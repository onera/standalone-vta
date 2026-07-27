import numpy as np
import os

_DTYPE_FROM_STORAGE = {
    "int8": np.int8,
    "int16": np.int16,
    "int32": np.int32,
    "uint8": np.uint8,
    "uint16": np.uint16,
    "uint32": np.uint32,
}


# Hardcoded VTA program used in random-data mode. Kept here so existing
# `make test_gemm` invocations keep emitting the same program they always did.
_HARDCODED_INSN_WORDS = np.array(
    [
        0x00000000,
        0x00000050,
        0x00010001,
        0x00000001,
        0x002000A2,
        0x00200008,
        0x00000810,
        0x00000000,
        0x00000110,
        0x00000001,
        0x00100001,
        0x00000010,
        0x200000C0,
        0x00000000,
        0x00010001,
        0x00000001,
        0x00000188,
        0x00000003,
        0x00100001,
        0x00000010,
        0x04000000,
        0x00000050,
        0x00010001,
        0x00000001,
        0x00200062,
        0x00200008,
        0x00000800,
        0x00000002,
        0x00000229,
        0x00000004,
        0x00100001,
        0x00000010,
        0x00000150,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000018,
        0x00000000,
        0x00000000,
        0x00000000,
        0x00000003,
        0x00000000,
        0x00000000,
        0x00000000,
    ],
    dtype=np.uint32,
)
_HARDCODED_UOP_WORDS = np.array([0x00000000, 0x00000000], dtype=np.uint32)

_HEADER_INCLUDES = """#include <cstddef>
#include <cstdint>
#include <cstring>

#include "vta.h"
"""

_FINISH_INSN_BLOCK = (
    "static const VTAInsn insn_finish[] = {\n"
    "    {{0x00000003u, 0x00000000u, 0x00000000u, 0x00000000u}}\n"
    "};\n"
)


def format_c_array(name, data, storage_dtype_str, chunk_size):
    """Format a numpy array into a C++ static const array (decimal, aligned)."""
    c_type = f"std::{storage_dtype_str}_t"
    res = f"static const {c_type} {name}[] = {{\n"

    flat_data = data.flatten()
    rows = []

    max_len = max(len(str(int(val))) for val in flat_data)

    for i in range(0, len(flat_data), chunk_size):
        chunk = flat_data[i : i + chunk_size]
        row_str = ", ".join([f"{int(val):>{max_len}}" for val in chunk])
        rows.append("    " + row_str)

    res += ",\n".join(rows)
    res += "\n};\n"
    return res


def format_insn_array(name, insn_words):
    """Emit `static const VTAInsn name[] = { ... };` from a uint32 word stream.

    Each VTAInsn is 4 x uint32 (128-bit). Length must be a multiple of 4.
    """
    if insn_words.size % 4 != 0:
        raise ValueError(
            f"Instruction stream has {insn_words.size} uint32 words; "
            f"expected a multiple of 4 (each VTAInsn is 4 x uint32)."
        )
    rows = insn_words.reshape(-1, 4)
    lines = [f"static const VTAInsn {name}[] = {{"]
    for i, row in enumerate(rows):
        hex_vals = ", ".join(f"0x{int(w) & 0xFFFFFFFF:08X}u" for w in row)
        sep = "," if i < len(rows) - 1 else ""
        lines.append(f"    {{{{{hex_vals}}}}}{sep}")
    lines.append("};")
    return "\n".join(lines) + "\n"


def format_uop_array(name, uop_words, chunk_size=4):
    """Emit `static const std::uint32_t name[] = { ... };` from a uint32 stream."""
    lines = [f"static const std::uint32_t {name}[] = {{"]
    n = len(uop_words)
    for i in range(0, n, chunk_size):
        chunk = uop_words[i : i + chunk_size]
        hex_vals = ", ".join(f"0x{int(w) & 0xFFFFFFFF:08X}u" for w in chunk)
        sep = "," if i + chunk_size < n else ""
        lines.append(f"    {hex_vals}{sep}")
    lines.append("};")
    return "\n".join(lines) + "\n"


def _load_bin(path, dtype, label):
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"{label}: required compiler-output file not found: {path}"
        )
    itemsize = np.dtype(dtype).itemsize
    nbytes = os.path.getsize(path)
    if nbytes % itemsize != 0:
        raise ValueError(
            f"{label}: file {path} has {nbytes} bytes, not a multiple of "
            f"{itemsize} ({np.dtype(dtype).name}). Check the matching "
            f"--*-storage flag."
        )
    return np.fromfile(path, dtype=dtype)


def _check_matrix_size(arr, n, label):
    if arr.size != n * n:
        raise ValueError(
            f"{label}: expected {n}*{n}={n * n} elements, got {arr.size}. "
            f"Adjust -n or check storage dtypes."
        )


def _compute_golden(inp, wgt, acc, acc_dtype, out_dtype):
    """Compute the SOUT-truncated golden output for a GEMM:
        acc_golden = acc + inp @ wgt.T   (in acc_dtype, to avoid overflow)
        out_golden = acc_golden.astype(out_dtype)   (matches compiler reference
                     truncate_to_int8 wrap semantics for narrowing casts)
    `acc` carries the initial accumulator state (usually zeros for test_gemm).
    """
    acc_golden = acc.astype(acc_dtype) + np.matmul(
        inp.astype(acc_dtype), np.transpose(wgt.astype(acc_dtype))
    )
    return acc_golden.astype(out_dtype)


def _load_from_compiler_output(
    compiler_output_dir,
    suffix,
    n,
    input_dtype,
    weight_dtype,
    acc_dtype,
    out_dtype,
):
    """Read input/weight/accumulator/uop/instructions from a compiler_output
    directory. The golden is computed in-script from the loaded matrices.
    """
    if not os.path.isdir(compiler_output_dir):
        raise FileNotFoundError(
            f"--compiler-output-dir not found or not a directory: "
            f"{compiler_output_dir}"
        )

    def p(basename):
        return os.path.join(compiler_output_dir, f"{basename}{suffix}.bin")

    inp = _load_bin(p("input"), input_dtype, "input")
    _check_matrix_size(inp, n, "input")
    inp = inp.reshape((n, n))

    wgt = _load_bin(p("weight"), weight_dtype, "weight")
    _check_matrix_size(wgt, n, "weight")
    wgt = wgt.reshape((n, n))

    acc = _load_bin(p("accumulator"), acc_dtype, "accumulator")
    _check_matrix_size(acc, n, "accumulator")
    acc = acc.reshape((n, n))

    out_golden = _compute_golden(inp, wgt, acc, acc_dtype, out_dtype)

    uop_words = _load_bin(p("uop"), np.uint32, "uop")
    insn_words = _load_bin(p("instructions"), np.uint32, "instructions")
    return inp, wgt, acc, out_golden, uop_words, insn_words


def _generate_random(
    n, input_dtype, weight_dtype, acc_dtype, out_dtype, min_val, max_val
):
    """Random-data path. Same golden formula as the compiler-output path."""
    inp = np.random.randint(min_val, max_val + 1, size=(n, n), dtype=input_dtype)
    wgt = np.random.randint(min_val, max_val + 1, size=(n, n), dtype=weight_dtype)
    acc_init = np.zeros((n, n), dtype=acc_dtype)
    out_golden = _compute_golden(inp, wgt, acc_init, acc_dtype, out_dtype)
    return (
        inp,
        wgt,
        acc_init,
        out_golden,
        _HARDCODED_UOP_WORDS,
        _HARDCODED_INSN_WORDS,
    )


def generate_vta_test_header(
    n=16,
    input_dtype=np.int8,
    weight_dtype=np.int8,
    inp_storage_dtype="int32",
    wgt_storage_dtype="int32",
    acc_storage_dtype="int32",
    out_storage_dtype=None,
    acc_dtype=np.int32,
    out_dtype=None,
    min_val=-128,
    max_val=127,
    path="gen/",
    filename="init_dram.h",
    compiler_output_dir=None,
    suffix="",
):
    # SOUT semantics: low N bits of each accumulator word, reinterpreted as
    # out_dtype. Numpy .astype(out_dtype) reproduces this for narrowing casts
    # and is identity when out_dtype == acc_dtype.
    if out_storage_dtype is None:
        out_storage_dtype = acc_storage_dtype
    if out_dtype is None:
        out_dtype = _DTYPE_FROM_STORAGE[out_storage_dtype]

    # Determine absolute path to avoid writing errors depending on CWD
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gen_dir_path = os.path.join(os.path.dirname(script_dir), path)
    os.makedirs(gen_dir_path, exist_ok=True)
    full_path = os.path.join(gen_dir_path, filename)

    if compiler_output_dir is not None:
        inp, wgt, acc, out_golden, uop_words, insn_words = _load_from_compiler_output(
            compiler_output_dir,
            suffix,
            n,
            _DTYPE_FROM_STORAGE[inp_storage_dtype],
            _DTYPE_FROM_STORAGE[wgt_storage_dtype],
            _DTYPE_FROM_STORAGE[acc_storage_dtype],
            out_dtype,
        )
    else:
        inp, wgt, acc, out_golden, uop_words, insn_words = _generate_random(
            n, input_dtype, weight_dtype, acc_dtype, out_dtype, min_val, max_val
        )

    with open(full_path, "w") as f:
        f.write(_HEADER_INCLUDES)
        f.write("\n")
        f.write(format_insn_array("insn", insn_words))
        f.write("\n")
        f.write(_FINISH_INSN_BLOCK)
        f.write("\n")
        f.write(format_uop_array("uop", uop_words))
        f.write("\n")
        f.write(format_c_array("input", inp, inp_storage_dtype, n))
        f.write("\n")
        f.write(format_c_array("wgt", wgt, wgt_storage_dtype, n))
        f.write("\n")
        f.write(format_c_array("acc", acc, acc_storage_dtype, n))
        f.write("\n")
        f.write(format_c_array("expected_out", out_golden, out_storage_dtype, n))
        f.write("\n")

    print(f"Success: File '{full_path}' generated.")
    print(f"File size: {os.path.getsize(full_path)} bytes.")


if __name__ == "__main__":
    import argparse

    VALID_TYPES = ["int8", "int16", "int32", "uint8", "uint16", "uint32"]

    parser = argparse.ArgumentParser(description="VTA test data generator.")
    parser.add_argument("-n", type=int, default=16, help="Matrix size (n x n).")
    parser.add_argument(
        "--inp-storage",
        type=str,
        default="int32",
        choices=VALID_TYPES,
        help="Storage type for input.",
    )
    parser.add_argument(
        "--wgt-storage",
        type=str,
        default="int32",
        choices=VALID_TYPES,
        help="Storage type for weight.",
    )
    parser.add_argument(
        "--acc-storage",
        type=str,
        default="int32",
        choices=VALID_TYPES,
        help="Storage type for accumulator (LOG_ACC_WIDTH).",
    )
    parser.add_argument(
        "--out-storage",
        type=str,
        default=None,
        choices=VALID_TYPES,
        help="Storage type for output (LOG_OUT_WIDTH). Defaults to --acc-storage.",
    )
    parser.add_argument(
        "--compiler-output-dir",
        type=str,
        default=None,
        help="If set, read input/weight/accumulator/uop/instructions/reference "
        "binaries from this directory instead of generating random data.",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="",
        help="Layer-name suffix appended to each binary basename "
        '(e.g. "QLinearConv1" -> inputQLinearConv1.bin). Default: empty.',
    )
    parser.add_argument(
        "--filename", type=str, default="init_dram.h", help="Output filename."
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="gen",
        help="Output directory relative to src/fpga/software/. Default: gen",
    )

    args = parser.parse_args()

    # generate_vta_test_header() joins its `path` argument onto the repository
    # root (one level above host/), so a relative outdir like "gen" resolves
    # to src/fpga/software/gen/.
    outdir = args.outdir.rstrip("/") + "/"

    generate_vta_test_header(
        n=args.n,
        inp_storage_dtype=args.inp_storage,
        wgt_storage_dtype=args.wgt_storage,
        acc_storage_dtype=args.acc_storage,
        out_storage_dtype=args.out_storage,
        compiler_output_dir=args.compiler_output_dir,
        suffix=args.suffix,
        path=outdir,
        filename=args.filename,
    )
