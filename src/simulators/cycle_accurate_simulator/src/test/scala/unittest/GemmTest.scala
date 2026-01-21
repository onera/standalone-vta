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
import chisel3.simulator.ChiselSim

class MACTester(c: MAC) extends ChiselSim {
  c.io.a.poke( -1)
  c.io.b.poke(  7)
  c.io.c.poke( 10)
  c.clock.step()
  c.io.y.expect(3)
  c.io.a.poke( -2)
  c.io.b.poke(  7)
  c.io.c.poke( 11)
  c.clock.step()
  c.io.y.expect(-3)
}

class MACTest extends GenericTest("MACTest", (p:Parameters) => new MAC(),
  (c:MAC) => new MACTester(c))

class PipeAdderTester(c: PipeAdder) extends ChiselSim {
  c.io.a.poke( -1)
  c.io.b.poke(  7)
  c.clock.step()
  c.io.y.expect(6)
  c.io.a.poke( -2)
  c.io.b.poke(  7)
  c.clock.step()
  c.io.y.expect(5)
}

class PipeAdderTest extends GenericTest("PipeAdderTest", (p:Parameters) => new PipeAdder(),
  (c:PipeAdder) => new PipeAdderTester(c))

class AdderTester(c: Adder) extends ChiselSim {
  c.io.a.poke( -1)
  c.io.b.poke(  7)
  c.io.y.expect(6)
  c.clock.step()

  c.io.a.poke( -2)
  c.io.b.poke(  7)
  c.io.y.expect(5)
  c.clock.step()
}

class AdderTest extends GenericTest("AdderTest", (p:Parameters) => new Adder(),
  (c:Adder) => new AdderTester(c))

class DotProductTester(c: DotProduct) extends ChiselSim {
  for {i<- 0 until 16} {
    c.io.a(i).poke( if (i %2 == 0) 1 else -1)
    c.io.b(i).poke( i)
  }
  c.clock.step()
  for {i<- 0 until 16} {
    c.io.a(i).poke( if (i %2 == 1) 1 else -1)
    c.io.b(i).poke( i)
  }
  c.clock.step()
  c.io.y.expect(-8)
  c.clock.step()
  c.io.y.expect(8)
}

class DotProductTest extends GenericTest("DotProductTest", (p:Parameters) => new DotProduct(),
  (c:DotProduct) => new DotProductTester(c))
