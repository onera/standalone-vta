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
CFLAGS = -Wall -Werror -g -DDUMP_MEM=false

# Define the variables for the configuration (vta_config.json)
CONFIG_PY := python ./config/vta_config.py --defs # The command to execute the python script
VTA_DEFS := $(shell $(CONFIG_PY)) # To store the output of running CONFIG_PY
VTA_DEF_FLAGS := $(patsubst -D%,%,$(filter -D%,$(VTA_DEFS))) # To extract the "-D" flags from VTA_DEFS

# Define the main files
SRCS = main_simulator.cc simulator_functions.cc
SRCS += $(wildcard src/*.cc)
OBJS = $(patsubst main_simulator.cc, build/main_simulator.o, $(SRCS))
OBJS += $(patsubst simulator_functions.cc, build/simulator_functions.o, $(SRCS))
OBJS += $(patsubst src/%.cc, build/%.o, $(SRCS))

# Configuration files
CONFIG_FILES := $(wildcard ../config/*)


# ---------------------
# COMPILATION & LINKING 
# ---------------------

# Generic commands
# ----------------
# Build everything
all: config build/vta_simulator

# Generate the configuration file log 
config: build/vta_config_def.txt

# Compile without linking (main_simulator.cc and src/*.cc)
compile_only: $(OBJS) 


# LINKING
# -------
# Dependencies: device_api -> runtime -> sim_driver -> sim_tlpp & virtual_memory

# Link the standalone VTA simulator executable
build/vta_simulator: build/vta_config_def.txt $(OBJS) lib_tvm
	$(CC) build/main_simulator.o build/simulator_functions.o \
	build/virtual_memory.o build/sim_tlpp.o \
	build/sim_driver.o \
	$(OBJ_LIB_TVM) -o $@
	@echo
	@echo "Successful link!"
	@echo "To run the executable: ./build/vta_simulator" 


# COMPILING SIMULATOR AND MAIN FILES (without linking: -c)
# ----------------------------------
# Compile the main file:
build/main_simulator.o: main_simulator.cc simulator_header.h
	$(CC) $(VTA_DEFS) $(CFLAGS) -o build/main_simulator.o -c main_simulator.cc

# Compile the function file (used by main):
build/simulator_functions.o: simulator_functions.cc simulator_header.h
	$(CC) $(VTA_DEFS) $(CFLAGS) -o build/simulator_functions.o -c simulator_functions.cc

# Compile simulator files
build/sim_driver.o: src/sim_driver.cc include/driver.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c src/sim_driver.cc -o build/sim_driver.o

build/sim_tlpp.o: src/sim_tlpp.cc include/sim_tlpp.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c src/sim_tlpp.cc -o build/sim_tlpp.o

build/virtual_memory.o: src/virtual_memory.cc include/virtual_memory.h build/vta_config_def.txt
	$(CC) $(VTA_DEFS) $(CFLAGS) -c src/virtual_memory.cc -o build/virtual_memory.o

# Generic rules for all in one (require to execute $ make depend)
#build/%.o: src/%.cc build/vta_config_def.txt
#	$(CC) $(VTA_DEFS) $(CFLAGS) -o $@ -c $<


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
execute: build/vta_simulator
	./build/vta_simulator > prompt.txt
	code prompt.txt


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
	find build/ -type f -delete

# Generate dependencies
depend:
	makedepend $(SRCS)

# ###################################################
# AUTOMATICALLY GENERATED DEPENDENCIES ($ make depend)
# ###################################################
# RQ: Be careful: it may be the bad target (src/*.o rather than build/*.o)

# DO NOT DELETE
