# VTA FPGA synthesis - one-command bitstream + XSA.
#
# The real work is in build_fpga.py (orchestrator) + build_fpga.tcl (Vivado recipe)
# + boards/<board>.json (board definition). This Makefile is a thin convenience entry.
#
# Source the Vivado environment first:
#   source <Xilinx>/2025.2/Vivado/settings64.sh

BOARD   ?= zcu104
CONFIG  ?= ../../../config/vta_config.json
OUT     ?= build
PY      ?= python3

# Optional flags: `make bitstream SKIP_EMIT=1`, `make bitstream JOBS=8`
FLAGS :=
ifdef SKIP_EMIT
FLAGS += --skip-emit
endif
ifdef SKIP_PACKAGE
FLAGS += --skip-package
endif
ifdef JOBS
FLAGS += --jobs $(JOBS)
endif

.PHONY: all bitstream dry-run clean help

all: help

help:
	@echo "Targets:"
	@echo "  bitstream  - full chain config+board -> RTL -> IP -> bitstream -> XSA"
	@echo "               (BOARD, CONFIG, OUT, JOBS, SKIP_EMIT, SKIP_PACKAGE)"
	@echo "  dry-run    - print the plan + generated board_params.tcl, run nothing"
	@echo "  clean      - remove the output directory ($(OUT)/)"
	@echo ""
	@echo "Examples:"
	@echo "  make bitstream CONFIG=../../../config/vta_config.json BOARD=zcu104"
	@echo "  make bitstream BOARD=zcu104 SKIP_EMIT=1"
	@echo "  make dry-run   BOARD=zcu104"

bitstream:
	$(PY) build_fpga.py --board $(BOARD) --config $(CONFIG) --out $(OUT) $(FLAGS)

dry-run:
	$(PY) build_fpga.py --board $(BOARD) --config $(CONFIG) --out $(OUT) $(FLAGS) --dry-run

clean:
	@rm -rf $(OUT)
