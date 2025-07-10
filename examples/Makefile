# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# DIRECTORIES
#############
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR)/..)
COMPILER_OUTPUT_DIR := $(PROJECT_DIR)/compiler_output
SIMULATOR_OUTPUT_DIR := $(PROJECT_DIR)/simulators_output
SRC_DIR := $(PROJECT_DIR)/src
COMPILER_DIR := $(SRC_DIR)/compiler
VTA_COMPILER_DIR := $(COMPILER_DIR)/vta_compiler
FSIM_DIR := $(SRC_DIR)/simulators/functional_simulator
CONFIG := $(PROJECT_DIR)/config

# VARIABLES
###########
DEBUG ?= True


# EXECUTION
###########
all: help

matrix_16x16: ## Mutliply two 16x16-matrices
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_16x16_relu: ## Mutliply two 16x16-matrices and apply a ReLU (MAX with 0)
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16_relu.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_16x16_maxpool: ## Multiply two 16x16-matrices and apply a MAX vector-vector with a stride of 1 (preliminary to MAXPOOL)
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16_maxpool.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt

matrix_20x20: ## Multiply two 20x20-matrices and perform some ALU operations
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_20x20.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt

matrix_8blocks: ## Multiply a 4x2-blocks INP with a 2x3-blocks WGT
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_8blocks.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt


# CREATE OUTPUTS DIRECTORIES
############################
$(COMPILER_OUTPUT_DIR):
	mkdir $(COMPILER_OUTPUT_DIR)
$(SIMULATOR_OUTPUT_DIR):
	mkdir $(SIMULATOR_OUTPUT_DIR)


# CLEAN
#######
.PHONY: clean debug help
clean: ## Clean the project generated files (standalone/compiler_output/ and standalone/simulator_output/)
	-rm $(COMPILER_OUTPUT_DIR)/*.*
	-rm $(SIMULATOR_OUTPUT_DIR)/*.*


# DEBUG
#######
debug: 
	@echo "--- PATHS ---"
	@echo "PROJECT_DIR: $(PROJECT_DIR)"
	@echo "COMPILER_OUTPUT_DIR: $(COMPILER_OUTPUT_DIR)"
	@echo "SIMULATOR_OUTPUT_DIR: $(SIMULATOR_OUTPUT_DIR)"
	@echo "SRC_DIR: $(SRC_DIR)"
	@echo "COMPILER_DIR: $(COMPILER_DIR)"
	@echo "VTA_COMPILER_DIR: $(VTA_COMPILER_DIR)"


# HELP
######
# Return all the possible option for the makefile (must be referenced with ##)
help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":[ \t]*##[ \t]*"}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'
