import onnx
from onnx import helper, TensorProto
import numpy as np

def generate_random_model(
    model_name="qlinearconv_debug.onnx",
    input_shape=(1, 3, 32, 32),  # (N, C, H, W)
    out_channels=3,
    kernel_shape=(3, 3),
    pads=[0, 0, 0, 0],   # [top, left, bottom, right]
    strides=[1, 1],      # [stride_h, stride_w]
    scales={'x': 0.0315, 'w': 0.0050, 'y': 0.0241},
    zps={'x': -128, 'w': 0, 'y': -128}
):
    """
    Create an ONNX model with a single QLinearConv.
    The weights are random.
    """
    
    # --- 1. Dimensions---
    N, in_channels, H, W = input_shape
    kH, kW = kernel_shape
    
    # ONNX pads: [top, left, bottom, right]
    pad_top, pad_left, pad_bottom, pad_right = pads
    stride_h, stride_w = strides

    weight_shape = (out_channels, in_channels, kH, kW)
    
    # Out dimension
    out_H = (H + pad_top + pad_bottom - kH) // stride_h + 1
    out_W = (W + pad_left + pad_right - kW) // stride_w + 1
    
    # Sanity check
    if out_H <= 0 or out_W <= 0:
        raise ValueError(f"Out dimensions are null or negative : H={out_H}, W={out_W}")

    output_shape = [N, out_channels, out_H, out_W]

    # --- 2. Random data ---
    # Poids (INT8)
    W_data = np.random.randint(-128, 127, size=weight_shape, dtype=np.int8)
    # Biais (INT32)
    B_data = np.random.randint(-1000, 1000, size=(out_channels,), dtype=np.int32)

    # --- 3. Create the tensors ---
    
    def make_scalar(name, val, dtype):
        return helper.make_tensor(name, dtype, [], [val])

    initializers = [
        make_scalar('x_scale', scales['x'], TensorProto.FLOAT),
        make_scalar('x_zp', zps['x'], TensorProto.INT8),

        helper.make_tensor('W', TensorProto.INT8, weight_shape, W_data.tobytes(), raw=True),
        make_scalar('w_scale', scales['w'], TensorProto.FLOAT),
        make_scalar('w_zp', zps['w'], TensorProto.INT8),

        make_scalar('y_scale', scales['y'], TensorProto.FLOAT),
        make_scalar('y_zp', zps['y'], TensorProto.INT8),

        helper.make_tensor('B', TensorProto.INT32, [out_channels], B_data.tobytes(), raw=True),
    ]

    # --- 4. Graph definition ---
    
    X_info = helper.make_tensor_value_info('X', TensorProto.INT8, input_shape)
    Y_info = helper.make_tensor_value_info('Y', TensorProto.INT8, output_shape)

    conv_node = helper.make_node(
        'QLinearConv',
        inputs=['X', 'x_scale', 'x_zp', 'W', 'w_scale', 'w_zp', 'y_scale', 'y_zp', 'B'],
        outputs=['Y'],
        kernel_shape=kernel_shape,
        pads=pads,      
        strides=strides  
    )

    graph = helper.make_graph(
        [conv_node],
        'random_qconv_graph',
        [X_info],
        [Y_info],
        initializers
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    
    # Check model validity
    try:
        onnx.checker.check_model(model)
        print("✅ Check ONNX: OK.")
    except onnx.checker.ValidationError as e:
        print(f"❌ Check ONNX: Validation error -> {e}")

    onnx.save(model, model_name)
    print(f"💾 Model saves as '{model_name}'")
    print(f"   Input: {input_shape} | Kernel: {kernel_shape} | Pads: {pads} | Strides: {strides}")
    print(f"   Calculated Output: {output_shape}")

# --- UTILISATION ---
if __name__ == "__main__":
    generate_random_model(
        model_name="qlinearconv_debug.onnx",
        input_shape=(1, 3, 5, 5),      
        out_channels=3,                  
        kernel_shape=(3, 3),
        pads=[1, 1, 1, 1],   # [Top, Left, Bottom, Right]
        strides=[1, 1],      # [H, W]
        scales={'x': 0.0315, 'w': 0.0050, 'y': 0.0241}, 
        zps={'x': -128, 'w': 0, 'y': -128}
    )