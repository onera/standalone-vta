import onnx
import numpy as np
import onnxruntime as ort
from onnx import numpy_helper

def get_node_attribute(node, attribute_name, default=None):
    for attr in node.attribute:
        if attr.name == attribute_name:
            if attr.type == onnx.AttributeProto.INTS:
                return tuple(attr.ints)
            if attr.type == onnx.AttributeProto.INT:
                return attr.i
    return default

class NumPyReferenceEngine:
    def __init__(self, model_path):
        self.model = onnx.load(model_path)
        self.graph = self.model.graph
        # Storage of intermediate tensors and weights
        self.tensors = {}
        
        # Load the initialisers (weights, biases, fixed scales) into the dictionary
        for initializer in self.graph.initializer:
            self.tensors[initializer.name] = numpy_helper.to_array(initializer)

    def _get_val(self, name):
        """Retrieves a value either from initialisers or from previous calculations."""
        if name in self.tensors:
            return self.tensors[name]
        raise ValueError(f"Tensor {name} not found in graph inputs or initialisers.")

    def _requantize(self, data, scale, zero_point, min_val=-128, max_val=127):
        """
        Applies: Output = Clamp(Round(Data * Scale) + ZeroPoint)
        Note: ORT often uses 'Round to nearest, ties to even'
        """
        # Multiplication by the floating-point scale
        scaled = data * scale
        
        # Rounding (NumPy round rounds to the nearest even integer for .5)
        rounded = np.round(scaled)
        
        # Addition of the zero point
        shifted = rounded + zero_point
        
        # Clipping and conversion
        clipped = np.clip(shifted, min_val, max_val)
        return clipped.astype(np.int8)

    def run(self, input_name, input_data):
        self.tensors[input_name] = input_data
        
        for node in self.graph.node:
            op_type = node.op_type
            inputs = [self._get_val(i) if i != '' else None for i in node.input]
            output_name = node.output[0]
            
            if op_type == "QLinearConv":
                res = self._qlinear_conv(node, inputs)
                self.tensors[output_name] = res
                
            elif op_type == "QLinearAdd":
                res = self._qlinear_add(inputs)
                self.tensors[output_name] = res
                
            elif op_type == "QLinearMul":
                res = self._qlinear_mul(inputs)
                self.tensors[output_name] = res
                
            else:
                print(f"Warning: Operator {op_type} not implemented in pure NumPy. Ignored.")
                
        # Returns the output of the last calculated (or specified) node
        last_output_name = self.graph.node[-1].output[0]
        return self.tensors[last_output_name]

    def _qlinear_conv(self, node, inputs):
        # Mapping of standard QLinearConv inputs
        # x, x_scale, x_zp, w, w_scale, w_zp, y_scale, y_zp, B(opt)
        x = inputs[0]
        x_scale = inputs[1]
        x_zp = inputs[2]
        w = inputs[3]
        w_scale = inputs[4]
        w_zp = inputs[5]
        y_scale = inputs[6]
        y_zp = inputs[7]
        bias = inputs[8] if len(inputs) > 8 else None

        # Convolution attributes
        pads = get_node_attribute(node, 'pads', default=(0, 0, 0, 0))
        strides = get_node_attribute(node, 'strides', default=(1, 1))
        
        # 1. Input de-offsetting (switching to int32 to avoid overflow)
        # Note: NumPy broadcasting handles whether x_zp or w_zp are scalars or vectors
        x_int32 = x.astype(np.int32) - x_zp.astype(np.int32)
        w_int32 = w.astype(np.int32) - w_zp.astype(np.int32)

        # 2. Manual padding (Only handling symmetric padding logic for simplicity here)
        # pads format: [y_begin, x_begin, y_end, x_end]
        if sum(pads) > 0:
            pad_width = ((0,0), (0,0), (pads[0], pads[2]), (pads[1], pads[3]))
            x_int32 = np.pad(x_int32, pad_width, mode='constant', constant_values=0)

        # 3. Manual convolution (Slow but explicit)
        batch, in_chan, in_h, in_w = x_int32.shape
        out_chan, _, k_h, k_w = w_int32.shape
        stride_h, stride_w = strides
        
        # Calculation of output dimensions
        out_h = (in_h - k_h) // stride_h + 1
        out_w = (in_w - k_w) // stride_w + 1
        
        output_acc = np.zeros((batch, out_chan, out_h, out_w), dtype=np.int32)

        # Naïve loop implementation (to understand the logic)
        # For performance, using as_strided or tensor dot is better, but here we want mathematical clarity
        for b in range(batch):
            for oc in range(out_chan):
                # Retrieve the kernel and bias for this output channel
                curr_w = w_int32[oc]  # shape (in_chan, kh, kw)
                curr_b = bias[oc] if bias is not None else 0
                
                # Sliding window
                for i in range(out_h):
                    for j in range(out_w):
                        h_start = i * stride_h
                        w_start = j * stride_w
                        patch = x_int32[b, :, h_start:h_start+k_h, w_start:w_start+k_w]
                        
                        # Accumulation: Sum of products + Bias
                        # This is where int32 is crucial
                        acc = np.sum(patch * curr_w) + curr_b
                        output_acc[b, oc, i, j] = acc

        # 4. Requantisation
        # Formula: RealScale = (S_x * S_w) / S_y
        # Calculate the effective scale. Warning: w_scale can be a vector (per-channel)
        effective_scale = (x_scale * w_scale) / y_scale
        
        # Reshape for correct broadcasting if per-channel
        if isinstance(effective_scale, np.ndarray) and effective_scale.size > 1:
            effective_scale = effective_scale.reshape(1, -1, 1, 1)

        return self._requantize(output_acc, effective_scale, y_zp)

    def _qlinear_add(self, inputs):
        # A, A_scale, A_zp, B, B_scale, B_zp, C_scale, C_zp
        a, a_scale, a_zp = inputs[0], inputs[1], inputs[2]
        b, b_scale, b_zp = inputs[3], inputs[4], inputs[5]
        c_scale, c_zp = inputs[6], inputs[7]
        
        # Approximate dequantisation to float for addition
        # (ORT often does this in high-precision int32 but the float mental model is valid)
        a_deq = (a.astype(np.float32) - a_zp) * a_scale
        b_deq = (b.astype(np.float32) - b_zp) * b_scale
        
        res_float = a_deq + b_deq
        
        # Requantisation to C
        # res_int = (res_float / c_scale) + c_zp
        # We can reuse the requantise method by passing 1/c_scale
        return self._requantize(res_float, 1.0/c_scale, c_zp)

    def _qlinear_mul(self, inputs):
        # Similar to Add
        a, a_scale, a_zp = inputs[0], inputs[1], inputs[2]
        b, b_scale, b_zp = inputs[3], inputs[4], inputs[5]
        c_scale, c_zp = inputs[6], inputs[7]
        
        a_deq = (a.astype(np.float32) - a_zp) * a_scale
        b_deq = (b.astype(np.float32) - b_zp) * b_scale
        
        res_float = a_deq * b_deq
        
        return self._requantize(res_float, 1.0/c_scale, c_zp)

