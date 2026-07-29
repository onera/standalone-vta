# Makefile to run examples: compile data and operations, then execute the simulator.
#
# Usage: make [CONFIG_FILE=vta_config.json] <target>

# ==============================================================================
# DIRECTORIES
# ==============================================================================

MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))
PROJECT_DIR  := $(abspath $(MAKEFILE_DIR)/..)

COMPILER_OUTPUT_DIR  := $(PROJECT_DIR)/compiler_output
SIMULATOR_OUTPUT_DIR := $(PROJECT_DIR)/simulators_output
HW_OUTPUT_DIR := $(PROJECT_DIR)/build
MILL=cd $(PROJECT_DIR) && ./mill

# The compiler scripts resolve their output dir from VTA_COMPILER_OUT (no '.git'
# walk). make runs them from examples/, so pin it to the project-level dir; this
# covers every invocation, including the ones without an '-o' flag (reference,
# check, random_raw_binary_generator).
export VTA_COMPILER_OUT := $(COMPILER_OUTPUT_DIR)
# The simulators write final_output*.bin to the simulator output dir; pin it so
# the checker (check_bin.py) reads the result from the same place. The simulator
# binaries bake in this same default (see modules/simulator/Makefile), so a plain
# run and the checker agree without extra flags.
export VTA_SIMULATOR_OUT := $(SIMULATOR_OUTPUT_DIR)

SRC_DIR          := $(PROJECT_DIR)/modules
COMPILER_DIR     := $(SRC_DIR)/compiler
LOG_OUTPUT_DIR   := $(PROJECT_DIR)/log_output

VTA_COMPILER_DIR := $(COMPILER_DIR)/vta_compiler
NN_COMPILER_DIR  := $(COMPILER_DIR)/nn_compiler
FSIM_DIR         := $(SRC_DIR)/simulator
TSIM_DIR         := $(SRC_DIR)/hardware
CONFIG_DIR       := $(PROJECT_DIR)/config

# ==============================================================================
# CONFIGURATION
# ==============================================================================

CONFIG_FILE ?= vta_config.json
CONFIG       = $(CONFIG_DIR)/$(CONFIG_FILE)

# Helper: read a LOG_*_WIDTH key from the config JSON and map to a C dtype name.
# Usage: $(call dtype,LOG_INP_WIDTH)  →  int8 | int16 | int32
dtype = $(shell python3 -c \
  "import json,sys; w=json.load(open('$(CONFIG)'))['$(1)']; \
   sys.stdout.write('int8' if w==3 else ('int16' if w==4 else 'int32'))")

INP_DTYPE := $(call dtype,LOG_INP_WIDTH)
WGT_DTYPE := $(call dtype,LOG_WGT_WIDTH)
ACC_DTYPE  := $(call dtype,LOG_ACC_WIDTH)

# ==============================================================================
# VARIABLES
# ==============================================================================

PYTHON_CMD ?= python
# PYTHON_CMD := python -m cProfile -o $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

