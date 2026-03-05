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
CFLAGS = -std=c++17 -lstdc++fs -Wall -g
# CFLAGS = -std=c++17 -lstdc++fs -fsanitize=address -g
DEBUGFLAG := -DDEBUG_SIM=false
#-fsanitize=address 

# Define the variables for the configuration (vta_config.json)
CONFIG_PY := python config/vta_config.py --defs # The command to execute the python script
VTA_DEFS := $(shell $(CONFIG_PY)) # To store the output of running CONFIG_PY
VTA_DEF_FLAGS := $(patsubst -D%,%,$(filter -D%,$(VTA_DEFS))) # To extract the "-D" flags from VTA_DEFS

# Define the main files (exclude verilated_device.cc — only used in verilated target)
SRCS = $(filter-out src/verilated_device.cc, $(wildcard src/*.cc))
OBJS = $(patsubst src/%.cc, build/%.o, $(SRCS))

# Verilated RTL build settings
# Path to the generated VTAShell sources (produced by ./mill emitVerilog)
VTASHELL_DIR ?= ../cycle_accurate_simulator/generatedResources
# Path to Verilator install (override if not in PATH)
VERILATOR      ?= verilator
VERILATOR_ROOT := $(shell $(VERILATOR) --getenv VERILATOR_ROOT 2>/dev/null)
VERILATOR_INC  := $(VERILATOR_ROOT)/include

VERILATED_OBJ_DIR = build/verilated
VERILATED_SRCS = src/dpi/dpi_host.cc src/dpi/dpi_mem.cc src/dpi/dpi_sim.cc \
                 src/verilated_device.cc
VERILATED_OBJS = $(patsubst src/%.cc, $(VERILATED_OBJ_DIR)/%.o, $(VERILATED_SRCS))

# Configuration files
CONFIG_FILES := $(wildcard ../config/*)


# ---------------------
# COMPILATION & LINKING 
# ---------------------

# Generic commands
# ----------------
# Build everything
all: config build/functional_simulator

nn_fsim: build/fsim_nn

# Build the Verilated RTL executable (requires Verilator + VTAShell.sv)
# Prerequisites:
#   1. cd ../cycle_accurate_simulator && ./mill emitVerilog
#   2. cd src/simulators/functional_simulator && make verilate_vtashell
#   3. make verilated
verilated: config build/functional_simulator_rtl

# Step 2: Run Verilator to generate C++ from VTAShell.sv (uses filelist.f for all sub-modules)
verilate_vtashell:
	mkdir -p $(VERILATED_OBJ_DIR)
	$(VERILATOR) --cc \
	  --trace-fst \
	  -f $(VTASHELL_DIR)/filelist.f \
	  --top-module VTAShell \
	  +incdir+$(VTASHELL_DIR) \
	  --Mdir $(VERILATED_OBJ_DIR)/VVTAShell \
	  --build -j 0

# Step 3: Link the RTL simulator executable.
# sim_driver.o and functional_simulator.o must be recompiled with
# -DSTANDALONE_BUILD so the VerilatedDevice dispatch is active.
$(VERILATED_OBJ_DIR)/sim_driver.o: src/sim_driver.cc include/driver.h \
    include/vta_device_backend.h build/vta_config_def.txt \
    | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -DSTANDALONE_BUILD \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/functional_simulator.o: src/functional_simulator.cc \
    include/simulator_header.h include/vta_device_backend.h \
    | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -DSTANDALONE_BUILD \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

VVTASHELL_ARCHIVE = $(VERILATED_OBJ_DIR)/VVTAShell/VVTAShell__ALL.a

build/functional_simulator_rtl: build/vta_config_def.txt \
    lib_tvm verilate_vtashell \
    $(VERILATED_OBJ_DIR)/functional_simulator.o \
    $(VERILATED_OBJ_DIR)/sim_driver.o \
    $(VERILATED_OBJS) \
    build/simulator_functions.o build/virtual_memory.o build/sim_tlpp.o
	$(CC) $(CFLAGS) \
	  $(VERILATED_OBJ_DIR)/functional_simulator.o \
	  build/simulator_functions.o \
	  build/virtual_memory.o build/sim_tlpp.o \
	  $(VERILATED_OBJ_DIR)/sim_driver.o \
	  $(VERILATED_OBJS) \
	  $(VVTASHELL_ARCHIVE) \
	  $(VERILATOR_INC)/verilated.cpp \
	  $(VERILATOR_INC)/verilated_threads.cpp \
	  $(VERILATOR_INC)/verilated_fst_c.cpp \
	  $(OBJ_LIB_TVM) \
	  -lz -o $@

# Generate the configuration file log 
config: build/vta_config_def.txt

# Compile without linking (main_simulator.cc and src/*.cc)
compile_only: $(OBJS) 


# LINKING
# -------
# Dependencies: device_api -> runtime -> sim_driver -> sim_tlpp & virtual_memory

# Link the standalone VTA simulator executable
build/fsim_single_layer: build/vta_config_def.txt $(OBJS) lib_tvm
	$(CC) $(CFLAGS) build/fsim_single_layer.o build/simulator_functions.o \
	build/virtual_memory.o build/sim_tlpp.o \
	build/sim_driver.o \
	$(OBJ_LIB_TVM) -o $@
# 	@echo
# 	@echo "Successful link!"
# 	@echo "To run the executable: ./build/functional_simulator"


build/fsim_nn: build/vta_config_def.txt $(OBJS) lib_tvm
	$(CC) $(CFLAGS) build/fsim_nn.o build/simulator_functions.o \
	build/virtual_memory.o build/sim_tlpp.o \
	build/sim_driver.o \
	$(OBJ_LIB_TVM) -o $@


# COMPILING SIMULATOR AND MAIN FILES (without linking: -c)
# ----------------------------------
# Compile the main file:
build/fsim_single_layer.o: src/fsim_single_layer.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -o build/fsim_single_layer.o -c src/fsim_single_layer.cc

build/fsim_nn.o: src/fsim_nn.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -o build/fsim_nn.o -c src/fsim_nn.cc

# Compile the function file (used by main):
build/simulator_functions.o: src/simulator_functions.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -o build/simulator_functions.o -c src/simulator_functions.cc

# Compile simulator files
build/sim_driver.o: src/sim_driver.cc include/driver.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -c src/sim_driver.cc -o build/sim_driver.o

build/sim_tlpp.o: src/sim_tlpp.cc include/sim_tlpp.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -c src/sim_tlpp.cc -o build/sim_tlpp.o

build/virtual_memory.o: src/virtual_memory.cc include/virtual_memory.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -c src/virtual_memory.cc -o build/virtual_memory.o

build/reshape.o: src/reshape.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -c src/reshape.cc -o build/reshape.o

build/cpu_functions.o: src/cpu_functions.cc include/cpu_functions.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -c src/cpu_functions.cc -o build/cpu_functions.o

# Generic rules for all in one (require to execute $ make depend)
#build/%.o: src/%.cc build/vta_config_def.txt
#	$(CC) $(VTA_DEFS) $(CFLAGS) -o $@ -c $<


# COMPILING VERILATED DEVICE SOURCES
# ------------------------------------
$(VERILATED_OBJ_DIR)/dpi/%.o: src/dpi/%.cc | $(VERILATED_OBJ_DIR)/dpi/
	$(CC) $(VTA_DEFS) $(CFLAGS) -DSTANDALONE_BUILD \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/verilated_device.o: src/verilated_device.cc | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(CFLAGS) -DSTANDALONE_BUILD \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/:
	mkdir -p $(VERILATED_OBJ_DIR)
$(VERILATED_OBJ_DIR)/dpi/: | $(VERILATED_OBJ_DIR)/
	mkdir -p $(VERILATED_OBJ_DIR)/dpi

# COMPILING EXTERNAL LIBRARIES
# ----------------------------
# Define TVM LIB
SRC_LIB_TVM = $(wildcard external_lib/tvm/*.cc)
SRC_LIB_TVM += $(wildcard external_lib/tvm/**/*.cc)
OBJ_LIB_TVM = $(patsubst external_lib/tvm/%.cc, build/others/%.o, $(SRC_LIB_TVM))

# Generic rules
build/others/%.o: external_lib/tvm/%.cc
	$(CC) $(VTA_DEFS) $(CFLAGS) -o $@ -c $<	

# Aliases (to execute the compilation)
lib_tvm: $(OBJ_LIB_TVM)


# --------------
# EXECUTION AREA
# --------------
execute: 
	build/fsim_single_layer


nn_execute: 
	build/fsim_nn

# -------------
# CONFIGURATION 
# -------------
# Run the configuration file (execute build rules if build/ does not exist)
build/vta_config_def.txt: $(CONFIG_FILES) | build/ build/others/
	$(CONFIG_PY) > build/vta_config_def.txt
	$(VTA_DEF_FLAGS)


# ----------------------
# CREATE BUILD DIRECTORY (if it does not exist)
# ----------------------
# Create the build directory
build/:
	mkdir build/
build/others/: | build/
	mkdir build/others/


# ----------------
# CLEAN and DEPEND
# ----------------
.PHONY: clean depend

# Clean the build directory
clean: 
	-find build/ -type f -delete

# Generate dependencies
depend:
	makedepend $(SRCS)

# ###################################################
# AUTOMATICALLY GENERATED DEPENDENCIES ($ make depend)
# ###################################################
# RQ: Be careful: it may be the bad target (src/*.o rather than build/*.o)

# DO NOT DELETE
