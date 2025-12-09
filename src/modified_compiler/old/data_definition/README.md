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

    For instance, LeNet-5 first convolution has an input tensor is 1 channel deep, 32 pixels height and 32 pixel wide. Thus,
    ```
    input_channel = 1
    input_height = 32
    input_width = 32
    ```
    The convolution results in a 28x28 pixels tensor with 6 channel.
    ```
    output_channel = 6
    output_height = 28
    output_width = 28
    ```
    The kernel is a window of 5x5 pixels, there is a stride of 1 and no padding.
    ```
    kernel_height = 5
    kernel_width = 5
    stride_height = 1
    stride_width = 1
    pad_height = 0
    pad_width = 0
    ```
    Perform the conversion with `python tensor_matrix_converter.py`. It results in a matrix multiplication of 784x25 A matrix by 25x6 B matrix.


1.  **Configure the data generation:**  Use `user_configuration.py` to set:
    * The matrix shape and some initialisation parameters such as the initialisation values (either random or 0).
    * The computation parameters such as the application of a ReLU activation (ground to 0 the negative value) on the result.
    * The generation parameters to define if the program print, write binaries or JSON files.

    For instance, to get the LeNet-5's first layer matrices (i.e., a 784x25 matrix multiplied by a 25x6 matrix), initialised with random value, you must define the following parameters:
    ```
    isInitRandom = True
    A_row = 784
    A_col = 25
    B_col = 6
    ```
    The VTA architecture takes 16 element vectors in input and the matrices are expected to be square, thus:
    ```
    block_size = 16
    isSquare = True
    ```
    The matrices are going to be padded such that A becomes 784x32 and B becomes 32x16. The multiplication is followed by a ReLU activation.
    ```
    useReLU = True
    ```
    Then, we want to generate a JSON file but we do not want binary data:
    ```
    doWriteBinaryFile = False
    doWriteJSON = True
    ```

2.  **Run the main_matrix_generator.py:**  Run `python main_matrix_generator.py user_configuration` in a terminal to generate the data.
    To test example, such as `data_lenet5_conv1.py`, the terminal command is:
    ```
    python main_matrix_generator.py examples.data_lenet5_conv1
    ```

An important remark is that the VTA uses the transposed of the matrix B for its computation.