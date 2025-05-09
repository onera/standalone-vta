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

package vta

import chisel3._
import vta.util.config._
import vta.shell._
import vta.core._
import vta.test._
import circt.stage.ChiselStage // CIRCT = Circuit IR Compilers and Tools

/** VTA.
 *
 * This file contains all the configurations supported by VTA.
 * These configurations are built in a mix/match form based on core
 * and shell configurations.
 */
class DefaultPynqConfig extends Config(new CoreConfig ++ new PynqConfig)
class DefaultF1Config extends Config(new CoreConfig ++ new F1Config)
class DefaultDe10Config extends Config(new CoreConfig ++ new De10Config)

object DefaultPynqConfig extends App {
  implicit val p: Parameters = new DefaultPynqConfig
  ChiselStage.emitSystemVerilog(new XilinxShell, args)
}

object DefaultF1Config extends App {
  implicit val p: Parameters = new DefaultF1Config
  ChiselStage.emitSystemVerilog(new XilinxShell, args)
}

object DefaultDe10Config extends App {
  implicit val p: Parameters = new DefaultDe10Config
  ChiselStage.emitSystemVerilog(new IntelShell, args)
}

object TestDefaultPynqConfig extends App {
  implicit val p: Parameters = new DefaultPynqConfig
  ChiselStage.emitSystemVerilog(new Test, args)
}

object TestDefaultF1Config extends App {
  implicit val p: Parameters = new DefaultF1Config
  ChiselStage.emitSystemVerilog(new Test, args)
}

object TestDefaultDe10Config extends App {
  implicit val p: Parameters = new DefaultDe10Config
  ChiselStage.emitSystemVerilog(new Test, args)
}
