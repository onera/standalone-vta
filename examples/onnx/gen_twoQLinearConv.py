import onnx
from onnx import helper, TensorProto
import numpy as np

# ==========================================
# USER CONFIGURATION
# ==========================================

# 1. Shape
channel = 32
dim = 256

input_shape = [1, channel, dim, dim] # N, C, H, W
kernel_shape = [3, 3]
pads = [1, 1, 1, 1]
strides = [1, 1]
out_ch_1 = channel  # Intermediate tensor
out_ch_2 = channel  

# 2. Weight range for random generation
wgt_range = (-128, 127) 

# 3. Quantisation parameters
params = {
    # Input NODE 1
    "in_scale":  0.0250,
    "in_zp":     -128,    

    # Weight NODE 1
    "w1_scale":  0.0166, 
    "w1_zp":     0,
    "b1_val":    100, # Bias (int32)
    
    # Input NODE 2 (output NODE 1)
    "mid_scale": 0.0241,  
    "mid_zp":    -128,

    # Weight NODE 2
    "w2_scale":  0.0089, 
    "w2_zp":     0,
    "b2_val":    -50, # Bias (int32

    # Output
    "out_scale": 0.0256,
    "out_zp":    -128
}

# ==========================================
# UTILS 
# ==========================================

def create_scalar(name, value, dtype):
    """Create scalar tensor (constant)"""
    return helper.make_tensor(name, dtype, [], [value])

def create_weight_tensor(name, shape, value_range):
    """Generate random int8 weights"""
    low, high = value_range
    # high is exclusive (+1)
    data = np.random.randint(low, high + 1, size=shape).astype(np.int8)
    print(f"[{name}] Shape: {shape} | Min: {data.min()} | Max: {data.max()}")
    return helper.make_tensor(name, TensorProto.INT8, shape, data.tobytes(), raw=True)

# ==========================================
# GRAPH CREATION
# ==========================================

initializers = []

# --- 1. Create constants ---
# Input
initializers.append(create_scalar("in_scale", params["in_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("in_zp",    params["in_zp"],    TensorProto.INT8))

# Node 1 Params
initializers.append(create_scalar("w1_scale", params["w1_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("w1_zp",    params["w1_zp"],    TensorProto.INT8))
initializers.append(create_scalar("mid_scale",params["mid_scale"],TensorProto.FLOAT)) 
initializers.append(create_scalar("mid_zp",   params["mid_zp"],   TensorProto.INT8)) 

# Bias Node 1 (broadcast - all identical)
bias1_data = np.full((out_ch_1,), params["b1_val"], dtype=np.int32)
initializers.append(helper.make_tensor("bias1", TensorProto.INT32, [out_ch_1], bias1_data))

# Node 2 Params
initializers.append(create_scalar("w2_scale", params["w2_scale"], TensorProto.FLOAT))
initializers.append(create_scalar("w2_zp",    params["w2_zp"],    TensorProto.INT8))
initializers.append(create_scalar("out_scale",params["out_scale"],TensorProto.FLOAT))
initializers.append(create_scalar("out_zp",   params["out_zp"],   TensorProto.INT8))

bias2_data = np.full((out_ch_2,), params["b2_val"], dtype=np.int32)
initializers.append(helper.make_tensor("bias2", TensorProto.INT32, [out_ch_2], bias2_data))


# --- 2. Weights creation ---
# Conv1 Weights: [Out, In, K, K]
w1_shape = [out_ch_1, input_shape[1], kernel_shape[0], kernel_shape[1]]
initializers.append(create_weight_tensor("w1", w1_shape, wgt_range))

# Conv2 Weights: [Out, In, K, K]
w2_shape = [out_ch_2, out_ch_1, kernel_shape[0], kernel_shape[1]]
initializers.append(create_weight_tensor("w2", w2_shape, wgt_range))


# --- 3. Create input / output of the graph ---
# INPUT
input_info = helper.make_tensor_value_info('input_quantized', TensorProto.INT8, input_shape)

# OUTPUTS 
# Final output
output_info = helper.make_tensor_value_info('final_output', TensorProto.INT8, [1, out_ch_2, input_shape[2], input_shape[3]])
# # Intermediate output for debug
# inter_info = helper.make_tensor_value_info('inter_output', TensorProto.INT8, [1, out_ch_1, input_shape[2], input_shape[3]])


# --- 4. Node creation ---

# Node 1
# Inputs order: X, X_scale, X_zp, W, W_scale, W_zp, Y_scale, Y_zp, B
node1 = helper.make_node(
    'QLinearConv',
    inputs=[
        'input_quantized', 'in_scale', 'in_zp',  # Input
        'w1', 'w1_scale', 'w1_zp',               # Weight
        'mid_scale', 'mid_zp',                   # Output 
        'bias1'                                  # Bias
    ],
    outputs=['inter_output'],
    name='Conv1',
    dilations=[1, 1],
    group=1,
    kernel_shape=kernel_shape,
    pads=pads,
    strides=strides
)

# Node 2
node2 = helper.make_node(
    'QLinearConv',
    inputs=[
        'inter_output', 'mid_scale', 'mid_zp',   # Input 
        'w2', 'w2_scale', 'w2_zp',               # Weight
        'out_scale', 'out_zp',                   # Output
        'bias2'                                  # Bias
    ],
    outputs=['final_output'],
    name='Conv2',
    dilations=[1, 1],
    group=1,
    kernel_shape=kernel_shape,
    pads=pads,
    strides=strides
)


# --- 5. Graph creation ---
graph_def = helper.make_graph(
    [node1, node2],
    'CustomDebugModel',
    [input_info],
    [output_info], 
    # [inter_info, output_info], # -> TO DEBUG
    initializer=initializers
)

model_def = helper.make_model(graph_def, producer_name='onnx-gen')
model_def.opset_import[0].version = 13

# Validation
try:
    onnx.checker.check_model(model_def)
    print("✅ Check ONNX: OK.")
except Exception as e:
    print(f"❌ Check ONNX: Validation error -> {e}")

output_filename = "two_qlinearconv_debug.onnx"
onnx.save(model_def, output_filename)
print(f"Model saves as: {output_filename}")