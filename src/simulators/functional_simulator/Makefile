# Makefile documentation: https://www.gnu.org/software/make/manual/make.html
#
# Directory layout:
#   src/          simulator C++ sources
#   include/      simulator headers
#   config/       VTA hardware configuration (JSON + Python scripts)
#   external_lib/ vendored dependencies
#   build/        object files and executables

# ==============================================================================
# VARIABLES
# ==============================================================================

CC              := g++
CFLAGS           = -std=c++17 -lstdc++fs -Wall -g -MMD -MP
# CFLAGS         = -std=c++17 -lstdc++fs -fsanitize=address -g -MMD -MP
DEBUGFLAG       ?= -DDEBUG_SIM=false

# Verilated objects sit on the per-cycle hot path — optimise for throughput.
VERILATED_CFLAGS = -std=c++17 -O3 -march=native -fomit-frame-pointer -MMD -MP

# VTA hardware configuration, defaults to ../../../config/vta_config.json
# Override at build time: make CONFIG=path/to/config.json [target]
CONFIG          ?=
USE_CFG_FLAG     = $(if $(CONFIG),--use-cfg $(CONFIG),)
VTA_CONFIG_H    := build/vta_config.h
VTA_CONFIG_ARGS_FILE := build/.vta_config_args
FORCE_INCLUDE    = -include $(VTA_CONFIG_H)
CONFIG_FILES    := $(wildcard ../config/*)

# Functional simulator sources and objects
# (verilated_device.cc is verilated-RTL-only and compiled separately)
SRCS = $(filter-out src/verilated_device.cc, $(wildcard src/*.cc))
OBJS = $(patsubst src/%.cc, build/%.o, $(SRCS))

# External TVM library
SRC_LIB_TVM = $(wildcard external_lib/tvm/*.cc) \
               $(wildcard external_lib/tvm/**/*.cc)
OBJ_LIB_TVM = $(patsubst external_lib/tvm/%.cc, build/others/%.o, $(SRC_LIB_TVM))

# ---------------------
# Verilated RTL build
# ---------------------

VTASHELL_DIR     ?= ../cycle_accurate_simulator/build/emitted/vta-sim-shell
VERILATOR        ?= verilator
VERILATOR_ROOT   := $(shell $(VERILATOR) --getenv VERILATOR_ROOT 2>/dev/null)
VERILATOR_INC    := $(VERILATOR_ROOT)/include
VERILATED_OBJ_DIR = build/verilated

VERILATED_SRCS = src/dpi/dpi_host.cc src/dpi/dpi_mem.cc src/dpi/dpi_sim.cc \
                 src/verilated_device.cc
VERILATED_OBJS = $(patsubst src/%.cc, $(VERILATED_OBJ_DIR)/%.o, $(VERILATED_SRCS))

VVTASHELL_ARCHIVE = $(VERILATED_OBJ_DIR)/VVTAShell/VTest__ALL.a

# Include flags shared by all objects that link against the Verilator runtime
VERILATOR_INCLUDES = -I$(VERILATOR_INC) -I$(VERILATOR_INC)/vltstd \
                     -I$(VERILATED_OBJ_DIR)/VVTAShell

# Objects common to both RTL link targets
VERILATED_COMMON_OBJS = \
  build/simulator_functions.o \
  build/virtual_memory.o \
  build/sim_tlpp.o \
  $(VERILATED_OBJ_DIR)/sim_driver.o \
  $(VERILATED_OBJS)

# Simulation threads used by the verilated VTA
SIM_THREADS ?= 8

# Trace format: fst (default) or vcd
# Override: TRACE_FORMAT=vcd make verilate_vtashell && make <rtl-target>
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

# Verilator runtime sources compiled directly into each RTL executable
VERILATED_RUNTIME_SRCS = \
  $(VERILATOR_INC)/verilated.cpp \
  $(VERILATOR_INC)/verilated_dpi.cpp \
  $(VERILATOR_INC)/verilated_threads.cpp \
  $(TRACE_RUNTIME_LIB)

