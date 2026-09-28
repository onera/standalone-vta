# IMPORT PACKAGES
# ---------------
import os
import sys

import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_project_root import *
import utils.tensor_matrix_converter as TM
from utils.conv_layout import (
    direct_conv_geometry,
    direct_conv_supported,
    direct_conv_work_ratio,
)

import nn_compiler.shape_data.shape_data as SD



###############################################


# MAIN FUNCTION
# -------------
def node_conv(node, param={}, node_mapping={}, node_info={}, filename='', 
              inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
              doExpandBiasAtCompilation=False, directConv=False,
              directConvMaxWork=1.0, block_size=16,
              inp_buffer_size=None, wgt_buffer_size=None,
              acc_buffer_size=None, uop_buffer_size=None,
              producersFlat=True, aliasableProducers=frozenset(),
              foldInpZp=False, debug=False):
    # Reset the vta_ir
    vta_ir = {}

    # ---
    # PARSE METADATA
    # --------------

    # Get the metadata
    # ---
    op_type = node['op_type']
    inp_list = node['inputs']
    out_list = node['outputs']
    if (op_type != 'MatMul'):
        attributes_dict = node['attributes']

    # Reset the node data
    # ---
    inp_tensor_shape = []
    inp_matrix_shape = []
    wgt_tensor_shape = []
    wgt_matrix_shape = []
    isBias = False
    out_tensor_shape = []
    out_matrix_shape = []

    # For Quantisation
    A_scale = 1.
    A_zp = 0
    B_scale = 1.
    B_zp = 0
    C_scale = 1.
    C_zp = 0


    # Get the output tensors
    # ---
    # A single output is expected
    if ( len(out_list) != 1 ):
        raise Exception(f"ERROR (in {filename}): There are {len(out_list)} dimensions when only 1 is expected! \n")

    out_shape = out_list[0]['shape']

    # If MatMul, the shape must be expanded
    if (op_type == 'MatMul'):
        if ( len(out_shape) != 2 ):
            raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_shape)} dimensions when 2 are expected)! \n")
        out_tensor_shape = (out_shape[0], out_shape[1], 1, 1) 

    else: # 4 dimensions tensors
        if ( len(out_shape) != 4 ):
            raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_shape)} dimensions when 4 are expected)! \n")
        out_tensor_shape = out_shape # NCHW


    # Get the input tensors
    # ---
    # Count the nodes
    isInpGet = -1
    isWgtGet = -1

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get A
        if (inp_name in node_mapping):
            if (op_type == 'MatMul'):
                # Check there are 2 dimensions
                if ( len(inp_shape) != 2 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 2 are expected)! \n")
                # Get the shape
                if (isInpGet < 0):
                    isInpGet = j
                    inp_tensor_shape = (inp_shape[0], inp_shape[1], 1, 1)
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")
            else:
                # Check there are 4 dimensions
                if ( len(inp_shape) != 4 ):
                    raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
                # Get the shape
                if (isInpGet < 0):
                    isInpGet = j
                    inp_tensor_shape = inp_shape # NCHW
                else:
                    raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")

        
        # Get B or X
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == isInpGet+1): # INP SCALE
                    A_scale = param[inp_name]
                elif (j == isInpGet+2): # INP ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == isWgtGet+1): # WGT SCALE
                    B_scale = param[inp_name]
                elif (j == isWgtGet+2): # WGT ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]

            # X (bias)
            elif ( (len(inp_shape) == 1) and (isBias == False) ):
                isBias = True
                acc_tensor = param[inp_name].astype(acc_dtype)

            else: # B (weight)
                if (isWgtGet >= 0):
                    raise Exception(f"ERROR (in {filename}): Multiple weight tensors in the node! \n")

                elif (op_type == 'MatMul'):
                    # Check there are 2 dimensions
                    if ( len(inp_shape) != 2 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 2 are expected)! \n")
                    wgt_tensor_shape = (inp_shape[0], inp_shape[1], 1, 1)
                    wgt_tensor = param[inp_name].astype(wgt_dtype)
                else:
                    # Check there are 4 dimensions
                    if ( len(inp_shape) != 4 ):
                        raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
                    wgt_tensor_shape = inp_shape # NCHW
                    wgt_tensor = param[inp_name].astype(wgt_dtype)
                isWgtGet = j
        
        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")


    # Get the attributes
    # ---
    nc = inp_tensor_shape[1]
    nh = inp_tensor_shape[2]
    nw = inp_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    fh = wgt_tensor_shape[2]
    fw = wgt_tensor_shape[3]
    if (op_type != 'MatMul'):
        # Check consistency
        if (fh != attributes_dict['kernel_shape'][0] or fw != attributes_dict['kernel_shape'][1]):
            raise Exception(f"ERROR (in {filename}): Kernel size not consistent! \n")

    if (op_type != 'MatMul'):
        sh = attributes_dict['strides'][0]
        sw = attributes_dict['strides'][1]

        # attributes_dict['pads'] = [TOP, LEFT, BOTTOM, RIGHT]
        if ('pads' in attributes_dict):
            ph = (attributes_dict['pads'][0], attributes_dict['pads'][2])
            pw = (attributes_dict['pads'][1], attributes_dict['pads'][3])
        elif ('auto_pad' in attributes_dict):
            if ( attributes_dict['auto_pad'].startswith("SAME") and sh == 1 and sw == 1):
                phtotal = fh - 1
                pwtotal = fw - 1
                ph = (phtotal//2, phtotal//2)
                pw = (pwtotal//2, pwtotal//2)
        else:
            ph = (0, 0)
            pw = (0, 0)

    else:
        sh = 1
        sw = 1
        ph = (0, 0)
        pw = (0, 0)

    
    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    inp_matrix_shape, wgt_matrix_shape, out_matrix_shape = \
        TM.im2row_matrix_dimension(nc=nc, nh=nh, nw=nw,
                                   mc=mc, mh=mh, mw=mw,
                                   fh=fh, fw=fw,
                                   sh=sh, sw=sw,
                                   ph=ph, pw=pw,
                                   debug=False)

    Ah = inp_matrix_shape[0] #mh*mw
    Aw_Bh = inp_matrix_shape[1] #nc*fh*fw
    Bw = wgt_matrix_shape[1] #mc


    # Transform tensor in matrix
    # ---
    # WGT
    if (B_zp != 0):
        wgt_tensor = wgt_tensor - B_zp
    wgt_matrix = SD.ker2col(wgt_tensor, dtype=wgt_dtype)

    # ---
    # DIRECT CONVOLUTION
    # ------------------
    # Lower onto the GEMM loop nest instead of a GEMM over a CPU-built im2row
    # matrix, when that does not cost more GEMM work than im2row does. The
    # ratio is 1.0 whenever the input channel count is a multiple of the block
    # and grows as the channels get sparser, so this declines the first layer
    # of an image model (C=1 or 3) and takes the rest of the network.
    if directConv and op_type != 'MatMul':
        work = direct_conv_work_ratio(nc, fh, fw, block_size)
        # Activations stay block-tiled between layers; a direct convolution
        # reads and writes flat, so it is bracketed by two layout conversions.
        # That is two passes over the activation where the im2row it replaces
        # writes kh*kw times as much - a clear win for a real kernel, and a
        # loss for 1x1, whose im2row is already just a copy. So decline 1x1
        # rather than make it slower.
        if fh * fw <= 1:
            if debug:
                print(f"[direct-conv] {filename}: declined - 1x1, whose im2row "
                      f"is already a single pass")
            directConv = False
        # A layer fed by the network input reads raw HWC bytes delivered at
        # run time, not a block-tiled activation, so what it needs is
        # format_input - there is no flat equivalent, and a relayout would have
        # no producer buffer to point at. The runner also requires exactly one
        # FORMAT_INPUT step to know where to put the incoming image.
        if "image" in node_info.get("input_nodes", []):
            if debug:
                print(f"[direct-conv] {filename}: declined - reads the network "
                      f"input, which arrives as raw HWC and needs format_input")
            directConv = False
        # Both halves of the compiler have to reach the same verdict: if this
        # emits a CONV section vta_compiler cannot lower, the build fails late
        # with a geometry error instead of quietly using im2row. So ask the
        # same direct_conv_supported() the lowering will ask.
        geom = direct_conv_geometry(nc, nh, nw, mc, fh, fw, sh, sw,
                                    (ph[0], pw[0], ph[1], pw[1]), block_size)
        fits, why = direct_conv_supported(
            geom, fh, fw, sh, sw, nh, nw,
            inp_buffer_size=inp_buffer_size, wgt_buffer_size=wgt_buffer_size,
            acc_buffer_size=acc_buffer_size, uop_buffer_size=uop_buffer_size)
        if debug and not fits:
            print(f"[direct-conv] {filename}: declined - {why}")
        if directConv and fits and work <= directConvMaxWork:
            return _direct_conv_ir(
                filename=filename, nc=nc, nh=nh, nw=nw, mc=mc,
                fh=fh, fw=fw, sh=sh, sw=sw, ph=ph, pw=pw,
                wgt_tensor=wgt_tensor, acc_tensor=acc_tensor, isBias=isBias,
                inp_tensor_shape=inp_tensor_shape,
                out_tensor_shape=out_tensor_shape,
                wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, block_size=block_size,
                A_zp=A_zp, A_scale=A_scale, B_zp=B_zp, B_scale=B_scale,
                C_zp=C_zp, C_scale=C_scale, node_info=node_info, work=work)

    # Fold the input zero point into the bias, so INP carries raw activations.
    # After the direct-conv dispatch: _direct_conv_ir folds on its own terms.
    foldedA = False
    if foldInpZp:
        acc_tensor, isBias, foldedA = _fold_input_zero_point(
            acc_tensor, isBias, wgt_tensor, mc, A_zp, acc_dtype)

    # BIAS
    acc_matrix = []
    if (isBias == True):
        if (doExpandBiasAtCompilation == False):
            acc_matrix = SD.expand_bias(acc_tensor, 1)
        else:
            acc_matrix = SD.expand_bias(acc_tensor, Ah)
    else:
        if (doExpandBiasAtCompilation == False):
            acc_matrix = np.zeros((1, Bw), dtype=acc_dtype)
        else:
            acc_matrix = np.zeros((Ah, Bw), dtype=acc_dtype)

    # ---
    # WRITE VTA IR
    # ------------
    if (doExpandBiasAtCompilation == False):
        X_ir = [1, Bw, "../compiler_output/"+filename+"accumulator_1x"+str(Bw)+".bin"]
    else:
        X_ir = [Ah, Bw, "../compiler_output/"+filename+"accumulator_"+str(Ah)+"x"+str(Bw)+".bin"]

    alias_of = _alias_producer(node_info, aliasableProducers, fh, fw, sh, sw,
                               ph, pw, foldedA, A_zp, filename, inp_dtype, debug)

    # Define the VTA IR
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw_Bh, "input"],
            "B": [Aw_Bh, Bw, "../compiler_output/"+filename+"weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin"],
            "X": X_ir,
            "C": [Ah, Bw, "output"]
        },
        "LOAD": {
            "INP": ["A"],
            "WGT": ["B"],
            "ACC": ["X"]
        },
        "GEMM": ["C", "A", "B"],
        "STORE": {
            "C": ["C"]
        },
        "STRATEGY": 2
    }
    if alias_of is not None:
        # Consumed by main_vta_compiler: address the loads at this producer's
        # OUT instead of at this layer's own INP region.
        vta_ir["ALIAS_INP"] = alias_of


    # ---
    # WRITE BINARIES
    # --------------
    output_dir = compiler_output_setup()
    # WGT
    file_wgt_path = filepath_definition(output_dir, filename+"weight_"+str(Aw_Bh)+"x"+str(Bw)+".bin")
    # ACC
    if (doExpandBiasAtCompilation == False):
        file_acc_path = filepath_definition(output_dir, filename+"accumulator_1x"+str(Bw)+".bin")
    else:
        file_acc_path = filepath_definition(output_dir, filename+"accumulator_"+str(Ah)+"x"+str(Bw)+".bin")

    # WRITE
    with open(file_wgt_path, 'wb') as f:
        wgt_matrix.tofile(f)
    with open(file_acc_path, 'wb') as f:
        acc_matrix.tofile(f)
    
    # # DEBUG
    # file_debug_wgt_path = filepath_definition(output_dir, "debug_weight"+filename+".bin")
    # file_debug_acc_path = filepath_definition(output_dir, "debug_acc"+filename+".bin")
    # with open(file_debug_wgt_path, 'wb') as f:
    #     wgt_tensor.tofile(f)
    # with open(file_debug_acc_path, 'wb') as f:
    #     acc_tensor.tofile(f)


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ah, Aw_Bh, Bw),
        "processor": "vta",
        "reshape": "im2row",
        # Zero when folded into the bias above; otherwise the runtime still
        # subtracts it.
        "offsetA": 0 if foldedA else A_zp,
        # The zero point still has to reach a padded position: with the offset
        # folded away, a pad stands for a raw activation equal to it.
        "padValueA": int(A_zp) if foldedA else 0,
        "scaleA": A_scale,
        "offsetB": B_zp,
        "scaleB": B_scale,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "offsetC": C_zp,
        "scaleC": C_scale,
        "rescaling": (A_scale * B_scale)/C_scale
    })

    return vta_ir, node_info



