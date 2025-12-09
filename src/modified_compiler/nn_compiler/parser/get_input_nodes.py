def get_input_nodes(compute_nodes, input_nodes, dict_name_index):
    # Init the list
    input_nodes_list = []

    # Iterate over all the inputs
    for inp in input_nodes:
        # Get the name
        inp_name = inp['name']

        # If the input is in the dict, it comes from another layer
        if (inp_name in dict_name_index):
            # Get the node index
            node_idx = dict_name_index[inp_name]

            # Special case: idx = 0 <=> Graph input
            if (node_idx == 0):
                input_nodes_list.append( "image" )
            else: # Input come from another node
                inp_node = compute_nodes[node_idx - 1]
                # Get the filename of the other nodes
                filename = inp_node['op_type'] + str( inp_node['index'] )
                # Append the list
                input_nodes_list.append( filename )

    # return the list
    return input_nodes_list

