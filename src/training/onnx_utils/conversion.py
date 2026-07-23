import onnx
from onnx import helper, numpy_helper
import numpy as np
from typing import Dict, Set, List, Optional

def convert_qdq_to_qlinear_onnx(input_path: str, output_path: str) -> None:
    """Converts an ONNX model from QDQ (QuantizeDequantize) format to QLinear format.

    Args:
        input_path: Path to the input QDQ ONNX model.
        output_path: Path where the converted QLinear ONNX model will be saved.
    """
    model = onnx.load(input_path)
    graph = model.graph

    # Add com.microsoft opset import if not already present
    has_ms_domain = False
    for opset in model.opset_import:
        if opset.domain == "com.microsoft":
            has_ms_domain = True
            break
    if not has_ms_domain:
        ms_opset = model.opset_import.add()
        ms_opset.domain = "com.microsoft"
        ms_opset.version = 1
    
    def get_initializer(name: str) -> Optional[onnx.TensorProto]:
        for init in graph.initializer:
            if init.name == name:
                return init
        return None

    # Compute tensor usage counts to avoid removing Dequantize nodes whose outputs
    # are needed by other branches (e.g. residual skip connections)
    input_use_count: Dict[str, int] = {}
    for out in graph.output:
        input_use_count[out.name] = 1
    for node in graph.node:
        for inp in node.input:
            input_use_count[inp] = input_use_count.get(inp, 0) + 1

    # Iterative pattern matching
    nodes_to_remove: Set[int] = set()
    replacements: Dict[int, onnx.NodeProto] = {}  # id(old_node) -> new_node
    new_initializers: List[onnx.TensorProto] = []
    
    producer_map = {tensor: node for node in graph.node for tensor in node.output}

    for node in graph.node:
        if node.op_type == "Conv":
            x_dq = producer_map.get(node.input[0])
            w_dq = producer_map.get(node.input[1])
            if x_dq and x_dq.op_type == "DequantizeLinear" and w_dq and w_dq.op_type == "DequantizeLinear":
                # Look for Q after Conv
                q_after: Optional[onnx.NodeProto] = None
                relu_node: Optional[onnx.NodeProto] = None
                for n in graph.node:
                    if node.output[0] in n.input:
                        if n.op_type == "QuantizeLinear":
                            q_after = n
                        elif n.op_type == "Relu":
                            relu_node = n
                            for n2 in graph.node:
                                if n.output[0] in n2.input and n2.op_type == "QuantizeLinear":
                                    q_after = n2
                                    break
                        break
                if q_after:
                    # Construct QLinearConv
                    x_q, x_s, x_zp = x_dq.input[0], x_dq.input[1], x_dq.input[2]
                    w_q, w_s, w_zp = w_dq.input[0], w_dq.input[1], w_dq.input[2]
                    y_s, y_zp, y_q = q_after.input[1], q_after.input[2], q_after.output[0]
                    inputs = [x_q, x_s, x_zp, w_q, w_s, w_zp, y_s, y_zp]
                    if len(node.input) > 2:
                        bias_name = node.input[2]
                        b_init = get_initializer(bias_name)
                        x_s_init = get_initializer(x_s)
                        w_s_init = get_initializer(w_s)
                        xs_val = numpy_helper.to_array(x_s_init) if x_s_init else None
                        ws_val = numpy_helper.to_array(w_s_init) if w_s_init else None
                        if b_init and xs_val is not None and ws_val is not None:
                            b_q = np.round(numpy_helper.to_array(b_init) / (xs_val * ws_val)).astype(np.int32)
                            b_q_name = bias_name + "_quantized"
                            new_initializers.append(numpy_helper.from_array(b_q, name=b_q_name))
                            inputs.append(b_q_name)
                        else:
                            inputs.append(bias_name)
                    attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
                    if "kernel_shape" not in attrs:
                        w_init = get_initializer(w_q)
                        if w_init:
                            attrs["kernel_shape"] = list(w_init.dims[2:])
                    replacements[id(q_after)] = helper.make_node(
                        "QLinearConv",
                        inputs=inputs,
                        outputs=[y_q],
                        name=node.name + "_qlinear",
                        **attrs
                    )
                    nodes_to_remove.add(id(node))
                    if input_use_count.get(x_dq.output[0], 0) <= 1:
                        nodes_to_remove.add(id(x_dq))
                    if input_use_count.get(w_dq.output[0], 0) <= 1:
                        nodes_to_remove.add(id(w_dq))
                    if relu_node:
                        nodes_to_remove.add(id(relu_node))

        elif node.op_type in ["Relu", "MaxPool", "Flatten"]:
            x_dq = producer_map.get(node.input[0])
            if x_dq and x_dq.op_type == "DequantizeLinear":
                q_after = None
                for n in graph.node:
                    if node.output[0] in n.input and n.op_type == "QuantizeLinear":
                        q_after = n
                        break
                if q_after:
                    replacements[id(q_after)] = helper.make_node(
                        node.op_type,
                        inputs=[x_dq.input[0]],
                        outputs=[q_after.output[0]],
                        name=node.name + "_quantized",
                        **{a.name: helper.get_attribute_value(a) for a in node.attribute}
                    )
                    nodes_to_remove.add(id(node))
                    if input_use_count.get(x_dq.output[0], 0) <= 1:
                        nodes_to_remove.add(id(x_dq))

        elif node.op_type == "Add":
            x_dq = producer_map.get(node.input[0])
            y_dq = producer_map.get(node.input[1])
            if x_dq and x_dq.op_type == "DequantizeLinear" and y_dq and y_dq.op_type == "DequantizeLinear":
                q_after = None
                relu_node = None
                for n in graph.node:
                    if node.output[0] in n.input:
                        if n.op_type == "QuantizeLinear":
                            q_after = n
                        elif n.op_type == "Relu":
                            relu_node = n
                            for n2 in graph.node:
                                if n.output[0] in n2.input and n2.op_type == "QuantizeLinear":
                                    q_after = n2
                                    break
                        break
                if q_after:
                    x_q, x_s, x_zp = x_dq.input[0], x_dq.input[1], x_dq.input[2]
                    y_q, y_s, y_zp = y_dq.input[0], y_dq.input[1], y_dq.input[2]
                    out_s, out_zp, out_q = q_after.input[1], q_after.input[2], q_after.output[0]
                    replacements[id(q_after)] = helper.make_node(
                        "QLinearAdd",
                        inputs=[x_q, x_s, x_zp, y_q, y_s, y_zp, out_s, out_zp],
                        outputs=[out_q],
                        name=node.name + "_qlinear",
                        domain="com.microsoft"
                    )
                    nodes_to_remove.add(id(node))
                    if input_use_count.get(x_dq.output[0], 0) <= 1:
                        nodes_to_remove.add(id(x_dq))
                    if input_use_count.get(y_dq.output[0], 0) <= 1:
                        nodes_to_remove.add(id(y_dq))
                    if relu_node:
                        nodes_to_remove.add(id(relu_node))

        elif node.op_type == "Concat":
            is_qdq_concat = True
            dq_nodes = []
            for inp_name in node.input:
                x_dq = producer_map.get(inp_name)
                if x_dq and x_dq.op_type == "DequantizeLinear":
                    dq_nodes.append(x_dq)
                else:
                    is_qdq_concat = False
                    break
            
            if is_qdq_concat:
                q_after = None
                for n in graph.node:
                    if node.output[0] in n.input and n.op_type == "QuantizeLinear":
                        q_after = n
                        break
                if q_after:
                    y_scale, y_zp, y_q = q_after.input[1], q_after.input[2], q_after.output[0]
                    inputs = [y_scale, y_zp]
                    for x_dq in dq_nodes:
                        inputs.extend([x_dq.input[0], x_dq.input[1], x_dq.input[2]])
                    
                    attrs = {a.name: helper.get_attribute_value(a) for a in node.attribute}
                    replacements[id(q_after)] = helper.make_node(
                        "QLinearConcat",
                        inputs=inputs,
                        outputs=[y_q],
                        name=node.name + "_qlinear",
                        domain="com.microsoft",
                        **attrs
                    )
                    nodes_to_remove.add(id(node))
                    for x_dq in dq_nodes:
                        if input_use_count.get(x_dq.output[0], 0) <= 1:
                            nodes_to_remove.add(id(x_dq))

    # Assemble and maintain topological order
    new_node_list: List[onnx.NodeProto] = []
    for node in graph.node:
        if id(node) in replacements:
            new_node_list.append(replacements[id(node)])
        elif id(node) not in nodes_to_remove:
            new_node_list.append(node)
    graph.ClearField("node")
    graph.node.extend(new_node_list)
    graph.initializer.extend(new_initializers)

    # Strip start Q and end DQ to leave pure quantized inputs/outputs
    if len(graph.node) > 0 and graph.node[0].op_type == "QuantizeLinear":
        q_node = graph.node.pop(0)
        old_in, new_in = q_node.input[0], q_node.output[0]
        
        in_shape = []
        for inp in graph.input:
            if inp.name == old_in:
                for d in inp.type.tensor_type.shape.dim:
                    if d.HasField("dim_value"):
                        in_shape.append(d.dim_value)
                    else:
                        in_shape.append(d.dim_param)
                break

        for n in graph.node:
            for i, inp in enumerate(n.input):
                if inp == new_in:
                    n.input[i] = "input"
        for inp in graph.input:
            if inp.name == old_in:
                inp.name = "input"
                inp.type.tensor_type.elem_type = onnx.TensorProto.INT8
                s = inp.type.tensor_type.shape
                s.ClearField("dim")
                for d in in_shape:
                    dim_obj = s.dim.add()
                    if isinstance(d, int):
                        dim_obj.dim_value = d
                    else:
                        dim_obj.dim_param = d

    # Find the node that produces the final output (before DQ) and format it
    if len(graph.node) > 0:
        last_node = graph.node[-1]
        if last_node.op_type == "DequantizeLinear":
            dq_node = graph.node.pop(-1)
            new_out, old_out = dq_node.input[0], dq_node.output[0]
            
            out_shape = []
            for out in graph.output:
                if out.name == old_out:
                    for d in out.type.tensor_type.shape.dim:
                        if d.HasField("dim_value"):
                            out_shape.append(d.dim_value)
                        else:
                            out_shape.append(d.dim_param)
                    break

            for n in graph.node:
                for i, out in enumerate(n.output):
                    if out == new_out:
                        n.output[i] = "output"
            for out in graph.output:
                if out.name == old_out:
                    out.name = "output"
                    out.type.tensor_type.elem_type = onnx.TensorProto.INT8
                    s = out.type.tensor_type.shape
                    s.ClearField("dim")
                    for d in out_shape:
                        dim_obj = s.dim.add()
                        if isinstance(d, int):
                            dim_obj.dim_value = d
                        else:
                            dim_obj.dim_param = d

    # Cleanup unused attributes and scalars
    scalar_inits: Set[str] = set()
    for node in graph.node:
        if node.op_type in ["QuantizeLinear", "DequantizeLinear", "QLinearConv", "QLinearMatMul"]:
            idx = [1, 2] if "Quantize" in node.op_type else [1, 2, 4, 5, 6, 7]
            for i in idx:
                if i < len(node.input):
                    scalar_inits.add(node.input[i])
            attrs = [a for a in node.attribute if a.name not in ["axis", "auto_pad"]]
        else:
            attrs = [a for a in node.attribute if a.name not in ["auto_pad"]]
        node.ClearField("attribute")
        node.attribute.extend(attrs)

    for init in graph.initializer:
        if init.name in scalar_inits:
            init.ClearField("dims")

    # Dead node elimination pass for unused Q/DQ nodes
    while True:
        used_tensors: Set[str] = set()
        for out in graph.output:
            used_tensors.add(out.name)
        for node in graph.node:
            for inp in node.input:
                used_tensors.add(inp)
        
        nodes_to_keep = []
        removed_any = False
        for node in graph.node:
            if node.op_type in ["DequantizeLinear", "QuantizeLinear"]:
                if not any(out in used_tensors for out in node.output):
                    removed_any = True
                    continue
            nodes_to_keep.append(node)
            
        if not removed_any:
            break
        graph.ClearField("node")
        graph.node.extend(nodes_to_keep)

    # Clean up unused initializers
    used_tensors = set()
    for node in graph.node:
        for inp in node.input:
            used_tensors.add(inp)
    inits_to_keep = [init for init in graph.initializer if init.name in used_tensors]
    graph.ClearField("initializer")
    graph.initializer.extend(inits_to_keep)

    try:
        onnx.checker.check_model(model)
    except Exception as e:
        print(f"⚠️ ONNX Model Checker Warning: {e}")

    onnx.save(model, output_path)
    print(f"✅ Successfully converted QDQ model to QLinear model at: {output_path}")

