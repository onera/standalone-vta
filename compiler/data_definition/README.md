# Data Definition Tools

This directory contains Python scripts for generating binary instruction and data files compatible with the VTA functional simulator. It also provides JSON files with data to be used with the cycle-accurate simulator. Note that the JSON file must be updated with the correct UOP and instructions.

## Overview

The scripts use `numpy` to create and manipulate matrices, so you must install it prior going further.
```
pip install numpy
```

## Usage

0.  **Define the size of the matrices:**  (optional) Use `tensor_matrix_converter.py` to obtain the shape of the input and weight matrices from the tensor dimension.
    * Modify the file with the input and output tensor dimension as well as the kernel parameters.
    * Execute in a terminal: `python tensor_matrix_converter.py`

1.  **Configure the data generation:**  Use `user_configuration.py` to set:
    * The matrix shape and some initialisation parameters such as the initialisation values (either random or 0).
    * The computation parameters such as the application of a ReLU activation (ground to 0 the negative value) on the result.
    * The generation parameters to define if the program print, write binaries or JSON files.

    For instance, to execute a 10x10 matrix multiplied by a 10x10 matrix, both initialised with random value, you must define the following parameters:
    ```
    isInitRandom = True
    A_row = 10
    A_col = 10
    B_col = 10
    ```
    The VTA architecture takes 16 element vectors in input and the matrices are expected to be square, thus:
    ```
    block_size = 16
    isSquare = True
    ```
    The matrices are going to be padded to be 16x16. 
    We do not apply ReLU on the multiplication:
    ```
    useReLU = False
    ```
    Then, we want to generate a JSON file:
    ```
    doWriteJSON = True
    ```

2.  **Run the main_matrix_generator.py:**  Run `python main_matrix_generator.py` in a terminal to generate the data.

An important remark is that the VTA uses the transposed of the matrix B for its computation.