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

# Verilated objects sit on the per-cycle hot path - optimise for throughput.
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
# X-state init: "fast" zero-fills uninitialised vars/mems (default, deterministic).
# Override with VERILATOR_XFLAGS="--x-assign unique --x-initial unique" to seed
# X-state from a Verilator-internal RNG, exposing read-before-write hazards.
VERILATOR_XFLAGS ?= --x-assign fast --x-initial fast

# Compile-time register / memory randomization (independent of --x-initial).
# The emitted SystemVerilog gates its initial-block randomization on the
# RANDOMIZE_REG_INIT and RANDOMIZE_MEM_INIT macros; enabling them seeds the
# corresponding state with random values at time 0. By default the SV uses
# $random (deterministic, seeded by Verilator); set NONDET_RANDOM=1 to switch
# to $urandom for a non-reproducible stream. These are compile-time +define+s,
# not a make dependency, so force an archive rebuild after toggling them:
#   rm -f build/verilated/VVTAShell/VTest__ALL.a && make RANDOMIZE=1 vsim
#   RANDOMIZE=1      randomize both registers and memories
#   RANDOMIZE_REG=1  registers only
#   RANDOMIZE_MEM=1  memories only
#   NONDET_RANDOM=1  use $urandom instead of $random
RANDOMIZE       ?= 0
RANDOMIZE_REG   ?= $(RANDOMIZE)
RANDOMIZE_MEM   ?= $(RANDOMIZE)
NONDET_RANDOM   ?= 0

RANDOMIZE_FLAGS :=
ifeq ($(RANDOMIZE_REG),1)
  RANDOMIZE_FLAGS += +define+RANDOMIZE_REG_INIT
endif
ifeq ($(RANDOMIZE_MEM),1)
  RANDOMIZE_FLAGS += +define+RANDOMIZE_MEM_INIT
endif
ifeq ($(NONDET_RANDOM),1)
  RANDOMIZE_FLAGS += '+define+RANDOM=$$urandom'
endif

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

# Simulation threads used by the verilated VTA
SIM_THREADS ?= 8

# Trace format: fst (default) or vcd
# Override: rm -f build/verilated/VVTAShell/VTest__ALL.a && TRACE_FORMAT=vcd make <rtl-target>
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

# SystemVerilog verification layer.
#
# firtool emits per-module verification logic into verification/ (printfs and
# the matching `bind X X_Verification verification ()` umbrellas) and
# verification/assert/ (assertion modules + `bind X X_Verification_Assert
# verification_assert ()` umbrellas). filelist.f lists the module bodies but
# not the umbrellas, so the binds only fire when a top-level umbrella file is
# passed to verilator on the command line.
#
# layers-Test-Verification-Assert.sv is the top of the assert chain and
# transitively includes the printf chain, so a single source file covers
# both. Assume/Cover umbrellas exist but are empty in the current emit.
#
# The assert layer is always on. VTA_VERIF_DEBUG=1 additionally gates in the
# firtool debug printfs (e.g. "[Compute] start gemm"), guarded in the emitted
# SV by `ifdef layer$Verification$DebugLayer`. Both knobs are compile-time
# +define+s - rebuild the Verilated archive after changing them:
#   rm -f build/verilated/VVTAShell/VTest__ALL.a && VTA_VERIF_DEBUG=1 make vsim
VERIFICATION_TOP = $(VTASHELL_DIR)/verification/assert/layers-Test-Verification-Assert.sv

VERIFICATION_INCDIRS = \
  +incdir+$(VTASHELL_DIR)/verification \
  +incdir+$(VTASHELL_DIR)/verification/assert \
  +incdir+$(VTASHELL_DIR)/verification/assume \
  +incdir+$(VTASHELL_DIR)/verification/cover

VERIFICATION_CONDS = \
  '+define+ASSERT_VERBOSE_COND=!Test.reset' \
  '+define+PRINTF_COND=!Test.reset' \
  '+define+STOP_COND=!Test.reset'

VTA_VERIF_DEBUG ?= 0
# When the SV debug printf layer is gated in, advertise it to the C++ side too
# so fsim_main can default --sv-log to simulators_output/verilator.log instead
# of letting the firtool stream flood stderr.
VTA_VERIF_DEBUG_FLAG :=
ifeq ($(VTA_VERIF_DEBUG),1)
  VERIFICATION_CONDS += '+define+layer$$Verification$$DebugLayer'
  VTA_VERIF_DEBUG_FLAG := -DVTA_VERIF_DEBUG=1
endif

VERIFICATION_FLAGS = --assert $(VERIFICATION_INCDIRS) $(VERIFICATION_CONDS) $(VERIFICATION_TOP)

# ==============================================================================
# PHONY TARGETS
# ==============================================================================

.PHONY: all config compile_only lib_tvm \
        fsim vsim vsim-debug vsim-hazard \
        clean depend FORCE

# ==============================================================================
# TOP-LEVEL TARGETS
# ==============================================================================

all:
	@echo "Usage: make [CONFIG=path/to/config.json] <target>"
	@echo ""
	@echo "Build & run (full NN by default; pass --layer N for single-layer):"
	@echo "  fsim                build + run build/fsim          (C++ functional backend)"
	@echo "  vsim                build + run build/vsim          (Verilator RTL backend)"
	@echo ""
	@echo "Canned vsim configurations (wipe the cached archive first):"
	@echo "  vsim-debug          rebuild with VTA_VERIF_DEBUG=1 and run"
	@echo "  vsim-hazard         rebuild with RANDOMIZE=1 NONDET_RANDOM=1 and unique X-init, run"
	@echo ""
	@echo "Build only:"
	@echo "  build/fsim          build the C++ functional binary"
	@echo "  build/vsim          build the Verilator RTL binary"
	@echo ""
	@echo "Utilities:"
	@echo "  config              regenerate build/vta_config.h from the active config JSON"
	@echo "  compile_only        compile all functional simulator objects without linking"
	@echo "  clean               delete all build artefacts"