# Optional Verilator assertion layer (VERILATOR_DEBUG=1 make verilate_vtashell)
VERILATOR_DEBUG ?= 0
ifeq ($(VERILATOR_DEBUG),1)
  VERILATOR_DEBUG_FLAGS = --assert \
    +incdir+$(VTASHELL_DIR)/verification/assume \
    +incdir+$(VTASHELL_DIR)/verification/assert \
    +incdir+$(VTASHELL_DIR)/verification/cover \
    +incdir+$(VTASHELL_DIR)/verification \
    $(VTASHELL_DIR)/verification/layers-VTAShell-Verification.sv \
    +define+layer\$$Verification\$$DebugLayer
else
  VERILATOR_DEBUG_FLAGS =
endif

# ==============================================================================
# PHONY TARGETS
# ==============================================================================

.PHONY: all config compile_only lib_tvm \
        verilate_vtashell execute nn_execute \
				fsim fsim_single_layer \
				vsim vsim_single_layer \
        clean depend FORCE

# ==============================================================================
# TOP-LEVEL TARGETS
# ==============================================================================

all:
	@echo "Usage: make [CONFIG=path/to/config.json] <target>"
	@echo ""
	@echo "Functional simulator:"
	@echo "  fsim_single_layer   build and run fsim_single_layer"
	@echo "  fsim                build and run fsim_nn"
	@echo ""
	@echo "RTL simulator (require generating the VTA hardware first):"
	@echo "  vsim_single_layer   build and run fsim_single_layer_rtl"
	@echo "  vsim                build and run fsim_nn_rtl"
	@echo ""
	@echo "Utilities:"
	@echo "  config              regenerate build/vta_config.h from the active config JSON"
	@echo "  compile_only        compile all functional simulator objects without linking"
	@echo "  clean               delete all build artefacts"

# Functional simulators
fsim_single_layer: build/fsim_single_layer
	./build/fsim_single_layer

fsim: build/fsim_nn
	./build/fsim_nn

# Verilated simulators
vsim: build/fsim_nn_rtl
	./build/fsim_nn_rtl --verilator --no-timeout

vsim_single_layer: build/fsim_single_layer_rtl
	./build/fsim_single_layer_rtl --verilator --no-timeout

# Generate the VTA config header (implicit in every compile, explicit here for convenience)
config: $(VTA_CONFIG_H)

compile_only: $(OBJS)

execute:
	build/fsim_single_layer

nn_execute:
	build/fsim_nn

# ==============================================================================
# FUNCTIONAL SIMULATOR — LINK
# ==============================================================================

build/fsim_single_layer: $(OBJS) $(OBJ_LIB_TVM) | build/
	$(CC) $(CFLAGS) \
	  build/fsim_single_layer.o build/simulator_functions.o \
	  build/virtual_memory.o build/sim_tlpp.o build/sim_driver.o \
	  $(OBJ_LIB_TVM) -o $@

build/fsim_nn: $(OBJS) $(OBJ_LIB_TVM) | build/
	$(CC) $(CFLAGS) \
	  build/fsim_nn.o build/simulator_functions.o \
	  build/virtual_memory.o build/sim_tlpp.o build/sim_driver.o \
	  $(OBJ_LIB_TVM) -o $@

# ==============================================================================
# RTL SIMULATOR — VERILATE + LINK
#
# Workflow:
#   1. cd ../cycle_accurate_simulator && ./mill emitVtaSimConfig
#   2. make build/fsim_{single_layer,nn}_rtl
# ==============================================================================


$(VVTASHELL_ARCHIVE): $(VTASHELL_DIR)/filelist.f | $(VERILATED_OBJ_DIR)/
	$(VERILATOR) --cc \
	  $(VERILATOR_TRACE_FLAG) \
	  -f $< \
	  --top-module Test \
	  +incdir+$(VTASHELL_DIR) \
	  $(VERILATOR_DEBUG_FLAGS) \
	  --Mdir $(VERILATED_OBJ_DIR)/VVTAShell \
	  -O3 \
	  --threads $(SIM_THREADS) \
	  --x-assign fast \
	  --x-initial fast \
	  --build -j 0

