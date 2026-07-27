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

package vta.core

import vta.parsers.ConfigParser.{getConfigParametersFromMap, parseConfigJson}
import vta.util.config._

import scala.math.pow

/** CoreConfig.
 *
 * This is one supported configuration for VTA. This file will be eventually
 * filled out with class configurations that can be mixed/matched with Shell
 * configurations for different backends.
 */
class CoreConfig
extends Config((site, here, up) => { case CoreKey =>
  DefaultCoreConfig.config
  // val configFileName =
  //   System.getProperty("vta.config.file", "vta_config.json")
  // val useResources =
  //   System.getProperty("vta.config.fromResources", "false").toBoolean
  // val decodedJson = parseConfigJson(configFileName, fromResources = useResources).get
  // val target = decodedJson("TARGET")
  // val params = getConfigParametersFromMap(decodedJson)
  // CoreConfig.coreParams(params, target)
})

object DefaultCoreConfig {

  private lazy val decodedJson= {
    val configFileName =
      System.getProperty("vta.config.file", "vta_config.json")
    val useResources =
      System.getProperty("vta.config.fromResources", "false").toBoolean
    parseConfigJson(configFileName, fromResources = useResources).get
  }

  def target = decodedJson("TARGET")
  lazy val params = getConfigParametersFromMap(decodedJson)
  lazy val config = 
    CoreConfig.coreParams(params, target)

}

object CoreConfig {

  /** Build [[CoreParams]] from already-resolved config values (each `LOG_*` is
   * a power of two, as produced by [[computeJSONFile]]) plus the target
   * string. Shared by the JVM-property-driven [[CoreConfig]] and any explicit
   * override (e.g. a host test that pins a specific config via
   * [[CoreConfigFromValues]]).
   */
  def coreParams(params: Map[String, Int], target: String): CoreParams =
    CoreParams(
      target = target,
      batch = params("LOG_BATCH"),
      blockOut = params("LOG_BLOCK"),
      blockOutFactor = 1,
      blockIn = params("LOG_BLOCK"),
      inpBits = params("LOG_INP_WIDTH"),
      wgtBits = params("LOG_WGT_WIDTH"),
      uopBits = 32,
      accBits = params("LOG_ACC_WIDTH"),
      outBits = params("LOG_OUT_WIDTH"),
      uopMemDepth = (params("LOG_UOP_BUFF_SIZE") * pow(2, 3)).toInt / (params(
        "LOG_BATCH"
        ) * pow(2, 0).toInt * pow(
          2,
          5
        ).toInt), // is 2048 here but used to be 8192
    inpMemDepth = (params("LOG_INP_BUFF_SIZE") * pow(2, 3).toInt) / (params(
      "LOG_BATCH"
    ) * params("LOG_BLOCK") * params("LOG_INP_WIDTH")),
wgtMemDepth = (params("LOG_WGT_BUFF_SIZE") * pow(2, 3).toInt) / (params(
  "LOG_BATCH"
  ) * params("LOG_BLOCK") * params("LOG_BLOCK") * params(
    "LOG_WGT_WIDTH"
  )),
      accMemDepth = (params("LOG_ACC_BUFF_SIZE") * pow(2, 3).toInt) / (params(
        "LOG_BATCH"
      ) * params("LOG_BLOCK") * params("LOG_ACC_WIDTH")),
  outMemDepth = (params("LOG_INP_BUFF_SIZE") * pow(2, 3).toInt) / (params(
    "LOG_BATCH"
  ) * params("LOG_BLOCK") * params("LOG_INP_WIDTH")),
      instQueueEntries = 512
    )
}

/** A [[CoreConfig]] built from explicit, pre-resolved config values instead of
 * the JVM-global `vta.config.file` property. Lets a tool or test pin a
 * specific hardware config (read directly from a file, with no `config/`-dir
 * resolution and no system-property mutation).
 */
class CoreConfigFromValues(params: Map[String, Int], target: String)
extends Config((site, here, up) => { case CoreKey =>
  CoreConfig.coreParams(params, target)
})
