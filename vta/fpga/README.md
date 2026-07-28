# VTA Implementation on FPGA

This directory contains the resources required for implementing the Versatile Tensor Accelerator (VTA) on an FPGA and programming it.

> [!IMPORTANT]
> All commands listed in this guide must be run inside the provided **Pixi shell** (`pixi shell`).
> 
> Before starting, it is highly recommended to clean previously generated artifacts from the repository root:
> ```bash
> make -C examples/ cleaner
> ```

> [!NOTE]
> This guide covers the standalone `make` / GUI route. The Mill build drives the
> same ground from the repo root - synthesis, baremetal codegen and Vitis
> workspace creation, plus a workspace from an existing XSA (no Vivado), the
> SD-card file set, and the on-board isolation debug chain. See *Run an Example*
> in the [root README](../../README.md).

---

## Automated Flow (Recommended)

This flow automates RTL generation, Vivado project creation, synthesis, and implementation using pre-configured target board configurations.

### Hardware Generation

1. **Source the Xilinx Vivado environment:**
   ```bash
   source <Xilinx>/2025.2/Vivado/settings64.sh
   ```
   *Replace `<Xilinx>` with the absolute path to your Xilinx installation directory.*

2. **Navigate to the synthesis directory:**
   ```bash
   cd vta/fpga/synthesis
   ```

3. **Generate the bitstream:**
   ```bash
   make bitstream BOARD=<BOARD> CONFIG=../../../config/vta_config.json JOBS=8
   ```
   *Replace `<BOARD>` with your target platform. Currently supported boards: `zcu104`, `vck190`, and `vek280`.*

The automated build system will:
- Emit Chisel-based RTL.
- Package the RTL as a Vivado custom IP block.
- Create a Vivado project at `vta/fpga/synthesis/build/project/<BOARD>`.
- Run synthesis, implementation, and export the hardware handoff file (`.xsa`) to `vta/fpga/synthesis/build/vta_<BOARD>.xsa`.

For further details and configuration options, see the [synthesis/README.md](synthesis/README.md).

### Software Generation

This step compiles the neural network model into VTA instructions and configures a Vitis workspace for a standalone (baremetal) application running on the board's processing system (APU).

1. **Compile the neural network model (from the repository root):**
   ```bash
   make -C examples/ compile_and_run ONNX_FILE=onnx/<MODEL>.onnx
   ```
   *Replace `<MODEL>` with the ONNX model file name (e.g., `lenet5.onnx`).*

2. **Navigate to the software directory:**
   ```bash
   cd vta/fpga/software
   ```

3. **Generate the baremetal source configuration files** (`make gen`, or the
   underlying Mill task from the repo root):
   ```bash
   make gen CONFIG=../../../config/vta_config.json DDR_BASE=0x200000
   # equivalently, from the repo root:
   ./mill -Dvta.config.file=vta_config.json vta.fpga.software.genNnBaremetal ../../../compiler_output/ \
       --ddr-base    0x200000      \
       --max-addr    0x1ff00000    \
       --outdir      gen
   ```

4. **Initialize the Vitis baremetal workspace:**
   Make sure the Xilinx tools are on your PATH:
   ```bash
   source <Xilinx>/2025.2/Vivado/settings64.sh
   ```
   Then initialize the workspace:
   ```bash
   vitis -s host/create_vitis_workspace.py \
       --xsa         ../synthesis/build/vta_<BOARD>.xsa \
       --workspace   build/vitis_proj  \
       --runner      run_nn_uart         \
       --data-loader elf \
       --cpu         <CPU> \
       --baud        115200
   ```
   *Where:*
   - `<BOARD>`: The target board (`zcu104`, `vck190`, or `vek280`).
   - `<CPU>`: Use `psv_cortexa72_0` for Versal architectures (`vck190` or `vek280`), and `psu_cortexa53_0` for UltraScale+ architectures (`zcu104`).

For further details and configuration options, see the [software/README.md](software/README.md).

### Compilation and Execution

1. **Build the Application:**
   Open the Vitis Unified IDE, import/open the workspace located at `vta/fpga/software/build/vitis_proj`, and compile the application component.

