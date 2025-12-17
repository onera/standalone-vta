import onnx
from onnx import helper, TensorProto
import numpy as np

# ==========================================
# USER CONFIGURATION
# ==========================================
input_shape = [1, 1, 3, 3] 

# We use [1] to define a single element tensor (a scalar wrapper).
const_shape = [1]  

# Output shape matches Input A
output_shape = input_shape 

val_range_b = (-50, 50) 

params = {
    "b_scale": 0.005, "b_zp": 0,
    "a_scale": 0.015, "a_zp": -128,
    "c_scale": 0.020, "c_zp": -128
}

# ==========================================
# UTILS 
# ==========================================
def create_scalar(name, value, dtype):
    """Creates a Rank-0 Scalar (Shape: []) for Scales/ZPs"""
    return helper.make_tensor(name, dtype, [], [value])

def create_constant_tensor(name, shape, value_range):
    """Generates the random data for the constant B"""
    low, high = value_range
    data = np.random.randint(low, high + 1, size=shape).astype(np.int8)
    print(f"[{name}] Shape: {shape} | Min: {data.min()} | Max: {data.max()}")
    return helper.make_tensor(name, TensorProto.INT8, shape, data.tobytes(), raw=True)

# ==========================================
# GRAPH CREATION
# ==========================================
initializers = []

# 1. Scales & ZPs (Must be Scalars [])
initializers.append(create_scalar("a_scale", params["a_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("a_zp",    params["a_zp"],    TensorProto.INT8))
initializers.append(create_scalar("b_scale", params["b_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("b_zp",    params["b_zp"],    TensorProto.INT8))
initializers.append(create_scalar("c_scale", params["c_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("c_zp",    params["c_zp"],    TensorProto.INT8))

# 2. Data Tensor B (Shape [1])
# This is now just a single int8 value
initializers.append(create_constant_tensor("const_B", const_shape, val_range_b))

# 3. IO Info
input_info = helper.make_tensor_value_info('input_A', TensorProto.INT8, input_shape)
output_info = helper.make_tensor_value_info('output_C', TensorProto.INT8, output_shape)

# 4. Node Creation
node_mul = helper.make_node(
    'QLinearMul',
    inputs=[
        'const_B', 'b_scale', 'b_zp', 
        'input_A', 'a_scale', 'a_zp', 
        'c_scale', 'c_zp'
    ],
    outputs=['output_C'],
    name='QLinearMul_Node',
    domain='com.microsoft' 
)

# 5. Graph
graph_def = helper.make_graph(
    [node_mul],
    'QLinearMul_Scalar_Test',
    [input_info],
    [output_info],
    initializer=initializers
)

# 6. Model & Opset
model_def = helper.make_model(graph_def, producer_name='onnx-gen-mul')
model_def.opset_import[0].version = 13
ms_opset = helper.make_opsetid("com.microsoft", 1)
model_def.opset_import.append(ms_opset)

# ==========================================
# VALIDATION
# ==========================================
try:
    onnx.checker.check_model(model_def)
    print("✅ Check ONNX: OK.")
except Exception as e:
    print(f"❌ Check ONNX: Validation error -> {e}")

output_filename = "qlinearmul_debug.onnx"
onnx.save(model_def, output_filename)
print(f"💾 Model saved as: {output_filename}")