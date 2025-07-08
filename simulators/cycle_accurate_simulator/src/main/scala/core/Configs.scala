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

import util.BinaryReader.computeJSONFile
import vta.util.config._

import scala.math.Fractional.Implicits.infixFractionalOps
import scala.math.pow

/** CoreConfig.
 *
 * This is one supported configuration for VTA. This file will
 * be eventually filled out with class configurations that can be
 * mixed/matched with Shell configurations for different backends.
 */
class CoreConfig extends Config((site, here, up) => {
  case CoreKey =>
    val params = computeJSONFile("vta_config.json", fromResources = false)
    CoreParams(
      batch = params("LOG_BATCH"),
      blockOut = params("LOG_BLOCK"),
      blockOutFactor = 1,
      blockIn = params("LOG_BLOCK"),
      inpBits = params("LOG_INP_WIDTH"),
      wgtBits = params("LOG_WGT_WIDTH"),
      uopBits = 32,
      accBits = params("LOG_ACC_WIDTH"),
      outBits = params("LOG_INP_WIDTH"),
      uopMemDepth = (params("LOG_UOP_BUFF_SIZE") * pow(2, 3)).toInt / (params("LOG_BATCH") * pow(2, 0).toInt * pow(2, 5).toInt), // 2048 de base mais ici 8192
      inpMemDepth = (params("LOG_INP_BUFF_SIZE") * pow(2, 3).toInt) / (params("LOG_BATCH") * params("LOG_BLOCK") * params("LOG_INP_WIDTH")), // 2048
      wgtMemDepth = (params("LOG_WGT_BUFF_SIZE") * pow(2, 3).toInt) / (params("LOG_BATCH") * params("LOG_BLOCK") * params("LOG_BLOCK") * params("LOG_WGT_WIDTH")), // 1024
      accMemDepth = (params("LOG_ACC_BUFF_SIZE") * pow(2, 3).toInt) / (params("LOG_BATCH") * params("LOG_BLOCK") * params("LOG_ACC_WIDTH")), // 2048
      outMemDepth = (params("LOG_INP_BUFF_SIZE") * pow(2, 3).toInt) / (params("LOG_BATCH") * params("LOG_BLOCK") * params("LOG_INP_WIDTH")), // 2048
      instQueueEntries = 512
    )
})
