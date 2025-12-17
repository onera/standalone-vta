import onnx
from onnx import helper, TensorProto, shape_inference
import numpy as np

# ==========================================
# 1. CONFIGURATION
# ==========================================

# Shapes 
N, H, W = 1, 64, 64
C_IN = 64   # Input Channels
C_MID = 32  # Internal Channels 

input_shape = [N, C_IN, H, W]

# Random Ranges
wgt_range = (-128, 127)
bias_range = (-100, 100)

# Quantization Parameters 
params = {
    "in_scale": 1., "in_zp": 0,

    # Node 1 
    "w1_scale": 1., "w1_zp": 0,
    "c1_scale": 1., "c1_zp": 0, 

    # Node 2 
    "w2_scale": 1., "w2_zp": 0,
    "c2_scale": 1., "c2_zp": 0,

    # Node 3
    "mul_const_scale": 1., "mul_const_zp": 0,
    "mul_out_scale": 1.,   "mul_out_zp": 0,

    # Node 4 
    "w3_scale": 1., "w3_zp": 0,
    "c3_scale": 1., "c3_zp": 0,

    # Add (Merge)
    "final_scale": 1., "final_zp": -128
}

# ==========================================
# 2. UTILS
# ==========================================

def create_scalar(name, value, dtype):
    return helper.make_tensor(name, dtype, [], [value])

def create_weight_tensor(name, shape):
    data = np.random.randint(wgt_range[0], wgt_range[1] + 1, size=shape).astype(np.int8)
    return helper.make_tensor(name, TensorProto.INT8, shape, data.tobytes(), raw=True)

def create_bias_tensor(name, shape):
    data = np.random.randint(bias_range[0], bias_range[1] + 1, size=shape).astype(np.int32)
    return helper.make_tensor(name, TensorProto.INT32, shape, data.tobytes(), raw=True)

def calculate_conv_output(in_shape, k_shape, p, s, out_ch):
    n, _, h, w = in_shape
    out_h = (h + p[0] + p[2] - k_shape[0]) // s[0] + 1
    out_w = (w + p[1] + p[3] - k_shape[1]) // s[1] + 1
    return [n, out_ch, out_h, out_w]

# ==========================================
# 3. GRAPH GENERATION
# ==========================================

initializers = []
value_infos = [] 

def add_qparams(p_dict):
    for name, val in p_dict.items():
        if "scale" in name:
            initializers.append(create_scalar(name, val, TensorProto.FLOAT))
        elif "zp" in name:
            initializers.append(create_scalar(name, val, TensorProto.INT8))

add_qparams(params)

# -----------------------------------------------------
# NODE 1: QLinearConv (1x1 Projection)
# -----------------------------------------------------
k1 = [1, 1]
p1 = [0, 0, 0, 0]
s1 = [1, 1]

w1_shape = [C_MID, C_IN, k1[0], k1[1]] 
initializers.append(create_weight_tensor("W1", w1_shape))
initializers.append(create_bias_tensor("B1", [C_MID]))

feat1_shape = calculate_conv_output(input_shape, k1, p1, s1, C_MID)
value_infos.append(helper.make_tensor_value_info('feat_map_1', TensorProto.INT8, feat1_shape))

node1 = helper.make_node(
    "QLinearConv",
    inputs=['input', 'in_scale', 'in_zp', 'W1', 'w1_scale', 'w1_zp', 'c1_scale', 'c1_zp', 'B1'],
    outputs=['feat_map_1'],
    name="Node1_Conv_1x1",
    kernel_shape=k1, pads=p1, strides=s1
)

# -----------------------------------------------------
# NODE 2: QLinearConv (3x3)
# -----------------------------------------------------
k2 = [3, 3]
p2 = [1, 1, 1, 1]
s2 = [1, 1]

w2_shape = [C_MID, C_MID, k2[0], k2[1]] 
initializers.append(create_weight_tensor("W2", w2_shape))
initializers.append(create_bias_tensor("B2", [C_MID]))

feat2_shape = calculate_conv_output(feat1_shape, k2, p2, s2, C_MID)
value_infos.append(helper.make_tensor_value_info('feat_map_2', TensorProto.INT8, feat2_shape))

