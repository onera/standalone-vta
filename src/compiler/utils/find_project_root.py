# PACKAGE IMPORT
# --------------
import os


# FIND PROJECT ROOT
# -----------------
def find_project_root(anchor='.git'):
    """
    Find the project root (i.e., where the '.git/' belongs).
    This function is used to write within a folder with absolute path, therefore avoiding issues when a script is moved.
    """
    path = os.path.abspath(__file__)
    current_dir = os.path.dirname(path)
    while True:
        if os.path.exists(os.path.join(current_dir, anchor)):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            raise FileNotFoundError(f"Error: '{anchor}' not found.")
        current_dir = parent_dir


# CREATE A DIRECTORY (if it does not exist)
# ------------------
def create_directory(path):
    os.makedirs(path, exist_ok=True)


# COMPILER OUTPUT FILE
# --------------------
def compiler_output_setup(filename = "default.bin"):
    project_root = find_project_root()
    output_dir = os.path.join(project_root, 'compiler_output')
    create_directory(output_dir)
    return output_dir


# DEFINE FILENAME
# ---------------
def filepath_definition(path, filename = "default.bin"):
    return os.path.join(path, filename)
