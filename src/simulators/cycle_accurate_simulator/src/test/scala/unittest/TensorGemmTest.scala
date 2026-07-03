/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package unittest

import unittest.mocks.{
  TensorGemmIdxTester,
  TensorGemmIndexGeneratorTester,
  TensorGemmPipelinedTester,
  TensorGemmResetTester,
  TensorGemmTester
}
import vta.core._
import vta.tags
import vta.util.AnyFlatSpecSim

@tags.UnitTests
class TensorGemmTestSuite extends AnyFlatSpecSim {
  behavior of "TensorGemmSimple"
  it should "compute a simple operation" in
    simulate(new TensorGemmSimple)(
      new TensorGemmTester(_)
    )

  it should "correctly generate indices" in simulate(new TensorGemmSimple)(
    new TensorGemmIdxTester(_)
  )

  behavior of "TensorGemmIndexGenerator"
  it should "perform correctly" in simulate(new TensorGemmIndexGenerator)(
    new TensorGemmIndexGeneratorTester(_)
  )

  behavior of "TensorGemmPipelinedSplit"

  it should "perform simple operation" in simulate(
    new TensorGemmPipelinedSplit()
  )(new TensorGemmPipelinedTester(_))

  it should "be reset correctly" in simulate(new TensorGemm)(
    new TensorGemmResetTester(_)
  )
}
