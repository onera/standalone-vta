import onnx
import onnx.shape_inference
from onnx import numpy_helper
from onnxruntime.tools.symbolic_shape_infer import SymbolicShapeInference
import numpy as np
import json # Import json for pretty printing the result
from typing import Dict, Union

def parse_onnx_to_dict(model_path, debug=False):
    """
    Loads an ONNX model, runs shape inference, and returns its structure
    as a dictionary (the graph) and a tensor-to-node-index map.

    The function extracts tensor shapes and operation attributes (e.g., kernel_size, strides).

    Args:
        model_path (str): The file path to the ONNX model.
        debug (bool): If True, prints the resulting graph structure.

    Returns:
        tuple: (graph_info, tensor_name_to_node_index) where:
               - graph_info (dict): The structured graph information.
               - tensor_name_to_node_index (dict): Maps tensor names to the 
                 index (1-based) of the node that produces them. Returns 
                 (None, None) on failure.
    """
    try:
        # 1. Load the original model
        model = onnx.load(model_path)
    except FileNotFoundError:
        print(f"Error: Model file not found at '{model_path}'")
        return None, None # Return None on failure
    except Exception as e:
        print(f"Error loading model: {e}")
        return None, None

    # 2. Run Shape Inference!
    # This is the key step. It returns a new model object with all tensor shapes filled in.
    try:
        inferred_model = onnx.shape_inference.infer_shapes(model)
        # inferred_model = SymbolicShapeInference.infer_shapes(model, auto_merge=True)
    except Exception as e:
        print(f"Warning: Error during symbolic shape inference: {e}")
        print("Falling back to standard inference...")
        try:
             inferred_model = onnx.shape_inference.infer_shapes(model)
        except:
             inferred_model = model
             
    graph = inferred_model.graph

    # --- Create a map of tensor names to their dimensions ---
    # This map will now be much more complete thanks to shape inference.
    tensor_dims = {}

    # Helper function to extract dimensions (dims)
    def get_dims(tensor):
        if tensor.type.tensor_type.HasField("shape"):
            # Use dim_value for static shapes, or dim_param for dynamic shapes
            return [d.dim_value if d.HasField("dim_value") else d.dim_param for d in tensor.type.tensor_type.shape.dim]
        else:
            return "Unknown Shape"

    # Populate dims for graph inputs, outputs, and intermediate value_info
    for tensor in list(graph.input) + list(graph.value_info) + list(graph.output):
        tensor_dims[tensor.name] = get_dims(tensor)

    # Populate dims for initializers (weights/biases)
    for initializer in graph.initializer:
        tensor_dims[initializer.name] = list(initializer.dims)


    # --- Prepare the data to be returned ---
    graph_info = {}
    graph_info['model_name'] = graph.name
    
    # Dictionary for mapping a tensor output name to the index of its producing node.
    tensor_name_to_node_index = {} 
    
    # --- Graph Inputs ---
    graph_info['inputs'] = []
    for inp in graph.input:
        graph_info['inputs'].append({
            'name': inp.name,
            'shape': tensor_dims.get(inp.name, 'Unknown')
        })
        # Add the input to the mapping with index 0
        tensor_name_to_node_index[inp.name] = 0

    # --- Graph Outputs ---
    graph_info['outputs'] = []
    for outp in graph.output:
        graph_info['outputs'].append({
            'name': outp.name,
            'shape': tensor_dims.get(outp.name, 'Unknown')
        })

    # --- Iterate through nodes in topological order ---
    graph_info['nodes'] = []
    
    for i, node in enumerate(graph.node):
        # We use 1-based indexing for better human readability, common in graph tools
        node_index = i + 1 
        
        node_info = {}
        node_info['index'] = node_index
        node_info['name'] = node.name if node.name else f"{node.op_type}_{node_index}"
        node_info['op_type'] = node.op_type

        # --- Extract Node Attributes (The missing part!) ---
        node_info['attributes'] = {}
        for attr in node.attribute:
            # We must check the attribute type to correctly extract the value
            if attr.HasField('f'): # Float
                node_info['attributes'][attr.name] = attr.f
            elif attr.HasField('i'): # Integer
                node_info['attributes'][attr.name] = attr.i
            elif attr.HasField('s'): # String (Decoded from bytes)
                node_info['attributes'][attr.name] = attr.s.decode('utf-8')
            elif attr.HasField('t'): # Tensor (Only store the shape)
                node_info['attributes'][attr.name] = list(onnx.numpy_helper.to_array(attr.t).shape)
            elif attr.HasField('g'): # Graph (Often too complex to log)
                node_info['attributes'][attr.name] = f"[Graph Attr: {attr.name}]"
            elif len(attr.floats): # List of Floats
                node_info['attributes'][attr.name] = list(attr.floats)
            elif len(attr.ints): # List of Integers (e.g., strides, kernel_shape, pads)
                node_info['attributes'][attr.name] = list(attr.ints)
            elif len(attr.strings): # List of Strings
                node_info['attributes'][attr.name] = [s.decode('utf-8') for s in attr.strings]
            else:
                 node_info['attributes'][attr.name] = "[Unsupported Attr Type]"

        # --- Node Inputs ---
        node_info['inputs'] = []
        for input_name in node.input:
            dims = tensor_dims.get(input_name, "N/A - Constant or Initializer")
            node_info['inputs'].append({
                'name': input_name,
                'shape': dims
            })

        # --- Node Outputs ---
        node_info['outputs'] = []
        for output_name in node.output:
            dims = tensor_dims.get(output_name, "Unknown")
            node_info['outputs'].append({
                'name': output_name,
                'shape': dims
            })
            # --- Populate the tensor_name_to_node_index map ---
            # Map this output tensor name to the current node index
            tensor_name_to_node_index[output_name] = node_index
        
        graph_info['nodes'].append(node_info)

    # Debug printing
    if (debug):
        print(f"Successfully parsed model: {model_path}")
        print("-" * 50)
        print("--- Graph Information ---")
        print(json.dumps(graph_info, indent=2))
        print("-" * 50)
        print("--- Tensor Name to Node Index Map (for linking) ---")
        print(json.dumps(tensor_name_to_node_index, indent=2))
        print("-" * 50)


    # Return the structured dictionary and the tensor map
    return graph_info, tensor_name_to_node_index


