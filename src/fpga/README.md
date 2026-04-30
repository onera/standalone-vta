# VTA Implementation on FPGA

This directory contains the resources required for implementing the Versatile Tensor Accelerator (VTA) on an FPGA and program it.

## Design Flow (Hardware)

The implementation follows a flow based on Chisel to generate the RTL, followed by Vivado for synthesis and implementation.

<!-- ### Automated Flow (# TODO: Work in Progress)

A Python script is provided to automate the entire process (RTL generation, IP packaging, Vivado project creation with CIPS and NoC, and synthesis) without needing to open the Vivado GUI.

From the project root:

```bash
# Ensure you have sourced the Vivado environment beforehand
source /opt/Xilinx/2025.2/Vitis/settings64.sh

# Launch full project creation and synthesis
./src/fpga/build_vivado_project.py --synth --impl
```

Available options:
- `--part <PART>`: Sets the FPGA target (default: `xcve2802-vsvh1760-2MP-e-S` for VEK280).
- `--project-dir <DIR>`: Sets the Vivado project directory (default: `vta_vivado_project`).
- `--synth`: Automatically launches synthesis after project creation.
- `--impl`: Automatically launches implementation.

--- -->

### Manual Flow

<!-- If you prefer to perform the integration yourself via the Vivado GUI, follow the steps below. -->

#### 1. RTL Generation (SystemVerilog)

From the project root, it is recommended to use the Docker container to generate the hardware source code:

```bash
cd src/simulators/cycle_accurate_simulator
./mill emitVtaFpgaConfig
```

By default, this command generates files in:
`src/simulators/cycle_accurate_simulator/build/emitted/vta-xilinx-shell/`

This folder contains:
- .sv (SystemVerilog) files for the VTA processor.
- A `filelist.f` file listing all source files.
- A `package_ip.tcl` TCL script to automate Vivado IP creation.


#### 2. Vivado IP Creation

Once the RTL is generated, you can use the provided TCL script to create a component (IP) ready to be imported into Vivado IP Integrator.

```bash
source /opt/Xilinx/2025.2/Vitis/settings64.sh
cd src/simulators/cycle_accurate_simulator/build/emitted/vta-xilinx-shell/
vivado -mode batch -source package_ip.tcl -tclargs --part <DEVICE_PART>
```

Replace `<DEVICE_PART>` with your targeted FPGA/MPSoC device (e.g., `xcve2802-vsvh1760-2MP-e-S`).

This will create an `ip_repo/vta/` folder containing the IP definition.


#### 3. Integration in Vivado (Versal VEK280)

1. **Create a Vivado Project:** Launch Vivado and create a new project targeting the **Versal VEK280 Evaluation Board** (part `xcve2802-vsvh1760-2MP-e-S`).
2. **Register the IP Repository:**
    - Navigate to **Flow Navigator** (left pannel) > **Project Manager** > **Settings**.
    - Go to **IP** > **Repository** and add the path to the `ip_repo/` folder generated in Section 2.
3. **Initialize the Block Design:**
    - Create a new **Block Design**.
    - Add the **Control, Interfaces & Processing System (CIPS)** IP core.
    - Add the **VTA** IP core from the IP Catalog.
4. **Run Block Automation:** Click the green banner to **Run Block Automation** for the CIPS IP.
    - **PL Clocks:** `1`
    - **PL Resets:** `1`
    - **Memory Controller Type:** `LPDDR` (this will automatically add an **AXI NoC** instance).
5. **Configure CIPS:** Double-click the CIPS block:
    - Open the **PS PMC** configuration.
    - **Clocking:** Navigate to **Output Clocks** > **PMC Domain Clocks** > **PL Fabric Clocks**. Set `PL CLK 0` to `100MHz`.
    - **Interfaces:** Navigate to **PS-PL Interfaces**. Enable the `M_AXI_FPD` (Full Power Domain) master interface and set its width to `32`.
6. **Configure AXI NoC:** Double-click the AXI NoC block:
    - In the **General** tab, increment the number of **AXI Slave Interfaces** and **AXI Clocks** by 1 (e.g., from `6` to `7`) to accommodate the VTA data master interface.
    - In the **Inputs** tab, ensure the new slave interface (e.g., `S06_AXI`) is connected to the **PL**.
    - In the **Connectivity** tab, ensure the new slave interface (e.g., `S06_AXI`) is connected to the **MC Port 0**.
