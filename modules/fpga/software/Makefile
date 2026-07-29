all:
	@echo "Targets:"
	@echo "  gen           - alias for gen-nn (compiler-output driven)"
	@echo "  gen-nn        - generate $(OUTDIR)/ from compiler output (CONFIG, DDR_BASE, OUTDIR)"
	@echo "  gen-sd        - gen-nn + nn_sd_manifest.h and $(OUTDIR)/sd_card/ (runtime SD loader)"
	@echo "  gen-sd-debug  - gen-sd + isolation-check goldens on the card (REF_DIR; for run_nn_debug/run_nn_cpu_debug DATA_LOADER=sd)"
	@echo "  gen-test_gemm - generate $(OUTDIR)/init_dram.h for the test_gemm unit test (no compiler output needed)"
	@echo "  workspace     - create Vitis workspace (XSA, CPU, RUNNER required)"
	@echo "  test-cpu-ops  - host unit test: CPU ops vs fsim reference (no board/model needed)"
	@echo "  clean         - remove $(OUTDIR)/ and build/"

.PHONY: all clean gen gen-nn gen-sd gen-sd-debug gen-test_gemm workspace test-cpu-ops

COMPILER_OUTPUT ?= ../../../compiler_output
COMPILER_OUTPUTS = $(wildcard $(COMPILER_OUTPUT)/*)
CONFIG    ?= ../../../config/vta_config.json
DDR_BASE  ?= 0x0
OUTDIR    ?= gen
RUNNER    ?= run_nn
DATA_LOADER ?= tcl
SD_DIR    ?=
REF_DIR   ?= ../../../simulators_output
XSA ?=
CPU ?=
GEN = $(wildcard $(OUTDIR)/*)

# The baremetal codegen is the Scala GenNnBaremetal task, run through Mill from
# the repo root. Mill resolves paths against the repo root, so the gen targets
# pass absolute paths; the active hardware config is selected by its file name
# via -Dvta.config.file (Mill reads config/<name>).
REPO_ROOT   := $(abspath ../../..)
MILL        := cd $(REPO_ROOT) && ./mill
CONFIG_NAME  = $(notdir $(CONFIG))

# Pass --sd-dir only when SD_DIR is set, so an empty value doesn't swallow the
# positional compiler-output argument.
SD_DIR_FLAG = $(if $(strip $(SD_DIR)),--sd-dir $(SD_DIR),)

# Default `gen` keeps the historical compiler-output driven pipeline so existing
# invocations from CI / users keep working.
gen: gen-nn

gen-nn: $(COMPILER_OUTPUTS) $(CONFIG)
	$(MILL) -Dvta.config.file=$(CONFIG_NAME) vta.fpga.genNnBaremetal \
		$(abspath $(COMPILER_OUTPUT)) \
		--ddr-base $(DDR_BASE)        \
		--outdir   $(abspath $(OUTDIR))

# gen-sd: gen-nn plus the runtime SD-card loader artifacts - nn_sd_manifest.h
# (file -> DDR map compiled into the ELF) and $(OUTDIR)/sd_card/ (the .bin set to
# copy to a FAT32 card). Set SD_DIR=<name> to read from a card subfolder (lets
# several models share one card). Used with `make workspace DATA_LOADER=sd`.
gen-sd: $(COMPILER_OUTPUTS) $(CONFIG)
	$(MILL) -Dvta.config.file=$(CONFIG_NAME) vta.fpga.software.genNnBaremetal \
		$(abspath $(COMPILER_OUTPUT)) \
		--ddr-base $(DDR_BASE)        \
		$(SD_DIR_FLAG)                \
		--outdir   $(abspath $(OUTDIR)) \
		--emit-sd-manifest

# gen-sd-debug: gen-sd plus the per-layer isolation-check goldens
# (input<suffix>.bin / output<suffix>.bin from a fsim VTA_DUMP_LAYERS=1 run in
# REF_DIR). Emits nn_debug_map.h + nn_cpu_debug_map.h and stages the goldens into
# $(OUTDIR)/sd_card/ alongside the model, so run_nn_debug / run_nn_cpu_debug can
# read their references from the card. Used with
# `make workspace RUNNER=run_nn_debug DATA_LOADER=sd`.
gen-sd-debug: $(COMPILER_OUTPUTS) $(CONFIG)
	$(MILL) -Dvta.config.file=$(CONFIG_NAME) vta.fpga.software.genNnBaremetal \
		$(abspath $(COMPILER_OUTPUT)) \
		--ddr-base $(DDR_BASE)        \
		$(SD_DIR_FLAG)                \
		--outdir   $(abspath $(OUTDIR)) \
		--emit-sd-manifest            \
		--emit-layer-check            \
		--emit-cpu-check              \
		--ref-dir  $(abspath $(REF_DIR))

# test_gemm is a unit test (hardcoded VTA program, randomised matrices); it
# does NOT consume compiler_output/.  Kept as a separate target so it can run
# in environments where no model has been compiled yet.
gen-test_gemm:
	$(MILL) vta.fpga.genInitDramTestGemm --outdir $(abspath $(OUTDIR))

# Host unit test for the PS-side CPU ops (driver/src/vta_cpu_ops.cc). Compiles
# the real ops with host stubs (test/host/) and checks them against the
# functional simulator's header-only reference (cpu_functions.h) on synthetic
# inputs. Needs no compiler output, no board, no fsim run - just g++.
FSIM_INC = ../../simulators/functional_simulator/include
test-cpu-ops:
	@mkdir -p build
	$(CXX) -std=c++17 -O2 -Wall -Wno-unused \
		test/test_cpu_ops.cc driver/src/vta_cpu_ops.cc \
		-Itest/host -Idriver/include -I$(FSIM_INC) \
		-o build/test_cpu_ops
	./build/test_cpu_ops

build/vitis_proj: $(GEN)
	vitis -s host/create_vitis_workspace.py \
		--xsa         $(XSA)          \
		--runner      $(RUNNER)       \
		--data-loader $(DATA_LOADER)  \
		--cpu         $(CPU)          \
		--workspace   $@

workspace: build/vitis_proj

clean:
	@rm -rf $(OUTDIR)
	@rm -rf build
