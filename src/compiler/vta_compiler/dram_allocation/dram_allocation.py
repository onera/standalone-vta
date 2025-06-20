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

        # Define the size of the allocation 
        alloc_size_bytes = sum(matrix.nbytes for matrix in obj_value) # Bytes

        # Get the object address
        obj_addr, current_dram_addr = base_address_computation(obj_type, page_size, current_dram_addr, dram_offset, logical_divisor, alloc_size_bytes)

        # Increment the addresses list
        base_addresses.append(obj_addr)


    # Allocate space for the UOPs (consider a single UOP)
    obj_addr, current_dram_addr = base_address_computation("UOP", page_size, current_dram_addr, dram_offset, 4, 4) 
    base_addresses.append(obj_addr)


    # DEBUG
    if (debug):
        print("\n\nDRAM ALLOCATION:")
        for addr in base_addresses:
            print(addr)
        print(f"\nThe current physical dram base address is: current_dram_addr={hex(current_dram_addr)}\n")

    # Return 
    return base_addresses, current_dram_addr

# ---------------------------------------------

# BASE_ADDRESS
# ------------
def base_address_computation(obj_type, page_size, current_dram_addr, dram_offset, logical_divisor, alloc_size_bytes):
    # Increment current_dram_addr to the next page
    page_addr = (current_dram_addr // page_size)
    current_dram_addr = (page_addr + 1) * page_size

    # Define the object address
    obj_addr = {
        "type": obj_type,
        "physical_base_address": hex( current_dram_addr ),
        "logical_base_address": hex( (current_dram_addr - dram_offset) // logical_divisor ),
        "size": alloc_size_bytes
    }

    # Update current_dram_addr
    current_dram_addr = current_dram_addr + alloc_size_bytes

    # Return
    return obj_addr, current_dram_addr

