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
import chisel3.util.log2Ceil
import org.scalatest.matchers.should.Matchers

import vta.core.{CoreKey, Semaphore}
import vta.tags.UnitTests
import vta.util.AnyFlatSpecSim
import vta.util.config._

/** SemaphoreTest - dependency-counter corner cases (suspect #3).
  *
  * The VME cross-module dependency tracking uses `core.Semaphore`: producers
  * `spost`, consumers `swait`, and a counter records the outstanding token
  * count. The hazard is that the counter is only `counterBits` wide and
  * SATURATES (it drops `spost` once it hits its max, see Semaphore.scala), and
  * producers post unconditionally with no full-queue backpressure - unlike the
  * original VTA dependence FIFO. A schedule that lets one module run more than
  * `2**counterBits - 1` posts ahead therefore loses tokens, and the consumer
  * later waits forever on a token that was silently dropped -> pipeline hang.
  */
@UnitTests
class SemaphoreTest extends AnyFlatSpecSim with Matchers {
  behavior of "Semaphore"

  /** Post `n` tokens (spost high, swait low), then drain for `drainCycles`,
    * asserting `swait` whenever the semaphore is ready. Returns the number of
    * waits actually served (i.e. how many of the posts were observable).
    */
  private def postThenDrain(dut: Semaphore, n: Int, drainCycles: Int): Int = {
    dut.io.spost.poke(false.B)
    dut.io.swait.poke(false.B)
    for (_ <- 0 until n) {
      dut.io.spost.poke(true.B)
      dut.io.swait.poke(false.B)
      dut.clock.step()
    }
    dut.io.spost.poke(false.B)
    var served = 0
    for (_ <- 0 until drainCycles) {
      if (dut.io.sready.peekBoolean()) {
        dut.io.swait.poke(true.B)
        served += 1
      } else {
        dut.io.swait.poke(false.B)
      }
      dut.clock.step()
    }
    dut.io.swait.poke(false.B)
    served
  }

  it should "serve every posted token within its counter capacity" in {
    simulate(new Semaphore(counterBits = 8, counterInitValue = 0)) { dut =>
      dut.io.spost.poke(false.B)
      dut.io.swait.poke(false.B)
      dut.clock.step()
      // 100 < capacity (255): no saturation, every post must be served.
      val served = postThenDrain(dut, n = 100, drainCycles = 200)
      served shouldBe 100
    }
  }

  // #3: a dependency primitive must not lose posts - every `spost` must be
  // matched by exactly one `swait`, regardless of how far the producer runs
  // ahead. The counter is sized to the worst-case outstanding count (a producer
  // can run at most instQueueEntries ahead), so it cannot saturate. 300 posts
  // exceed an 8-bit counter's range (255) but fit the sized counter, so all 300
  // must be served.
  private val semBits = log2Ceil(p(CoreKey).instQueueEntries) + 1

  it should "not lose posts beyond 8-bit counter range (#3)" in {
    simulate(new Semaphore(counterBits = semBits, counterInitValue = 0)) {
      dut =>
        dut.io.spost.poke(false.B)
        dut.io.swait.poke(false.B)
        dut.clock.step()
        val served = postThenDrain(dut, n = 300, drainCycles = 400)
        served shouldBe 300
    }
  }
}
