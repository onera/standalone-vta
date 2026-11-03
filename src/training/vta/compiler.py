import logging
import os
import shlex
import subprocess
import sys

logger = logging.getLogger(__name__)

def compile_and_run_vta(onnx_path: str) -> bool:
    """Compiles and executes the ONNX model using the standalone-vta toolchain.

    Args:
        onnx_path: Path to the QLinear ONNX model.

    Returns:
        True if compilation and execution succeeded, False otherwise.
    """
    # Manage paths relative to current script
    # This file is located in src/training/vta/, we need to go up three levels to find the repo root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Target execution directory (../../examples relative to root)
    target_cwd = os.path.abspath(os.path.join(script_dir, "..", "..", "..", "examples"))
    
    # Path relative to the target working directory
    abs_onnx_path = os.path.abspath(onnx_path)
    rel_onnx_path = os.path.relpath(abs_onnx_path, target_cwd)

    command = [
        "make", 
        "compile_and_run", 
        f"ONNX_FILE={rel_onnx_path}"
    ]
    
    logger.info("[vta] Starting compilation and execution")
    logger.debug(f"[vta] Working directory: {target_cwd}")
    logger.debug(f"[vta] Command: {shlex.join(command)}")
    
    try:
        process = subprocess.Popen(
            command,
            cwd=target_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                print(line.rstrip())
                sys.stdout.flush()
                
        return_code = process.poll()
        if return_code != 0:
            logger.error(f"[vta] Compilation or execution failed: exit code={return_code}")
            return False
            
        logger.info("[vta] Compilation and execution completed")
        return True

    except FileNotFoundError:
        logger.error(f"[vta] Cannot launch make; check executable and working directory: {target_cwd}")
        return False
