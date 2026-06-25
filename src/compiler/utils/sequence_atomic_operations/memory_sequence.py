# INPUTS
# ------
# Logical base addresses
sram_base = 0
dram_base = 0

# Parameters
x_stride = 3
x_size = 2
x_pad_right = 2
y_size = 2


# Sequence generator:
# -------------------
sequence = []
for i in range(0, y_size):
    for j in range(0, x_size):
        # Compute the logical addresses
        sram_idx = sram_base + j + i * (x_size + x_pad_right)
        dram_idx = dram_base + j + i * x_stride
        # Create mem
        mem = (sram_idx, dram_idx)
        # Append the sequence
        sequence.append( mem )


# Print information:
# ------------------
sequence_length = x_size * y_size
print(f"\nThe sequence contains {sequence_length} mem: \n")
for idx, mem in enumerate(sequence):
    print(f"\n mem {idx}: \t SRAM={mem[0]} \t DRAM={mem[1]}")
    

