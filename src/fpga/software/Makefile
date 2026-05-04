all:
	@echo "Targets:"
	@echo "  config       — generate config/ from compiler output (RUNNER, DATA_LOADER, DDR_BASE)"
	@echo "  workspace    — create Vitis workspace (XSA, CPU required)"
	@echo "  clean        — remove config/ and build/"

.PHONY: all clean config workspace

COMPILER_OUTPUT ?= ../../../compiler_output
COMPILER_OUTPUTS = $(wildcard $(COMPILER_OUTPUT)/*)
CONFIG    ?= ../../../config/vta_config.json
DDR_BASE  ?= 0x200000
OUTDIR    ?= gen
RUNNER    ?= run_nn
DATA_LOADER ?= tcl
XSA ?=
CPU ?=
GEN = $(wildcard $(OUTDIR)/*)

config: $(COMPILER_OUTPUTS) $(CONFIG)
	python host/gen_nn_baremetal.py \
		--config-json $(CONFIG)     \
		--ddr-base    $(DDR_BASE)   \
		--outdir      $(OUTDIR)     \
		--runner      $(RUNNER)     \
		--data-loader $(DATA_LOADER)\
		$(COMPILER_OUTPUT)

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
