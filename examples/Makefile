# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# DIRECTORIES
#############
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR)/..)
COMPILER_OUTPUT_DIR := $(PROJECT_DIR)/compiler_output
SIMULATOR_OUTPUT_DIR := $(PROJECT_DIR)/simulator_output
SRC_DIR := $(PROJECT_DIR)/src
COMPILER_DIR := $(SRC_DIR)/compiler
VTA_COMPILER_DIR := $(COMPILER_DIR)/vta_compiler
# TO MODIFY
CONFIG := $(VTA_COMPILER_DIR)/config

# VARIABLES
###########
DEBUG ?= True


# EXECUTION
###########
all: debug

matrix_16x16:
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt


# CREATE OUTPUTS DIRECTORIES
############################
$(COMPILER_OUTPUT_DIR):
	mkdir $(COMPILER_OUTPUT_DIR)
$(SIMULATOR_OUTPUT_DIR):
	mkdir $(SIMULATOR_OUTPUT_DIR)


# CLEAN
#######
.PHONY: clean
clean:
	rm $(COMPILER_OUTPUT_DIR)/*.*
	rm $(SIMULATOR_OUTPUT_DIR)/*.*


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

