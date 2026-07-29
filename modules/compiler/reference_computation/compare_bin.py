# IMPORT PACKAGES
# ---------------
import os
import sys


###############################################


# MAIN FUNCTION
# -------------
def compare_bin(path_a, path_b, show=8):
    """Byte-compare two binary files.

    Used where no golden reference exists (the raw VTA IR fixtures), to check
    that the functional simulator and the Verilated RTL produced the same
    bytes. Returns True when the two files are identical.
    """
    with open(path_a, "rb") as f:
        data_a = f.read()
    with open(path_b, "rb") as f:
        data_b = f.read()

    name_a = os.path.basename(path_a)
    name_b = os.path.basename(path_b)

    if len(data_a) != len(data_b):
        print(f"MISMATCH: sizes differ: {name_a} is {len(data_a)} bytes, "
              f"{name_b} is {len(data_b)} bytes")
        return False

    offsets = [i for i in range(len(data_a)) if data_a[i] != data_b[i]]

    if not offsets:
        print(f"MATCH: {len(data_a)} bytes identical")
        return True

    print(f"MISMATCH: {len(offsets)} of {len(data_a)} bytes differ, "
          f"first at offset {offsets[0]}")
    for offset in offsets[:show]:
        print(f"  offset {offset}: {name_a}={data_a[offset]} {name_b}={data_b[offset]}")
    return False


###############################################


# EXECUTE MAIN FUNCTION
# ---------------------
if __name__ == "__main__":
    """
    To execute:
        > python compare_bin.py <a.bin> <b.bin>
    Exits 0 when identical, 1 when they differ, 2 on a usage error.
    """
    if len(sys.argv) != 3:
        print("usage: compare_bin.py <a.bin> <b.bin>", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if compare_bin(sys.argv[1], sys.argv[2]) else 1)
