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

package vta.shell

import vta.core.CoreKey
import vta.core.CoreParams
import vta.interface.axi._
import vta.util.config._

/** PynqConfig. Shell configuration for Pynq */
class PynqConfig
    extends Config((site, here, up) => { case ShellKey =>
      ShellParams(
        hostParams = AXIParams(
          coherent = false,
          addrBits = 16,
          dataBits = 32,
          lenBits = 8,
          userBits = 1
        ),
        memParams = AXIParams(
          coherent = true,
          addrBits = 32,
          idBits = 8,
          dataBits = 64,
          lenBits = 8,
          userBits = 1
        ),
        vcrParams = VCRParams(),
        vmeParams = VMEParams()
      )
    })

class ZusysConfig
    extends Config((site, here, up) => {
      // Default configuration
      case CoreKey =>
        CoreParams(
          batch = 1,
          blockOut = 16,
          blockOutFactor = 1,
          blockIn = 16,
          inpBits = 8,
          wgtBits = 8,
          uopBits = 32,
          accBits = 32,
          outBits = 8,
          uopMemDepth = 2048,
          inpMemDepth = 2048,
          wgtMemDepth = 1024,
          accMemDepth = 2048,
          outMemDepth = 2048,
          instQueueEntries = 512
        )
      // Copy of PynqConfig in vta.shell.Configs.PynqConfig
      case ShellKey =>
        ShellParams(
          hostParams = AXIParams(
            coherent = false,
            addrBits = 16,
            dataBits = 32,
            lenBits = 8,
            userBits = 1
          ),
          memParams = AXIParams(
            coherent = true,
            addrBits = 32,
            dataBits = 64,
            lenBits = 8,
            userBits = 1
          ),
          vcrParams = VCRParams(),
          vmeParams = VMEParams()
        )
    })

/** F1Config. Shell configuration for F1 */
class F1Config
    extends Config((site, here, up) => { case ShellKey =>
      ShellParams(
        hostParams = AXIParams(
          coherent = false,
          addrBits = 16,
          dataBits = 32,
          lenBits = 8,
          userBits = 1
        ),
        memParams = AXIParams(
          coherent = false,
          addrBits = 64,
          dataBits = 64,
          lenBits = 8,
          userBits = 1
        ),
        vcrParams = VCRParams(),
        vmeParams = VMEParams()
      )
    })

/** De10Config. Shell configuration for De10 */
class De10Config
    extends Config((site, here, up) => { case ShellKey =>
      ShellParams(
        hostParams =
          AXIParams(addrBits = 16, dataBits = 32, idBits = 13, lenBits = 4),
        memParams = AXIParams(
          addrBits = 32,
          dataBits = 64,
          userBits = 5,
          lenBits = 4, // limit to 16 beats, instead of 256 beats in AXI4
          coherent = true
        ),
        vcrParams = VCRParams(),
        vmeParams = VMEParams()
      )
    })