build/fsim_single_layer_rtl: $(VERILATED_OBJ_DIR)/fsim_single_layer.o \
    $(VERILATED_COMMON_OBJS) $(VVTASHELL_ARCHIVE) $(OBJ_LIB_TVM) | build/
	$(CC) $(VERILATED_CFLAGS) -DVL_USER_FINISH $(VERILATOR_INCLUDES) \
	  $(VERILATED_OBJ_DIR)/fsim_single_layer.o \
	  $(VERILATED_COMMON_OBJS) $(VVTASHELL_ARCHIVE) \
	  $(VERILATED_RUNTIME_SRCS) $(OBJ_LIB_TVM) \
	  -lz -lpthread -o $@

build/fsim_nn_rtl: $(VERILATED_OBJ_DIR)/fsim_nn.o \
    $(VERILATED_COMMON_OBJS) $(VVTASHELL_ARCHIVE) $(OBJ_LIB_TVM) | build/
	$(CC) $(VERILATED_CFLAGS) -DVL_USER_FINISH $(VERILATOR_INCLUDES) \
	  $(VERILATED_OBJ_DIR)/fsim_nn.o \
	  $(VERILATED_COMMON_OBJS) $(VVTASHELL_ARCHIVE) \
	  $(VERILATED_RUNTIME_SRCS) $(OBJ_LIB_TVM) \
	  -lz -lpthread -o $@

# ==============================================================================
# COMPILE — FUNCTIONAL SIMULATOR  (build/%.o)
# ==============================================================================

build/%.o: src/%.cc $(VTA_CONFIG_H) | build/
	$(CC) $(CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) -c $< -o $@

# ==============================================================================
# COMPILE — VERILATED OBJECTS  (build/verilated/%.o)
# ==============================================================================

# src/sim_driver.cc and src/fsim_*.cc compiled against the Verilated model
$(VERILATED_OBJ_DIR)/%.o: src/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) \
	  -DVERILATOR_BUILD_ENABLED \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

# DPI glue — no DEBUGFLAG, tightly coupled to Verilator internals
$(VERILATED_OBJ_DIR)/dpi/%.o: src/dpi/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/dpi/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# Verilated device clock loop — also carries the trace-format define
$(VERILATED_OBJ_DIR)/verilated_device.o: src/verilated_device.cc $(VTA_CONFIG_H) \
    | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH $(TRACE_DEFINE) \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# ==============================================================================
# COMPILE — EXTERNAL TVM LIBRARY  (build/others/%.o)
# ==============================================================================

build/others/%.o: external_lib/tvm/%.cc $(VTA_CONFIG_H) | build/others/
	$(CC) $(CFLAGS) $(FORCE_INCLUDE) -c $< -o $@

lib_tvm: $(OBJ_LIB_TVM)

# ==============================================================================
# VTA CONFIGURATION HEADER
# ==============================================================================

# Refreshes the stamp only when USE_CFG_FLAG changes, avoiding spurious rebuilds.
$(VTA_CONFIG_ARGS_FILE): FORCE | build/
	@printf '%s' '$(USE_CFG_FLAG)' > $@.tmp
	@cmp -s $@.tmp $@ && rm $@.tmp || mv $@.tmp $@

FORCE:

# Regenerates when the active config JSON changes or a different config is selected.
# Usage:  make config                         (uses ../config/vta_config.json)
#         make config CONFIG=path/to/x.json   (uses a custom JSON)
$(VTA_CONFIG_H): $(CONFIG_FILES) $(CONFIG) $(VTA_CONFIG_ARGS_FILE) | build/
	python config/vta_config.py --export-header $@ $(USE_CFG_FLAG)

# ==============================================================================
# BUILD DIRECTORIES
# ==============================================================================

build/ build/others/ $(VERILATED_OBJ_DIR)/ $(VERILATED_OBJ_DIR)/dpi/:
	mkdir -p $@

# ==============================================================================
# HOUSEKEEPING
# ==============================================================================

clean:
	-find build/ -type f -delete

depend:
	makedepend $(SRCS)

# Auto-generated header dependency files (produced by -MMD -MP)
-include $(wildcard build/*.d build/others/*.d \
  $(VERILATED_OBJ_DIR)/*.d $(VERILATED_OBJ_DIR)/dpi/*.d)
