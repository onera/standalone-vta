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


# DEFINE FILENAME
# ---------------
def filepath_definition(path, filename = "default.bin"):
    return os.path.join(path, filename)
