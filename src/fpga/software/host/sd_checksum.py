#!/usr/bin/env python3
"""sd_checksum.py - host-side checksum matching apps/sd_loader_test.cc.

The on-board sd_loader_test app prints a 32-bit additive byte checksum of the
file it reads from the SD card. Run this on the same file to get the expected
value to compare against the UART output.

Usage:
    python3 host/sd_checksum.py path/to/test.bin
"""

import sys
from pathlib import Path


def checksum(data: bytes) -> int:
    """32-bit additive byte sum, matching add_byte() in sd_loader_test.cc."""
    return sum(data) & 0xFFFFFFFF


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: sd_checksum.py <file>")
    path = Path(sys.argv[1])
    data = path.read_bytes()
    print(f"file     : {path}")
    print(f"size     : {len(data)} bytes")
    print(f"checksum : 0x{checksum(data):08x}")


if __name__ == "__main__":
    main()
