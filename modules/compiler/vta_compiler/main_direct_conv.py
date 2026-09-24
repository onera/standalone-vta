# IMPORT PACKAGES
# ---------------
import ctypes
import csv
import os
import sys

import numpy as np

import dram_allocation.dram_allocation as DA
from operations_definition.direct_conv import (
    direct_conv_geometry,
    direct_conv_supported,
    direct_conv_tiles,
    direct_conv_work_ratio,
)
from operations_definition.direct_conv_layer import lower_direct_conv

# utils/ lives one level up (modules/compiler), like main_vta_compiler does it;
# the path has to be extended before those imports, not after.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.configuration as conf
from utils.find_project_root import *


###############################################


def _read_matrix(entry, dtype, what):
    """Read one IR matrix entry [rows, cols, path] as a raw array.

    The direct path takes its buffers in their final layout - flat activations,
    OIHWio weights, bias already expanded to one tensor per output position -
    so unlike data_definition there is no padding or block splitting here, and
    the file is used exactly as given.
    """
    rows, cols, path = entry[0], entry[1], entry[2]
    if not str(path).endswith(".bin"):
        return np.zeros((rows, cols), dtype=dtype)
    # Same resolution as data_definition.matrix_creation: the IR carries a
    # nominal path, the operand actually lives in $VTA_COMPILER_OUT.
    resolved = str(path)
    out = os.environ.get("VTA_COMPILER_OUT")
    if out:
        resolved = os.path.join(out, os.path.basename(resolved))
    flat = np.fromfile(resolved, dtype=dtype)
    if flat.size != rows * cols:
        raise ValueError(
            f"ERROR: {what} file '{path}' holds {flat.size} {np.dtype(dtype).name} "
            f"values but the IR declares {rows}x{cols}={rows*cols}.\n\n")
    return flat.reshape((rows, cols))


