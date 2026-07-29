# VTA FPGA synthesis - one-command bitstream + XSA.
#
# The real work is the Scala fpga.synthesis.BuildFpga task (orchestrator) +
# the classpath Vivado recipes (create_project.tcl + synthesis.tcl) +
# boards/<board>.json (board definition). This Makefile is a thin convenience
# entry that runs the task through Mill from the repo root.
#
# Source the Vivado environment first:
#   source <Xilinx>/2025.2/Vivado/settings64.sh

BOARD   ?= zcu104
CONFIG  ?= ../../../config/vta_config.json
OUT     ?= build

# Mill runs from the repo root and resolves paths against it, so pass absolute
# paths; the config file must live under <repo>/config (BuildFpga resolves the
# RTL emit's vta.config.file there). Mill injects --vivado from XILINX_VIVADO.
REPO_ROOT := $(abspath ../../..)
MILL      := cd $(REPO_ROOT) && ./mill
BUILD_FPGA = $(MILL) vta.fpga.synthesis.buildFpga --board $(BOARD) \
             --config $(abspath $(CONFIG)) --out $(abspath $(OUT))

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
	$(BUILD_FPGA) $(FLAGS)

dry-run:
	$(BUILD_FPGA) $(FLAGS) --dry-run

clean:
	@rm -rf $(OUT)
