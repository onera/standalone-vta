"""Readable NumPy implementation of the embedded VTA arithmetic contract.

Logical activations use NCHW layout here; blocking and DRAM padding belong to
the simulator/runtime. Explicit dtype conversions and separate floating-point
operations are part of the contract: algebraic simplification can change the
quantized result near a half-integer. See doc/QUANTIZED_ARITHMETIC_CONTRACT.md.
"""

from typing import Any, Dict, List, Optional

import onnx
import numpy as np
import onnxruntime as ort
from onnx import numpy_helper


def float32_reciprocal(scale: Any) -> np.float32:
    """Computes the project-defined float32 reciprocal of a scalar scale.

    Args:
        scale: Scalar value convertible to ``numpy.float32``.

    Returns:
        Reciprocal rounded to float32.

    Raises:
        ValueError: If ``scale`` is not scalar or is zero.
    """
    scale_array = np.asarray(scale, dtype=np.float32)
    if scale_array.size != 1:
        raise ValueError(f"Expected a scalar scale, got shape {scale_array.shape}.")
    scale_f32 = np.float32(scale_array.reshape(()))
    if scale_f32 == np.float32(0.0):
        raise ValueError("Quantization scale cannot be zero.")
    return np.float32(np.float32(1.0) / scale_f32)


def round_and_saturate(
    scaled: np.ndarray,
    zero_point: Any,
    output_dtype: np.dtype[Any] = np.dtype(np.int8),
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
) -> np.ndarray:
    """Rounds with ties-to-even, adds a zero-point, and saturates.

    Args:
        scaled: Values in the output quantized domain before rounding.
        zero_point: Scalar output zero-point.
        output_dtype: Integer dtype of the quantized result.
        min_val: Optional explicit saturation lower bound.
        max_val: Optional explicit saturation upper bound.

    Returns:
        Quantized array with ``output_dtype``.

    Raises:
        ValueError: If the requested output dtype is not an integer dtype.
    """
    dtype = np.dtype(output_dtype)
    if not np.issubdtype(dtype, np.integer):
        raise ValueError(f"Quantized output dtype must be integer, got {dtype}.")
    bounds = np.iinfo(dtype)
    lower = bounds.min if min_val is None else min_val
    upper = bounds.max if max_val is None else max_val
    # Round before adding the zero-point. Moving the integer shift inside the
    # round changes tie parity when the zero-point is odd.
    rounded = np.rint(scaled)
    shifted = rounded + np.asarray(zero_point, dtype=np.int64)
    return np.clip(shifted, lower, upper).astype(dtype)


def requantize_accumulator(
    accumulator: np.ndarray,
    multiplier: Any,
    zero_point: Any,
) -> np.ndarray:
    """Requantizes an integer accumulator using the VTA double multiply path.

    The effective multiplier is first rounded to float32, then widened to
    float64 for the element-wise multiplication. This mirrors fsim and the
    embedded ``run_rescale`` implementation.

    Args:
        accumulator: Integer accumulator values.
        multiplier: Scalar or per-channel effective float32 multiplier.
        zero_point: Output zero-point.

    Returns:
        Saturated int8 tensor.
    """
    multiplier_f32 = np.asarray(multiplier, dtype=np.float32)
    scaled = accumulator.astype(np.float64) * multiplier_f32.astype(np.float64)
    return round_and_saturate(scaled, zero_point, np.dtype(np.int8))


def get_node_attribute(node: Any, attribute_name: str, default: Any = None) -> Any:
    """Returns an integer or integer-list ONNX attribute.

    Args:
        node: ONNX node containing the requested attribute.
        attribute_name: Attribute identifier.
        default: Value returned when the attribute is absent.

    Returns:
        Attribute value or ``default``.
    """
    for attr in node.attribute:
        if attr.name == attribute_name:
            if attr.type == onnx.AttributeProto.INTS:
                return tuple(attr.ints)
            if attr.type == onnx.AttributeProto.INT:
                return attr.i
    return default


