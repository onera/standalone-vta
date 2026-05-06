import numpy as np
import os

def format_c_array(name, data, storage_dtype_str, chunk_size):
    """
    Formats a numpy array into a C++ static const array using decimal representation.
    Aligns the values neatly in columns for readability.
    """
    c_type = f"std::{storage_dtype_str}_t"
    res = f"static const {c_type} {name}[] = {{\n"
    
    flat_data = data.flatten()
    rows = []

    max_len = max(len(str(int(val))) for val in flat_data)
    
    for i in range(0, len(flat_data), chunk_size):
        chunk = flat_data[i:i+chunk_size]
        
        row_str = ", ".join([f"{int(val):>{max_len}}" for val in chunk])
        rows.append("    " + row_str)
    
    res += ",\n".join(rows)
    res += "\n};\n"
    return res

def generate_vta_test_header(
    n=16,
    input_dtype=np.int8,
    weight_dtype=np.int8,
    inp_storage_dtype="int32",
    wgt_storage_dtype="int32",
    acc_storage_dtype="int32",
    output_dtype=np.int32,
    min_val=-128,
    max_val=127,
    filename="init_dram.h"
    ):

    # Determine absolute path to avoid writing errors depending on CWD
    script_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(script_dir, filename)

    # 1. Data generation (algebraic values)
    # Use max_val + 1 because high is exclusive in randint
    inp = np.random.randint(min_val, max_val + 1, size=(n, n), dtype=input_dtype)
    wgt = np.random.randint(min_val, max_val + 1, size=(n, n), dtype=weight_dtype)

    # 2. Golden Model computation
    acc_golden = np.matmul(inp.astype(output_dtype), np.transpose(wgt.astype(output_dtype)))
    acc_zeros = np.zeros((n, n), dtype=output_dtype)

    # 3. Static content (Instructions remain in Hex for bitfield readability)
    vta_header = """#include <cstddef>
#include <cstdint>
#include <cstring>

#include "vta.h"

static const VTAInsn insn[] = {
    {{0x00000000u, 0x00000050u, 0x00010001u, 0x00000001u}},
    {{0x002000A2u, 0x00200008u, 0x00000810u, 0x00000000u}},
    {{0x00000110u, 0x00000001u, 0x00100001u, 0x00000010u}},
    {{0x200000C0u, 0x00000000u, 0x00010001u, 0x00000001u}},
    {{0x00000188u, 0x00000003u, 0x00100001u, 0x00000010u}},
    {{0x04000000u, 0x00000050u, 0x00010001u, 0x00000001u}},
    {{0x00200062u, 0x00200008u, 0x00000800u, 0x00000002u}},
    {{0x00000229u, 0x00000004u, 0x00100001u, 0x00000010u}},
    {{0x00000150u, 0x00000000u, 0x00000000u, 0x00000000u}},
    {{0x00000018u, 0x00000000u, 0x00000000u, 0x00000000u}},
    {{0x00000003u, 0x00000000u, 0x00000000u, 0x00000000u}}};
    
static const VTAInsn insn_finish[] = {
    {{0x00000003u, 0x00000000u, 0x00000000u, 0x00000000u}}};
    
static const std::uint32_t uop[] = {0x00000000u, 0x00000000u};
"""

    # 4. Robust writing
    try:
        with open(full_path, "w") as f:
            f.write(vta_header)
            f.write("\n")
            
            # Pass the string representation of the dtype for proper C++ mapping
            f.write(format_c_array("input", inp, inp_storage_dtype, n))
            f.write("\n")
            
            f.write(format_c_array("wgt", wgt, wgt_storage_dtype, n))
            f.write("\n")
            
            f.write(format_c_array("acc", acc_zeros, acc_storage_dtype, n))
            f.write("\n")
            
            f.write(format_c_array("expected_out", acc_golden, acc_storage_dtype, n))
            f.write("\n")
            
            f.flush()
            
        print(f"Success: File '{full_path}' generated.")
        print(f"File size: {os.path.getsize(full_path)} bytes.")
        
    except Exception as e:
        print(f"Error during writing: {e}")

if __name__ == "__main__":
    import argparse
    
    # We only need the valid choices for argparse validation now
    VALID_TYPES = ["int8", "int16", "int32", "uint8", "uint16", "uint32"]

    parser = argparse.ArgumentParser(description="VTA test data generator.")
    parser.add_argument("-n", type=int, default=16, help="Matrix size (n x n).")
    parser.add_argument("--inp-storage", type=str, default="int32", choices=VALID_TYPES, 
                        help="Storage type for input.")
    parser.add_argument("--wgt-storage", type=str, default="int32", choices=VALID_TYPES, 
                        help="Storage type for weight.")
    parser.add_argument("--acc-storage", type=str, default="int32", choices=VALID_TYPES, 
                        help="Storage type for accumulator/output.")
    parser.add_argument("--filename", type=str, default="init_dram.h", help="Output filename.")
    
    args = parser.parse_args()
    
    generate_vta_test_header(
        n=args.n,
        inp_storage_dtype=args.inp_storage,
        wgt_storage_dtype=args.wgt_storage,
        acc_storage_dtype=args.acc_storage,
        filename=args.filename
    )
