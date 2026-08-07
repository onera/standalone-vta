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

# Honour $(CXX) from the environment (the pixi env exports it, pointing at the toolchain that verilator
# also uses for the verilated archive) and fall back to g++ outside pixi.
CXX             ?= g++
CFLAGS           = -std=c++17 -lstdc++fs -Wall -g -MMD -MP
# CFLAGS         = -std=c++17 -lstdc++fs -fsanitize=address -g -MMD -MP
DEBUGFLAG       ?= -DDEBUG_SIM=false
RUNTIME_FLAGS   ?= 
ROOTDIR =  ../..

# Object/executable output tree. Default keeps standalone `make` unchanged;
# Mill overrides it per config (BUILD_DIR=build/<configKey>) so alternate
# configs coexist and switching back and forth does not recompile.
BUILD_DIR       ?= build

VTA_COMPILER_OUTPUT ?= $(ROOTDIR)/compiler_output
VTA_SIMULATOR_OUTPUT ?=$(ROOTDIR)/simulators_output
VTA_REFERENCE_OUTPUT ?= $(ROOTDIR)/reference_output

# Verilated objects sit on the per-cycle hot path - optimise for throughput.
VERILATED_CFLAGS = -std=c++17 -O3 -fomit-frame-pointer -MMD -MP
PATH_DEFINES          = -DVTA_COMPILER_OUTPUT='"$(abspath $(VTA_COMPILER_OUTPUT))"' \
                        -DVTA_SIMULATOR_OUTPUT='"$(abspath $(VTA_SIMULATOR_OUTPUT))"' \
                        -DVTA_REFERENCE_OUTPUT='"$(abspath $(VTA_REFERENCE_OUTPUT))"'
CFLAGS           += $(PATH_DEFINES)
VERILATED_CFLAGS += $(PATH_DEFINES)

# Inside a conda/pixi environment the toolchain compiles against its own sysroot
# and does not search the environment's include/lib dirs, so headers installed by
# the env (notably zlib.h, needed by verilated_fst_c.cpp) are invisible without
# these. Only the search paths are taken: the environment also exports CPPFLAGS /
# CXXFLAGS carrying -O2, -DNDEBUG and -march=nocona, which would silently disable
# asserts and change float codegen - fsim and vsim must agree bit-for-bit, so
# codegen flags stay under this Makefile's control.
ifdef CONDA_PREFIX
  CONDA_INCLUDE     = -isystem $(CONDA_PREFIX)/include
  CONDA_LIBS        = -L$(CONDA_PREFIX)/lib -Wl,-rpath,$(CONDA_PREFIX)/lib
  CFLAGS           += $(CONDA_INCLUDE)
  VERILATED_CFLAGS += $(CONDA_INCLUDE)
endif
# VTA hardware configuration. Empty means config/vta_config.py picks its own
# default ($(ROOTDIR)/config/vta_config.json).
# Override at build time: make CONFIG=path/to/config.json [target]
CONFIG          ?=
USE_CFG_FLAG     = $(if $(CONFIG),--use-cfg $(CONFIG),)
VTA_CONFIG_H    := $(BUILD_DIR)/vta_config.h
VTA_CONFIG_ARGS_FILE := $(BUILD_DIR)/.vta_config_args
FORCE_INCLUDE    = -include $(VTA_CONFIG_H)
CONFIG_FILES    := $(wildcard $(ROOTDIR)/config/*)

# Functional simulator sources and objects
# (verilated_device.cc is verilated-RTL-only and compiled separately)
SRCS = $(filter-out src/verilated_device.cc, $(wildcard src/*.cc))
OBJS = $(patsubst src/%.cc, $(BUILD_DIR)/%.o, $(SRCS))

# External TVM library
SRC_LIB_TVM = $(wildcard external_lib/tvm/*.cc) \
               $(wildcard external_lib/tvm/**/*.cc)
OBJ_LIB_TVM = $(patsubst external_lib/tvm/%.cc, $(BUILD_DIR)/others/%.o, $(SRC_LIB_TVM))

# ---------------------
# Verilated RTL build
# ---------------------

VTASHELL_DIR     ?= $(ROOTDIR)/build/emitted/vta-sim-shell
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
VERILATED_OBJ_DIR = $(BUILD_DIR)/verilated

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
        fsim vsim fsim_single_layer vsim_single_layer \
        vsim-debug vsim-hazard compile-fsim compile-vsim \
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
fsim: $(BUILD_DIR)/fsim
	./$(BUILD_DIR)/fsim $(RUNTIME_FLAGS)

vsim: $(BUILD_DIR)/vsim
	./$(BUILD_DIR)/vsim $(RUNTIME_FLAGS)

fsim_single_layer: $(BUILD_DIR)/fsim
	./$(BUILD_DIR)/fsim --layer 0 $(RUNTIME_FLAGS)

vsim_single_layer: $(BUILD_DIR)/vsim
	./$(BUILD_DIR)/vsim --layer 0 $(RUNTIME_FLAGS)

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

compile-vsim: $(BUILD_DIR)/vsim
compile-fsim: $(BUILD_DIR)/fsim
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
  $(BUILD_DIR)/simulator_functions.o \
  $(BUILD_DIR)/virtual_memory.o \
  $(BUILD_DIR)/sim_tlpp.o