###############################################


def get_onnx_parameters(model_path: str, debug=False) -> Union[Dict[str, np.ndarray], None]:
    """
    Loads an ONNX model and extracts the values of all initializers (weights and biases).

    Args:
        model_path (str): The file path to the ONNX model.

    Returns:
        Dict[str, np.ndarray] or None: A dictionary where keys are the 
        initializer names (the tensor names) and values are the actual NumPy 
        arrays containing the weights/biases. Returns None on failure.
    """
    try:
        # 1. Load the model
        model = onnx.load(model_path)
    except FileNotFoundError:
        print(f"Error: Model file not found at '{model_path}'")
        return None
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

    parameters = {}
    graph = model.graph

    # 2. Iterate through all initializers in the graph
    # Initializers store the constant data (weights/biases)
    for initializer in graph.initializer:
        # numpy_helper.to_array safely converts the ONNX TensorProto into a NumPy ndarray
        try:
            param_array = numpy_helper.to_array(initializer)
            parameters[initializer.name] = param_array
        except Exception as e:
            print(f"Warning: Could not convert initializer '{initializer.name}' to NumPy array: {e}")
            # Store a placeholder if conversion fails
            parameters[initializer.name] = f"Error loading data: {e}"

    if (debug):
        print(f"\nSuccessfully extracted {len(parameters)} parameters from the model.")
        for i, param in enumerate(parameters):
            print(f"\t {i}: '{param}' ") 
            # print(f"\t {parameters[param]}") 
        print(f"\n") 

    return parameters


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    """
    To execute: 
        > python parse_onnx_to_dict.py 
    """
    debug = True

    onnx_model_path = "../../../../onnx_zoo/yolonas.onnx" 

    # Execute the backend
    result = parse_onnx_to_dict(onnx_model_path, debug=debug)

    # END!



