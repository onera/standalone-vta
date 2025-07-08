package cli

import chiseltest.iotesters.PeekPokeTester
import unittest.GenericTest
import vta.core.Compute
import vta.util.config.Parameters

class ComputeLenet5(c: Compute, lenet_params: String, debug: Boolean = false, fromResources: Boolean = true)
  extends PeekPokeTester(c) {

  val computeLeNet5 = new ComputeCNN(
    c, lenet_params,
    doCompare = true, debug, fromResources)
}

class ComputeLeNet5_all_layers extends GenericTest("ComputeLeNet5_all_layers", (p:Parameters) =>
  new Compute(false)(p), (c: Compute) => new ComputeLenet5(c, "examples_compute/lenet5/lenet_params.csv"), isLongTest = true)