# Top-level runs
fsim: build/fsim
	./build/fsim

vsim: build/vsim
	./build/vsim --no-timeout

fsim_single_layer: build/fsim
	./build/fsim --layer 0

vsim_single_layer: build/vsim
	./build/vsim --layer 0

# Canned vsim configurations. The cached Verilated archive and the C++ objects
# that read VTA_VERIF_DEBUG aren't tracked as make dependencies, so wipe them
# before re-verilating / recompiling.
vsim-debug:
	$(RM) $(VVTASHELL_ARCHIVE) $(VERILATED_OBJ_DIR)/fsim_main.o
	$(MAKE) VTA_VERIF_DEBUG=1 build/vsim
	./build/vsim --no-timeout

vsim-hazard:
	$(RM) $(VVTASHELL_ARCHIVE)
	$(MAKE) RANDOMIZE=1 NONDET_RANDOM=1 \
	        VERILATOR_XFLAGS='--x-assign unique --x-initial unique' \
	        build/vsim
	./build/vsim --no-timeout

# Generate the VTA config header (implicit in every compile, explicit here for convenience)
config: $(VTA_CONFIG_H)

compile_only: $(OBJS)

# ==============================================================================
# FUNCTIONAL SIMULATOR - LINK
# ==============================================================================

# Objects that make up both binaries (built twice, once without and once with
# VERILATOR_BUILD_ENABLED, into build/ and build/verilated/ respectively).
FSIM_ENTRY_OBJS = \
  fsim_main.o \
  fsim_nn.o \
  fsim_single_layer.o \
  fsim_layer.o \
  sim_driver.o

# Backend-independent objects (compiled once into build/).
FSIM_SHARED_OBJS = \
  build/simulator_functions.o \
  build/virtual_memory.o \
  build/sim_tlpp.o

build/fsim: $(addprefix build/,$(FSIM_ENTRY_OBJS)) $(FSIM_SHARED_OBJS) \
            $(OBJ_LIB_TVM) | build/
	$(CC) $(CFLAGS) \
	  $(addprefix build/,$(FSIM_ENTRY_OBJS)) $(FSIM_SHARED_OBJS) \
	  $(OBJ_LIB_TVM) -o $@

# ==============================================================================
# RTL SIMULATOR - VERILATE + LINK
#
# Workflow:
#   1. cd ../cycle_accurate_simulator && ./mill emitVtaSimConfig
#   2. make build/vsim
# ==============================================================================


$(VVTASHELL_ARCHIVE): $(VTASHELL_DIR)/filelist.f | $(VERILATED_OBJ_DIR)/
	$(VERILATOR) --cc \
	  $(VERILATOR_TRACE_FLAG) \
	  -f $< \
	  --top-module Test \
	  +incdir+$(VTASHELL_DIR) \
	  $(VERIFICATION_FLAGS) \
	  --Mdir $(VERILATED_OBJ_DIR)/VVTAShell \
	  -O3 \
	  --threads $(SIM_THREADS) \
	  $(VERILATOR_XFLAGS) \
	  $(RANDOMIZE_FLAGS) \
	  --build -j 0

build/vsim: $(addprefix $(VERILATED_OBJ_DIR)/,$(FSIM_ENTRY_OBJS)) \
            $(FSIM_SHARED_OBJS) $(VERILATED_OBJS) \
            $(VVTASHELL_ARCHIVE) $(OBJ_LIB_TVM) | build/
	$(CC) $(VERILATED_CFLAGS) -DVL_USER_FINISH $(VERILATOR_INCLUDES) \
	  $(addprefix $(VERILATED_OBJ_DIR)/,$(FSIM_ENTRY_OBJS)) \
	  $(FSIM_SHARED_OBJS) $(VERILATED_OBJS) $(VVTASHELL_ARCHIVE) \
	  $(VERILATED_RUNTIME_SRCS) $(OBJ_LIB_TVM) \
	  -lz -lpthread -o $@

# ==============================================================================
# COMPILE - FUNCTIONAL SIMULATOR  (build/%.o)
# ==============================================================================

build/%.o: src/%.cc $(VTA_CONFIG_H) | build/
	$(CC) $(CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) -c $< -o $@

# ==============================================================================
# COMPILE - VERILATED OBJECTS  (build/verilated/%.o)
# ==============================================================================

# src/sim_driver.cc and src/fsim_*.cc compiled against the Verilated model
$(VERILATED_OBJ_DIR)/%.o: src/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) \
	  -DVERILATOR_BUILD_ENABLED $(VTA_VERIF_DEBUG_FLAG) \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

# DPI glue - no DEBUGFLAG, tightly coupled to Verilator internals
$(VERILATED_OBJ_DIR)/dpi/%.o: src/dpi/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/dpi/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# Verilated device clock loop - also carries the trace-format define
$(VERILATED_OBJ_DIR)/verilated_device.o: src/verilated_device.cc $(VTA_CONFIG_H) \
    | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CC) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH $(TRACE_DEFINE) \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# ==============================================================================
# COMPILE - EXTERNAL TVM LIBRARY  (build/others/%.o)
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
