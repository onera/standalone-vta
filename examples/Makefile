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
VTA_COMPILER_DIR := $(COMPILER_DIR)/layer_compiler
NN_COMPILER_DIR := $(COMPILER_DIR)/nn_compiler
FSIM_DIR := $(SRC_DIR)/simulators/functional_simulator
CONFIG := $(PROJECT_DIR)/config

# VARIABLES
###########
DEBUG ?= True


############################################################
############################################################

# Default
all: help

# FSIM EXECUTION
################

fsim: 
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


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
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmul_16x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmul_16x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_matmul: ## Test matrix multiplication with random size (1-2048)
	make clean
	@echo "Create the JSON matmul_relu"
	python $(COMPILER_DIR)/utils/testing.py matmul
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/matmul.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/matmul.json > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_matmul_relu: ## Test matrix multiplication and ReLU with random size (1-2048)
	make clean
	@echo "Create the JSON matmul_relu"
	python $(COMPILER_DIR)/utils/testing.py matmul_relu
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/matmul_relu.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/matmul_relu.json > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# MATRIX MULTIPLICATION WITH SCALAR EXAMPLES
matrix_mul_constant: ## Execute vta_ir/matmulConst_16x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 input int8
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmulConst_16x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/matmulConst_16x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_mulconstant: ## Test the multiplication between random size matrix and scalar
	make clean
	@echo "Create the JSON mulconstant"
	python $(COMPILER_DIR)/utils/testing.py mulconstant
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/mulconstant.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/mulconstant.json > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# MATRIX POOLING EXAMPLE
matrix_maxpool: ## Execute vta_ir/maxpool_36x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accumulator int32
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/maxpool_36x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/maxpool_36x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_maxpool: ## TestALU through MAXPOOL configuration with a random size matrix
	make clean
	@echo "Create the JSON maxpool"
	python $(COMPILER_DIR)/utils/testing.py maxpool
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/maxpool.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/maxpool.json > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# ADDING 2 MATRICES EXAMPLES
matrix_add: ## Execute vta_ir/add_36x16.json
	make clean
	@echo "Create the binaries"
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accumulator int32
	python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 36 16 accbis int32
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/add_36x16.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(MAKEFILE_DIR)vta_ir/add_36x16.json  > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_add: ## Test adding two same shape matrices together with random size
	make clean
	@echo "Create the JSON add_acc"
	python $(COMPILER_DIR)/utils/testing.py add_acc
	@echo ""
	@echo "Compiling the VTA IR"
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/add_acc.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide reference computation"
	python $(COMPILER_DIR)/reference_computation/reference_computation.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/add_acc.json > $(COMPILER_OUTPUT_DIR)/prompt_reference.txt
	@echo ""
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# GENERAL TESTS
###############
test: ## Test campaign
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
	@echo "Generate tests..."
	python $(COMPILER_DIR)/utils/testing.py matmul
	python $(COMPILER_DIR)/utils/testing.py matmul_relu
	python $(COMPILER_DIR)/utils/testing.py mulconstant
	python $(COMPILER_DIR)/utils/testing.py maxpool
	python $(COMPILER_DIR)/utils/testing.py add_acc
	@echo ""
	@echo "Compile tests..."
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(CONFIG)/vta_config.json \
	$(COMPILER_OUTPUT_DIR)/matmul.json \
	$(COMPILER_OUTPUT_DIR)/matmul_relu.json \
	$(COMPILER_OUTPUT_DIR)/mulconstant.json \
	$(COMPILER_OUTPUT_DIR)/maxpool.json \
	$(COMPILER_OUTPUT_DIR)/add_acc.json > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	@echo ""
	@echo "Provide references..."


############################################################
############################################################

# ONNX PARSING
##############
# MNIST / LeNet
parse_lenet: ## Parse a LeNet (mnsit-12) ONNX
	make clean
	@echo ""
	@echo "Parsing LENET ONNX..."
	python $(NN_COMPILER_DIR)/vta_backend.py \
	../../onnx_zoo/mnist-12.onnx \
	True \
	True > $(COMPILER_OUTPUT_DIR)/prompt_vta_backend.txt

# YOLONAS
parse_yolo: ## Parse a YoloNas ONNX
	make clean
	@echo ""
	@echo "Parsing YOLO ONNX..."
	python $(NN_COMPILER_DIR)/vta_backend.py \
	../../onnx_zoo/yolonas.onnx \
	True \
	True > $(COMPILER_OUTPUT_DIR)/prompt_vta_backend.txt


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