node2 = helper.make_node(
    "QLinearConv",
    inputs=['feat_map_1', 'c1_scale', 'c1_zp', 'W2', 'w2_scale', 'w2_zp', 'c2_scale', 'c2_zp', 'B2'],
    outputs=['feat_map_2'],
    name="Node2_Conv_3x3",
    kernel_shape=k2, pads=p2, strides=s2
)

# -----------------------------------------------------
# NODE 3: QLinearMul (INDEX 3 - Swapped to match Reference)
# -----------------------------------------------------
# Inputs: Alpha (Const), Node 1 Output
mul_const_shape = [1]
initializers.append(create_weight_tensor("Alpha_Const", mul_const_shape))

feat4_shape = feat1_shape # Output matches input shape
value_infos.append(helper.make_tensor_value_info('feat_map_4', TensorProto.INT8, feat4_shape))

node3_mul = helper.make_node(
    "QLinearMul",
    inputs=[
        'Alpha_Const', 'mul_const_scale', 'mul_const_zp', # Input A (Constant)
        'feat_map_1', 'c1_scale', 'c1_zp',                # Input B (From Node 1)
        'mul_out_scale', 'mul_out_zp'                     # Output
    ],
    outputs=['feat_map_4'],
    name="Node3_Mul",
    domain='com.microsoft'
)

# -----------------------------------------------------
# NODE 4: QLinearConv (3x3) (INDEX 4 - Swapped to match Reference)
# -----------------------------------------------------
# Note: Input is feat_map_2 (Output of Node 2)
k3 = [3, 3]
p3 = [1, 1, 1, 1]
s3 = [1, 1]

w3_shape = [C_MID, C_MID, k3[0], k3[1]]
initializers.append(create_weight_tensor("W3", w3_shape))
initializers.append(create_bias_tensor("B3", [C_MID]))

feat3_shape = calculate_conv_output(feat2_shape, k3, p3, s3, C_MID)
value_infos.append(helper.make_tensor_value_info('feat_map_3', TensorProto.INT8, feat3_shape))

node4_conv = helper.make_node(
    "QLinearConv",
    inputs=['feat_map_2', 'c2_scale', 'c2_zp', 'W3', 'w3_scale', 'w3_zp', 'c3_scale', 'c3_zp', 'B3'],
    outputs=['feat_map_3'],
    name="Node4_Conv_3x3",
    kernel_shape=k3, pads=p3, strides=s3
)

# -----------------------------------------------------
# NODE 5: QLinearAdd
# -----------------------------------------------------
# Input A: Mul (Node 3 output), Input B: Conv (Node 4 output)

node5 = helper.make_node(
    "QLinearAdd",
    inputs=[
        'feat_map_4', 'mul_out_scale', 'mul_out_zp', # Input A: From Mul 
        'feat_map_3', 'c3_scale', 'c3_zp',           # Input B: From Conv 
        'final_scale', 'final_zp'
    ],
    outputs=['final_output'],
    name="Node5_Add",
    domain='com.microsoft'
)

# ==========================================
# 4. EXPORT
# ==========================================

input_info = helper.make_tensor_value_info('input', TensorProto.INT8, input_shape)
output_info = helper.make_tensor_value_info('final_output', TensorProto.INT8, feat3_shape)

# Create graph with strictly ordered nodes: [1, 2, MUL(3), CONV(4), 5]
graph_def = helper.make_graph(
    [node1, node2, node3_mul, node4_conv, node5],
    'Reparam_Pattern_Gen',
    [input_info],
    [output_info],
    initializer=initializers,
    value_info=value_infos
)

model_def = helper.make_model(graph_def, producer_name='onnx-reparam-gen')
model_def.opset_import[0].version = 13
model_def.opset_import.append(helper.make_opsetid("com.microsoft", 1))

model_def = shape_inference.infer_shapes(model_def)

try:
    onnx.checker.check_model(model_def)
    print("✅ Check ONNX: OK.")
except Exception as e:
    print(f"❌ Check ONNX: Validation error -> {e}")

out_name = "pattern_debug.onnx"
onnx.save(model_def, out_name)
print(f"💾 Model saved as: {out_name}")