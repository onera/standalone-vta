all: 
	@echo "Usage: "
	@echo "clean --- cleanup generated files"

.phony: clean workspace

COMPILER_OUTPUTS=$(wildcard ../../../compiler_output/*)
CONFIG=../../../config/vta_config.json
DDR_BASE=0x200000
XSA ?=
CPU ?=
GEN = $(wildcard config/*)

config: ${COMPILER_OUTPUTS} ${CONFIG}
	python scripts/gen_nn_baremetal.py --config-json ${CONFIG} --ddr-base ${DDR_BASE} ../../../compiler_output

build/vitis_proj: ${GEN}
	vitis -s scripts/create_vitis_workspace.py --xsa ${XSA} --runner elf --cpu ${CPU} --workspace $@

workspace: build/vitis_proj


clean:
	@rm -rf config
	@rm -rf build
