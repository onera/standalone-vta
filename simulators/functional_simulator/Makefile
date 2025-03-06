# -------------------
# GENERAL INFORMATION
# -------------------

# Makefile documentation: https://www.gnu.org/software/make/manual/make.html 

# Remark on the current project:
# 	'main_simulator.cc': main function to execute the simulator
# 	'src/': simulator files
# 	'include/': simulator header files
# 	'config/': VTA simulator configuration files (headers and python scripts)
# 	'external_lib/': all the dependencies (headers and source files)
# 	'build/': object files and executable 'vta_simulator'


# ###################################################
# MAKEFILE 
# ###################################################

# -----------------
# VARIABLE SETTINGS
# -----------------
# Define the compilation option (compiler: gcc, flags: -Wall)
CC := g++ 
CFLAGS = -std=c++17 -Wall -g

# Define the path of the Makefile
MAKEFILE_DIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# Define the variables for the configuration (vta_config.json)
CONFIG_PY := python $(MAKEFILE_DIR)config/vta_config.py --defs # The command to execute the python script
VTA_DEFS := $(shell $(CONFIG_PY)) # To store the output of running CONFIG_PY
VTA_DEF_FLAGS := $(patsubst -D%,%,$(filter -D%,$(VTA_DEFS))) # To extract the "-D" flags from VTA_DEFS

# Define the main files
SRCS = $(MAKEFILE_DIR)main_simulator.cc $(MAKEFILE_DIR)simulator_functions.cc
SRCS += $(wildcard $(MAKEFILE_DIR)src/*.cc)
OBJS = $(patsubst $(MAKEFILE_DIR)main_simulator.cc, $(MAKEFILE_DIR)build/main_simulator.o, $(SRCS))
OBJS += $(patsubst $(MAKEFILE_DIR)simulator_functions.cc, $(MAKEFILE_DIR)build/simulator_functions.o, $(SRCS))
OBJS += $(patsubst $(MAKEFILE_DIR)src/%.cc, $(MAKEFILE_DIR)build/%.o, $(SRCS))

# Configuration files
CONFIG_FILES := $(wildcard $(MAKEFILE_DIR)../config/*)


# ---------------------
# COMPILATION & LINKING 
# ---------------------

# Generic commands
# ----------------
# Build everything
all: config $(MAKEFILE_DIR)build/vta_simulator

# Generate the configuration file log 
config: $(MAKEFILE_DIR)build/vta_config_def.txt

# Compile without linking (main_simulator.cc and src/*.cc)
compile_only: $(OBJS) 


# LINKING
# -------
# Dependencies: device_api -> runtime -> sim_driver -> sim_tlpp & virtual_memory

# Link the standalone VTA simulator executable
$(MAKEFILE_DIR)build/vta_simulator: $(MAKEFILE_DIR)build/vta_config_def.txt $(OBJS) lib_tvm
	$(CC) $(MAKEFILE_DIR)build/main_simulator.o $(MAKEFILE_DIR)build/simulator_functions.o \
	$(MAKEFILE_DIR)build/virtual_memory.o $(MAKEFILE_DIR)build/sim_tlpp.o \
	$(MAKEFILE_DIR)build/sim_driver.o \
	$(OBJ_LIB_TVM) -o $@
	@echo
	@echo "Successful link!"
	@echo "To run the executable: ./build/vta_simulator" 


# COMPILING SIMULATOR AND MAIN FILES (without linking: -c)
# ----------------------------------
# Compile the main file:
$(MAKEFILE_DIR)build/main_simulator.o: $(MAKEFILE_DIR)main_simulator.cc $(MAKEFILE_DIR)simulator_header.h
	$(CC) $(VTA_DEFS) $(CFLAGS) -o $(MAKEFILE_DIR)build/main_simulator.o -c $(MAKEFILE_DIR)main_simulator.cc

# Compile the function file (used by main):
$(MAKEFILE_DIR)build/simulator_functions.o: $(MAKEFILE_DIR)simulator_functions.cc $(MAKEFILE_DIR)simulator_header.h
	$(CC) $(VTA_DEFS) $(CFLAGS) -o $(MAKEFILE_DIR)build/simulator_functions.o -c $(MAKEFILE_DIR)simulator_functions.cc

# Compile simulator files
$(MAKEFILE_DIR)build/sim_driver.o: $(MAKEFILE_DIR)src/sim_driver.cc $(MAKEFILE_DIR)include/driver.h $(MAKEFILE_DIR)build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c $(MAKEFILE_DIR)src/sim_driver.cc -o $(MAKEFILE_DIR)build/sim_driver.o

$(MAKEFILE_DIR)build/sim_tlpp.o: $(MAKEFILE_DIR)src/sim_tlpp.cc $(MAKEFILE_DIR)include/sim_tlpp.h $(MAKEFILE_DIR)build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c $(MAKEFILE_DIR)src/sim_tlpp.cc -o $(MAKEFILE_DIR)build/sim_tlpp.o

$(MAKEFILE_DIR)build/virtual_memory.o: $(MAKEFILE_DIR)src/virtual_memory.cc $(MAKEFILE_DIR)include/virtual_memory.h $(MAKEFILE_DIR)build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c $(MAKEFILE_DIR)src/virtual_memory.cc -o $(MAKEFILE_DIR)build/virtual_memory.o

# Generic rules for all in one (require to execute $ make depend)
#build/%.o: src/%.cc build/vta_config_def.txt
#	$(CC) $(VTA_DEFS) $(CFLAGS) -o $@ -c $<


# COMPILING EXTERNAL LIBRARIES
# ----------------------------
# Define TVM LIB
SRC_LIB_TVM = $(wildcard $(MAKEFILE_DIR)external_lib/tvm/*.cc)
SRC_LIB_TVM += $(wildcard $(MAKEFILE_DIR)external_lib/tvm/**/*.cc)
OBJ_LIB_TVM = $(patsubst $(MAKEFILE_DIR)external_lib/tvm/%.cc, build/others/%.o, $(SRC_LIB_TVM))

