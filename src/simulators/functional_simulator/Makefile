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
DEBUGFLAG ?= -DDEBUG_SIM=false
#-fsanitize=address

# C++ flags for verilated sources (DPI glue, verilated_device, Verilator runtime).
# Optimised for simulation throughput: no debug symbols, native tuning.
# These files sit on the per-cycle hot path so compiler optimisation matters.
VERILATED_CFLAGS = -std=c++17 -O3 -march=native -fomit-frame-pointer
# Optional external config path.
CONFIG ?= 
USE_CFG_FLAG= $(if $(CONFIG),--use-cfg $(CONFIG),)

# Define the variables for the configuration (vta_config.json)
# The command to execute the python script
CONFIG_PY := python config/vta_config.py --defs $(USE_CFG_FLAG) 
# To store the output of running CONFIG_PY
VTA_DEFS := $(shell $(CONFIG_PY))
# To extract the "-D" flags from VTA_DEFS
VTA_DEF_FLAGS := $(patsubst -D%,%,$(filter -D%,$(VTA_DEFS))) 

# Define the main files (exclude verilated_device.cc — only used in verilated target)
SRCS = $(filter-out src/verilated_device.cc, $(wildcard src/*.cc))
OBJS = $(patsubst src/%.cc, build/%.o, $(SRCS))

# Verilated RTL build settings
# Path to the generated VTAShell sources (produced by chisel code)
VTASHELL_DIR ?= ../cycle_accurate_simulator/build/emitted/vta-sim-shell
# Path to Verilator install (override if not in PATH)
VERILATOR      ?= verilator
VERILATOR_ROOT := $(shell $(VERILATOR) --getenv VERILATOR_ROOT 2>/dev/null)
VERILATOR_INC  := $(VERILATOR_ROOT)/include

VERILATED_OBJ_DIR = build/verilated
VERILATED_SRCS = src/dpi/dpi_host.cc src/dpi/dpi_mem.cc src/dpi/dpi_sim.cc \
                 src/verilated_device.cc
VERILATED_OBJS = $(patsubst src/%.cc, $(VERILATED_OBJ_DIR)/%.o, $(VERILATED_SRCS))

# Thread counts for Verilated simulation.
# SIM_THREADS:   parallel evaluation threads (scales with design complexity).
SIM_THREADS   ?= 8

# Trace format selection: fst (default) or vcd
# Override at build time: TRACE_FORMAT=vcd make verilate_vtashell && make verilated
TRACE_FORMAT ?= fst
ifeq ($(TRACE_FORMAT),vcd)
  VERILATOR_TRACE_FLAG = --trace-vcd
  TRACE_DEFINE         = -DTRACE_FORMAT_VCD=1
  TRACE_RUNTIME_LIB    = $(VERILATOR_INC)/verilated_vcd_c.cpp
else
  VERILATOR_TRACE_FLAG = --trace-fst
  TRACE_DEFINE         =
  TRACE_RUNTIME_LIB    = $(VERILATOR_INC)/verilated_fst_c.cpp
endif

# Verilator debug/assertion flags (verification layer)
# Override at build time: VERILATOR_DEBUG=1 make verilate_vtashell
VERILATOR_DEBUG ?= 0
ifeq ($(VERILATOR_DEBUG),1)
  VERILATOR_DEBUG_FLAGS = --assert \
    +incdir+$(VTASHELL_DIR)/verification/assume \
    +incdir+$(VTASHELL_DIR)/verification/assert \
    +incdir+$(VTASHELL_DIR)/verification/cover \
    +incdir+$(VTASHELL_DIR)/verification \
    $(VTASHELL_DIR)/verification/layers-VTAShell-Verification.sv \
    +define+layer\$$Verification\$$Debug
else
  VERILATOR_DEBUG_FLAGS =
endif

# Configuration files
CONFIG_FILES := $(wildcard ../config/*)

# ---------------------
# COMPILATION & LINKING 
# ---------------------

# Generic commands
# ----------------
# Build everything
all: config build/fsim_single_layer

nn_fsim: build/fsim_nn

# Build the Verilated RTL executable (requires Verilator + VTAShell.sv)
# Prerequisites:
#   1. cd ../cycle_accurate_simulator && sbt runMain "vta.StandaloneSimConfig" or ./mill emitVtaSimConfig
#   2. cd src/simulators/functional_simulator && make verilate_vtashell
#   3. make verilated

# Step 2: Run Verilator to generate C++ from VTAShell.sv (uses filelist.f for all sub-modules)
verilate_vtashell:
	mkdir -p $(VERILATED_OBJ_DIR)
	$(VERILATOR) --cc \
	  $(VERILATOR_TRACE_FLAG) \
	  -f $(VTASHELL_DIR)/filelist.f \
	  --top-module Test \
	  +incdir+$(VTASHELL_DIR) \
	  $(VERILATOR_DEBUG_FLAGS) \
	  --Mdir $(VERILATED_OBJ_DIR)/VVTAShell \
	  -O3 \
	  --x-assign fast \
	  --x-initial fast \
	  --build -j 0

# Step 3: Link the RTL simulator executable.
# sim_driver.o and functional_simulator.o must be recompiled with
# -DVERILATOR_BUILD_ENABLED so the VerilatedDevice dispatch is active.
$(VERILATED_OBJ_DIR)/sim_driver.o: src/sim_driver.cc include/driver.h \
    include/vta_device_backend.h build/vta_config_def.txt \
    | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(VERILATED_CFLAGS) -DVERILATOR_BUILD_ENABLED \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/fsim_nn.o: src/fsim_nn.cc \
    include/simulator_header.h include/vta_device_backend.h \
    | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(VERILATED_CFLAGS) -DVERILATOR_BUILD_ENABLED \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/fsim_single_layer.o: src/fsim_single_layer.cc \
    include/simulator_header.h include/vta_device_backend.h \
    | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(VERILATED_CFLAGS) -DVERILATOR_BUILD_ENABLED \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@


VVTASHELL_ARCHIVE = $(VERILATED_OBJ_DIR)/VVTAShell/VTest__ALL.a


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


build/fsim_nn_rtl: build/vta_config_def.txt $(OBJS) \
    lib_tvm verilate_vtashell \
    $(VERILATED_OBJ_DIR)/fsim_nn.o \
    $(VERILATED_OBJ_DIR)/sim_driver.o \
    $(VERILATED_OBJS) \
    build/simulator_functions.o build/virtual_memory.o build/sim_tlpp.o
	$(CC) $(VERILATED_CFLAGS) \
	  -DVL_USER_FINISH -I$(VERILATOR_INC) -I$(VERILATOR_INC)/vltstd \
	  $(VERILATED_OBJ_DIR)/fsim_nn.o \
	  build/simulator_functions.o \
	  build/virtual_memory.o build/sim_tlpp.o \
	  $(VERILATED_OBJ_DIR)/sim_driver.o \
	  $(VERILATED_OBJS) \
	  $(VVTASHELL_ARCHIVE) \
	  $(VERILATOR_INC)/verilated.cpp \
	  $(VERILATOR_INC)/verilated_dpi.cpp \
	  $(VERILATOR_INC)/verilated_threads.cpp \
	  $(TRACE_RUNTIME_LIB) \
	  $(OBJ_LIB_TVM) \
	  -lz -lpthread -o $@


build/fsim_single_layer_rtl: build/vta_config_def.txt $(OBJS) \
    lib_tvm verilate_vtashell \
    $(VERILATED_OBJ_DIR)/fsim_single_layer.o \
    $(VERILATED_OBJ_DIR)/sim_driver.o \
    $(VERILATED_OBJS) \
    build/simulator_functions.o build/virtual_memory.o build/sim_tlpp.o
	$(CC) $(VERILATED_CFLAGS) \
	  -DVL_USER_FINISH -I$(VERILATOR_INC) -I$(VERILATOR_INC)/vltstd \
	  $(VERILATED_OBJ_DIR)/fsim_single_layer.o \
	  build/simulator_functions.o \
	  build/virtual_memory.o build/sim_tlpp.o \
	  $(VERILATED_OBJ_DIR)/sim_driver.o \
	  $(VERILATED_OBJS) \
	  $(VVTASHELL_ARCHIVE) \
	  $(VERILATOR_INC)/verilated.cpp \
	  $(VERILATOR_INC)/verilated_dpi.cpp \
	  $(VERILATOR_INC)/verilated_threads.cpp \
	  $(TRACE_RUNTIME_LIB) \
	  $(OBJ_LIB_TVM) \
	  -lz -lpthread -o $@
# COMPILING SIMULATOR AND MAIN FILES (without linking: -c)
# ----------------------------------
# Compile the main file:
build/fsim_single_layer.o: build/vta_config_def.txt src/fsim_single_layer.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -o build/fsim_single_layer.o -c src/fsim_single_layer.cc

build/fsim_nn.o: build/vta_config_def.txt src/fsim_nn.cc include/simulator_header.h
	$(CC) $(VTA_DEFS) $(DEBUGFLAG) $(CFLAGS) -o build/fsim_nn.o -c src/fsim_nn.cc

# Compile the function file (used by main):
build/simulator_functions.o: build/vta_config_def.txt src/simulator_functions.cc include/simulator_header.h
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
	$(CC) $(VTA_DEFS) $(VERILATED_CFLAGS) -DVERILATOR_BUILD_ENABLED \
	  -DVL_USER_FINISH \
	  -I$(VERILATOR_INC) -I$(VERILATOR_INC)/vltstd -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

$(VERILATED_OBJ_DIR)/verilated_device.o: src/verilated_device.cc | $(VERILATED_OBJ_DIR)/
	$(CC) $(VTA_DEFS) $(VERILATED_CFLAGS) -DVERILATOR_BUILD_ENABLED $(TRACE_DEFINE) \
	  -DVL_USER_FINISH \
	  -I$(VERILATOR_INC) -I$(VERILATOR_INC)/vltstd -I$(VERILATED_OBJ_DIR)/VVTAShell \
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
build/vta_config_def.txt: $(CONFIG_FILES) $(CONFIG) | build/ build/others/
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
