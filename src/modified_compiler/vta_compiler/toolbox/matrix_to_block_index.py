# IMPORT PACKAGES
# ---------------


###############################################


# vectorMatrixToBlock
# -------------------
def vectorMatrixToBlock(matrix_vector, block_size=16, nb_blocks_col=2):
    """
    A matrix vector X(a) is a set of block vectors X_{b}(c).
    The function takes "a" and returns both: a list of absolute idx (b*bs+c) and a list of pair [(b,c)].
    
    Inputs:
        - matrix_vector (int): index of the vector on the global matrix
        - block_size (int): number of vectors within a block
        - nb_blocks_col (int): number of column within the block matrix
    Output:
        - flat_block_vectors (list of int): list the indices from 0 to the last vectors
        - pair_block_vectors (list of typle: int, int): return a list of associated block idx and row idx within the block
    """
    # Initialise the lists
    flat_block_vectors = []
    pair_block_vectors = []
    block_idx = 0
    row_idx = 0

    # Loop on all the columns
    for i in range(0, nb_blocks_col):
        block_idx = (matrix_vector // block_size) * nb_blocks_col + i
        row_idx = matrix_vector % block_size

        # Append the lists
        flat_block_vectors.append( block_idx * block_size + row_idx )
        pair_block_vectors.append( (block_idx, row_idx) )

    # Return the list
    return flat_block_vectors, pair_block_vectors


###############################################


# aluMatrixToBlock
# ----------------
def aluMatrixToBlock(alu_list, block_size=16, nb_blocks_col=2):
    """
    Transform an ALU given by the VTA IR in list of pair vectors (op C(a) with C(b)).
    
    Inputs:
        - alu_list (-): VTA IR list for ALU
        - block_size (int): number of vectors within a block
        - nb_blocks_col (int): number of column within the block matrix
    Output:
        - pair_alu_block_list (list of list: [str, int, int]): list of ALU
    """
    # Initialise the list
    pair_alu_matrix_list = []
    pair_alu_block_list = []

    # Decode the previous list and flatten it
    for alu in alu_list:
        # Save the operator
        op = alu[0]

        #Get the destination and the number of loop
        dst_idx = alu[1][0][0]
        dst_step = alu[1][0][1]
        nb_loop = alu[1][2]

        # If immediate value -> scalar
        if ( type(alu[1][1]) == int ):
            scalar = alu[1][1]

            # Flatten the list
            for i in range(0, nb_loop):
                current_dst = dst_idx + dst_step * i 
                # pair_alu_matrix_list.append( [op, current_dst, scalar] )

                # Get the list by block
                block_vectors = vectorMatrixToBlock(current_dst, block_size=block_size, nb_blocks_col=nb_blocks_col)

                # Flatten again
                for vector in block_vectors:
                    pair_alu_block_list.append( [op, vector, scalar] )

        
        else: # Not immediate value
            # Get the source
            src_idx = alu[1][1][0]
            src_step = alu[1][1][1]

            # Flatten the list
            for i in range(0, nb_loop):
                current_dst = dst_idx + dst_step * i 
                current_src = src_idx + src_step * i 
                # pair_alu_matrix_list.append( [op, current_dst, current_src] )

                # Get the list by block
                dst_block_vectors = vectorMatrixToBlock(current_dst, block_size=block_size, nb_blocks_col=nb_blocks_col)
                src_block_vectors = vectorMatrixToBlock(current_src, block_size=block_size, nb_blocks_col=nb_blocks_col)

                # Flatten again
                for idx, vector in enumerate(dst_block_vectors):
                    pair_alu_block_list.append( [op, vector, src_block_vectors[idx]] )

    # Return the list
    return pair_alu_block_list



###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__": 
    # Parameters
    alu_list1 = [
        ["MAX_IMM", [[0,1], 0, 16]]
    ]
    alu_list2 = [
        ["MAX", [[0,0], [1,1], 8]],
        ["MAX", [[9,0], [10,1], 8]],
        ["MAX", [[18,0], [19,1], 8]],
        ["MAX", [[27,0], [28,1], 8]]
    ]

    block_size = 2
    nb_blocks_col = 3

    # Execution
    res = aluMatrixToBlock(alu_list2, block_size=block_size, nb_blocks_col=nb_blocks_col)

    # Print
    print(f"\nDEBUG: res={res} \n")
    for i in res:
        print(i)

