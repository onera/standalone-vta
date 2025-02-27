/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "simulator_header.h"


/**************
    DUMP_MEMORY
***************/
/*!
 * \brief Dump memory into a binary file
 */
void dump_memory(void * ptr, const char * path, size_t size, size_t n_element){
    // Stream
    FILE * pFile;
    // Open and write the file
    // FWRITE to write the binary content in a file 
    pFile = fopen(path, "wb"); 
    fwrite(ptr, size, n_element, pFile); 
    // Close the file
    fclose(pFile);
}


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
                printf("\n");
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
                printf("\n");
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
