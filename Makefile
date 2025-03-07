# MAKEFILE TO EXECUTE EXAMPLES (compile data and operation, then execute the functional simulator on it)
##############################
# Define the path of the Makefile
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

all: lenet5_layer1

# LeNet-5 layer 1 example (conv1 + ReLU + average pooling)
lenet5_layer1: | OUTPUT/
	python compiler/data_definition/main_matrix_generator.py examples.data_lenet5_conv1 > OUTPUT/prompt_data.txt
	python compiler/operations_definition/examples/insn_lenet5_conv1_relu_average_pooling.py > OUTPUT/prompt_insn.txt
	cd simulators/functional_simulator && make -s execute > $(MAKEFILE_DIR)OUTPUT/prompt_fsim.txt


# CREATE OUTPUT DIRECTORY
#########################
OUTPUT/:
	mkdir OUTPUT

# CLEAN
#######
.PHONY: clean
clean:
	make -f OUTPUT/Makefile clean