###############################################


# DIRECT CONVOLUTION IR
# ---------------------
def _direct_conv_ir(filename, nc, nh, nw, mc, fh, fw, sh, sw, ph, pw,
                    wgt_tensor, acc_tensor, isBias,
                    inp_tensor_shape, out_tensor_shape,
                    wgt_dtype, acc_dtype, block_size,
                    A_zp, A_scale, B_zp, B_scale, C_zp, C_scale,
                    node_info, work):
    """Emit a CONV section instead of the im2row GEMM triple.

    The two lowerings differ in what the VTA is handed, so the buffers differ
    too: weights are packed OIHWio rather than ker2col, the bias is always
    expanded to one tensor per output position (the GEMM accumulates straight
    onto ACC, so there is no separate broadcast step), and the activations stay
    in the flat spatial layout the previous layer already wrote.

    node_info["reshape"] = "direct" is what tells the runtime there is no CPU
    pass between the producer and this layer at all.
    """
    oH = (nh + ph[0] + ph[1] - fh) // sh + 1
    oW = (nw + pw[0] + pw[1] - fw) // sw + 1
    ic_pad = ((nc + block_size - 1) // block_size) * block_size
    oc_pad = ((mc + block_size - 1) // block_size) * block_size

    # WGT: OIHWio, flattened to a 2D (blocks*block, block) matrix on disk
    if B_zp != 0:
        wgt_tensor = wgt_tensor - B_zp
    wgt_blocks = SD.ker2oihwio(wgt_tensor, block_size=block_size, dtype=wgt_dtype)
    wgt_matrix = wgt_blocks.reshape(-1, block_size)

    # ACC: the bias at every output position, with the input zero point folded
    # in per position.
    acc_matrix, isBias, foldedA = _direct_conv_acc(
        acc_tensor, isBias, wgt_tensor, mc, oc_pad, A_zp, acc_dtype,
        oH, oW, fh, fw, sh, sw, ph, pw, nh, nw)

    wgt_name = filename + "weight_" + str(wgt_matrix.shape[0]) + "x" + \
        str(wgt_matrix.shape[1]) + ".bin"
    acc_name = filename + "accumulator_" + str(oH * oW) + "x" + str(oc_pad) + ".bin"

    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [nh * nw, ic_pad, "input"],
            "B": [wgt_matrix.shape[0], wgt_matrix.shape[1],
                  "../compiler_output/" + wgt_name],
            "X": [oH * oW, oc_pad, "../compiler_output/" + acc_name],
            "C": [oH * oW, oc_pad, "output"],
        },
        "LOAD": {"INP": ["A"], "WGT": ["B"], "ACC": ["X"]},
        "CONV": {
            "output": "C", "input": "A", "weight": "B", "acc": "X",
            "in_shape": [nc, nh, nw],
            "out_channels": mc,
            "kernel": [fh, fw],
            "stride": [sh, sw],
            "pad": [ph[0], pw[0], ph[1], pw[1]],
        },
        "STORE": {"C": ["C"]},
    }

    output_dir = compiler_output_setup()
    with open(filepath_definition(output_dir, wgt_name), "wb") as f:
        wgt_matrix.tofile(f)
    with open(filepath_definition(output_dir, acc_name), "wb") as f:
        acc_matrix.tofile(f)

    node_info.update({
        "matrix_shape": (oH * oW, ic_pad, oc_pad),
        "processor": "vta",
        "reshape": "direct",
        # Zero when folded into the accumulator above, which leaves the
        # relayout feeding this layer with nothing to do but move bytes.
        "offsetA": 0 if foldedA else A_zp,
        # Always zero: nothing on this path fills a pad. The accelerator's DMA
        # zero-fills it, and _direct_conv_acc corrects for that per position.
        "padValueA": 0,
        "scaleA": A_scale,
        "offsetB": B_zp,
        "scaleB": B_scale,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "offsetC": C_zp,
        "scaleC": C_scale,
        "rescaling": (A_scale * B_scale) / C_scale,
        "direct_conv_work": work,
    })

    return vta_ir, node_info


