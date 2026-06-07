#!/usr/bin/env python3
"""Baremetal NN generator entry point.

The implementation lives in the ``nnbaremetal`` package (one module per purpose:
config, model, parse, layout, emit_headers, emit_load, debug_emit, checks, cli).
This thin shim keeps the historical entry point working: the Makefile ``gen``
target, ``python host/gen_nn_baremetal.py ...`` on the command line, and
``import gen_nn_baremetal as gen`` from the sibling host scripts (uart_nn,
check_output, audit_dram) all resolve through here.
"""

from nnbaremetal import *  # noqa: F401,F403  - re-export the public API
from nnbaremetal.cli import main

if __name__ == "__main__":
    main()
