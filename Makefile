MILL = pixi run ./mill
ONNX ?= examples/onnx/qyolo_pattern.onnx
CONFIG ?= vta_config
BOARD ?= zcu104
DDR_BASE ?= 0x100000
MILL_FLAGS = -i --ticker false
DEFINES = -Dvta.onnx.file=$(ONNX) -Dvta.board.name=$(BOARD) -Dvta.ddr.base=$(DDR_BASE) -Dvta.config.file=$(CONFIG)
CMD = $(MILL) $(MILL_FLAGS) $(DEFINES)

RUNNER ?= run_nn run_nn_uart
DATA_LOADER ?= elf sd

all: help

.PHONY: all compile fsim vsim synthesis baremetal inspect help clean cleaner clean-target check_onnx check_irs


compile: ## Compile the ONNX to VTA binaries
	@$(CMD) default.compile

fsim: ## Run functional simulation
	@$(CMD) default.fsim

vsim: ## Run cycle-accurate simulation
	@$(CMD) default.vsim --no-timeout

synthesis: ## Run vivado synthesis
	@$(CMD) targets[$(CONFIG),$(BOARD)].synth

baremetal: ## Create vitis workspace with baremetal apps
	@$(CMD) default.createVitisProject --runner $(RUNNER) --data-loader $(DATA_LOADER)

check_onnx: ## Run all example in simulation on default config
	@$(CMD) examples.onnx[_,vta_config].fsim

check_irs: ## Run raw vta ir in both simulators on $CONFIG
	@$(MILL) -i -k examples.irs[_,_].check

tests: ## Run all test suites (slow ~20min)
	@$(MILL) -k modules.hardware.test.unittest + modules.fpga.synthesis.test + modules.fpga.software.test

inspect: ## Run mill inspect on default target
	@$(CMD) inspect default._

clean: ## Clean only the current config run artifacts (out/run/<MODEL>)
	@$(CMD) clean run[]

cleaner: ## Clean all cached artifacts (out/run)
	@$(CMD) clean run[_]

clean-target: ## Clean fpga target cache
	@$(CMD) clean targets[$(CONFIG),$(BOARD)]

help: ## Show this help
	@echo "Convenient helper for compiling, simulating and executing an ONNX model on the VTA"
	@echo "Wrap mill commands for the default run pipeline. For more advanced usage, use ./mill directly (see MILL.md)."
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":[^#]*##[ \t]*"}; {printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@echo " Current target:"
	@echo "  ONNX: $(ONNX) (onnx model)"
	@echo "  CONFIG: $(CONFIG) (target config)"
	@echo "  BOARD: $(BOARD) (target FPGA board name)"
	@echo "  DDR_BASE: $(DDR_BASE) (DDR offset for baremetal)"

