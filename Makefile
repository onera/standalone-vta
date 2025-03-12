# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# Define the path of the Makefile
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# Define the default value if it is not provided
FILENAME ?= lenet5_layer1

# Define the name of the files to use
DATA_FILE := examples.data_$(FILENAME)
INSN_FILE := insn_$(FILENAME)

# Default example
all: $(FILENAME)

# Execution with specified FILENAME
$(FILENAME): | compiler_output/ simulators_output/
	python compiler/data_definition/main_matrix_generator.py $(DATA_FILE) > compiler_output/prompt_data.txt
	python compiler/operations_definition/examples/$(INSN_FILE).py > compiler_output/prompt_insn.txt
	cd simulators/functional_simulator && make -s execute > $(MAKEFILE_DIR)simulators_output/fsim_report.txt


# LIST THE POSSIBLE FILENAMES
#############################
DATA_DIR := compiler/data_definition/examples
INSN_DIR := compiler/operations_definition/examples

DATA_FILES := $(wildcard $(DATA_DIR)/data_*)
INSN_FILES := $(wildcard $(INSN_DIR)/insn_*)

DATA_FILENAMES := $(patsubst $(DATA_DIR)/data_%.py,%,$(DATA_FILES))
INSN_FILENAMES := $(patsubst $(INSN_DIR)/insn_%.py,%,$(INSN_FILES))

# Find common filenames
COMMON_FILENAMES := $(foreach FILE,$(DATA_FILENAMES),\
                      $(if $(findstring $(FILE),$(INSN_FILENAMES)),$(FILE)))

POSSIBLE_FILENAMES := $(COMMON_FILENAMES)

.PHONY: list
list:
	@echo "Possible FILENAME values are:"
	@for name in $(POSSIBLE_FILENAMES); do \
		echo $$name; \
	done
	@echo "" && echo "Command line: make FILENAME=<filename>"

# Provide some help
.PHONY: help
help: 
	@echo "To execute the command:"
	@echo "  1 - Consult the list of available examples: make list"
	@echo "  2 - Execute an examples: make FILENAME=<filename>"
	@echo "  3 - Check within compiler_output/ folder to see the compiler result," 
	@echo "      and within simulators_output/ folder to see the simulators results"
	@echo "  4 - Clean the folders with: make clean"


# CREATE OUTPUTS DIRECTORIES
############################
compiler_output/:
	mkdir compiler_output
simulators_output/:
	mkdir simulators_output


# CLEAN
#######
.PHONY: clean
clean:
	rm $(MAKEFILE_DIR)compiler_output/*.*
	rm $(MAKEFILE_DIR)simulators_output/*.*