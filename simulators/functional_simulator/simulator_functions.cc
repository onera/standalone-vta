/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"


/***************
    PRINT_VECTOR
****************/
/*!
 * \brief Print a vector with 8-bit data
 */
void print_int8_vector(int8_t * vector, uint64_t size){
    // Loop over the vector elements
    for (uint64_t elem = 0; elem < size; elem++){
        // New line each 16 elements
        if (elem%16 == 0){
            printf("\n");
            if (elem%256 == 0){
                printf("\n \t(Element nb: %ld) \n", elem/256);
            }
        }
        // Print the element
        printf("\t %d", vector[elem]);
    }
}

/*!
 * \brief Print a vector with 32-bit data
 */
void print_int32_vector(int32_t * vector, uint64_t size){
    // Loop over the vector elements
    for (uint64_t elem = 0; elem < size; elem++){
        // New line each 16 elements
        if (elem%16 == 0){
            printf("\n");
            if (elem%256 == 0){
                printf("\n \t(Element nb: %ld) \n", elem/256);
            }
        }
        // Print the element
        printf("\t %d", vector[elem]);
    }
}


/*****************
    COMPARE_VECTOR
******************/
/*!
 * \brief Compare two vectors with 8-bit data and return a boolean (true if identical, else false)
 */
bool compare_vector(int8_t * vector_A, int8_t * vector_B, uint64_t size){
    bool is_same = true;
    // Loop over the vector elements
    for (uint64_t elem = 0; elem < size; elem++){
        // Check if the element is the same
        if (vector_A[elem] != vector_B[elem]){
            is_same = false;
            printf("\nDiscrepancy at element: %lu \n", elem);
        }
    }
    // Return the boolean
    return is_same;
}


/*********************
    INIT_VECTOR_VALUES
**********************/
/*!
 * \brief Initialise vector with random values or with "-1" values
 */
int8_t * init_vector_values(int8_t * vector, uint64_t size, bool random_value, unsigned int seed = static_cast<unsigned int>(time(0))){
    // Init the seed generator for random numbers
    if (random_value){
        srand(seed);
    }

    // Fullfil the vector
    for (uint64_t i = 0; i < size; i++){
        if (random_value){
            vector[i] = rand() % 256 - 128;
        }
        else {
            vector[i] = -1;
        }
    }

    // Return the boolean
    return vector;
}


/*********************
    RESHAPE VECTORS
**********************/
std::vector<int8_t> reshape(const std::vector<int8_t>& intermediate_result, 
                            int in_channel = 6, int in_tensor_size = 14, 
                            int out_tensor_size = 10, int kernel_size = 5, 
                            int stride = 1, int block_size = 16, 
                            int nb_elements = 112*160) {
    // Size of the input matrix
    int matrix_width = in_channel * kernel_size * kernel_size;

    // Compute the padding
    int width_padding = ((in_channel * kernel_size * kernel_size - 1) / 16 + 1) * 16 - matrix_width;

    // Compute the number of copied elements
    int copied_elements = out_tensor_size * out_tensor_size * in_channel * kernel_size * kernel_size + width_padding * out_tensor_size * out_tensor_size;

    // Compute the number of 0 to add
    int elements_padding = nb_elements - copied_elements;

    // Output vector
    std::vector<int8_t> reshaped_result;

    // Fulfill the output vector
    for (int wh = 0; wh < out_tensor_size; ++wh) {
        for (int ww = 0; ww < out_tensor_size; ++ww) {
            for (int c = 0; c < in_channel; ++c) {
                for (int kh = 0; kh < kernel_size; ++kh) {
                    for (int kw = 0; kw < kernel_size; ++kw) {
                        // Compute the source index and push it in the output vector
                        int src_index = (kw + kh * in_tensor_size + ww * stride + wh * stride * in_tensor_size) * block_size + c;
                        reshaped_result.push_back(intermediate_result[src_index]);

                        // Pad on the width
                        if (c == in_channel - 1 && kh == kernel_size - 1 && kw == kernel_size - 1) {
                            for (int i = 0; i < width_padding; ++i) {
                                reshaped_result.push_back(0);
                            }
                        }
                    }
                }
            }
        }
    }

    // Add the final padding
    for (int i = 0; i < elements_padding; ++i) {
        reshaped_result.push_back(0);
    }

    return reshaped_result;
}