###############################################


# INPUT ZERO POINT
# ----------------
def _alias_producer(node_info, aliasableProducers, fh, fw, sh, sw, ph, pw,
                    foldedA, A_zp, filename, inp_dtype=np.int8, debug=False):
    """The producer whose OUT this layer's INP can be addressed at, or None.

    Once the input zero point is folded away, a 1x1 stride-1 unpadded layer's
    im2row matrix is its producer's block-tiled output activation, so the
    im2row is a plain copy. The producer must be a VTA layer (aliasableProducers)
    and not the network input, which arrives as raw HWC.

    INP must be int8: the producer's OUT is read in place after its rescale to
    int8, and a wider INP (e.g. LOG_INP_WIDTH=5) would read those bytes as
    wider elements.
    """
    producers = node_info.get("input_nodes", [])
    if np.dtype(inp_dtype) != np.int8:
        if debug and aliasableProducers:
            print(f"[alias] {filename}: declined - INP is {np.dtype(inp_dtype).name}, "
                  f"aliasing needs int8")
        return None
    ok = (fh == 1 and fw == 1 and sh == 1 and sw == 1
          and not any(ph) and not any(pw)
          and (foldedA or int(A_zp) == 0)
          and len(producers) == 1
          and producers[0] != "image"
          and producers[0] in aliasableProducers)
    if ok and debug:
        print(f"[alias] {filename}: INP -> {producers[0]} OUT (1x1 s1 unpadded)")
    return producers[0] if ok else None


