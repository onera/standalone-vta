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
FSIM_DIR := $(SRC_DIR)/simulators/functional_simulator
CONFIG := $(PROJECT_DIR)/config

# VARIABLES
###########
DEBUG ?= True


# EXECUTION
###########
all: help

fsim: 
	@echo "Functional simulation"
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# MATRIX MULTIPLICATION EXAMPLES
matmul_16x16: ## Mutliply two 16x16-matrices and apply a ReLU (MAX with 0)
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
test_matmul:
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
test_matmul_relu:
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
matrix_mul_constant: ## Mutliply a 16x16-matrices with a constant
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
test_mulconstant:
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
matrix_maxpool: ## Apply a maxpool with a 3x3-kernel on a flatten 6x6-tensor
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
test_maxpool:
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
matrix_add: ## Add two 36x16 matrices together
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
test_add:
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
test:
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


# LENET-5 TESTS
###############
lenet5_layer1: 
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_layer1.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

lenet5_layer2: 
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_layer2.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

lenet5_layer3: 
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_layer3.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

lenet5_layer4: 
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_layer4.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

lenet5_layer5: 
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_layer5.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

lenet5_full: ## LeNet-5 simulation
	make clean 
	python $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/main_reference_lenet5.py > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/lenet5_layer1.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler_L1.txt
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/lenet5_layer2.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler_L2.txt
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/lenet5_layer3.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler_L3.txt
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/lenet5_layer4.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler_L4.txt
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/lenet5/lenet5_full/lenet5_layer5.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler_L5.txt
	cd $(FSIM_DIR) && make -s lenet5 > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt
	@echo ""
	@echo "SUCCESS!"


# YOLONAS TESTS
###############
yolonas_conv1:
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/yolonas/yolonas_conv1.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

yolonas_conv2:
	make clean 
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/yolonas/yolonas_conv2.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# CREATE OUTPUTS DIRECTORIES
############################
$(COMPILER_OUTPUT_DIR):
	mkdir $(COMPILER_OUTPUT_DIR)
$(SIMULATOR_OUTPUT_DIR):
	mkdir $(SIMULATOR_OUTPUT_DIR)


# CLEAN
#######
.PHONY: clean debug help force_clean
clean: | $(COMPILER_OUTPUT_DIR) $(SIMULATOR_OUTPUT_DIR) ## Clean the project generated files (standalone/compiler_output/ and standalone/simulator_output/)
	-rm $(COMPILER_OUTPUT_DIR)/*.*
	-rm $(SIMULATOR_OUTPUT_DIR)/*.*

force_clean:
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
