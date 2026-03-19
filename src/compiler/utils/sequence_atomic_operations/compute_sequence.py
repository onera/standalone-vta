# Inputs:
# -------
# BADDR buffer
BADDR = []
for i in range(0,2):
    BADDR.append( (i*1, i*0, i*2) )

# Base addresses (range)
baddStart = 0
baddEnd = 1

# Number of laddr per baddr
x = 1
y = 1

# Strides
delta_dst_x = 0
delta_dst_y = 0
delta_src_x = 0
delta_src_y = 0
delta_wgt_x = 0
delta_wgt_y = 0


# Sequence generator:
# -------------------
sequence = []
for i in range(0, y):
    for j in range(0, x):
        for k in range(baddStart, baddEnd):
            # Read logical base addresses
            (c, a, b) = BADDR[k]
            # Compute the logical base addresses
            dst = c + j * delta_dst_x + i * delta_dst_y
            src = a + j * delta_src_x + i * delta_src_y
            wgt = b + j * delta_wgt_x + i * delta_wgt_y
            # Create laddr
            laddr = (dst, src, wgt)
            # Append the sequence
            sequence.append( laddr )


# Print information:
# ------------------
for idx, laddr in enumerate(sequence):
    print(f"\n laddr {idx}: \t DST={laddr[0]} \t SRC={laddr[1]} \t WGT={laddr[2]} ")
