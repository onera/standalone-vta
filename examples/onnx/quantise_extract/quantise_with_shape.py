# IMPORT PACKAGES
# ---------------
import os
import numpy as np
import onnx
from onnx import helper, TensorProto, shape_inference
import onnxruntime as ort
import onnxruntime.quantization
from onnxruntime.quantization import QuantFormat, QuantType

###############################################

# CREATE INPUT
# ------------
def create_input(shape=(1, 3, 640, 640), dtype=np.uint8):
    """
    Generates dummy in-memory data for both calibration and shape inference.
    """
    print(f"Generatng dummy input with shape {shape} and type {dtype.__name__}...")
    if dtype == np.uint8:
        # Generate integers between 0 and 255 for models with built-in preprocessing
        data = np.random.randint(0, 255, size=shape).astype(np.uint8)
    elif dtype == np.float32:
        # Generate normalised floats if preprocessing is handled externally
        data = np.random.rand(*shape).astype(np.float32)
    else:
        # Fallback for other types
        data = np.zeros(shape, dtype=dtype)
    return data

class InMemoryCalibrationDataReader(onnxruntime.quantization.CalibrationDataReader):
    """
    A simple data reader that yields a single batch of in-memory data 
    for ONNX quantisation calibration, removing the need for binary files.
    """
    def __init__(self, input_name, calibration_data):
        self.data_reader = iter([{input_name: calibration_data}])

    def get_next(self):
        return next(self.data_reader, None)


