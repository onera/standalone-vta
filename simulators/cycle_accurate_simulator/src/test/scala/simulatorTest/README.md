# Cycle-accurate simulator

The cycle-accurate simulator can be executed at different level, here, three levels are proposed:
* **alu**: To simulate `TensorAlu`
* **compute**: To simulate `Compute`
* **gemm**: To simulate `TensorGemm`

The simulators use a JSON file in input. The JSON file must be located in `src/test/resources`. The JSON files differ from a simulation level to another.
Most of the JSON fields are represented as follows:
* A field name, e.g., `"inp"`
* One or more values each one with an index, e.g., `"idx": "00000000", "vec": []`

## ALU JSON
The JSON for the ALU is composed of:
* **inst**: the decoded instruction to execute on TensorAlu.
* **acc**: the value in the ACC buffer on which the ALU will perform the operation. Each vector has 16 elements of 32 bits each.
* **acc_expect**: the expected result at the end of the ALU execution.
* **uop**: the value in the UOP buffer. Each vector has 3 elements, the first is the 11-bit ACC index, the second is the 11-bit INP index and the last 10-bit value is not used.

The ALU JSON can only simulate a single instruction.

## GEMM JSON
The JSON for the ALU is composed of:
* **inst**: the decoded instruction to execute on TensorGemm
* **inp**: the value in the INP buffer. Each vector has 16 elements of 8 bits each.
* **wgt**: the value in the WGT buffer. Each vector has 256 elements of 8 bits each.
* **acc_i**: the initial state of the ACC buffer. Each vector has 16 elements of 32 bits each.
* **acc_o**: the expected final state of the ACC buffer.
* **uop**: the value in the UOP buffer. Each vector has 3 elements, the first is the 11-bit ACC index, the second is the 11-bit INP index and the last is the 10-bit WGT index.

The GEMM JSON can only simulate a single instruction.

## COMPUTE JSON
The JSON for the Compute is composed of:
* **inst**: the 128-bit little-endian encoded instructions. The instructions must finish with a `FINISH` instruction (i.e., `"00000000000000000000000000000003"`).
* **dram**: the value to load from the DRAM, the index must be the physical address.
* **inp**: the value in the INP buffer. Each vector has 16 elements of 8 bits each.
* **wgt**: the value in the WGT buffer. Each vector has 256 elements of 8 bits each.
* **out**: the initial state of the OUT buffer to initialise the OUT cell. The value are going to be overwritten.
* **out_expect**: the expected final state of the OUT buffer. Each vector has 16 elements of 16 bits each.


A physical address is computed in Bytes as follows:
```
Physical address = base address + (logical address * bitwidth of the vector)
```
* For an accumulator vector:
    * **base address** = `acc_baddr` (fixed to 0 in `ComputeTest.scala`).
    * **logical address** is the one given by the instruction, for instance `0x0001`.
    * **bitwidth of the vector** = 64 Bytes for an accumulator (16 elements of 4 Bytes).
    * ```Physical address = 0 + 0x0001 * 64 = 0x0040```
* For an UOP vector:
    * **base address** = `uop_baddr` (fixed to 0 in `ComputeTest.scala`).
    * **logical address** is the one given by the instruction, for instance `0x1000`.
    * **bitwidth of the vector** = 4 Bytes for an UOP.
    * ```Physical address = 0 + 0x1000 * 4 = 0x4000```

### Example of execution

The class `ComputeTest` instantiates the `Compute` module. 
It emulates the different memory behaviour to interact with the module.

Then, the test class is instantiated in an executable class, such as `ComputeApp`.
The class gives to `ComputeTest` the JSON file to consider.

```
class ComputeApp extends GenericTest("ComputeApp", (p:Parameters) =>
  new Compute(true)(p), (c: Compute) => new ComputeTest(c, "/examples_compute/compute_investigation.json"))
```
