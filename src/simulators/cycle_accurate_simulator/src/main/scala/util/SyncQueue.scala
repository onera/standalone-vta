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

package vta.util

import chisel3._
import chisel3.util._

/** Synchronous queue factory object
  */
object SyncQueue {

  /** SyncQueue implementation if entries < 4 or forceSimpleQueue is true, then
    * use simple queue, else use SyncReadMem
    *
    * @param gen
    *   chisel type of data loaded in the queue
    * @param entries
    *   depth of the queue
    * @param forceSimpleQueue
    * @param pipe
    * @param flow
    * @return
    */
  def apply[U <: Data, T <: ReadyValidIO[U], A <: Queue[T]](
      gen: U,
      entries: Int,
      forceSimpleQueue: Boolean = false,
      pipe: Boolean = false,
      flow: Boolean = false
  ) = {
    if (forceSimpleQueue || entries < 4) {
      new Queue(gen, entries, pipe, flow)
    } else {
      new Queue(gen, entries, pipe, flow, useSyncReadMem = true)

    }
  }
}
