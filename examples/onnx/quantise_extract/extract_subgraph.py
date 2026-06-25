# IMPORT PACKAGES
# ---------------
import os
import onnx
from onnx import utils

###############################################

# EXTRACT SUBGRAPH
# ----------------
def extract_subgraph(input_model_path, output_model_path, input_names, output_names):
    """
    Extracts a subgraph from an ONNX model based on defined input and output tensor names.
    Creates a new, valid ONNX model containing only the required nodes.
    """
    print("Starting subgraph extraction...")
    print(f"Target Input(s):  {input_names}")
    print(f"Target Output(s): {output_names}")
    print(f"Reading from:     {input_model_path}")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_model_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        # Perform the extraction
        utils.extract_model(
            input_path=input_model_path,
            output_path=output_model_path,
            input_names=input_names,
            output_names=output_names
        )
        print(f"Success! The extracted subgraph has been saved to: {output_model_path}")
        
        # Optional: Verify the validity of the newly created model
        print("Running ONNX checker on the extracted model...")
        extracted_model = onnx.load(output_model_path)
        onnx.checker.check_model(extracted_model)
        print("Validation passed. The extracted model is a valid ONNX graph. ✅\n")

    except Exception as e:
        print(f"❌ Error during extraction: {e}\n")


###############################################

# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    
    # ==========================================
    # 1. CONFIGURATION (Modify parameters here)
    # ==========================================
    
    # Paths
    INPUT_MODEL_PATH = "qyolo_nas_s.onnx" 
    OUTPUT_MODEL_PATH = "subgraph.onnx"
    
    # Subgraph Boundaries
    # Note: These should correspond to exact tensor names in the ONNX graph.
    
    INPUT_NAMES = [
        "/pre_process/pre_process.0/Cast_output_0_quantized"
    ]

    OUTPUT_NAMES = [
        "/model/heads/head3/cls_pred/Conv_output_0_quantized"
    ]
    
    # ==========================================
    # 2. EXECUTION PIPELINE
    # ==========================================
    
    extract_subgraph(
        input_model_path=INPUT_MODEL_PATH,
        output_model_path=OUTPUT_MODEL_PATH,
        input_names=INPUT_NAMES,
        output_names=OUTPUT_NAMES
    )
