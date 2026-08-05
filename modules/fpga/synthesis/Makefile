# VTA FPGA synthesis - one-command bitstream + XSA.
#
# The real work is the Scala fpga.synthesis.{PackageIp,BuildFpga} tasks +
# the classpath Vivado recipes (create_project.tcl + synthesis.tcl) +
# boards/<board>.json (board definition). This Makefile is a thin convenience
# entry that runs them through Mill from the repo root.
#
# It drives the *uncached* pass-through commands, so it re-emits, re-packages
# and re-synthesizes on every run. The cached path - which skips whatever is
# already up to date - is the crossed task, and it is the one to prefer:
#
#   ./mill "targets[vta_config,zcu104].synth"
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
EMIT_DIR  ?= $(REPO_ROOT)/build/emitted/vta-xilinx-shell
IP_REPO   ?= $(abspath $(OUT))/ip_repo

BUILD_FPGA = $(MILL) modules.fpga.synthesis.buildFpga --board $(BOARD) \
             --config $(abspath $(CONFIG)) --out $(abspath $(OUT)) \
             --emit-dir $(EMIT_DIR) --ip-repo $(IP_REPO)

# Optional flags: `make bitstream JOBS=8`
FLAGS :=
ifdef JOBS
FLAGS += --jobs $(JOBS)
endif

.PHONY: all bitstream emit package-ip dry-run clean help

all: help

help:
	@echo "Targets:"
	@echo "  bitstream  - full chain config+board -> RTL -> IP -> bitstream -> XSA"
	@echo "               (BOARD, CONFIG, OUT, EMIT_DIR, IP_REPO, JOBS)"
	@echo "  emit       - emit the Xilinx-shell RTL only, into EMIT_DIR"
	@echo "  package-ip - package the emitted RTL as a Vivado IP, into IP_REPO"
	@echo "  dry-run    - print the plan + generated board_params.tcl, run nothing"
	@echo "  clean      - remove the output directory ($(OUT)/)"
	@echo ""
	@echo "Examples:"
	@echo "  make bitstream CONFIG=../../../config/vta_config.json BOARD=zcu104"
	@echo "  make bitstream BOARD=zcu104 JOBS=8"
	@echo "  make dry-run   BOARD=zcu104"
	@echo ""
	@echo "Prefer the cached task when you just want an XSA:"
	@echo "  ./mill \"targets[vta_config,$(BOARD)].synth\""

emit:
	$(MILL) modules.hardware.emitVtaFpgaConfig $(EMIT_DIR)

# BuildFpga no longer packages the IP - that is PackageIp's job, so that Mill
# can cache the two separately (see docs/fpga/mill_caching_review.md). The
# bitstream target therefore has to run it first; BuildFpga fails with a clear
# message if IP_REPO holds no packaged core.
package-ip: emit
	$(MILL) modules.fpga.synthesis.packageIp --board $(BOARD) \
	        --emit-dir $(EMIT_DIR) --out $(IP_REPO)

bitstream: package-ip
	$(BUILD_FPGA) $(FLAGS)

dry-run:
	$(BUILD_FPGA) $(FLAGS) --dry-run

clean:
	@rm -rf $(OUT)