# QUANTISE (Qops)
# ---------------
def quantise_model(input_model_path, output_quantised_path, calibration_data, input_name):
    """
    Performs static quantisation using QOperator format.
    Includes preliminary shape inference on the FP32 model to ensure stability.
    """
    print(f"Loading FP32 ONNX model from: {input_model_path}")
    
    # Ensure output directory exists
    output_dir = os.path.dirname(output_quantised_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    print("Running preliminary shape inference on FP32 model...")
    model_fp32 = onnx.load(input_model_path)
    model_fp32 = shape_inference.infer_shapes(model_fp32)
    
    # Save the intermediate "clean" model temporarily
    temp_fp32_inferred = "temp_fp32_inferred.onnx"
    onnx.save(model_fp32, temp_fp32_inferred)
    
    print("Preparing in-memory calibration data reader...")
    calibration_data_reader = InMemoryCalibrationDataReader(
        input_name=input_name,
        calibration_data=calibration_data
    )

    print("Starting static quantisation with ONNX Runtime (QOperator format)...")
    onnxruntime.quantization.quantize_static(
        model_input=temp_fp32_inferred,
        model_output=output_quantised_path,
        calibration_data_reader=calibration_data_reader,
        quant_format=QuantFormat.QOperator,
        activation_type=QuantType.QInt8,
        weight_type=QuantType.QInt8
    )

    # Clean up temporary FP32 file
    if os.path.exists(temp_fp32_inferred):
        os.remove(temp_fp32_inferred)

    print(f"Quantisation process completed successfully. ✅")
    print(f"Initial quantised model saved to: {output_quantised_path}\n")


# PROPAGATE SHAPE
# ---------------
def _map_np_dtype_to_onnx(np_dtype):
    """Maps numpy data types to ONNX TensorProto types."""
    if np_dtype == np.float32: return TensorProto.FLOAT
    if np_dtype == np.int8:    return TensorProto.INT8
    if np_dtype == np.uint8:   return TensorProto.UINT8
    if np_dtype == np.int32:   return TensorProto.INT32
    if np_dtype == np.int64:   return TensorProto.INT64
    return TensorProto.UNDEFINED

def propagate_shapes(input_model_path, output_model_path, dummy_data, input_name):
    """
    Executes a dummy pass on the quantised model to deduce dynamic/missing shapes,
    and hardcodes these discovered shapes and types into the ONNX graph's value_info.
    """
    print(f"🔧 Repairing shapes and types for: {input_model_path}")
    
    # 1. Load the model
    model = onnx.load(input_model_path)
    
    # 2. Expose all intermediate nodes as outputs to capture their shapes during inference
    orig_outputs = [o.name for o in model.graph.output]
    all_tensor_names = set()
    
    for node in model.graph.node:
        for output in node.output:
            if output: # check it is not empty
                all_tensor_names.add(output)
            
    for tensor_name in all_tensor_names:
        if tensor_name not in orig_outputs:
            model.graph.output.extend([onnx.ValueInfoProto(name=tensor_name)])
            
    temp_shape_model_path = "temp_shape_inference.onnx"
    onnx.save(model, temp_shape_model_path)
    
    # 3. Execute the model to capture actual shapes
    print("🚀 Executing a single inference pass to determine intermediate shapes...")
    sess = ort.InferenceSession(temp_shape_model_path, providers=['CPUExecutionProvider'])
    results = sess.run(None, {input_name: dummy_data})
    
    # 4. Map the captured results to their respective shapes and types
    tensor_info = {}
    for i, output_info in enumerate(sess.get_outputs()):
        res = results[i]
        tensor_info[output_info.name] = {
            'shape': res.shape,
            'type': res.dtype
        }

    # 5. Apply the discovered shapes to the ORIGINAL quantised model
    final_model = onnx.load(input_model_path)
    
    # Clear any corrupted or existing value_info
    del final_model.graph.value_info[:]
    
    # Repopulate cleanly
    for name, info in tensor_info.items():
        onnx_type = _map_np_dtype_to_onnx(info['type'])
        
        # Failsafe: Avoid writing UNDEFINED types which could crash ONNX Runtime
        if onnx_type == TensorProto.UNDEFINED:
            print(f"⚠️ Warning: Unsupported numpy type {info['type']} for '{name}'. Skipped.")
            continue

        vi = helper.make_tensor_value_info(
            name,
            onnx_type,
            info['shape']
        )
        final_model.graph.value_info.append(vi)
        
    # 6. Save final model and clean up
    onnx.save(final_model, output_model_path)
    
    if os.path.exists(temp_shape_model_path):
        os.remove(temp_shape_model_path)
        
    print(f"✅ Final repaired model saved to: {output_model_path}")

###############################################

# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    
    # ==========================================
    # 1. CONFIGURATION (Modify parameters here)
    # ==========================================
    
    # Paths
    MODEL_FP32_PATH = './yolo_nas_s.onnx'
    MODEL_QUANT_TEMP_PATH = "qyolo_nas_s_temp.onnx"    # Intermediate quantised file
    MODEL_FINAL_PATH = "qyolo_nas_s.onnx"     # Final model with fixed shapes
    
    # Model Input Specifications
    INPUT_SHAPE = (1, 3, 640, 640)
    INPUT_DTYPE = np.uint8 # Change to np.float32 if your model requires normalised floats
    
    # Automatically retrieve the input name from the FP32 graph
    _temp_model = onnx.load(MODEL_FP32_PATH)
    if not _temp_model.graph.input:
        raise ValueError("The ONNX model graph has no inputs.")
    INPUT_NAME = _temp_model.graph.input[0].name
    print(f"Detected model input name: '{INPUT_NAME}'\n")
    del _temp_model # Free memory
    
    
    # ==========================================
    # 2. EXECUTION PIPELINE
    # ==========================================
    
    # Step A: Generate unified dummy data for calibration and shape fixing
    dummy_input_data = create_input(shape=INPUT_SHAPE, dtype=INPUT_DTYPE)
    
    # Step B: Quantise the model using QOperator logic
    quantise_model(
        input_model_path=MODEL_FP32_PATH, 
        output_quantised_path=MODEL_QUANT_TEMP_PATH, 
        calibration_data=dummy_input_data, 
        input_name=INPUT_NAME
    )
    
    # Step C: Propagate and hardcode shapes into the quantised model
    # Note: We pass the exact same dummy data type to the quantised model's session
    propagate_shapes(
        input_model_path=MODEL_QUANT_TEMP_PATH,
        output_model_path=MODEL_FINAL_PATH,
        dummy_data=dummy_input_data,
        input_name=INPUT_NAME
    )
    
    # Clean up the intermediate un-fixed quantised file to avoid clutter
    if os.path.exists(MODEL_QUANT_TEMP_PATH):
        os.remove(MODEL_QUANT_TEMP_PATH)
        
    print("\n🎉 Pipeline finished completely.")
