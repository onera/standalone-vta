all:
	@echo "Targets:"
	@echo "  gen           - alias for gen-nn (compiler-output driven)"
	@echo "  gen-nn        - generate $(OUTDIR)/ from compiler output (CONFIG, DDR_BASE, OUTDIR)"
	@echo "  gen-test_gemm - generate $(OUTDIR)/init_dram.h for the test_gemm unit test (no compiler output needed)"
	@echo "  workspace     - create Vitis workspace (XSA, CPU, RUNNER required)"
	@echo "  test-cpu-ops  - host unit test: CPU ops vs fsim reference (no board/model needed)"
	@echo "  clean         - remove $(OUTDIR)/ and build/"

.PHONY: all clean gen gen-nn gen-test_gemm workspace test-cpu-ops

COMPILER_OUTPUT ?= ../../../compiler_output
COMPILER_OUTPUTS = $(wildcard $(COMPILER_OUTPUT)/*)
CONFIG    ?= ../../../config/vta_config.json
DDR_BASE  ?= 0x0
OUTDIR    ?= gen
RUNNER    ?= run_nn
DATA_LOADER ?= tcl
XSA ?=
CPU ?=
GEN = $(wildcard $(OUTDIR)/*)

# Default `gen` keeps the historical compiler-output driven pipeline so existing
# invocations from CI / users keep working.
gen: gen-nn

gen-nn: $(COMPILER_OUTPUTS) $(CONFIG)
	python host/gen_nn_baremetal.py \
		--config-json $(CONFIG)     \
		--ddr-base    $(DDR_BASE)   \
		--outdir      $(OUTDIR)     \
		$(COMPILER_OUTPUT)

# test_gemm is a unit test (hardcoded VTA program, randomised matrices); it
# does NOT consume compiler_output/.  Kept as a separate target so it can run
# in environments where no model has been compiled yet.
gen-test_gemm:
	python host/gen_init_dram_test_gemm.py --outdir $(OUTDIR)

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