# INTEGRATION FUNCTION
# ----------------------
def compare_numpy_vs_ort(model_path, input_data, ort_output):
    input_name = "Input" # Adapt according to the real name in your ONNX (often 'input' or 'data')
    
    # 1. Launch the NumPy implementation
    numpy_engine = NumPyReferenceEngine(model_path)
    
    # Retrieve the real input name from the loaded graph
    real_input_name = numpy_engine.graph.input[0].name
    
    numpy_output = numpy_engine.run(real_input_name, input_data)

    # 2. Comparison
    print("\n--- COMPARATIVE RESULTS ---")
    print(f"Shape ORT   : {ort_output.shape}")
    print(f"Shape NumPy : {numpy_output.shape}")
    
    # Calculation of the error
    # Convert to int to avoid overflow during subtraction
    diff = np.abs(numpy_output.astype(int) - ort_output.astype(int))
    max_diff = np.max(diff)
    exact_match = np.array_equal(numpy_output, ort_output)
    
    print(f"Exact match : {exact_match}")
    print(f"Max absolute difference : {max_diff}")
    
    if not exact_match:
        mismatch_idx = np.where(diff > 0)
        print(f"Example of difference at index {list(zip(*mismatch_idx))[0]}:")
        print(f"  ORT: {ort_output[mismatch_idx][0]}")
        print(f"  NumPy: {numpy_output[mismatch_idx][0]}")
        print("Note: Differences of +/- 1 are common due to floating-point rounding vs CPU optimisations.")

    return numpy_output

# Usage in your main script:
# numpy_res = compare_numpy_vs_ort(model_path, input_data, output_data)