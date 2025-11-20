# IMPORT PACKAGES
# ---------------

# IM2ROW_MATRIX_DIMENSION
# -----------------------
def output_dimension(inp_dim=(1, 1), # (input_height, input_width)
                     wgt_dim=(1, 1), # (kernel_height, kernel_width)
                     stride=(1, 1), # (stride_height, stride_width)
                     padding=((0,0), (0,0))): # (pad_height, pad_width)
    """Compute the output tensor dimension with: input and weight dimension, stride and padding."""
    # Height
    mh = int( (inp_dim[0] + padding[0][0]+padding[0][1] - wgt_dim[0]) / stride[0] + 1 )
    # Width
    mw = int( (inp_dim[1] + padding[1][0]+padding[1][1] - wgt_dim[1]) / stride[1] + 1 )

    # Return the result in tuple
    return (mh, mw)


def im2row_matrix_dimension(nc=1, nh=1, nw=1,
                            mc=1, mh=1, mw=1,
                            fh=1, fw=1,
                            sh=1, sw=1,
                            ph=(0,0), pw=(0,0),
                            debug=False):
    """Compute the dimension of the input and weight matrices from the dimension of the tensors.
    Dimension names:
        nc=input_channel, nh=input_height, nw=input_width,
        mc=output_channel, mh=output_height, mw=output_width,
        fh=kernel_height, fw=kernel_width,
        sh=stride_height, sw=stride_width,
        ph= pad_height, pw=pad_width
    """
    # Get output dimension
    expected_out = output_dimension(inp_dim=(nh, nw), wgt_dim=(fh, fw), stride=(sh, sw), padding=(ph, pw))
    assert expected_out[0] == mh
    assert expected_out[1] == mw

    # Size of the input matrix
    inp_height = mh * mw
    inp_width = nc * fh * fw
    # Size of the weight matrix
    wgt_height = nc * fh * fw
    wgt_width = mc
    # Size of the output matrix
    out_height = mh * mw
    out_width = mc

    # Return the result
    if (debug):
        print(f"\nInput tensor: nc = {nc}, nh = {nh}, nw = {nw} \n" + \
            f"Output tensor: mc = {mc}, mh = {mh}, mw = {mw} \n" + \
            f"Kernel: fh = {fh}, fw = {fw} \n" + \
            f"Parameters: stride = ({sh}, {sw}), pad = ({ph}, {pw}) \n\n")
        
        print(f"Input matrix: height = {inp_height}, width = {inp_width} \n" + \
            f"Weight matrix: height = {wgt_height}, width = {wgt_width} \n" + \
            f"Output matrix: height = {out_height}, width = {out_width} \n\n")
    
    return (inp_height, inp_width), (wgt_height, wgt_width), (out_height, out_width)

# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == '__main__':
    # DEFINE VARIABLES
    # ----------------
    # Input tensor
    input_channel = 1
    input_height = 32
    input_width = 32

    # Output tensor
    output_channel = 6
    output_height = 28
    output_width = 28

    # Filter tensor 
    # => (number of filters = output_channel)
    # => (number of channels within filters = input_channel)
    kernel_height = 5
    kernel_width = 5

    # Computation parameters
    stride_height = 1
    stride_width = 1
    pad_height = 0
    pad_width = 0

    # EXECUTE
    # -------
    im2row_matrix_dimension(input_channel, input_height, input_width, \
                            output_channel, output_height, output_width, \
                            kernel_height, kernel_width, \
                            stride_height, stride_width, pad_height, pad_width,
                            debug=True)