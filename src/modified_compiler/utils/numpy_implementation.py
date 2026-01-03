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
            
            # --- OPERATORS ---
            if op_type == "QLinearConv":
                res = self._qlinear_conv(node, inputs)
                self.tensors[output_name] = res
            elif op_type == "QLinearAdd":
                res = self._qlinear_add(inputs)
                self.tensors[output_name] = res
            elif op_type == "QLinearMul":
                res = self._qlinear_mul(inputs)
                self.tensors[output_name] = res
            elif op_type == "QuantizeLinear":
                res = self._quantize_linear(inputs)
                self.tensors[output_name] = res
            
            elif op_type == "DequantizeLinear":
                res = self._dequantize_linear(node, inputs)
                self.tensors[output_name] = res
                
            elif op_type == "QLinearConcat":
                res = self._qlinear_concat(node, inputs)
                self.tensors[output_name] = res
                
            elif op_type == "MaxPool":
                res = self._max_pool(node, inputs)
                self.tensors[output_name] = res
                
            elif op_type == "ConvTranspose":
                res = self._conv_transpose(node, inputs)
                self.tensors[output_name] = res
                
            else:
                print(f"Warning: Operator {op_type} not implemented in pure NumPy. Ignored.")
                
        # Return last node output
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

    def _quantize_linear(self, inputs):
        # Standard Inputs: x, y_scale, y_zero_point (optional)
        x = inputs[0]
        y_scale = inputs[1]
        
        # Handle optional Zero Point (Default to uint8 / 0)
        if len(inputs) > 2 and inputs[2] is not None:
            y_zp = inputs[2]
            dtype = y_zp.dtype
        else:
            y_zp = 0
            dtype = np.uint8
            
        # 1. Scale (Float -> Int domain)
        # QuantizeLinear definition: y = saturate(round(x / y_scale) + y_zero_point)
        # Note: We must ensure x is float for division
        scaled = x.astype(np.float32) / y_scale
        
        # 2. Round (Round to nearest, ties to even)
        rounded = np.rint(scaled)
        
        # 3. Add Zero Point
        shifted = rounded + y_zp
        
        # 4. Saturate (Clamp) based on the target dtype
        # We look at the dtype of the Zero Point to know if we target int8 or uint8
        if dtype == np.uint8:
            q_min, q_max = 0, 255
        elif dtype == np.int8:
            q_min, q_max = -128, 127
        elif dtype == np.int32: # Sometimes used for intermediate ops
            q_min, q_max = -2147483648, 2147483647
        else:
            # Fallback for unexpected types (e.g. int16)
            try:
                iinfo = np.iinfo(dtype)
                q_min, q_max = iinfo.min, iinfo.max
            except ValueError:
                # Default safety net
                q_min, q_max = -128, 127

        clipped = np.clip(shifted, q_min, q_max)
            
        return clipped.astype(dtype)

    def _dequantize_linear(self, node, inputs):
        x = inputs[0]
        x_scale = inputs[1]
        
        # 1. Handle Optional Zero Point
        if len(inputs) > 2 and inputs[2] is not None:
            x_zp = inputs[2]
        else:
            # Default is 0 (same type as x)
            x_zp = np.array(0, dtype=x.dtype)

        # 2. Handle Per-Channel Broadcasting
        # NumPy broadcasts from the last dimension (right-to-left).
        # ONNX DequantizeLinear usually broadcasts along a specific 'axis' (default 1).
        if x_scale.ndim == 1 and x_scale.size > 1 and x.ndim > 1:
            axis = get_node_attribute(node, 'axis', default=1)
            
            # Handle negative axis (e.g. -1)
            if axis < 0: 
                axis += x.ndim

            # Create the broadcast shape: e.g. for (N, C, H, W) and axis 1 -> (1, C, 1, 1)
            new_shape = [1] * x.ndim
            new_shape[axis] = x_scale.size
            
            # Reshape Scale
            x_scale = x_scale.reshape(new_shape)
            
            # Reshape Zero Point (if it's not a scalar)
            if x_zp.ndim == 1:
                x_zp = x_zp.reshape(new_shape)

        # 3. Calculation
        # (x - zp) * scale
        # Cast to float32 is strictly necessary to avoid int overflow during subtraction
        res = (x.astype(np.float32) - x_zp.astype(np.float32)) * x_scale
        
        return res

    def _qlinear_concat(self, node, inputs):
        """
        Input Format for com.microsoft.QLinearConcat:
        [Y_scale, Y_zp, X1, X1_scale, X1_zp, X2, X2_scale, X2_zp, ...]
        """
        # 1. Extract Attributes
        axis = get_node_attribute(node, 'axis', default=1)
        
        # 2. Extract Output Parameters (Always the FIRST two inputs)
        y_scale = inputs[0]
        y_zp = inputs[1]

        # Determine output range based on Zero Point type (uint8 vs int8)
        if y_zp.dtype == np.uint8:
            min_val, max_val = 0, 255
        else:
            min_val, max_val = -128, 127

        # 3. Process Input Triplets (starting from index 2)
        # Sequence: [X1, Scale1, ZP1, X2, Scale2, ZP2, ...]
        content_inputs = inputs[2:]
        num_inputs = len(content_inputs) // 3
        
        dequantized_tensors = []
        
        for i in range(num_inputs):
            base_idx = i * 3
            val = content_inputs[base_idx]
            scale = content_inputs[base_idx + 1]
            zp = content_inputs[base_idx + 2]
            
            # Dequantize to Float32
            # Formula: (val - zp) * scale
            deq = (val.astype(np.float32) - zp) * scale
            dequantized_tensors.append(deq)
            
        # 4. Concatenate in Float32
        # This preserves accuracy even if inputs have different scales
        concatenated = np.concatenate(dequantized_tensors, axis=axis)
        
        # 5. Re-quantize to Output specifications
        # Pass the correct min/max limits found above
        return self._requantize(concatenated, 1.0/y_scale, y_zp, min_val=min_val, max_val=max_val)

    def _max_pool(self, node, inputs):
        x = inputs[0]
        
        # Attributes
        kernel_shape = get_node_attribute(node, 'kernel_shape')
        pads = get_node_attribute(node, 'pads', default=[0]*4) # [y_begin, x_begin, y_end, x_end]
        strides = get_node_attribute(node, 'strides', default=(1, 1))
        
        # Handling padding with -inf (or min value) so it doesn't affect Max
        # For int8, we should use the type's min; for float, -inf.
        if np.issubdtype(x.dtype, np.integer):
            pad_val = np.iinfo(x.dtype).min
        else:
            pad_val = -np.inf
            
        # Apply Padding
        if sum(pads) > 0:
            pad_width = ((0,0), (0,0), (pads[0], pads[2]), (pads[1], pads[3]))
            x_padded = np.pad(x, pad_width, mode='constant', constant_values=pad_val)
        else:
            x_padded = x

        batch, channels, h_in, w_in = x_padded.shape
        k_h, k_w = kernel_shape
        s_h, s_w = strides
        
        # Output dims
        # Note: 'ceil_mode' attribute affects this, assumed 0 (floor) here for simplicity
        h_out = (h_in - k_h) // s_h + 1
        w_out = (w_in - k_w) // s_w + 1
        
        output = np.zeros((batch, channels, h_out, w_out), dtype=x.dtype)
        
        # Naive sliding window
        for i in range(h_out):
            for j in range(w_out):
                h_start = i * s_h
                w_start = j * s_w
                h_end = h_start + k_h
                w_end = w_start + k_w
                
                window = x_padded[:, :, h_start:h_end, w_start:w_end]
                output[:, :, i, j] = np.max(window, axis=(2, 3))
                
        return output

    def _conv_transpose(self, node, inputs):
        # Inputs: X, W, B (optional)
        X = inputs[0]
        W = inputs[1]
        B = inputs[2] if len(inputs) > 2 else None
        
        # 1. Attributes
        pads = get_node_attribute(node, 'pads', default=(0,0,0,0))
        strides = get_node_attribute(node, 'strides', default=(1,1))
        dilations = get_node_attribute(node, 'dilations', default=(1,1)) # <--- NEW
        output_padding = get_node_attribute(node, 'output_padding', default=(0,0))
        group = get_node_attribute(node, 'group', default=1)
        
        # 2. Dimensions
        batch, in_chan, in_h, in_w = X.shape
        # ONNX ConvTranspose Weights: (In_C, Out_C/Group, kH, kW)
        ic_w, oc_per_group, k_h, k_w = W.shape
        out_chan = oc_per_group * group
        
        s_h, s_w = strides
        d_h, d_w = dilations # <--- NEW
        
        # 3. Calculate Effective Kernel Size (with dilation)
        k_h_eff = (k_h - 1) * d_h + 1
        k_w_eff = (k_w - 1) * d_w + 1
        
        # 4. Canvas Size Calculation
        # The canvas represents the "uncropped" scatter area.
        # Height = (Input-1)*Stride + EffectiveKernel + OutputPadding
        canvas_h = (in_h - 1) * s_h + k_h_eff + output_padding[0]
        canvas_w = (in_w - 1) * s_w + k_w_eff + output_padding[1]
        
        # Initialize float32 accumulator (handles int8 inputs safely)
        output_canvas = np.zeros((batch, out_chan, canvas_h, canvas_w), dtype=np.float32)

        # 5. Scatter Loop
        # Iterate over input pixels and project the kernel onto the canvas
        for b in range(batch):
            for g in range(group):
                ic_start = g * (in_chan // group)
                ic_end = ic_start + (in_chan // group)
                oc_start = g * oc_per_group
                
                for ic_off in range(ic_end - ic_start):
                    ic = ic_start + ic_off
                    for oc_off in range(oc_per_group):
                        oc = oc_start + oc_off
                        
                        # Weight: W[ic, oc_off] is the kernel (kH, kW)
                        curr_w = W[ic, oc_off] 
                        
                        # Optimization: Find non-zero input pixels to avoid useless adds
                        # (Optional, removes inner loop overhead if input is sparse)
                        rows, cols = np.where(X[b, ic] != 0)
                        
                        for r, c in zip(rows, cols):
                            val = X[b, ic, r, c]
                            
                            # Top-left corner on canvas
                            h_start = r * s_h
                            w_start = c * s_w
                            
                            # Define the slice on the canvas
                            # We use slicing with 'step' = dilation
                            h_end = h_start + k_h_eff
                            w_end = w_start + k_w_eff
                            
                            # ACCUMULATION
                            # canvas slice: [start : end : dilation] shape matches kernel (kH, kW)
                            output_canvas[b, oc, h_start:h_end:d_h, w_start:w_end:d_w] += val * curr_w

        # 6. Crop (Handle Padding)
        y_start = pads[0]
        x_start = pads[1]
        # Ensure we don't slice past the canvas (safety for negative padding/cropping)
        y_end = max(y_start, canvas_h - pads[2])
        x_end = max(x_start, canvas_w - pads[3])
        
        final_output = output_canvas[:, :, y_start:y_end, x_start:x_end]
        
        # 7. Add Bias
        if B is not None:
            final_output += B.reshape(1, -1, 1, 1)
            
        return final_output

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