# Lazy expansion: glob is resolved after the compiler has produced JSON files.
JSON_FILES = $(COMPILER_OUTPUT_DIR)/*.json

DEBUG           ?= False
DEBUG_PARSE     ?= True
COMPILE_SUMMARY ?= True
DRAM_JSON       ?= False
EXPANDBIAS_AT_COMPILATION ?= True
REF_MODE        ?= numpy   # ort | numpy | compare

NN_DEBUG_FLAG   := $(if $(filter True true,$(DEBUG_PARSE)),--debug,)
EXPANDBIAS_FLAG := $(if $(filter True true,$(EXPANDBIAS_AT_COMPILATION)),--expand-bias,)
VTA_DEBUG_FLAG  := $(if $(filter True true,$(DEBUG)),--debug,)
SUMMARY_FLAG    := $(if $(filter True true,$(COMPILE_SUMMARY)),--summary,)
DRAM_JSON_FLAG  := $(if $(filter True true,$(DRAM_JSON)),--dram-json,)

ONNX_FILE ?= onnx/qyolo_pattern.onnx
# onnx/qlinearconv_debug.onnx
# onnx/qyolo_qconvtranspose.onnx
# onnx/qyolo_qconv_maxpool_qconcat.onnx
# onnx/qyolo_pattern.onnx
# onnx/qyolo.onnx # -> around 30% of the value with +/-3

# ==============================================================================
# PHONY TARGETS
# ==============================================================================

.PHONY: all view_profiler \
        nn_compiler vta_compiler \
        fsim_clean fsim_compile fsim_compile_single_layer \
        exported_sv vsim_compile vsim_compile_single_layer \
        reference check check_vsim \
        fsim_inference fsim_single_layer vsim_single_layer vsim_inference tsim \
        run execute compile_and_run compile_all run_all \
        test_gemm test_alu custom_insn \
        clean force_clean cleaner clean_bin clean_csv clean_hw \
        debug help FORCE

# ==============================================================================
# TOP-LEVEL
# ==============================================================================

all: help

view_profiler: ## Open profiler output in snakeviz
	@snakeviz $(COMPILER_OUTPUT_DIR)/vta_compiler.prof

# ==============================================================================
# COMPILATION
# ==============================================================================

nn_compiler: ## Stage 1 - qONNX -> CPU parameters + VTA IRs
	$(MAKE) clean
	@echo "Parsing ONNX..."
	@date
	python $(NN_COMPILER_DIR)/vta_backend.py \
	$(NN_DEBUG_FLAG) \
	$(EXPANDBIAS_FLAG) \
	$(CONFIG) \
	$(ONNX_FILE) > $(LOG_OUTPUT_DIR)/prompt_vta_backend.txt
	@date

vta_compiler: ## Stage 2 - VTA IRs → VTA binary
	@echo "Compiling VTA IRs..."
	@date
	$(PYTHON_CMD) \
	$(VTA_COMPILER_DIR)/main_vta_compiler.py \
	$(VTA_DEBUG_FLAG) \
	$(SUMMARY_FLAG) \
	$(DRAM_JSON_FLAG) \
	$(CONFIG) \
	$(JSON_FILES) > $(LOG_OUTPUT_DIR)/prompt_vta_compiler.txt
	@date

# ==============================================================================
# FSIM BUILD
# ==============================================================================

fsim_clean: ## Clean the FSIM build directory
	$(MAKE) -C $(FSIM_DIR) clean

fsim_compile: ## Build fsim_nn
	$(MAKE) -C $(FSIM_DIR) CONFIG=$(CONFIG) build/fsim

fsim_compile_single_layer: ## Build fsim_single_layer
	$(MAKE) -C $(FSIM_DIR) CONFIG=$(CONFIG) build/fsim

# ==============================================================================
# VSIM BUILD (RTL)
# ==============================================================================


exported_sv:
	$(MILL) -Dvta.config.file=$(CONFIG_FILE) vta.hardware.emitVtaSimConfig


vsim_compile: exported_sv ## Generate Verilated C++ model and build fsim_nn_rtl
	$(MAKE) -C $(FSIM_DIR) CONFIG=$(CONFIG) build/vsim

vsim_compile_single_layer: exported_sv ## Generate Verilated C++ model and build fsim_single_layer_rtl
	$(MAKE) -C $(FSIM_DIR) CONFIG=$(CONFIG) build/vsim

# ==============================================================================
# REFERENCE
# ==============================================================================

reference: ## Compute ONNX reference output
	@echo "Computing reference..."
	python $(COMPILER_DIR)/reference_computation/reference_onnx.py \
	$(DEBUG) \
	$(REF_MODE) \
	$(ONNX_FILE) > $(LOG_OUTPUT_DIR)/prompt_reference.txt

check: ## Check FSIM output against reference
	python $(COMPILER_DIR)/reference_computation/check_bin.py \
	$(DEBUG) > $(LOG_OUTPUT_DIR)/prompt_checker.txt
	@echo ""
	@echo "SUCCESS!"

check_vsim: ## Check RTL simulation output against reference
	python $(COMPILER_DIR)/reference_computation/check_bin.py \
	  $(DEBUG) True > $(LOG_OUTPUT_DIR)/prompt_checker_rtl.txt
	@echo "SUCCESS!"

# ==============================================================================
# SIMULATION
# ==============================================================================

fsim_inference: ## Build (if needed) and run fsim_nn, capture output
	@echo "Running functional simulation (NN)..."
	@date
	$(MAKE) -s -C $(FSIM_DIR) CONFIG=$(CONFIG) fsim > $(LOG_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo "FINAL_OUTPUT.BIN generated!"

fsim_single_layer: ## Build (if needed) and run fsim_single_layer, capture output
	@echo "Running functional simulation (single layer)..."
	@date
	$(MAKE) -s -C $(FSIM_DIR) CONFIG=$(CONFIG) RUNTIME_FLAGS=--verbose fsim_single_layer > $(LOG_OUTPUT_DIR)/fsim_report.txt
	@date
	@echo "FSIM DONE!"

vsim_single_layer: exported_sv ## Build (if needed) and run fsim_single_layer_rtl, capture output
	$(MAKE) -s -C $(FSIM_DIR) CONFIG=$(CONFIG) vsim_single_layer > $(LOG_OUTPUT_DIR)/tsim_report.txt

vsim_inference: exported_sv ## Build (if needed) and run fsim_nn_rtl, capture output
	@echo "Running RTL simulation (NN)..."
	@date
	$(MAKE) -s -C $(FSIM_DIR) CONFIG=$(CONFIG) RUNTIME_FLAGS=--no-timeout vsim > $(LOG_OUTPUT_DIR)/tsim_report.txt
	@date
	@echo "FINAL_OUTPUT_RTL.BIN generated!"

tsim: ## Run cycle-accurate TSIM via Mill/ScalaTest
	@echo "Running TSIM..."
	@date
	$(MILL) -Dvta.config.file=$(CONFIG_FILE) \
	  vta.hardware.runMain org.scalatest.run cli.ComputeApp \
	  > $(LOG_OUTPUT_DIR)/tsim_report.txt
	@date
	@echo "TSIM DONE!"

# ==============================================================================
# ORCHESTRATION
# ==============================================================================

run: nn_compiler vta_compiler reference fsim_inference check ## Full pipeline: compile → simulate → check

execute: reference fsim_inference check ## Simulate and check (skip compilation)

compile_and_run: fsim_clean fsim_compile run ## Recompile FSIM then run full pipeline

compile_all: fsim_clean clean_hw fsim_compile vsim_compile ## Rebuild all simulators from scratch

run_all: run vsim_inference check_vsim ## Run both functional and RTL simulation

# ==============================================================================
# TESTS
# ==============================================================================

test_gemm: ## Test a 16×16 GEMM with random data
	$(MAKE) clean
	@echo "Copying VTA IR..."
	@cp ./vta_ir/matmul_16x16.json $(COMPILER_OUTPUT_DIR)
	@echo "Generating random input/weight data..."
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 input  $(INP_DTYPE)
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 weight $(WGT_DTYPE)
	@echo ""
	@echo "Compile VTA IR"
	$(MAKE) vta_compiler
	@echo ""
	@echo "Execute FSIM"
	$(MAKE) fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	$(MAKE) tsim

test_alu: ## Test a 16×16 ALU op with random data
	$(MAKE) clean
	@echo "Copying VTA IR..."
	@cp ./vta_ir/alu_16x16.json $(COMPILER_OUTPUT_DIR)
	@echo "Generating random accumulator data..."
	@python $(COMPILER_DIR)/utils/random_raw_binary_generator.py 16 16 accumulator $(ACC_DTYPE)
	@echo ""
	@echo "Compile VTA IR"
	$(MAKE) vta_compiler
	@echo ""
	@echo "Execute FSIM"
	$(MAKE) fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	$(MAKE) tsim

test_bias_expansion:
	$(MAKE) clean
	@echo "Copy VTA IR in compiler/output"
	@cp ./vta_ir/matmul_bias_expansion.json $(COMPILER_OUTPUT_DIR)
	@echo "Generate random data"
	$(PYTHON_CMD) $(COMPILER_DIR)/utils/random_raw_binary_generator.py 32 32 input $(INP_DTYPE)
	$(PYTHON_CMD) $(COMPILER_DIR)/utils/random_raw_binary_generator.py 32 32 weight $(WGT_DTYPE)
	$(PYTHON_CMD) $(COMPILER_DIR)/utils/random_raw_binary_generator.py 1 32 accumulator $(ACC_DTYPE)
	@echo ""
	@echo "Compile VTA IR"
	$(MAKE) vta_compiler
	@echo ""
	@echo "Execute FSIM"
	$(MAKE) fsim_single_layer
	@echo ""
	@echo "Execute TSIM"
	$(MAKE) tsim


custom_insn: ## Generate custom instruction test
	@python $(COMPILER_DIR)/utils/tests_instructions.py \
	  > $(LOG_OUTPUT_DIR)/prompt_vta_compiler.txt

# ==============================================================================
# CLEAN
# ==============================================================================

clean: | $(COMPILER_OUTPUT_DIR) $(SIMULATOR_OUTPUT_DIR) $(LOG_OUTPUT_DIR) ## Delete generated compiler and simulator output files
	-rm $(COMPILER_OUTPUT_DIR)/*.*
	-rm $(LOG_OUTPUT_DIR)/*.*
	-rm $(SIMULATOR_OUTPUT_DIR)/*.*

cleaner: clean fsim_clean clean_hw ## Delete generated files and the FSIM build directory

force_clean: cleaner ## backward compatible clean

clean_bin: | $(COMPILER_OUTPUT_DIR) ## Delete binary output files only
	-rm $(COMPILER_OUTPUT_DIR)/*.bin

clean_csv: | $(COMPILER_OUTPUT_DIR) ## Delete CSV output files only
	-rm $(COMPILER_OUTPUT_DIR)/*.csv

clean_hw: ## Clean Chisel/Mill build outputs
	-rm -rf $(HW_OUTPUT_DIR)/*

# ==============================================================================
# OUTPUT DIRECTORIES
# ==============================================================================

$(COMPILER_OUTPUT_DIR) $(SIMULATOR_OUTPUT_DIR) $(LOG_OUTPUT_DIR):
	mkdir -p $@

# ==============================================================================
# UTILITIES
# ==============================================================================

debug: ## Print all resolved paths and active configuration
	@echo "PROJECT_DIR:          $(PROJECT_DIR)"
	@echo "COMPILER_OUTPUT_DIR:  $(COMPILER_OUTPUT_DIR)"
	@echo "SIMULATOR_OUTPUT_DIR: $(SIMULATOR_OUTPUT_DIR)"
	@echo "LOG_OUTPUT_DIR:       $(LOG_OUTPUT_DIR)"
	@echo "SRC_DIR:              $(SRC_DIR)"
	@echo "COMPILER_DIR:         $(COMPILER_DIR)"
	@echo "CONFIG:               $(CONFIG)"
	@echo "INP_DTYPE:            $(INP_DTYPE)"
	@echo "WGT_DTYPE:            $(WGT_DTYPE)"
	@echo "ACC_DTYPE:            $(ACC_DTYPE)"
	@echo "PYTHON_CMD:           $(PYTHON_CMD)"

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?##' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":[^#]*##[ \t]*"}; {printf "\033[36m%-28s\033[0m %s\n", $$1, $$2}'
