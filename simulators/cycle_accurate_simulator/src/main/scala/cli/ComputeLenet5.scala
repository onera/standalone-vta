package cli

import chiseltest.iotesters.PeekPokeTester
import vta.core.Compute

class ComputeLenet5(c: Compute, insn: String, uop: String, input: String, weight: String, out: String, acc: String, expected_out: String,
                    base_addresses: String, doCompare: Boolean = false, debug: Boolean = false, fromResources: Boolean = true)
  extends PeekPokeTester(c) {

  val computeSimulator = new ComputeSimulator(
    c, insn, uop, input, weight, out, acc, expected_out, base_addresses,
    doCompare, debug, fromResources)
}