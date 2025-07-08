# Formal verification

The formal verification uses `chiseltest 6.0` to define the formal properties and generates a SMTLib problem.
To verify the formal properties, the Z3 solver is needed. It can either be located in the system path or in the CHISEL project root (`cycle_accurate_simulator/`).

To download Z3, follow the instruction there: https://github.com/Z3Prover/z3/releases

## Formal properties definition

To illustrate the formal properties definition, we use the case of `FormalMAC.scala`.
The **MAC** is the lower module of the VTA which is located in **TensorGemm**.

To define a formal property, we must define a new module which instantiates **MAC**:
```
class MacFormalSpec extends Module {
    val dut = Module(new MAC(8, 8, 16, false))
    ...
}
```

Then, we must connect all the module **IO** with the **MAC**'s **IO**.
```
  val io = IO(chiselTypeOf(dut.io))
  io <> dut.io
```

We can probe internal signal with the function `observe`:
```
  val mult = observe(dut.mult)
  val add = observe(dut.add)
```

Then, we can define a property with the function `assert`. 
For instance, we can verify that the multiplication node result in the product of the inputs **a** and **b**:
```
    assert(mult === (io.a * io.b))
```

We can also define temporal property with the function `past` which takes the state of the signal at the previous cycle.
In the case `flopIn = False`, there is a register between the **add** node and the output. 
It implies that the value of add is given to the output at the next cycle.
```
    assert(io.y === past(add))
```

Finally, we can define an executable class that extends `AnyFlatSpec` with options such as `Formal`.
The function `verify` is then used to perform the formal verification.
The function parameters are:
* The module which defines the formal properties (`MacFormalSpec`).
* The number of cycle to verify with `Seq(BoundedCheck())`, here we verify for 10 cycles.
* Others features, here we use `WriteVcdAnnotation` feature to obtain a VCD in case the test fails. It enables us to have counterexample. 
```
class MacFormalTester extends AnyFlatSpec with ChiselScalatestTester with Formal {
  "MAC" should "pass formal properties" in {
    verify(new MacFormalSpec, Seq(BoundedCheck(10), WriteVcdAnnotation))
  }
}
```