# MAIN FUNCTION - DIRECT CONVOLUTION
# ----------------------------------
def compile_direct_conv(
    vta_config_dict,
    operations_dict,
    base_address,
    dram_offset,
    dram_state_dictionary={},
    debug=True,
    summary=True,
):
    """Compile one convolution with the direct lowering.

    Bypasses data_definition / matrix_partitioning / operations_definition
    entirely: those exist to tile a GEMM over a block-tiled im2row matrix,
    and none of it applies when the convolution runs on the GEMM loop nest
    directly. Same return contract as main_vta_compiler.main().
    """
    name = operations_dict["NAME"]
    matrices_dict = operations_dict["MATRICES"]
    conv = operations_dict["CONV"]

    inp_dtype = conf.data_type(vta_config_dict["LOG_INP_WIDTH"])
    wgt_dtype = conf.data_type(vta_config_dict["LOG_WGT_WIDTH"])
    acc_dtype = conf.data_type(vta_config_dict["LOG_ACC_WIDTH"])
    out_dtype = conf.data_type(vta_config_dict["LOG_OUT_WIDTH"])
    block_size = 2 ** vta_config_dict["LOG_BLOCK"]

    inp_buffer_size = conf.buffer_size(
        vta_config_dict["LOG_INP_BUFF_SIZE"], vta_config_dict["LOG_INP_WIDTH"],
        block_size)
    wgt_buffer_size = conf.buffer_size(
        vta_config_dict["LOG_WGT_BUFF_SIZE"], vta_config_dict["LOG_WGT_WIDTH"],
        block_size * block_size)
    acc_buffer_size = conf.buffer_size(
        vta_config_dict["LOG_ACC_BUFF_SIZE"], vta_config_dict["LOG_ACC_WIDTH"],
        block_size)
    uop_buffer_size = conf.buffer_size(vta_config_dict["LOG_UOP_BUFF_SIZE"], 5, 1)

    # GEOMETRY
    # --------
    C, H, W = conv["in_shape"]
    OC = conv["out_channels"]
    kh, kw = conv["kernel"]
    sh, sw = conv.get("stride", [1, 1])
    pad = tuple(conv.get("pad", [0, 0, 0, 0]))
    g = direct_conv_geometry(C, H, W, OC, kh, kw, sh, sw, pad, block_size)

    ok, why = direct_conv_supported(
        g, kh, kw, sh, sw, H, W,
        inp_buffer_size=inp_buffer_size, wgt_buffer_size=wgt_buffer_size,
        acc_buffer_size=acc_buffer_size, uop_buffer_size=uop_buffer_size)
    if not ok:
        raise ValueError(
            f"ERROR: '{name}' cannot use the direct convolution lowering: {why}.\n"
            f"Use the im2row lowering for this layer.\n\n")

    IC_b, OC_b = g["IC_b"], g["OC_b"]
    oH, oW = g["oH"], g["oW"]

    # BUFFERS
    # -------
    A_matrix = _read_matrix(matrices_dict[conv["input"]], inp_dtype, "INP")
    B_matrix = _read_matrix(matrices_dict[conv["weight"]], wgt_dtype, "WGT")
    X_matrix = _read_matrix(matrices_dict[conv["acc"]], acc_dtype, "ACC")
    C_matrix = np.zeros((oH * oW, OC_b * block_size), dtype=out_dtype)

    # DRAM ALLOCATION
    # ---------------
    # The instructions have to carry the UOP base, so UOP is allocated before
    # the lowering runs and its size has to be known up front. Tiling emits one
    # kernel set per distinct input-window width, so derive the count from the
    # tiles rather than assuming a single set.
    inp_max = min(2048, inp_buffer_size)
    acc_max = min(2048, acc_buffer_size)
    _tiles = direct_conv_tiles(g, kh, kw, sh, sw, inp_max, acc_max)
    n_widths = len({(tw - 1) * sw + kw for _, _, _, tw in _tiles})
    n_uop = n_widths * OC_b * kh * kw * IC_b
    object_list = [
        ("INP", [A_matrix]),
        ("WGT", [B_matrix]),
        ("ACC", [X_matrix]),
        ("OUT", [C_matrix]),
        ("UOP", [None] * n_uop),
    ]
    base_addresses_list, updated_base_address = DA.dram_allocation(
        object_list, base_addr=base_address, block_size=block_size,
        inp_dtype=inp_dtype, out_dtype=out_dtype, wgt_dtype=wgt_dtype,
        acc_dtype=acc_dtype, dram_offset=dram_offset, debug=debug)

    def logical(kind):
        for entry in base_addresses_list:
            if entry["type"] == kind:
                return int(entry["logical_base_address"], 16)
        raise KeyError(kind)

    # LOWERING
    # --------
    insn_buffer, uop_buffer = lower_direct_conv(
        g, kh, kw, sh, sw, H, W,
        inp_dram_base=logical("INP"), wgt_dram_base=logical("WGT"),
        acc_dram_base=logical("ACC"), out_dram_base=logical("OUT"),
        uop_dram_base=logical("UOP"), block_size=block_size,
        inp_buffer_size=inp_buffer_size, acc_buffer_size=acc_buffer_size)

    if len(uop_buffer) != n_uop:
        raise AssertionError(
            f"ERROR: predicted {n_uop} uops for the UOP allocation but the "
            f"lowering produced {len(uop_buffer)}.\n\n")

    insn_addr, updated_base_address = DA.dram_allocation(
        [("INSN", insn_buffer)], base_addr=updated_base_address,
        block_size=block_size, inp_dtype=inp_dtype, out_dtype=out_dtype,
        wgt_dtype=wgt_dtype, acc_dtype=acc_dtype, dram_offset=dram_offset,
        debug=debug)
    base_addresses_list.append(insn_addr[0])

    # BINARISATION
    # ------------
    output_dir = compiler_output_setup()

    def write(fname, payload):
        path = filepath_definition(output_dir, fname)
        with open(path, "wb") as f:
            if isinstance(payload, np.ndarray):
                payload.tofile(f)
            else:
                for item in payload:
                    f.write(item)
        return path

    write("input" + name + ".bin", A_matrix)
    write("weight" + name + ".bin", B_matrix)
    write("accumulator" + name + ".bin", X_matrix)
    # The baremetal loader reads the *_block sibling, not the raw matrix, so a
    # direct convolution that skips it silently ships an empty ACC section and
    # the bias never reaches DRAM - fsim, which reads the raw file, stays
    # correct and hides it. Here the two are the same bytes: the direct path
    # already expands the bias into its final per-output-position layout, so
    # there is no block splitting to do.
    write("accumulator" + name + "_block.bin", X_matrix)
    # The second accumulator is a two-matrix-ALU thing a convolution never uses,
    # but fsim opens it unconditionally; write it empty rather than let every
    # run print a file-not-found.
    write("add_accumulator" + name + ".bin", np.zeros((0,), dtype=acc_dtype))
    write("add_accumulator" + name + "_block.bin", np.zeros((0,), dtype=acc_dtype))
    write("out_init.bin", C_matrix)
    write("instructions" + name + ".bin", insn_buffer)
    write("uop" + name + ".bin", uop_buffer)

    # metadata.csv is fsim's shaping contract (fsim_layer.cc): it re-reads each
    # operand and runs data_formatting() - the block-tiling - on it, and the
    # declared size is also what the DRAM allocation is sized from. The direct
    # path's activations are already flat, so they must not be re-tiled, but
    # they still need a real size (in the NN path the buffer starts empty and
    # only the declaration sizes it).
    #
    # Declaring them as (tensors x block_size) satisfies both: block-tiling a
    # matrix that is exactly block_size columns wide is the identity - one
    # column block, so the byte offset stays 16*r + c - while the element count
    # is unchanged.
    metadata = [
        {"type": "BS", "rows": block_size, "columns": block_size, "square": True},
        {"type": "A", "rows": H * W * IC_b, "columns": block_size, "square": False},
        {"type": "X", "rows": oH * oW * OC_b, "columns": block_size, "square": False},
        {"type": "Y", "rows": 0, "columns": 0, "square": True},
        {"type": "C", "rows": oH * oW * OC_b, "columns": block_size, "square": False},
    ]
    with open(filepath_definition(output_dir, "metadata" + name + ".csv"),
              "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Matrix (or Block Size)", "Nb rows", "Nb columns",
                         "Is it square?"])
        for data in metadata:
            writer.writerow([data["type"], data["rows"], data["columns"],
                             data["square"]])

    with open(filepath_definition(output_dir, "memory_addresses" + name + ".csv"),
              "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Buffer type", "Physical address (hex)",
                         "Logical address (hex)"])
        for obj_addr in base_addresses_list:
            writer.writerow([obj_addr["type"], obj_addr["physical_base_address"],
                             obj_addr["logical_base_address"]])

    # DRAM STATE (for the Chisel testbench)
    # -------------------------------------
    if dram_state_dictionary != False:
        dram_state_dictionary[name] = {}

        def hex_values(array, dtype):
            dt = np.dtype(dtype)
            n_bits = dt.itemsize * 8
            mask = (1 << n_bits) - 1
            fmt = f"{{:0{n_bits // 4}X}}"
            return [fmt.format(int(v) & mask) for v in np.asarray(array).flatten()]

        def hex_insn(insn):
            raw = ctypes.string_at(ctypes.byref(insn), ctypes.sizeof(insn))
            return raw[::-1].hex().upper()

        payloads = {
            "INP": lambda: hex_values(A_matrix, inp_dtype),
            "WGT": lambda: hex_values(B_matrix, wgt_dtype),
            "ACC": lambda: hex_values(X_matrix, acc_dtype),
            "OUT": lambda: hex_values(C_matrix, out_dtype),
            "UOP": lambda: [hex_insn(u) for u in uop_buffer],
            "INSN": lambda: [hex_insn(i) for i in insn_buffer],
        }
        for mem in base_addresses_list:
            mem_type = mem["type"]
            dram_state_dictionary[name][mem_type] = {
                "PhysicalAddr": mem["physical_base_address"].removeprefix("0x"),
                "values": payloads.get(mem_type, list)(),
            }

    # SUMMARY
    # -------
    nb_steps = 1
    nb_uop = len(uop_buffer)
    nb_insn = len(insn_buffer)
    if debug or summary:
        print(f"\nVTA COMPILER SUMMARY: {name} [direct convolution]")
        print(f"Geometry: C={C} {H}x{W} -> OC={OC} k{kh}x{kw} "
              f"s{sh},{sw} pad{pad} => {oH}x{oW}")
        print(f"GEMM work vs im2row: "
              f"{direct_conv_work_ratio(C, kh, kw, block_size):.2f}x"
              f"   tiles: {len(_tiles)}")
        print(f"The compilation of '{name}' generates: \n\t {nb_steps} steps "
              f"\n\t {nb_uop} UOPs \n\t {nb_insn} instructions")
        print(f"\n\nBinary files successfully written at: {output_dir}\n")
        print("-" * 50)

    return (updated_base_address, name, nb_steps, nb_uop, nb_insn,
            dram_state_dictionary)