2. **Setup the Target Board:**
   - Connect the power, JTAG, and UART cables to your hardware.
   - *Example for VEK280:* Refer to the AMD documentation [for the board setup diagram](https://vitisai.docs.amd.com/en/latest/_images/target_board_updated.png).
   - Power on the target board.

3. **Run the Inference via Host Script (from `vta/fpga/software`):**
   Start the application execution in Vitis and run the host UART interface script simultanously (to send the input data and verify results):
   ```bash
   python host/uart_nn.py \
       --port /dev/ttyUSB1 \
       --input ../../../compiler_output/input_nn.bin \
       --output ../../../compiler_output/out_board.bin \
       --check ../../../simulators_output/final_output.bin
   ```

---

## Manual Flow (Advanced)

If you prefer to perform the integration yourself using the Vivado and Vitis GUIs, follow the step-by-step procedures below.

### Hardware Design in Vivado GUI

#### 1. RTL Generation (SystemVerilog)

From the repository root, run the Chisel compiler to generate the hardware description files:
```bash
./mill vta.hardware.emitVtaFpgaConfig
```

By default, the compilation output is generated in:
`build/emitted/vta-xilinx-shell/` at the repository root

This directory contains:
- `.sv` (SystemVerilog) source files for the VTA processor.
- A `filelist.f` file listing all generated source files.
- A `package_ip.tcl` TCL script to package the design as a custom Vivado IP block.

#### 2. Vivado IP Packaging

Once the RTL is generated, package it into an IP block compatible with the Vivado IP Catalog:
```bash
source <Xilinx>/2025.2/Vivado/settings64.sh
cd build/emitted/vta-xilinx-shell/
vivado -mode batch -source package_ip.tcl -tclargs --part <DEVICE_PART>
```
- Replace `<DEVICE_PART>` with your target FPGA part number (e.g., `xcve2802-vsvh1760-2MP-e-S` for VEK280).

This script generates an IP repository directory at `ip_repo/vta/` containing the IP definition.

#### 3. Integration in Vivado (Versal VEK280 Example)

1. **Create a Vivado Project:** Launch Vivado and create a new project targeting the **Versal VEK280 Evaluation Board** (part `xcve2802-vsvh1760-2MP-e-S`).
2. **Register the IP Repository:**
   - Go to **Flow Navigator** > **Project Manager** > **Settings**.
   - Navigate to **IP** > **Repository**, click the **+** button, and add the path to the `ip_repo/` folder generated in the previous step.
3. **Initialize the Block Design:**
   - Create a new **Block Design**.
   - Add the **Control, Interfaces & Processing System (CIPS)** IP block.
   - Add the **VTA** IP core from the IP Catalog.
4. **Run Block Automation:** Click the green banner to **Run Block Automation** for the CIPS IP:
   - **PL Clocks:** `1`
   - **PL Resets:** `1`
   - **Memory Controller Type:** `LPDDR` (this adds an **AXI NoC** instance).
5. **Configure CIPS:** Double-click the CIPS block to configure:
   - Go to the **PS PMC** configuration.
   - **Clocking:** Under **Output Clocks** > **PMC Domain Clocks** > **PL Fabric Clocks**, set `PL CLK 0` to `100MHz`.
   - **Interfaces:** Under **PS-PL Interfaces**, enable the `M_AXI_FPD` (Full Power Domain) master interface and set its width to `32`.
6. **Configure AXI NoC:** Double-click the AXI NoC block:
   - In the **General** tab, increment the number of **AXI Slave Interfaces** and **AXI Clocks** by 1 (e.g., from `6` to `7`) to accommodate the VTA data path.
   - In the **Inputs** tab, ensure the new slave interface (e.g., `S06_AXI`) is connected to the **PL**.
   - In the **Connectivity** tab, ensure the new slave interface (e.g., `S06_AXI`) is connected to the **MC Port 0**.
7. **Run Connection Automation and Insert SmartConnect:**
   - Click the green banner to **Run Connection Automation** twice. This lets Vivado automatically configure the clocks, resets, the control path (inserting `axi_smc` between CIPS and VTA), and the internal CIPS memory ports (`FPD_CCI_NOC_*`, `LPD_AXI_NOC_0`, etc.) connected to the AXI NoC.
   - **Manual Correction for the Data Path:**
     - By default, Vivado's Connection Automation connects the VTA master port (`m_axi_gemm`) **directly** to the AXI NoC slave interface (`S06_AXI`), skipping the AXI SmartConnect.
     - To prevent AXI read interleaving issues, modify this connection manually:
       1. **Delete** the direct AXI net connecting `m_axi_gemm` to `S06_AXI`.
       2. **Add** an **AXI SmartConnect** block manually from the IP Catalog, and name it `vta_dram_smc`.
       3. **Connect the AXI interfaces:**
          - Connect the VTA master port (`m_axi_gemm`) to the slave interface (`S00_AXI`) of `vta_dram_smc`.
          - Connect the master interface (`M00_AXI`) of `vta_dram_smc` to the AXI NoC slave interface (`S06_AXI`).
       4. **Connect the Clock and Reset manually:**
          - Connect `aclk` of `vta_dram_smc` to `pl0_ref_clk` on the CIPS block.
          - Connect `aresetn` of `vta_dram_smc` to the `peripheral_aresetn` output pin of the **Processor System Reset** block (`proc_sys_reset_0`) created by the automation.
8. **Address Mapping:**
   - Go to the **Address Editor** tab.
   - Right-click on the VTA IP and select **Assign All** (if not already assigned).
   - *Note:* Ensure the `m_axi_gemm` range covers the LPDDR memory space.
9. **Validation and HDL Wrapper:**
   - Click **Regenerate Layout** to organize the diagram.
   - Run **Validate Design** (`F6`) and resolve any warnings/errors.
   - In the **Sources** tab, right-click the Block Design (`.bd` file) and choose **Create HDL Wrapper**. Select **Let Vivado manage wrapper and auto-update**.
10. **Generate Device Image:**
    - Click **Generate Block Design** in the Flow Navigator.
    - Click **Run Synthesis**, then **Run Implementation**.
    - Click **Generate Device Image** once implementation succeeds.
11. **Export Hardware:** Go to **File** > **Export** > **Export Hardware**. Select **Fixed**, check **Include device image**, and save the resulting `.xsa` file.

### Software Setup in Vitis IDE

This section describes how to manually compile and run the `test_gemm` standalone application using the Vitis Unified IDE.

#### 1. Generate `init_dram.h`

The `test_gemm` application requires a pre-generated header containing test matrices. From the repository root, run:
```bash
cd vta/fpga/software
make gen-test_gemm
```
This generates `vta/fpga/software/gen/init_dram.h`.

#### 2. Configure Vitis Project

1. **Launch Vitis:** Open the Vitis Unified IDE.
2. **Set a Workspace:** Choose a dedicated directory for your Vitis projects (outside the Vivado project directory).
3. **Create the Platform Component:**
   - Select **File** > **New Component** > **Platform**.
   - **Hardware Design (XSA):** Browse to the `.xsa` file exported from Vivado.
   - **Operating System:** `standalone`
   - **Processor:** `psv_cortexa72_0` (default for VEK280).
   - In the **Flow** navigator, click **Build** to generate the platform.
4. **Create the Application Component:**
   - Select **File** > **New Component** > **Application**.
   - **Platform:** Select the platform you just created.
   - **Domain:** Ensure the `standalone` domain is selected.
   - **Source Files:** Select **Add folders** and add the following directories one by one:
     - `vta/fpga/software/driver/src/`
     - `vta/fpga/software/driver/include/`
     - `vta/fpga/software/apps/test_gemm/`
     - `vta/fpga/software/gen/` (provides `init_dram.h`)
5. **Configure Base Addresses:**
   - Open `test_gemm.cc` inside the Vitis application component.
   - Around line 23, verify that `VTA_VCR_BASE` is set to the base address of the VTA peripheral (e.g., `XPAR_VTA_0_BASEADDR`).
6. **Build the Application:**
   - In the Vitis **Flow** panel, click **Build** under your application component.
7. **Connect the Board:**
   - Connect the power, JTAG, and UART cables of your board. Refer to the [setup diagram](https://vitisai.docs.amd.com/en/latest/_images/target_board_updated.png) for cabling details.
   - Open a serial terminal configured for the board's UART interface (baud rate: `115200`, e.g., using `/dev/ttyUSB0` or as explained in the [VEK280 setup guide](https://toulouse-embedded-accel.github.io/HEAT/quickstarts/vek280-setup/)).
   - Power on the target board.
8. **Run the Application:**
   - **Via Vitis GUI:** In the Flow panel, select your application and click **Run**.
   - **Via XSDB Console (Alternative):**
     Launch the XSDB console in Vitis and execute:
     ```tcl
     connect
     targets
     device program "<VITIS_WORKSPACE>/platform/hw/sdt/design_1_wrapper.pdi"
     targets -set -filter {name =~ "*Cortex-A72 #0"}
     rst -processor 
     dow "<VITIS_WORKSPACE>/app_component/build/app_component.elf"
     con
     ```
     *Replace `<VITIS_WORKSPACE>` with the absolute path to your Vitis workspace.*
9. **Observe the Results:** Check the serial terminal for the output of the GEMM test showing `GEMM test passed!`.
