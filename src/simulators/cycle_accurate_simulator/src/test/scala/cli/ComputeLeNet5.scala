package cli

import unittest.GenericTest
import vta.core.Compute
import vta.util.config.Parameters

class ComputeLeNet5(
    c: Compute,
    lenet_params: String,
    debug: Boolean = false,
    fromResources: Boolean = true
) {

  val computeLeNet5 =
    new ComputeCNN(c, lenet_params, doCompare = true, debug, fromResources)
}

class ComputeLeNet5_all_layers
    extends GenericTest(
      "ComputeLeNet5_all_layers",
      (p: Parameters) => new Compute()(p),
      (c: Compute) =>
        new ComputeLeNet5(
          c,
          "examples_compute/lenet5/lenet_params.csv"
        ),
      isLongTest = true
    )