def _fold_input_zero_point(acc_tensor, isBias, wgt_tensor, out_channels,
                           A_zp, acc_dtype):
    """Move the input zero point out of the activations and into the bias.

    The GEMM computes sum_c W.(x - z). Expanding it,

        sum_c W.(x - z) = sum_c W.x  -  z * sum_c W

    so subtracting z from every activation is equivalent to leaving the
    activations alone and adding the per-output-channel constant -z*sum_c W to
    the bias. That constant is known at compile time.

    With an int8 INP buffer this is also what makes the input fit: x - z needs
    nine bits when z is -128, while the raw activation fits exactly.

    Spatial padding follows along. A padded position stands for "0 in the
    offset-adjusted space", i.e. a raw activation equal to the zero point; once
    the activations are raw those positions have to hold z rather than 0, which
    is what padValueA tells the CPU's im2row to fill with. The direct
    convolution cannot be told that - VTA's LOAD pad fields zero-fill and take
    no value - so it does not use this helper at all; see [[_direct_conv_acc]],
    which corrects for the zero fill per output position instead.

    Returns (acc_tensor, isBias, folded); when folded the caller emits
    offsetA = 0 and padValueA = A_zp, otherwise offsetA = A_zp and
    padValueA = 0.
    """
    if A_zp == 0:
        return acc_tensor, isBias, False

    # Sum over (in-channel, kh, kw) per output channel, in int64: the weights
    # are already zero-point-adjusted, and the sum can be large. A_zp arrives
    # as a numpy int8, and -np.int8(-128) is still -128 - which silently flips
    # the sign of the whole correction for the commonest zero point there is,
    # so widen it before negating.
    correction = -int(A_zp) * wgt_tensor.reshape(out_channels, -1).sum(
        axis=1, dtype=np.int64)

    if isBias:
        return (acc_tensor.astype(np.int64) + correction).astype(acc_dtype), True, True
    return correction.astype(acc_dtype), True, True


