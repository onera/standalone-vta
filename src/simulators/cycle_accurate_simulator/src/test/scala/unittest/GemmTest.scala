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

import vta.core._
import vta.util.config._
import vta.testing.tags.UnitTests

@UnitTests
class GemmTest extends AnyFlatSpecSim {

  "MAC" should "compute a multiplication accumulation" in {
    simulate(new MAC) { c =>
      c.io.a.poke(-1)
      c.io.b.poke(7)
      c.io.c.poke(10)
      c.clock.step()
      c.io.y.expect(3)
      c.io.a.poke(-2)
      c.io.b.poke(7)
      c.io.c.poke(11)
      c.clock.step()
      c.io.y.expect(-3)
    }
  }

  "PipeAdder" should "compute an addition" in {

    simulate(new PipeAdder()) { c =>
      c.io.a.poke(-1)
      c.io.b.poke(7)
      c.clock.step()
      c.io.y.expect(6)
      c.io.a.poke(-2)
      c.io.b.poke(7)
      c.clock.step()
      c.io.y.expect(5)
    }
  }

  "Adder" should "compute additions" in {

    simulate(new Adder()) { c =>
      c.io.a.poke(-1)
      c.io.b.poke(7)
      c.io.y.expect(6)
      c.clock.step()

      c.io.a.poke(-2)
      c.io.b.poke(7)
      c.io.y.expect(5)
      c.clock.step()
    }
  }

  "DotProduct" should "compute a dot product" in {

    simulate(new DotProduct()) { c =>
      for { i <- 0 until 16 } {
        c.io.a(i).poke(if (i % 2 == 0) 1 else -1)
        c.io.b(i).poke(i)
      }
      c.clock.step()
      for { i <- 0 until 16 } {
        c.io.a(i).poke(if (i % 2 == 1) 1 else -1)
        c.io.b(i).poke(i)
      }
      c.clock.step()
      c.io.y.expect(-8)
      c.clock.step()
      c.io.y.expect(8)
    }
  }
}
