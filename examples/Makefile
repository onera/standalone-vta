# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# DIRECTORIES
#############
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR)/..)
COMPILER_OUTPUT_DIR := $(PROJECT_DIR)/compiler_output
#SIMULATOR_OUTPUT_DIR := $(PROJECT_DIR)/simulator_output
LOG_OUTPUT_DIR := $(PROJECT_DIR)/log_output
SRC_DIR := $(PROJECT_DIR)/src
COMPILER_DIR := $(SRC_DIR)/compiler
VTA_COMPILER_DIR := $(COMPILER_DIR)/vta_compiler
NN_COMPILER_DIR := $(COMPILER_DIR)/nn_compiler
FSIM_DIR := $(SRC_DIR)/simulators/functional_simulator
TSIM_DIR := $(SRC_DIR)/simulators/cycle_accurate_simulator
CONFIG := $(PROJECT_DIR)/config


# VARIABLES
###########
PYTHON_CMD := python 
# PYTHON_CMD := python -m cProfile -o $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

JSON_FILES := $(COMPILER_OUTPUT_DIR)/*.json

DEBUG ?= False
DEBUG_PARSE ?= True
COMPILE_SUMMARY ?= True
DRAM_JSON ?= False
EXPANDBIAS_AT_COMPILATION ?= True
# ort, numpy, compare
REF_MODE ?= numpy

ONNX_FILE ?= onnx/qyolo_pattern.onnx
# onnx/qlinearconv_debug.onnx
# onnx/qyolo_qconvtranspose.onnx
# onnx/qyolo_qconv_maxpool_qconcat.onnx
# onnx/qyolo_pattern.onnx
# onnx/qyolo.onnx # -> around 30% of the value with +/-3

# ../../onnx_zoo/qyolo_debug.onnx # -> Bit-accurate result


############################################################
############################################################

# Default
all: help

view_profiler:
	@snakeviz $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

# NN COMPILER (1st stage compilation)
#############
nn_compiler: ## NN compilation: qONNX -> CPU parameters + VTA IRs
	make clean
	@echo ""
	@echo "PARSE ONNX..."
	@date
	python $(NN_COMPILER_DIR)/vta_backend.py \
	$(DEBUG_PARSE) \
	$(EXPANDBIAS_AT_COMPILATION) \
	$(CONFIG)/vta_config.json \
	$(ONNX_FILE) > $(LOG_OUTPUT_DIR)/prompt_vta_backend.txt
	@date


# VTA COMPILER (2nd stage compilation) 
##############
vta_compiler: ## VTA compilation: VTA IRs -> VTA code
	@echo ""
	@echo "COMPILE tests..."
	@date
	$(PYTHON_CMD) \
	$(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(DEBUG) \
	$(COMPILE_SUMMARY) \
	$(DRAM_JSON) \
	$(CONFIG)/vta_config.json \
	$(JSON_FILES) > $(LOG_OUTPUT_DIR)/prompt_vta_compiler.txt
	@date


# COMPILE FSIM
##############
fsim_clean: ## Clean FSIM repository
	cd $(FSIM_DIR) && make clean

fsim_compile: ## Compile FSIM
	cd $(FSIM_DIR) && make build/fsim_nn

fsim_compile_single_layer:
	cd $(FSIM_DIR) && make build/fsim_single_layer


# REFERENCE EXECUTION
#####################
reference:
	@echo ""
	@echo "PROVIDE ONNX reference..."
	python $(COMPILER_DIR)/reference_computation/reference_onnx.py \
	$(DEBUG) \
	$(REF_MODE) \
	$(ONNX_FILE) > $(LOG_OUTPUT_DIR)/prompt_reference.txt

check:
	python $(COMPILER_DIR)/reference_computation/check_bin.py \
	$(DEBUG) > $(LOG_OUTPUT_DIR)/prompt_checker.txt
	@echo ""
	@echo "SUCCESS!"


# FSIM EXECUTION
################
fsim_inference: ## Infer FSIM with random values
	@echo ""
	@echo "RUN functional simulation (for NN)..."
	@date
	cd $(FSIM_DIR) && make -s nn_execute > $(LOG_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo ""
	@echo "FINAL_OUTPUT.BIN generated!"

fsim_single_layer:
	@echo ""
	@echo "RUN functional simulation (for single layer)..."
	@date
	cd $(FSIM_DIR) && make -s execute > $(LOG_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo ""
	@echo "FSIM DONE!"


# EXECUTION
###########
# Do "make compile_nn_fsim"
run: ## Run: NN compiler + VTA compiler + inference and check
	@make nn_compiler
	@make vta_compiler
	@make reference
	@make fsim_inference
	@make check

execute: ## Execute: only inference and check
	@make reference
	@make fsim_inference
	@make check


compile_and_run: ## Compile FSIM and run
	@make fsim_clean
	@make fsim_compile
	@make run

# CYCLE ACCURATE TSIM
#####################
tsim: # Work only with unamed files (e.g., test_gemm)
	@echo ""
	@echo "RUN TSIM..."
	@date
	cd $(TSIM_DIR) && sbt "runMain org.scalatest.run cli.ComputeApp" > $(LOG_OUTPUT_DIR)/tsim_report.txt
	@date
	@echo ""
	@echo "TSIM DONE!"
	

############################################################
############################################################

test_gemm:
	@make clean
	@echo "Copy VTA IR in compiler/output"
	@cp ./vta_ir/matmul_16x16.json $(COMPILER_OUTPUT_DIR)
	@echo "Generate random data"
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 input int32
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 weight int32
	@echo ""
	@echo "Compile VTA IR"
	@make vta_compiler
	@echo ""
	@echo "Compile FSIM"
	@make fsim_compile_single_layer
	@echo ""
	@echo "Execute FSIM"
	@make fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	@make tsim

test_alu:
	@make clean
	@echo "Copy VTA IR in compiler/output"
	@cp ./vta_ir/alu_16x16.json $(COMPILER_OUTPUT_DIR)
	@echo "Generate random data"
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 accumulator int32
	@echo ""
	@echo "Compile VTA IR"
	@make vta_compiler
	@echo ""
	@echo "Compile FSIM"
	@make fsim_compile_single_layer
	@echo ""
	@echo "Execute FSIM"
	@make fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	@make tsim

test_bias_expansion:
	@make clean
	@echo "Copy VTA IR in compiler/output"
	@cp ./vta_ir/matmul_bias_expansion.json $(COMPILER_OUTPUT_DIR)
	@echo "Generate random data"
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 32 32 input int32
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 32 32 weight int32
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 1 32 accumulator int32
	@echo ""
	@echo "Compile VTA IR"
	@make vta_compiler
	@echo ""
	@echo "Compile FSIM"
	@make fsim_compile_single_layer
	@echo ""
	@echo "Execute FSIM"
	@make fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	@make tsim

custom_insn:
	@python $(COMPILER_DIR)/utils/tests_instructions.py > $(LOG_OUTPUT_DIR)/prompt_vta_compiler.txt


############################################################
############################################################


# CREATE OUTPUTS DIRECTORIES
############################
$(COMPILER_OUTPUT_DIR):
	mkdir $(COMPILER_OUTPUT_DIR)
#$(SIMULATOR_OUTPUT_DIR):
#	mkdir $(SIMULATOR_OUTPUT_DIR)
$(LOG_OUTPUT_DIR):
	mkdir $(LOG_OUTPUT_DIR)


# CLEAN
#######
.PHONY: debug help clean force_clean
clean: | $(COMPILER_OUTPUT_DIR) $(LOG_OUTPUT_DIR) ## Clean the project generated files (standalone/compiler_output/ and standalone/log_output/)
	-rm $(COMPILER_OUTPUT_DIR)/*.*
	-rm $(LOG_OUTPUT_DIR)/*.*
#	-rm $(SIMULATOR_OUTPUT_DIR)/*.*

force_clean: ## Clean the FSIM directory
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
	@echo "LOG_OUTPUT_DIR: $(LOG_OUTPUT_DIR)"
	@echo "SRC_DIR: $(SRC_DIR)"
	@echo "COMPILER_DIR: $(COMPILER_DIR)"
	@echo "VTA_COMPILER_DIR: $(VTA_COMPILER_DIR)"


# HELP
######
# Return all the possible option for the makefile (must be referenced with ##)
help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":[ \t]*##[ \t]*"}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'