###############################################


# DIRECT CONVOLUTION ACCUMULATOR
# ------------------------------
def _direct_conv_acc(acc_tensor, isBias, wgt_tensor, out_channels, oc_pad,
                     A_zp, acc_dtype, oH, oW, fh, fw, sh, sw, ph, pw, nh, nw):
    """Build the direct convolution's accumulator, folding the input zero point
    in per output position.

    [[_fold_input_zero_point]] cannot serve this lowering. It assumes every tap
    reads an activation the CPU wrote, so one constant -z*sum W per output
    channel corrects the whole tensor. Here the taps that fall outside the
    image are written by VTA's LOAD, whose pad fields zero-fill and take no
    value - they read 0 where a raw activation of z is meant. How many taps
    that is depends on where the output position sits, so the correction is not
    one constant but a value per (position, channel).

    Writing it out, for output position p the accelerator produces

        sum_{t in bounds} W.x_t  +  sum_{t padded} W.0

    while the layer means sum over every tap of W.(x_t - z) with x_t = z on the
    padded ones. The difference collapses to a sum over the in-bounds taps
    only, so

        ACC[p, oc] = bias[oc] - z * sum_{t in bounds at p} sum_c W[oc, c, t]

    which for an unpadded layer has every tap in bounds and reduces exactly to
    the flat -z*sum W that _fold_input_zero_point applies.

    This costs nothing at run time: the lowering already expands the bias to
    one tensor per output position, so these are different numbers in a buffer
    that was already this size.

    Returns (acc_matrix, isBias, folded); when folded the caller emits
    offsetA = 0.
    """
    acc_matrix = np.zeros((oH * oW, oc_pad), dtype=acc_dtype)
    if isBias:
        for oc in range(out_channels):
            acc_matrix[:, oc] = acc_tensor[oc]
    if A_zp == 0:
        return acc_matrix, isBias, False

    # Sum over the input channels first: what a tap contributes is the same for
    # every position that reads it. int64 throughout - the weights are already
    # zero-point-adjusted and these sums get large.
    tap = wgt_tensor.astype(np.int64).sum(axis=1)          # (out_channels, fh, fw)

    # Which taps land inside the image, per output row and per output column.
    # Separable, so this is two small 2D masks rather than one 4D one.
    iy = np.arange(oH)[:, None] * sh + np.arange(fh)[None, :] - ph[0]
    ix = np.arange(oW)[:, None] * sw + np.arange(fw)[None, :] - pw[0]
    row_ok = ((iy >= 0) & (iy < nh)).astype(np.int64)      # (oH, fh)
    col_ok = ((ix >= 0) & (ix < nw)).astype(np.int64)      # (oW, fw)

    # -z * sum of the in-bounds taps. A_zp arrives as a numpy int8, and
    # -np.int8(-128) is still -128, so widen it before negating.
    inbounds = np.einsum("yk,xl,okl->yxo", row_ok, col_ok, tap)
    acc_matrix[:, :out_channels] += (
        -int(A_zp) * inbounds.reshape(oH * oW, out_channels)).astype(acc_dtype)
    return acc_matrix, True, True


