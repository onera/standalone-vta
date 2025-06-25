# IMPORT PACKAGES
# ---------------
import numpy as np


###############################################


# DRAM_allocation
# ---------------
def dram_allocation(object_list, base_addr=0x0000, block_size=16, 
                    inp_dtype=np.int8, wgt_dtype=np.int8, acc_dtype=np.int32,
                    dram_offset=0x0000, debug=True):
    # Define the page size (4KiB = 0x1000)
    page_size = 0x1000

    # Define the current dram physical address
    current_dram_addr = base_addr

    # Define the addresses list
    base_addresses = []

    # Iterate over the object
    for (obj_type, obj_value) in object_list:
        # Check the object type to define the logical divisor for logical address
        if (obj_type == "INP" or obj_type == "OUT"):
            logical_divisor = np.dtype(inp_dtype).itemsize * block_size
        elif (obj_type == "WGT"):
            logical_divisor = np.dtype(wgt_dtype).itemsize * block_size * block_size
        elif (obj_type == "ACC"):
            logical_divisor = np.dtype(acc_dtype).itemsize * block_size
        else:
            raise Exception(f"ERROR: Unknown object type ({obj_type})! \n\n")

        # Get the object address
        obj_addr, current_dram_addr = addresses_computation(obj_type, obj_value, page_size, current_dram_addr, dram_offset, logical_divisor)

        # Increment the addresses list
        base_addresses.append(obj_addr)


    # Allocate space for the UOPs (consider a single UOP)
    obj_addr, current_dram_addr = addresses_computation("UOP", [], page_size, current_dram_addr, dram_offset, 4) 
    base_addresses.append(obj_addr)


    # DEBUG
    if (debug):
        print("\n\nDRAM ALLOCATION:")
        for addr in base_addresses:
            print(addr, "\n")
        print(f"\nThe current physical dram base address is: current_dram_addr={hex(current_dram_addr)}\n")

    # Return 
    return base_addresses, current_dram_addr

# ---------------------------------------------

# ADDRESSES COMPUTATION
# ---------------------
def addresses_computation(obj_type, obj_value, page_size, current_dram_addr, dram_offset, logical_divisor):
    # Increment current_dram_addr to the next page
    page_idx = (current_dram_addr // page_size)
    current_dram_addr = (page_idx + 1) * page_size

    # Define the address of the blocks
    blocks_addresses = []
    local_addr = current_dram_addr
    i = 0
    if not (obj_value):
        alloc_size_bytes = logical_divisor
    else:
        for matrix in obj_value:
            blocks_addresses.append(
                (get_block_name(obj_type, i),
                 hex( local_addr ), # physical address
                 hex( (local_addr - dram_offset) // logical_divisor )) # Logical address
            )
            local_addr = local_addr + matrix.nbytes
            i = i + 1

        # Define the size of the allocation 
        alloc_size_bytes = sum(matrix.nbytes for matrix in obj_value) # Bytes

    # Define the object address
    obj_addr = {
        "type": obj_type,
        "physical_base_address": hex( current_dram_addr ),
        "logical_base_address": hex( (current_dram_addr - dram_offset) // logical_divisor ),
        "size": alloc_size_bytes,
        "blocks_addresses": blocks_addresses
    }

    # Update current_dram_addr
    current_dram_addr = current_dram_addr + alloc_size_bytes - 1

    # Return
    return obj_addr, current_dram_addr


# Get block name
# --------------
def get_block_name(obj_type, index):
    if (obj_type == "INP"):
        block_name = f"A{index}"
    elif (obj_type == "WGT"):
        block_name = f"B{index}"
    elif (obj_type == "ACC"):
        block_name = f"X{index}"
    elif (obj_type == "OUT"):
        block_name = f"C{index}"
    else:
        block_name = f"{obj_type}{index}"
    return block_name
