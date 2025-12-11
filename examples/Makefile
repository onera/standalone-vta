# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# DIRECTORIES
#############
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR)/..)
COMPILER_OUTPUT_DIR := $(PROJECT_DIR)/compiler_output
SIMULATOR_OUTPUT_DIR := $(PROJECT_DIR)/simulators_output
SRC_DIR := $(PROJECT_DIR)/src
COMPILER_DIR := $(SRC_DIR)/modified_compiler
VTA_COMPILER_DIR := $(COMPILER_DIR)/vta_compiler
NN_COMPILER_DIR := $(COMPILER_DIR)/nn_compiler
FSIM_DIR := $(SRC_DIR)/simulators/modified_functional_simulator
CONFIG := $(PROJECT_DIR)/config


# VARIABLES
###########
PYTHON_CMD := python 
# PYTHON_CMD := python -m cProfile -o $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

JSON_FILES := $(COMPILER_OUTPUT_DIR)/*.json
# JSON_FILES := $(COMPILER_OUTPUT_DIR)/QLinearAdd5.json

DEBUG ?= True

ONNX_FILE ?= ../../onnx_zoo/qlinearconv_debug.onnx
# ../../onnx_zoo/qlinearconv3x3.onnx
# ../../onnx_zoo/qlinearconv_debug.onnx
# ../../onnx_zoo/twoQLinearConv_debug.onnx
# ../../onnx_zoo/qlinearconv_yolo.onnx 
# ../../onnx_zoo/twoQLinearConv.onnx
# ../../onnx_zoo/subgraph_Qops_pattern.onnx
# ../../onnx_zoo/yolonas_Qops_fixed.onnx


############################################################
############################################################

# Default
all: help

view_profiler:
	@snakeviz $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

# ONNX PARSING
##############
parse_onnx: ## Parse the specified ONNX
	make clean
	@echo ""
	@echo "PARSE ONNX..."
	@date
	python $(NN_COMPILER_DIR)/vta_backend.py \
	$(ONNX_FILE) \
	True \
	$(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_backend.txt
	@date


# COMPILE EXISTING 
##################
compile:
	@echo ""
	@echo "COMPILE tests..."
	@date
	$(PYTHON_CMD) \
	$(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(JSON_FILES) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@date


# FSIM compilation
compile_clean_fsim:
	cd $(FSIM_DIR) && make clean

compile_fsim:
	cd $(FSIM_DIR) && make build/functional_simulator

compile_nn_fsim:
	cd $(FSIM_DIR) && make build/fsim_nn


# REFERENCE EXECUTION
#####################
reference:
	@echo ""
	@echo "PROVIDE references..."
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(JSON_FILES) > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt

reference_onnx:
	@echo ""
	@echo "PROVIDE ONNX reference..."
	python $(COMPILER_DIR)/reference_computation/reference_onnx.py \
	$(DEBUG) \
	$(ONNX_FILE) > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt

check:
	python $(COMPILER_DIR)/reference_computation/check_bin.py \
	$(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_checker.txt
	@echo ""
	@echo "SUCCESS!"


# FSIM EXECUTION
################
fsim: 
	@echo ""
	@echo "RUN functional simulation..."
	@date
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo ""
	@echo "SUCCESS!"

nn_fsim: 
	@echo ""
	@echo "RUN functional simulation (for NN)..."
	@date
	cd $(FSIM_DIR) && make -s nn_execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo ""
	@echo "FINAL_OUTPUT.BIN generated!"


# EXECUTION
###########
# Do "make compile_fsim"
run:
	@make clean
	@make compile
	@make reference
	@make fsim


# Do "make compile_nn_fsim"
nn_run:
	@make parse_onnx
	@make compile
	@make reference_onnx
	@make nn_fsim
	@make check

nn_execute:
	@make reference_onnx
	@make nn_fsim
	@make check

############################################################
############################################################

# COMPILATION TESTS
###################

# MATRIX MULTIPLICATION EXAMPLES
matmul_16x16: ## Execute vta_ir/matmul_16x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 input int8
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 weight int8
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmul_16x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmul_16x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@make fsim

# Test
test_matmul: ## Test matrix multiplication with random size (1-2048)
	make clean
	@echo "CREATE the JSON matmul_relu"
	python $(COMPILER_DIR)/utils/testing.py matmul
	@make compile
	@make reference
	@make fsim

# Test
test_matmul_relu: ## Test matrix multiplication and ReLU with random size (1-2048)
	make clean
	@echo "CREATE the JSON matmul_relu"
	python $(COMPILER_DIR)/utils/testing.py matmul_relu
	@make compile
	@make reference
	@make fsim


# MATRIX MULTIPLICATION WITH SCALAR EXAMPLES
matrix_mul_constant: ## Execute vta_ir/matmulConst_16x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 input int8
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmulConst_16x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmulConst_16x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@make fsim

# Test
test_mulconstant: ## Test the multiplication between random size matrix and scalar
	make clean
	@echo "CREATE the JSON mulconstant"
	python $(COMPILER_DIR)/utils/testing.py mulconstant
	@make compile
	@make reference
	@make fsim


# MATRIX POOLING EXAMPLE
matrix_maxpool: ## Execute vta_ir/maxpool_36x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accumulator int32
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/maxpool_36x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/maxpool_36x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_maxpool: ## TestALU through MAXPOOL configuration with a random size matrix
	make clean
	@echo "CREATE the JSON maxpool"
	python $(COMPILER_DIR)/utils/testing.py maxpool
	@make compile
	@make reference
	@make fsim


# ADDING 2 MATRICES EXAMPLES
matrix_add: ## Execute vta_ir/add_36x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accumulator int32
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accbis int32
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/add_36x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(DEBUG) \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/add_36x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@make fsim

# Test
test_add: ## Test adding two same shape matrices together with random size
	make clean
	@echo "CREATE the JSON add_acc"
	python $(COMPILER_DIR)/utils/testing.py add_acc
	@make compile
	@make reference
	@make fsim


# GENERAL TESTS
###############
test: ## Test campaign
	@make test_matmul
	@make test_matmul_relu
	@make test_mulconstant
	@make test_maxpool
	@make test_add
	@echo ""
	@echo "Everything has matched the reference!"

test_sequence:
	@make clean
	@echo ""
	@echo "GENERATE tests..."
	python $(COMPILER_DIR)/utils/testing.py matmul
	python $(COMPILER_DIR)/utils/testing.py matmul_relu
	python $(COMPILER_DIR)/utils/testing.py mulconstant
	python $(COMPILER_DIR)/utils/testing.py maxpool
	python $(COMPILER_DIR)/utils/testing.py add_acc
	@make compile
	@make reference
	@make fsim


############################################################
############################################################


# CREATE OUTPUTS DIRECTORIES
############################
$(COMPILER_OUTPUT_DIR):
	mkdir $(COMPILER_OUTPUT_DIR)
$(SIMULATOR_OUTPUT_DIR):
	mkdir $(SIMULATOR_OUTPUT_DIR)


# CLEAN
#######
.PHONY: debug help clean force_clean
clean: | $(COMPILER_OUTPUT_DIR) $(SIMULATOR_OUTPUT_DIR) ## Clean the project generated files (standalone/compiler_output/ and standalone/simulator_output/)
	-rm $(COMPILER_OUTPUT_DIR)/*.*
	-rm $(SIMULATOR_OUTPUT_DIR)/*.*

force_clean: ## Clean the FSIM directory
	make clean
	cd $(FSIM_DIR) && make clean

clean_bin: | $(COMPILER_OUTPUT_DIR) 
	-rm $(COMPILER_OUTPUT_DIR)/*.bin
clean_csv: | $(COMPILER_OUTPUT_DIR) 
	-rm $(COMPILER_OUTPUT_DIR)/*.csv


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
