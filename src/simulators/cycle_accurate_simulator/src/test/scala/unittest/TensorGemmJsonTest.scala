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

import chisel3._
import chisel3.util._
import unittest.util._
import vta.core._
import vta.util.config._

import scala.io._
import scala.language.postfixOps
import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.scala.DefaultScalaModule
import chisel3.simulator.ChiselSim
import unittest.mocks.TensorGemmJsonTester
import vta.tags

class TensorGemmJsonTest extends AnyFlatSpecSim {

  behavior of "TensorGemmPipelinedSplit"

  it should "run gemm_1uop_overflow_offset.json without errors" in simulate(
    new TensorGemmPipelinedSplit()
  )(new TensorGemmJsonTester(_, "/gemm_1uop_overflow_offset.json"))

  it should "run gemm_2uop_overflow_cascaded.json without errors" in simulate(
    new TensorGemmPipelinedSplit()
  )(new TensorGemmJsonTester(_, "/gemm_2uop_overflow_cascaded.json"))
}