7. **Run Connection Automation:** Click the banner to **Run Connection Automation** twice.
    - **VTA Data Path:** Connect the VTA master port (`m_axi_gemm`) to the AXI NoC slave interface (`S06_AXI`).
    - **VTA Control Path:** Connect the VTA slave port (`s_axi_control`) to the CIPS `M_AXI_FPD` interface. Vivado will automatically insert an **AXI SmartConnect**.
    - **Infrastructure:**
        - Connect all AXI clock ports to `pl0_ref_clk`.
        - Connect all AXI reset ports to `pl0_resetn`.
8. **Address Mapping**:
    - Go to the **Address Editor** tab.
    - If the VTA IP is unassigned, right-click on it and select **Assign All**. 
    - *Note:* Ensure the `m_axi_gemm` range covers the LPDDR memory space.
9. **Validation and HDL Wrapper:**
    - Click **Regenerate Layout** to organize the diagram.
    - Run **Validate Design** (F6) and address any critical warnings or errors.
    - In the **Sources** window, right-click the Block Design (`.bd` file) and select **Create HDL Wrapper**. Choose **Let Vivado manage wrapper and auto-update**.
10. **Generate Device Image:**
    - Click **Generate Block Design** in the Flow Navigator.
    - Click **Run Synthesis**, followed by **Run Implementation**.
    - Click **Generate Device Image** once implementation is complete.
11. **Export Hardware:** Go to **File** > **Export** > **Export Hardware**. Select **Fixed** and **Include device image**, then save the resulting `.xsa` file for use in Vitis.

## Software Setup with Vitis (Versal VEK280)

This section describes how to create a Standalone (Baremetal) application in Vitis to run the VTA driver and examples on the Versal APU (simple example with test_gemm.cc).

1. **Launch Vitis Unified IDE:** Open the Vitis Unified IDE.
2. **Set a Workspace:** Choose a dedicated directory for your Vitis projects (outside the Vivado project).
3. **Create a Platform Component:**
    - Select **File** > **New Component** > **Platform**.
    - **Hardware Design (XSA):** Browse to the `.xsa` file exported from Vivado.
    - **Operating System:** `standalone`
    - **Processor:** `psv_cortexa72_0` (should be the default for VEK280).
    - In the **Flow** navigator, click **Build** to generate the platform.
4. **Create an Application Component:**
    - Select **File** > **New Component** > **Application**.
    - **Platform:** Select the platform you just created.
    - **Domain:** Ensure the `standalone` domain is selected.
    - **Source Files:** Select **Add folders** and add one-by-one the following folders `standalone-vta/src/fpga/software/src/`, `standalone-vta/src/fpga/software/include/`, and `standalone-vta/src/fpga/software/test_gemm/`.
6. **Adapt the software to your platform:**
    - Open `test_gemm/test_gemm.cc`. Around line 20, set `VTA_VCR_BASE` to the base address of the VTA peripheral defined in the `xparameters.h` file (e.g. `XPAR_VTA_0_BASEADDR`).
7. **Build the Application:**
    - In the **Flow** panel, click **Build** under your application component.
8. **Connect the board:**
    - Connect the power, JTAG, and UART cables [as shown in this image](https://vitisai.docs.amd.com/en/latest/_images/target_board_updated.png).
    - Open a terminal on Versal UART0 [as explained in this guide](https://toulouse-embedded-accel.github.io/HEAT/quickstarts/vek280-setup/).
    - Power on the VEK280 board.
9. **Run the application:**
    - **Automatic:** In the Flow panel, select your application and click **Run**.
    - **Manual (via XSDB Console):**
    ```tcl
        connect
        targets
        device program "<VITIS_WORKSPACE>/platform/hw/sdt/design_1_wrapper.pdi"
        targets -set -filter {name =~ "*Cortex-A72 #0"}
        rst -processor 
        dow "<VITIS_WORKSPACE>/app_component/build/app_component.elf"
        con
    ```
10. **Observe the results:** Check the serial terminal for the output of the GEMM test.
