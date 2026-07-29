# IMPORT PACKAGES
# ---------------
import json
import os
import re
import sys

try:
    from find_project_root import *
    from random_raw_binary_generator import random_raw_binary_generator
except ImportError:
    from utils.find_project_root import *
    from utils.random_raw_binary_generator import random_raw_binary_generator


###############################################

# Buffer role -> the config key holding its log2 element width.
ROLE_WIDTH_KEY = {
    "INP": "LOG_INP_WIDTH",
    "WGT": "LOG_WGT_WIDTH",
    "ACC": "LOG_ACC_WIDTH",
}

# Operand files are named "<stem>_<rows>x<cols>.bin", which is what
# random_raw_binary_generator produces from a stem plus the matrix shape.
OPERAND_RE = re.compile(r"^(?P<stem>.+)_(?P<rows>\d+)x(?P<cols>\d+)\.bin$")


# DTYPE FROM CONFIG
# -----------------
def dtype_name(log_width):
    """Map a config LOG_*_WIDTH to the dtype name the generator expects."""
    if log_width == 3:
        return "int8"
    if log_width == 4:
        return "int16"
    if log_width == 5:
        return "int32"
    raise ValueError(f"unsupported log2 width {log_width} (expected 3, 4 or 5)")


# LOAD SECTION -> BUFFER ROLES
# ----------------------------
def operand_roles(load_dict):
    """Map each matrix name in LOAD to the buffer it is loaded into.

    Mirrors main_vta_compiler.py: INP and WGT take their first entry, ACC takes
    the first as the accumulator and an optional second string entry as accbis,
    which is an accumulator too and so shares its dtype. Non-string entries are
    skipped: a numeric ACC entry is a scalar, not a matrix name.
    """
    roles = {}
    for role in ("INP", "WGT", "ACC"):
        for name in load_dict.get(role, []):
            if isinstance(name, str):
                roles[name] = role
    return roles


# MAIN FUNCTION
# -------------
def gen_ir_inputs(config_path, ir_path, debug=False):
    """Generate every operand a raw VTA IR fixture declares.

    Writes into the directory compiler_output_setup() resolves, i.e.
    $VTA_COMPILER_OUT. Operands already present are kept, so hand-made data can
    be dropped in before compiling.
    """
    with open(config_path) as f:
        config = json.load(f)
    with open(ir_path) as f:
        ir = json.load(f)

    matrices = ir.get("MATRICES", {})
    roles = operand_roles(ir.get("LOAD", {}))
    output_dir = compiler_output_setup()

    for name, role in sorted(roles.items()):
        if name not in matrices:
            raise KeyError(
                f"{ir_path}: LOAD names '{name}', which is absent from MATRICES"
            )
        rows, columns, source = matrices[name][0], matrices[name][1], matrices[name][2]

        # Only file-backed matrices are operands. A "output" or "debug" source
        # is built by the compiler itself (data_definition.matrix_creation).
        if not isinstance(source, str) or not source.endswith(".bin"):
            continue

        basename = os.path.basename(source)
        match = OPERAND_RE.match(basename)
        if match is None:
            raise ValueError(
                f"{ir_path}: operand '{basename}' of matrix '{name}' does not follow "
                "the '<stem>_<rows>x<cols>.bin' naming convention"
            )
        if int(match.group("rows")) != rows or int(match.group("cols")) != columns:
            raise ValueError(
                f"{ir_path}: operand '{basename}' disagrees with the MATRICES entry "
                f"'{name}' = [{rows}, {columns}]"
            )

        target = os.path.join(output_dir, basename)
        if os.path.exists(target):
            print(f"Keeping the existing operand {basename}")
            continue

        dtype = dtype_name(config[ROLE_WIDTH_KEY[role]])
        print(f"Generating {basename} ({role}, {dtype})...")
        random_raw_binary_generator(rows, columns, match.group("stem"), dtype, debug)


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__":
    """
    To execute:
        > python gen_ir_inputs.py <config.json> <vta_ir.json>
    Operands are written to $VTA_COMPILER_OUT.
    """
    if len(sys.argv) != 3:
        print("usage: gen_ir_inputs.py <config.json> <vta_ir.json>", file=sys.stderr)
        sys.exit(2)

    gen_ir_inputs(sys.argv[1], sys.argv[2])