# Generic rules
build/others/%.o: $(MAKEFILE_DIR)external_lib/tvm/%.cc
	$(CC) $(VTA_DEFS) $(CFLAGS) -o $@ -c $<	

# Aliases (to execute the compilation)
lib_tvm: $(OBJ_LIB_TVM)


# --------------
# EXECUTION AREA
# --------------
execute: $(MAKEFILE_DIR)build/vta_simulator
	$(MAKEFILE_DIR)build/vta_simulator

# -------------
# CONFIGURATION 
# -------------
# Run the configuration file (execute build rules if build/ does not exist)
$(MAKEFILE_DIR)build/vta_config_def.txt: $(CONFIG_FILES) | $(MAKEFILE_DIR)build/ $(MAKEFILE_DIR)build/others/
	$(CONFIG_PY) > $(MAKEFILE_DIR)build/vta_config_def.txt
	$(VTA_DEF_FLAGS)


# ----------------------
# CREATE BUILD DIRECTORY (if it does not exist)
# ----------------------
# Create the build directory
$(MAKEFILE_DIR)build/:
	mkdir $(MAKEFILE_DIR)build/
$(MAKEFILE_DIR)build/others/: | $(MAKEFILE_DIR)build/
	mkdir $(MAKEFILE_DIR)build/others/


# ----------------
# CLEAN and DEPEND
# ----------------
.PHONY: clean depend

# Clean the build directory
clean: 
	find $(MAKEFILE_DIR)build/ -type f -delete

# Generate dependencies
depend:
	makedepend $(SRCS)

# ###################################################
# AUTOMATICALLY GENERATED DEPENDENCIES ($ make depend)
# ###################################################
# RQ: Be careful: it may be the bad target (src/*.o rather than build/*.o)

# DO NOT DELETE
