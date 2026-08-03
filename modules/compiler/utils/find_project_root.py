# PACKAGE IMPORT
# --------------
import os


# CREATE A DIRECTORY (if it does not exist)
# ------------------
def create_directory(path):
    os.makedirs(path, exist_ok=True)


# COMPILER OUTPUT FILE
# --------------------
def compiler_output_setup(filename = "default.bin"):
    """
    Resolve the directory where compiler artefacts are written.

    Resolution order (no '.git' walk, so a script can run from any location):
      1. the VTA_COMPILER_OUT environment variable, if set (also fed by the
         '-o/--output-dir' flag of the compiler entry points), otherwise
      2. a 'compiler_output' directory under the current working directory.

    Callers that need a fixed location (the Makefile, the Mill tasks) pass it
    explicitly; direct invocations default to the CWD so the output is
    predictable from where the script is launched.
    """
    override = os.environ.get("VTA_COMPILER_OUT")
    if override:
        output_dir = os.path.abspath(override)
    else:
        output_dir = os.path.join(os.getcwd(), 'compiler_output')
    create_directory(output_dir)
    return output_dir


# REFERENCE OUTPUT FILE
# ---------------------
def reference_output_setup(filename = "default.bin"):
    """
    Resolve the directory where the ONNX reference is written/read.

    Mirrors compiler_output_setup(), but for the reference: reference_onnx.py
    writes the golden output (reference.bin) and the randomly generated network
    input (input_nn.bin) here. Neither is a compiler artefact - input_nn.bin in
    particular is random, and keeping it out of the compiler output dir removes
    one source of nondeterminism from a compile. That does not make a compile
    reproducible on its own, though: nn_compiler/vta_backend.py still writes
    unseeded random placeholder accumulator data for MaxPool/Relu/QLinearAdd
    nodes straight into the compiler output dir.

    Resolution order (no '.git' walk, so a script can run from any location):
      1. the VTA_REFERENCE_OUT environment variable, if set, otherwise
      2. a 'reference_output' directory under the current working directory.
    """
    override = os.environ.get("VTA_REFERENCE_OUT")
    if override:
        output_dir = os.path.abspath(override)
    else:
        output_dir = os.path.join(os.getcwd(), 'reference_output')
    create_directory(output_dir)
    return output_dir


# SIMULATOR OUTPUT FILE
# ---------------------
def simulator_output_setup(filename = "default.bin"):
    """
    Resolve the directory where simulator results are written/read.

    Mirrors compiler_output_setup(), but for the simulator side: the simulators
    write final_output.bin / final_output_rtl.bin here (never into the compiler
    output dir, which holds only compiler artefacts; the reference lives in its own dir, see reference_output_setup).

    Resolution order (no '.git' walk, so a script can run from any location):
      1. the VTA_SIMULATOR_OUT environment variable, if set, otherwise
      2. a 'simulators_output' directory under the current working directory.
    """
    override = os.environ.get("VTA_SIMULATOR_OUT")
    if override:
        output_dir = os.path.abspath(override)
    else:
        output_dir = os.path.join(os.getcwd(), 'simulators_output')
    create_directory(output_dir)
    return output_dir


# DEFINE FILENAME
# ---------------
def filepath_definition(path, filename = "default.bin"):
    return os.path.join(path, filename)
