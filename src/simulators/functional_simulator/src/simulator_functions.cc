/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"


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
                printf("\n \t(block_id: %ld) \n", elem/256);
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
                printf("\n \t(block_id: %ld) \n", elem/256);
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
            int block_id = elem/256;
            int block_row = (elem/16)%16;
            int block_col = (elem%256)%16;
            printf("\nDiscrepancy at element: %lu (block_id: %d, block_row: %d, block_col: %d)" 
                   "\n\t C_elem=%d -> ref=%d \n", 
                elem, block_id, block_row, block_col, vector_A[elem], vector_B[elem]);
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
    READ_CSV
**********************/
/**
 * Finds a row by its first element (the 'name') and returns the
 * element at the specified column index from that row.
 *
 * @param filename The path to the CSV file.
 * @param rowName The "key" to search for in the first column.
 * @param targetCol The 0-indexed column to retrieve from that row.
 * @return The element as a std::string, or an error message.
 */
    std::string getCsvElementByName(const std::string& filename, 
                                    const std::string& rowName, 
                                    int targetCol) {
        
        std::ifstream file(filename);
        if (!file.is_open()) {
            return "Error: Could not open file.";
        }

        std::string line;
        // 1. Loop through each line in the file
        while (std::getline(file, line)) {
            std::stringstream ss(line);
            std::string firstCell;

            // 2. Get the first cell (the "key" or "name")
            if (!std::getline(ss, firstCell, ',')) {
                continue; // Skip empty or malformed lines
            }

            // 3. Check if this is the row we're looking for
            if (firstCell == rowName) {
                // Found the right row! Now find the right column.
                
                // Check if the user wanted the key itself (col 0)
                if (targetCol == 0) {
                    file.close();
                    return firstCell;
                }

                std::string targetCell;
                int currentCol = 1; // Start at 1, since we already read col 0

                // 4. Loop through the remaining cells on this line
                while (std::getline(ss, targetCell, ',')) {
                    if (currentCol == targetCol) {
                        file.close();
                        return targetCell; // Found it!
                    }
                    currentCol++;
                }
                
                // If we're here, the row was found but the col was out of bounds
                file.close();
                return "Error: Column index out of bounds for this row.";
            }
        }

        // If we're here, we looped through the whole file and never found the row
        file.close();
        return "Error: Row name not found.";
    }


// Convert str in int
int strToInt(const std::string value){
    int intValue;
    try {
        intValue = std::stoi(value);
    } catch (const std::exception& e) {
        std::cout << "Could not convert '" << value << "' to an integer." << std::endl;
    }
    return intValue;
}