$(BUILD_DIR)/fsim: $(addprefix $(BUILD_DIR)/,$(FSIM_ENTRY_OBJS)) $(FSIM_SHARED_OBJS) \
            $(OBJ_LIB_TVM) | $(BUILD_DIR)/
	$(CXX) $(CFLAGS) \
	  $(addprefix $(BUILD_DIR)/,$(FSIM_ENTRY_OBJS)) $(FSIM_SHARED_OBJS) \
	  $(OBJ_LIB_TVM) -o $@

# ==============================================================================
# RTL SIMULATOR - VERILATE + LINK
#
# Workflow:
#   1. from the repo root: ./mill modules.hardware.emitVtaSimConfig
#      (writes VTASHELL_DIR, i.e. <root>/build/emitted/vta-sim-shell)
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

$(BUILD_DIR)/vsim: $(addprefix $(VERILATED_OBJ_DIR)/,$(FSIM_ENTRY_OBJS)) \
            $(FSIM_SHARED_OBJS) $(VERILATED_OBJS) \
            $(VVTASHELL_ARCHIVE) $(OBJ_LIB_TVM) | $(BUILD_DIR)/
	$(CXX) $(VERILATED_CFLAGS) -DVL_USER_FINISH $(VERILATOR_INCLUDES) \
	  $(addprefix $(VERILATED_OBJ_DIR)/,$(FSIM_ENTRY_OBJS)) \
	  $(FSIM_SHARED_OBJS) $(VERILATED_OBJS) $(VVTASHELL_ARCHIVE) \
	  $(VERILATED_RUNTIME_SRCS) $(OBJ_LIB_TVM) \
	  $(CONDA_LIBS) -lz -lpthread -o $@

# ==============================================================================
# COMPILE - FUNCTIONAL SIMULATOR  (build/%.o)
# ==============================================================================

$(BUILD_DIR)/%.o: src/%.cc $(VTA_CONFIG_H) | $(BUILD_DIR)/
	$(CXX) $(CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) -c $< -o $@

# ==============================================================================
# COMPILE - VERILATED OBJECTS  (build/verilated/%.o)
# ==============================================================================

# src/sim_driver.cc and src/fsim_*.cc compiled against the Verilated model
$(VERILATED_OBJ_DIR)/%.o: src/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CXX) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) $(DEBUGFLAG) \
	  -DVERILATOR_BUILD_ENABLED $(VTA_VERIF_DEBUG_FLAG) \
	  -I$(VERILATOR_INC) -I$(VERILATED_OBJ_DIR)/VVTAShell \
	  -c $< -o $@

# DPI glue - no DEBUGFLAG, tightly coupled to Verilator internals
$(VERILATED_OBJ_DIR)/dpi/%.o: src/dpi/%.cc $(VTA_CONFIG_H) | $(VERILATED_OBJ_DIR)/dpi/ $(VVTASHELL_ARCHIVE)
	$(CXX) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# Verilated device clock loop - also carries the trace-format define
$(VERILATED_OBJ_DIR)/verilated_device.o: src/verilated_device.cc $(VTA_CONFIG_H) \
    | $(VERILATED_OBJ_DIR)/ $(VVTASHELL_ARCHIVE)
	$(CXX) $(VERILATED_CFLAGS) $(FORCE_INCLUDE) \
	  -DVERILATOR_BUILD_ENABLED -DVL_USER_FINISH $(TRACE_DEFINE) \
	  $(VERILATOR_INCLUDES) -c $< -o $@

# ==============================================================================
# COMPILE - EXTERNAL TVM LIBRARY  (build/others/%.o)
# ==============================================================================

$(BUILD_DIR)/others/%.o: external_lib/tvm/%.cc $(VTA_CONFIG_H) | $(BUILD_DIR)/others/
	$(CXX) $(CFLAGS) $(FORCE_INCLUDE) -c $< -o $@

lib_tvm: $(OBJ_LIB_TVM)

# ==============================================================================
# VTA CONFIGURATION HEADER
# ==============================================================================

# Refreshes the stamp only when USE_CFG_FLAG changes, avoiding spurious rebuilds.
$(VTA_CONFIG_ARGS_FILE): FORCE | $(BUILD_DIR)/
	@printf '%s' '$(USE_CFG_FLAG)' > $@.tmp
	@cmp -s $@.tmp $@ && rm $@.tmp || mv $@.tmp $@

FORCE:

# Regenerates when the active config JSON changes or a different config is selected.
# Usage:  make config                         (uses ../config/vta_config.json)
#         make config CONFIG=path/to/x.json   (uses a custom JSON)
$(VTA_CONFIG_H): $(CONFIG_FILES) $(CONFIG) $(VTA_CONFIG_ARGS_FILE) | $(BUILD_DIR)/
	python config/vta_config.py --export-header $@ $(USE_CFG_FLAG)

# ==============================================================================
# BUILD DIRECTORIES
# ==============================================================================

$(BUILD_DIR)/ $(BUILD_DIR)/others/ $(VERILATED_OBJ_DIR)/ $(VERILATED_OBJ_DIR)/dpi/:
	mkdir -p $@

# ==============================================================================
# HOUSEKEEPING
# ==============================================================================

clean:
	-find $(BUILD_DIR)/ -type f -delete

depend:
	makedepend $(SRCS)

# Auto-generated header dependency files (produced by -MMD -MP)
-include $(wildcard $(BUILD_DIR)/*.d $(BUILD_DIR)/others/*.d \
  $(VERILATED_OBJ_DIR)/*.d $(VERILATED_OBJ_DIR)/dpi/*.d)