###############################################


# MUL CONSTANT
# ------------
def node_mulconstant(node, param={}, node_mapping={}, node_info={}, filename='', 
                     inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
                     aliasableProducers=frozenset(), foldInpZp=False,
                     debug=False):
    # Reset the vta_ir
    vta_ir = {}

    # ---
    # PARSE METADATA
    # --------------

    # Get the metadata
    # ---
    op_type = node['op_type']
    inp_list = node['inputs']
    out_list = node['outputs']
    attributes_dict = node['attributes']

    # Reset the node data
    # ---
    inp_tensor_shape = []
    inp_matrix_shape = []
    out_tensor_shape = []
    out_matrix_shape = []
    scalar = 0

    # For Quantisation
    A_scale = 1.
    A_zp = 0
    B_scale = 1.
    B_zp = 0
    C_scale = 1.
    C_zp = 0


    # Get the output tensors
    # ---
    # A single output is expected
    if ( len(out_list) != 1 ):
        raise Exception(f"ERROR (in {filename}): There are {len(out_list)} dimensions when only 1 is expected! \n")

    out_tensor_shape = out_list[0]['shape']

    # The output must have 4 dimensions
    if ( len(out_tensor_shape) != 4 ):
        raise Exception(f"ERROR (in {filename}): Wrong output shape ({len(out_tensor_shape)} dimensions when 4 are expected)! \n")


    # Get the input tensors
    # ---
    # Count the nodes
    isInpGet = -1
    isScalarGet = -1

    for j, inp in enumerate(inp_list):
        # Get the name
        inp_name = inp['name']
        inp_shape = inp['shape']

        # Get A
        if (inp_name in node_mapping):
            # Check there are 4 dimensions
            if ( len(inp_shape) != 4 ):
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp_shape)} dimensions when 4 are expected)! \n")
            # Get the shape
            if (isInpGet < 0):
                isInpGet = j
                inp_tensor_shape = inp_shape # NCHW
            else:
                raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name})! \n")
            
            # Check consistency between input and output
            if (inp_tensor_shape != out_tensor_shape):
                raise Exception(f"ERROR (in {filename}): MulConstant should not modify the shape, but inp_tensor_shape={inp_tensor_shape} and out_tensor_shape={out_tensor_shape}! \n")


        # Get scalar
        elif (inp_name in param):
            # Empty field = metadata
            if (len(inp_shape) == 0):
                if (j == isScalarGet+1): # WGT SCALE
                    B_scale = param[inp_name]
                elif (j == isScalarGet+2): # WGT ZERO POINT
                    B_zp = param[inp_name]
                
                elif (j == isInpGet+1): # INP SCALE
                    A_scale = param[inp_name]
                elif (j == isInpGet+2): # INP ZERO POINT
                    A_zp = param[inp_name]
                
                elif (j == 6): # OUT SCALE
                    C_scale = param[inp_name]
                elif (j == 7): # OUT ZERO POINT
                    C_zp = param[inp_name]
            
            # Scalar
            elif (len(inp['shape']) >= 1 and isScalarGet < 0):
                for shape in inp['shape']:
                    if (shape != 1):
                        raise Exception(f"ERROR (in {filename}): Wrong shape ({shape} when 1 is expected)! \n")
                isScalarGet = j
                scalar = np.asarray(param[inp['name']]).reshape(-1)[0]

            # Error on the shape
            else:
                raise Exception(f"ERROR (in {filename}): Wrong input shape ({len(inp['shape'])} dimensions when 1 is expected)! \n")


        # Else problem 
        else:
            raise Exception(f"ERROR (in {filename}): Unexpected input ({inp_name}) which does not come from another node nor parameters! \n")


    # Get the attributes
    # ---
    nc = inp_tensor_shape[1]
    nh = inp_tensor_shape[2]
    nw = inp_tensor_shape[3]

    mc = out_tensor_shape[1]
    mh = out_tensor_shape[2]
    mw = out_tensor_shape[3]

    fh = 1
    fw = 1

    if ('strides' in attributes_dict):
        sh = attributes_dict['strides'][0]
        sw = attributes_dict['strides'][1]
    else:
        sh = 1
        sw = 1

    # attributes_dict['pads'] = [TOP, LEFT, BOTTOM, RIGHT]
    if ('pads' in attributes_dict):
        ph = (attributes_dict['pads'][0], attributes_dict['pads'][2])
        pw = (attributes_dict['pads'][1], attributes_dict['pads'][3])
    else:
        ph = (0, 0)
        pw = (0, 0)

    
    # ---
    # DEFINE MATRICES
    # ---------------

    # Define the matrix dimensions
    # ---
    inp_matrix_shape, wgt_matrix_shape, out_matrix_shape = \
        TM.im2row_matrix_dimension(nc=nc, nh=nh, nw=nw,
                                   mc=mc, mh=mh, mw=mw,
                                   fh=fh, fw=fw,
                                   sh=sh, sw=sw,
                                   ph=ph, pw=pw,
                                   debug=False)

    Ah = inp_matrix_shape[0] #mh*mw
    Aw = inp_matrix_shape[1] #nc*fh*fw


    # Transform tensor in matrix
    # ---
    # WGT
    if (B_zp != 0):
        scalar = scalar - B_zp

    # Fold the input zero point into a bias row: with a scalar*I weight the
    # whole correction is the constant -A_zp*scalar.
    foldedA = foldInpZp and (A_zp != 0)
    if foldedA:
        acc_name = filename + "accumulator_1x" + str(Aw) + ".bin"
        acc_matrix = np.full((1, Aw), -int(A_zp) * int(scalar), dtype=acc_dtype)
        with open(filepath_definition(compiler_output_setup(), acc_name),
                  "wb") as f:
            acc_matrix.tofile(f)


    # ---
    # WRITE VTA IR
    # ------------
    # Define the VTA IR
    vta_ir = {
        "NAME": filename,
        "MATRICES": {
            "A": [Ah, Aw, "input"],
            "C": [Ah, Aw, "output"]
        },
        "LOAD": {
            "INP": ["A"]
        },
        "GEMM": ["C", "A", int( scalar )],
        "STORE": {
            "C": ["C"]
        }
    }
    if foldedA:
        vta_ir["MATRICES"]["X"] = [1, Aw, "../compiler_output/" + acc_name]
        vta_ir["LOAD"]["ACC"] = ["X"]

    alias_of = _alias_producer(node_info, aliasableProducers, fh, fw, sh, sw,
                               ph, pw, foldedA, A_zp, filename, inp_dtype, debug)
    if alias_of is not None:
        vta_ir["ALIAS_INP"] = alias_of


    # ---
    # RETURN
    # ------
    node_info.update({
        "matrix_shape": (Ah, Aw),
        "processor": "vta",
        "reshape": "im2row",
        # Folded into the bias above, so the runtime subtracts nothing.
        "offsetA": 0 if foldedA else A_zp,
        "padValueA": int(A_zp) if foldedA else 0,
        "scaleA": A_scale,
        "offsetB": B_zp,
        "scaleB": B_scale,
        "input_shape": inp_tensor_shape,
        "kernel": (fh, fw),
        "stride": (sh, sw),
        "padding": (ph[0], pw[0], ph[1], pw[1]),
        "output_shape": out_tensor_shape,
        "offsetC": C_zp,
        "scaleC": C_scale,
        "rescaling": (A_scale * B_scale)/C_scale
    })

    return vta_ir, node_info

