# IMPORT PACKAGES
# ---------------


# CALCULATE MEMORY ADDRESSES
# --------------------------
def calculate_memory_addresses(A_blocks, B_blocks, C_blocks, X_blocks, block_size):
    """Calculate both physical and logical addresses of the first element for each block."""
    current_phys = 0x1000
    addresses = []
    
    # Block size (in Bytes)
    block_sizes = {
        'INP': block_size * 16,  # 16 vectors de 16 Bytes
        'WGT': 256,              # 1 block = 1 vector of 256 Bytes 
        'OUT': block_size * 16,  # 16 vectors de 16 Bytes
        'ACC': block_size * 64   # 16 vectors de 64 Bytes (int32)
    }

    type_to_letter = {'INP': 'A', 'WGT': 'B', 'OUT': 'C', 'ACC': 'X'}
    
    # Allocation order
    for obj_type, blocks in [
        ('INP', A_blocks),
        ('WGT', B_blocks),
        ('OUT', C_blocks),
        ('UOP', [None]),  # Allocate a single page
        ('ACC', X_blocks)
    ]:
        if obj_type == 'UOP':
            current_phys = ((current_phys + 0x1000 - 1) // 0x1000) * 0x1000 + 0x1000
            continue

        for i, _ in enumerate(blocks):
            vector_size = 16 if obj_type in ['INP', 'OUT'] else 256 if obj_type == 'WGT' else 64
            logical = current_phys // vector_size
            
            addresses.append({
                'type': obj_type,
                'block': f"{type_to_letter[obj_type]}{i}",
                'phys_hex': hex(current_phys),
                'logic_hex': hex(logical)
            })
            
            current_phys += block_sizes[obj_type]
        
        # Data aligment
        current_phys = ((current_phys + 0x1000 - 1) // 0x1000) * 0x1000

    return addresses