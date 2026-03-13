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
import org.scalatest.Tag
import vta.util.config._

import vta.util.config._
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig
import chisel3.simulator.scalatest.ChiselSim
import vta.util.SimulationUtils.verilatorWithWaveDump
import chisel3.simulator.HasSimulator

object UnitTests extends Tag("UnitTests")
object LongTests extends Tag("LongTests")

trait AnyFlatSpecSim extends AnyFlatSpec with ChiselSim {

  implicit val p: Parameters = new DefaultPynqConfig

  implicit val verilatorWithVcd: HasSimulator = verilatorWithWaveDump
}
class GenericTest[T <: Module, C <: Parameters](
    tag: String,
    dutFactory: (Parameters) => T,
    testerFactory: (T) => Unit,
    isLongTest: Boolean = false
) extends AnyFlatSpec
    with ChiselSim {

  implicit val p: Parameters = new DefaultPynqConfig

  implicit val verilatorWithVcd: HasSimulator = verilatorWithWaveDump
  behavior of tag
  if (isLongTest) {
    it should "not have expect violations" taggedAs (LongTests) in {
      simulate(dutFactory(p), additionalResetCycles = 2) { c =>
        enableWaves()
        testerFactory(c)
      }
    }
  } else {
    it should "not have expect violations" taggedAs (UnitTests) in {
      simulate(dutFactory(p), additionalResetCycles = 2)(testerFactory)
    }
  }
}
