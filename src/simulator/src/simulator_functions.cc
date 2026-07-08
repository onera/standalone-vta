/***************************
    PRE-PROCESSOR DIRECTIVES
****************************/
#include "../include/simulator_header.h"


/*********************
    INIT_VECTOR_VALUES
**********************/
int8_t * init_vector_values(int8_t * vector, uint64_t size, bool random_value, unsigned int seed){
    if (random_value){
        srand(seed);
    }
    for (uint64_t i = 0; i < size; i++){
        if (random_value){
            vector[i] = rand() % 256 - 128;
        }
        else {
            vector[i] = -1;
        }
    }
    return vector;
}


/*********************
    READ_CSV (Optimized)
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

/**
 * \brief Helper function to remove spaces, newlines, and carriage returns.
 * This ensures keys and values in the map are "clean" immediately.
 */
static std::string sanitize_string(std::string s) {
    // Remove carriage returns (\r)
    s.erase(std::remove(s.begin(), s.end(), '\r'), s.end());
    // Remove newlines (\n)
    s.erase(std::remove(s.begin(), s.end(), '\n'), s.end());
    // Remove spaces (' ') - As requested by user logic
    s.erase(std::remove(s.begin(), s.end(), ' '), s.end());
    return s;
}

CsvMap load_csv_to_map(const std::string& filename) {
    CsvMap map;
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Error: Could not open CSV file: " << filename << std::endl;
        return map;
    }

    std::string line;
    while (std::getline(file, line)) {
        // Skip empty lines
        if (line.empty()) continue;

        std::stringstream ss(line);
        std::string cell;
        std::vector<std::string> row_data;
        
        while (std::getline(ss, cell, ',')) {
            // SANITIZE HERE: Clean the data before storing it
            row_data.push_back(sanitize_string(cell));
        }

        if (!row_data.empty()) {
            // Map Key = First Column (also sanitized)
            map[row_data[0]] = row_data;
        }
    }
    file.close();
    return map;
}

std::string get_csv_value(const CsvMap& map, const std::string& key, int col_index) {
    // Sanitize the key to ensure we match what is stored in the map
    // (e.g. if user asks for "Layer 1" but map has "Layer1")
    std::string clean_key = sanitize_string(key);

    auto it = map.find(clean_key);
    if (it != map.end()) {
        if (col_index < (int)it->second.size()) {
            return it->second[col_index];
        } else {
             // Optional: Warning disabled to avoid spamming if columns are optional
             // std::cerr << "Warning: Column index " << col_index << " out of bounds for key " << clean_key << std::endl;
             return "";
        }
    }
    return "";
}


// Convert str in int
int strToInt(const std::string value){
    int intValue = 0;
    try {
        intValue = std::stoi(value);
    } catch (...) {
        // Silent catch or minimal error
    }
    return intValue;
}

// Convert str in float
double strToFloat(const std::string value){
    double floatValue = 0.0f;
    try {
        floatValue = std::stod(value); //stof for float (32-bit) and stod for double (64-bit)
    } catch (...) {
    }
    return floatValue;
}