# Inputs:
# -------
# RANGE
uop_bgn = 0 
uop_end = 2

uop_buffer = [
    (0,0,0),
    (0,16,1)
]

# OUTER LOOP
end0 = 49 # loop extent 0
x0 = 16 # accumulator index factor 0
y0 = 32 # input index factor 0
z0 = 0 # weight index factor 0

# INNER LOOP
end1 = 1 # loop extent 1
x1 = 1 # accumulator index factor 1
y1 = 1 # input index factor 1
z1 = 0 # weight index factor 1


# Instructions:
# -------------
step = 0
for i0 in range(0, end0):
    for i1 in range (0, end1):
        for uop_idx in range(uop_bgn, uop_end):
            step = step + 1
            #x, y, z = decode_gemm_indices(uop_buffer[upc]) # TBD
            x, y, z = uop_buffer[uop_idx]
            
            reg_idx = i0*x0 + i1*x1 + x
            inp_idx = i0*y0 + i1*y1 + y
            wgt_idx = i0*z0 + i1*z1 + z
            
            #reg_file[reg_idx] += GEMM(inp_buff[inp_idx], wgt_buff[wgt_idx]) # TBD
            print(f"\nStep: {step}")
            print(f"ACC IDX: \t {reg_idx}")
            print(f"INP IDX: \t {inp_idx}")
            print(f"WGT IDX: \t {wgt_idx}\n")