class NumPyReferenceEngine:
    """Executes the supported ONNX subset using embedded arithmetic.

    Attributes:
        model: Loaded ONNX model.
        graph: Graph evaluated in topological order.
        tensors: Initializers, graph inputs, and logical intermediate outputs.
        integer_accumulators: Pre-rescale Conv/Mul tensors keyed by output name.
    """

    def __init__(self, model_path: str) -> None:
        """Loads a model and its initializers without executing it.

        Args:
            model_path: Path to the ONNX model.
        """
        self.model = onnx.load(model_path)
        self.graph = self.model.graph
        # Storage of intermediate tensors and weights
        self.tensors: Dict[str, np.ndarray] = {}
        # Keep integer results separate from quantized activations so debugging
        # can distinguish an accumulation error from a requantization error.
        self.integer_accumulators: Dict[str, np.ndarray] = {}
        self._last_integer_accumulator = np.empty(0, dtype=np.int32)
        
        # Load the initialisers (weights, biases, fixed scales) into the dictionary
        for initializer in self.graph.initializer:
            self.tensors[initializer.name] = numpy_helper.to_array(initializer)

    def _get_val(self, name: str) -> np.ndarray:
        """Retrieves an initializer, graph input, or intermediate output.

        Args:
            name: ONNX tensor name.

        Returns:
            Stored tensor, without copying it.

        Raises:
            ValueError: If the tensor has not been loaded or computed.
        """
        if name in self.tensors:
            return self.tensors[name]
        raise ValueError(f"Tensor {name} not found in graph inputs or initialisers.")

    def _requantize(
        self,
        data: np.ndarray,
        scale: Any,
        zero_point: Any,
        min_val: int = -128,
        max_val: int = 127,
    ) -> np.ndarray:
        """Applies the VTA accumulator rescale with explicit float64 products.

        Args:
            data: Integer accumulator tensor.
            scale: Effective multiplier, rounded to float32 before widening.
            zero_point: Output zero-point added after nearest-even rounding.
            min_val: Lower saturation bound.
            max_val: Upper saturation bound.

        Returns:
            Saturated int8 activation tensor.
        """
        multiplier_f32 = np.asarray(scale, dtype=np.float32)
        scaled = data.astype(np.float64) * multiplier_f32.astype(np.float64)
        return round_and_saturate(
            scaled,
            zero_point,
            np.dtype(np.int8),
            min_val=min_val,
            max_val=max_val,
        )

    def run(self, input_name: str, input_data: np.ndarray) -> np.ndarray:
        """Executes every supported node in graph order.

        Args:
            input_name: Real ONNX graph input name.
            input_data: Quantized input tensor.

        Returns:
            Output tensor of the final graph node.
        """
        self.tensors[input_name] = input_data
        
        for node in self.graph.node:
            op_type = node.op_type
            inputs = [self._get_val(i) if i != '' else None for i in node.input]
            output_name = node.output[0]
            
            # --- OPERATORS ---
            if op_type == "QLinearConv":
                res = self._qlinear_conv(node, inputs)
                self.tensors[output_name] = res
                self.integer_accumulators[output_name] = self._last_integer_accumulator
            elif op_type == "QLinearAdd":
                res = self._qlinear_add(inputs)
                self.tensors[output_name] = res
            elif op_type == "QLinearMul":
                res = self._qlinear_mul(inputs)
                self.tensors[output_name] = res
                self.integer_accumulators[output_name] = self._last_integer_accumulator
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

    def _qlinear_conv(self, node: Any, inputs: List[Any]) -> np.ndarray:
        """Accumulates centered convolution products, then requantizes.

        Args:
            node: ONNX node providing strides and explicit spatial pads.
            inputs: X, X scale/ZP, weights, weight scale/ZP, Y scale/ZP,
                and optional int32 bias, in ONNX input order.

        Returns:
            Int8 NCHW activation. The integer result is also retained in
            ``_last_integer_accumulator`` for pre-rescale diagnostics.
        """
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
        # Widen BEFORE subtracting zero-points: centered int8 values span
        # [-255, 255], which cannot be represented in int8.
        x_int32 = x.astype(np.int32) - x_zp.astype(np.int32)
        w_int32 = w.astype(np.int32) - w_zp.astype(np.int32)

        # 2. Pad the centered domain with zero (equivalent to X_zp in raw X).
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
                        # NumPy sums int32 products in a wider integer on this
                        # host; the stored accumulator is explicitly int32.
                        acc = np.sum(patch * curr_w) + curr_b
                        output_acc[b, oc, i, j] = acc

        # 4. Requantisation
        # Formula: RealScale = (S_x * S_w) / S_y
        # Calculate the effective scale. Warning: w_scale can be a vector (per-channel)
        effective_scale = np.asarray((x_scale * w_scale) / y_scale, dtype=np.float32)
        
        # Reshape for correct broadcasting if per-channel
        if isinstance(effective_scale, np.ndarray) and effective_scale.size > 1:
            effective_scale = effective_scale.reshape(1, -1, 1, 1)

        self._last_integer_accumulator = output_acc
        return self._requantize(output_acc, effective_scale, y_zp)

    def _qlinear_add(self, inputs: List[Any]) -> np.ndarray:
        """Adds two quantized tensors using precomputed float32 ratios.

        Args:
            inputs: A, A scale/ZP, B, B scale/ZP, C scale/ZP.

        Returns:
            Int8 sum in the output quantization domain.

        Raises:
            ValueError: If the output scale is zero or non-scalar.
        """
        # A, A_scale, A_zp, B, B_scale, B_zp, C_scale, C_zp
        a, a_scale, a_zp = inputs[0], inputs[1], inputs[2]
        b, b_scale, b_zp = inputs[3], inputs[4], inputs[5]
        c_scale, c_zp = inputs[6], inputs[7]
        
        # 1. Convert both input scales to the output domain once per layer.
        # Multiplying a rounded reciprocal is deliberately different from
        # dividing each element or dividing each scale directly by c_scale.
        inv_c = float32_reciprocal(c_scale)
        multiplier_a = np.float32(np.float32(a_scale) * inv_c)
        multiplier_b = np.float32(np.float32(b_scale) * inv_c)

        # 2. Center in integers, then round EACH product to float32. Explicit
        # dtype avoids NumPy promoting int32 * float32 to float64.
        centered_a = a.astype(np.int32) - np.asarray(a_zp, dtype=np.int32)
        centered_b = b.astype(np.int32) - np.asarray(b_zp, dtype=np.int32)
        term_a = np.multiply(centered_a, multiplier_a, dtype=np.float32)
        term_b = np.multiply(centered_b, multiplier_b, dtype=np.float32)
        # 3. Round the sum to float32 before nearest-even integer rounding.
        # Keep the two products separate, matching C++ with FMA disabled.
        scaled = np.add(term_a, term_b, dtype=np.float32)
        return round_and_saturate(scaled, c_zp, np.dtype(np.int8))

    def _qlinear_mul(self, inputs: List[Any]) -> np.ndarray:
        """Multiplies a quantized tensor by a scalar through the VTA path.

        Args:
            inputs: A, A scale/ZP, B, B scale/ZP, C scale/ZP.

        Returns:
            Int8 product after integer multiplication and accumulator rescale.

        Raises:
            ValueError: If neither operand contains a single element.
        """
        a, a_scale, a_zp = inputs[0], inputs[1], inputs[2]
        b, b_scale, b_zp = inputs[3], inputs[4], inputs[5]
        c_scale, c_zp = inputs[6], inputs[7]
        
        # The compiler lowers MulConstant to VTA integer multiplication. The
        # scalar initializer may appear on either side of the ONNX operation.
        if np.asarray(a).size == 1:
            scalar, scalar_scale, scalar_zp = a, a_scale, a_zp
            tensor, tensor_scale, tensor_zp = b, b_scale, b_zp
        elif np.asarray(b).size == 1:
            scalar, scalar_scale, scalar_zp = b, b_scale, b_zp
            tensor, tensor_scale, tensor_zp = a, a_scale, a_zp
        else:
            raise ValueError("Embedded QLinearMul supports one scalar operand only.")

        centered_tensor = tensor.astype(np.int32) - np.asarray(tensor_zp, dtype=np.int32)
        centered_scalar = int(np.asarray(scalar, dtype=np.int32).reshape(-1)[0]) - int(
            np.asarray(scalar_zp, dtype=np.int32).reshape(())
        )
        # No floating-point dequantization here: multiply the centered integer
        # values first, then rescale ONCE as for a convolution accumulator.
        output_acc = centered_tensor * centered_scalar
        effective_scale = np.float32(
            np.float32(np.float32(tensor_scale) * np.float32(scalar_scale))
            / np.float32(c_scale)
        )
        self._last_integer_accumulator = output_acc.astype(np.int32, copy=False)
        return requantize_accumulator(self._last_integer_accumulator, effective_scale, c_zp)

    def _quantize_linear(self, inputs: List[Any]) -> np.ndarray:
        """Quantizes floats using a layer-wide float32 reciprocal.

        Args:
            inputs: Float tensor, scalar output scale, and optional zero-point.

        Returns:
            Integer tensor with the zero-point dtype (uint8 if omitted).

        Raises:
            ValueError: If the output scale is zero or non-scalar.
        """
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
        # Compute 1/scale once, then use a float32 multiply per value as on ARM.
        # Substituting a direct division can move values across half-integers.
        inv_scale = float32_reciprocal(y_scale)
        scaled = np.multiply(x.astype(np.float32), inv_scale, dtype=np.float32)
        
        # 2. Select saturation bounds; the helper rounds, adds ZP, then clips.
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

        return round_and_saturate(
            scaled,
            y_zp,
            np.dtype(dtype),
            min_val=q_min,
            max_val=q_max,
        )

    def _dequantize_linear(self, node: Any, inputs: List[Any]) -> np.ndarray:
        """Maps quantized values to float32 using (X - ZP) * scale.

        Args:
            node: ONNX node with an optional per-channel axis attribute.
            inputs: Quantized tensor, scale, and optional zero-point.

        Returns:
            Float32 tensor in the same logical layout. Per-axis broadcasting
            is supported here; the embedded CPU descriptor uses scalar scales.
        """
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
        centered = np.subtract(
            x.astype(np.float32), x_zp.astype(np.float32), dtype=np.float32
        )
        res = np.multiply(centered, x_scale.astype(np.float32), dtype=np.float32)
        
        return res

    def _qlinear_concat(self, node: Any, inputs: List[Any]) -> np.ndarray:
        """Requantizes each branch, then concatenates integer activations.

        Args:
            node: ONNX node specifying the concatenation axis.
            inputs: Y scale/ZP followed by triplets (X, X scale, X ZP).

        Returns:
            Concatenated tensor in the output zero-point's integer dtype.

        Raises:
            ValueError: If the output scale is zero or non-scalar.
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
        
        requantized_tensors = []
        inv_output_scale = float32_reciprocal(y_scale)
        
        for i in range(num_inputs):
            base_idx = i * 3
            val = content_inputs[base_idx]
            scale = content_inputs[base_idx + 1]
            zp = content_inputs[base_idx + 2]
            
            # Each branch has its own scale. Move it to the common output
            # domain with one rounded float32 multiplier before copying it.
            multiplier = np.float32(np.float32(scale) * inv_output_scale)
            centered = val.astype(np.int32) - np.asarray(zp, dtype=np.int32)
            scaled = np.multiply(centered, multiplier, dtype=np.float32)
            requantized_tensors.append(
                round_and_saturate(
                    scaled,
                    y_zp,
                    np.dtype(y_zp.dtype),
                    min_val=min_val,
                    max_val=max_val,
                )
            )
            
        # 4. Concatenate the already rounded/saturated INTEGER branches. No
        # floating-point arithmetic is performed during the actual concat.
        return np.concatenate(requantized_tensors, axis=axis)

    def _max_pool(self, node: Any, inputs: List[Any]) -> np.ndarray:
        """Pools NCHW values without changing their quantization domain.

        Args:
            node: ONNX node with kernel, strides, and explicit pads; ceil mode
                and dilation are not implemented by this reference path.
            inputs: List containing the input activation tensor.

        Returns:
            Pooled tensor with the input dtype, scale, and zero-point.
        """
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

    def _conv_transpose(self, node: Any, inputs: List[Any]) -> np.ndarray:
        """Scatter-accumulates a transposed convolution in float32.

        Args:
            node: ONNX node describing pads, strides, and supported attributes.
            inputs: NCHW float input, weights [Cin, Cout, KH, KW], optional bias.

        Returns:
            Float32 NCHW output with bias added after all products.

        Raises:
            ValueError: If groups, dilation, output padding, or strides exceed
                the embedded subset supported below.
        """
        # Inputs: X, W, B (optional)
        X = inputs[0]
        W = inputs[1]
        B = inputs[2] if len(inputs) > 2 else None
        
        # 1. Attributes
        pads = get_node_attribute(node, 'pads', default=(0,0,0,0))
        strides = get_node_attribute(node, 'strides', default=(1,1))
        dilations = get_node_attribute(node, 'dilations', default=(1,1))
        output_padding = get_node_attribute(node, 'output_padding', default=(0,0))
        group = get_node_attribute(node, 'group', default=1)

        if group != 1:
            raise ValueError(f"Embedded ConvTranspose only supports group=1, got {group}.")
        if tuple(dilations) != (1, 1):
            raise ValueError(
                f"Embedded ConvTranspose only supports dilations=(1, 1), got {dilations}."
            )
        if tuple(output_padding) != (0, 0):
            raise ValueError(
                "Embedded ConvTranspose only supports output_padding=(0, 0), "
                f"got {output_padding}."
            )
        if strides[0] != strides[1]:
            raise ValueError(
                f"Embedded ConvTranspose requires equal strides, got {strides}."
            )
        
        # 2. Dimensions
        batch, in_chan, in_h, in_w = X.shape
        # ONNX ConvTranspose Weights: (In_C, Out_C/Group, kH, kW)
        ic_w, oc_per_group, k_h, k_w = W.shape
        out_chan = oc_per_group * group
        
        s_h, s_w = strides
        out_h = (in_h - 1) * s_h + k_h - pads[0] - pads[2]
        out_w = (in_w - 1) * s_w + k_w - pads[1] - pads[3]
        output = np.zeros((batch, out_chan, out_h, out_w), dtype=np.float32)

        # 3. Scatter each input pixel across output channels and kernel cells.
        # Preserve cin, hin, win, cout, ky, kx order: float sums are not
        # associative. Separately round the product and addition as in C++
        # compiled with -ffp-contract=off (no fused multiply-add).
        for b in range(batch):
            for ic in range(in_chan):
                for h_in in range(in_h):
                    for w_in in range(in_w):
                        input_value = np.float32(X[b, ic, h_in, w_in])
                        if input_value == np.float32(0.0):
                            continue
                        for oc in range(out_chan):
                            for ky in range(k_h):
                                for kx in range(k_w):
                                    h_out = h_in * s_h + ky - pads[0]
                                    w_out = w_in * s_w + kx - pads[1]
                                    if 0 <= h_out < out_h and 0 <= w_out < out_w:
                                        product = np.float32(input_value * np.float32(W[ic, oc, ky, kx]))
                                        output[b, oc, h_out, w_out] = np.float32(
                                            output[b, oc, h_out, w_out] + product
                                        )

        # 4. Add bias only after all input-channel contributions are summed.
        if B is not None:
            output = np.add(
                output,
                B.astype(np.float32).reshape(1, -1, 1, 1),
                dtype=np.float32,
            )

        return output

# INTEGRATION FUNCTION
# ----------------------
def compare_numpy_vs_ort(
    model_path: str, input_data: np.ndarray, ort_output: np.ndarray
) -> np.ndarray:
    """Prints an informational comparison with an externally obtained ORT result.

    Args:
        model_path: ONNX model path.
        input_data: Input used to obtain the supplied ORT output.
        ort_output: Output from the caller's ONNX Runtime configuration.

    Returns:
        Output from the embedded-contract NumPy reference. ORT agreement is
        informational and does not define the project's arithmetic contract.
    """
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
