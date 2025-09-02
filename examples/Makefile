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

# MATRIX MULTIPLICATION EXAMPLES
matrix_16x16: ## Mutliply two 16x16-matrices
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_16x16_relu: ## Mutliply two 16x16-matrices and apply a ReLU (MAX with 0)
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_16x16_relu.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_20x20: ## Multiply two 20x20-matrices and perform some ALU operations
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_20x20.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_8blocks: ## Multiply a 4x2-blocks INP with a 2x3-blocks WGT
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_8blocks.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_overfitting: ## Multiply a 4x2-blocks INP with a 2x3-blocks WGT
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_8blocks.json $(MAKEFILE_DIR)matrix_operations/alternative_config/config_for_overfitting.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_matmul:
	make clean
	python $(MAKEFILE_DIR)matrix_operations/testing/test_matmul_relu.py
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/testing/matmul_relu.json $(CONFIG)/vta_config.json False
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# MATRIX MULTIPLICATION WITH SCALAR EXAMPLES
matrix_mul_constant: ## Mutliply a 16x16-matrices with a constant
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_mul_constant.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_mul_constant:
	make clean
	python $(MAKEFILE_DIR)matrix_operations/testing/test_mul_constant.py
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/testing/mul_constant.json $(CONFIG)/vta_config.json False
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# MATRIX POOLING EXAMPLE
matrix_maxpool: ## Apply a maxpool with a 3x3-kernel on a flatten 6x6-tensor
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_maxpool.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_maxpool_overfitting: ## Apply a maxpool with a 3x3-kernel on a flatten 6x6-tensor, buffers can only store 16 vectors (A single step is required by MAX)
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_maxpool.json $(MAKEFILE_DIR)matrix_operations/alternative_config/config_pool_overfitting.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

matrix_maxpool_big_overfitting: ## Apply a maxpool with a 3x3-kernel on a flatten 6x6-tensor, buffers can only store 4 vectors (Multiple steps are required by MAX)
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/matrix_maxpool.json $(MAKEFILE_DIR)matrix_operations/alternative_config/config_pool_big_overfitting.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_maxpool:
	make clean
	python $(MAKEFILE_DIR)matrix_operations/testing/test_maxpool.py
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/testing/maxpool.json $(CONFIG)/vta_config.json False
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


# ADDING 2 MATRICES EXAMPLES
matrix_add: ## Add two 16x16 matrices together
	make clean
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/add_16x16matrix.json $(CONFIG)/vta_config.json $(DEBUG) > $(COMPILER_OUTPUT_DIR)/prompt_vta_compiler.txt
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt

# Test
test_add:
	make clean
	python $(MAKEFILE_DIR)matrix_operations/testing/test_add.py
	python $(VTA_COMPILER_DIR)/main_vta_compiler.py $(MAKEFILE_DIR)matrix_operations/testing/add_two_matrices.json $(CONFIG)/vta_config.json False
	cd $(FSIM_DIR) && make -s execute > $(SIMULATOR_OUTPUT_DIR)/fsim_report.txt


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



# GENERAL TESTS
###############
test:
	@make clean
	@echo ""
	@echo "test_matmul"
	@make test_matmul
	@echo ""
	@echo "test_mul_constant"
	@make test_mul_constant
	@echo ""
	@echo "test_maxpool"
	@make test_maxpool
	@echo ""
	@echo "test_add"
	@make test_add
	@echo ""
	@echo "lenet5_full"
	@make lenet5_full
	@echo ""
	@echo "SUCCESS!"



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
