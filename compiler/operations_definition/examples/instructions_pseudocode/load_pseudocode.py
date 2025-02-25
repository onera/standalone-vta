# INPUTS
# ------
# Settings
y = 2
x = 2
stride = 3

# Addresses
sram_base = 0x0000
dram_base = 0x00001000

# ------------
# INSTRUCTIONS
# ------------
# Step counter
step = 0
for i in range(0, y):
    for j in range(0, x):
		# Define the current memory location
        sram_loc = sram_base + i*(x)+j
        dram_loc = dram_base + (i)*stride + (j)
        
		# Increment the step
        step = step + 1
        
		# Condition for padding: not useful there
        if (i < 0) or (j < 0) or (i >= y) or (j >= x):
            print("ERROR!")
        else:
                print(f"Step {step}: \nDRAM = {hex(dram_loc)} \nSRAM = {hex(sram_loc)} \n")