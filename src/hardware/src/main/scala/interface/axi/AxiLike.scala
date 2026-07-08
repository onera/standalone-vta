package vta.interface.axi

import chisel3._
import chisel3.util._

trait AxiLike[T <: Data] {

  /** Handles the axi client write channel protocol
    *
    * @param enabled
    *   writing enabled signal
    * @return
    *   the write address
    */
  def writeHandler(enabled: Bool): UInt

  /** Handles the axi client read channel protocol
    *
    * @param enabled
    *   reading enabled signal
    * @return
    *   the read address
    */
  def readHandler(enabled: Bool): UInt
}

object AxiLike {

  implicit class AXIClientIsAxiLike(axi: AXIClient) extends AxiLike[AXIClient] {

    def writeHandler(enabled: Bool) = {

      val dataWidth = axi.params.dataBits

      object WriteState extends ChiselEnum {
        val idle, waddr, wdata = Value
      }

      val awReady = RegInit(false.B)
      val wReady = RegInit(false.B)
      val bValid = RegInit(false.B)
      val bResp = RegInit(false.B)
      val awLen = RegInit(0.U.asTypeOf(axi.aw.bits.len))
      val awBurst = RegInit(BurstType.fixed)
      val bId = RegInit(0.U.asTypeOf(axi.b.bits.id))

      val awLenCounter = RegInit(0.U.asTypeOf(axi.aw.bits.len))
      val awAddr = RegInit(0.U.asTypeOf(axi.aw.bits.addr))
      val awWrapSize = awLen * (dataWidth / 8).U
      val awWrapEn = (awAddr & awWrapSize) === awWrapSize
      val awSize = RegInit(0.U.asTypeOf(axi.aw.bits.size))
      val writeState = RegInit(WriteState.idle)

      axi.aw.ready := awReady
      axi.w.ready := wReady && enabled
      axi.b.valid := bValid
      axi.b.bits.resp := bResp
      axi.b.bits.id := bId

      val awBurstWire = axi.aw.bits.burst
      // axi.aw.bits.len := awLen
      // val addrLSB = (dataWidth / 32) + 1

      switch(writeState) {
        is(WriteState.idle) {
          awReady := true.B
          wReady := false.B
          writeState := WriteState.waddr
        }
        is(WriteState.waddr) {
          when(axi.aw.fire) {
            when(axi.w.fire && axi.w.bits.last) {
              bValid := true.B
              awReady := true.B
              wReady := false.B
              writeState := WriteState.waddr
            }.otherwise({
              when(axi.b.fire) {
                bValid := false.B
              }
              writeState := WriteState.wdata
              awReady := false.B
              wReady := true.B

            })
            awBurst := axi.aw.bits.burst
            awSize := axi.aw.bits.size
            awLen := axi.aw.bits.len
            bId := axi.aw.bits.id
          }.otherwise({
            writeState := writeState
            when(axi.b.fire) {
              bValid := false.B
            }
          })
        }

        is(WriteState.wdata) {
          when(axi.w.fire && axi.w.bits.last) {
            writeState := WriteState.waddr
            bValid := true.B
            awReady := true.B
            wReady := false.B
          }.otherwise({
            writeState := writeState
            wReady := true.B
          })
        }
      }

      // Write address increment
      when(axi.aw.fire) {
        when(axi.w.valid) {
          awLenCounter := 1.U
          when(
            awBurstWire === BurstType.fixed || (awBurstWire === BurstType.increment && !(axi.aw.bits.len === 0.U))
          ) {
            awAddr := axi.aw.bits.addr
          }
        }.otherwise({
          awLenCounter := 0.U
          awAddr := axi.aw.bits.addr
        })

      }
        .elsewhen(awLenCounter < awLen && axi.w.valid) {
          awLenCounter := awLenCounter + 1.U
          switch(awBurst) {
            is(BurstType.fixed) {
              awAddr := awAddr
            }
            is(BurstType.increment) {
              awAddr := awAddr + (1.U << awSize)
            }
            is(BurstType.wrapped) {
              when(awWrapEn) {
                awAddr := awAddr - awWrapSize
              }.otherwise {
                awAddr := awAddr + 1.U << awSize
              }
            }
          }
        }

      // TODO: add assertions for proper verification of the axi protocol
      // when(axi.aw.fire) {
      //   assert(
      //     axi.aw.bits.burst === fixed && axi.aw.bits.len + 1.U >= 16.U,
      //     "[AXI] for fixed bursts, length can be up to 16"
      //   )
      //   assert(
      //     axi.aw.bits.addr % 4096.U === ((axi.aw.bits.addr + (axi.aw.bits.len + 1.U) * axi.aw.bits.size)) % 4096.U,
      //     "[AXI] a transaction should not cross 4kB boundary"
      //   )
      //   assert(
      //     (axi.aw.bits.len + 1.U) * axi.aw.bits.size < 4096.U,
      //     "[AXI] a transaction cannot issue more than 4KB in a single burst"
      //   )
      // }

      awAddr

    }
    def readHandler(enabled: Bool) = {

      val idle :: raddr :: rdata :: Nil = util.Enum(3)

      val readState = RegInit(idle)

      val arReady = RegInit(false.B)
      val arLen = RegInit(0.U.asTypeOf(axi.ar.bits.len))
      val arBurst = RegInit(BurstType.increment)
      val rValid = RegInit(false.B)
      val rReady = RegInit(false.B)
      val rLast = RegInit(false.B)
      val rResp = RegInit(false.B)
      val rId = RegInit(0.U.asTypeOf(axi.r.bits.id))

      axi.ar.ready := arReady && enabled
      axi.r.valid := rValid
      axi.r.bits.last := rLast
      axi.r.bits.id := rId
      axi.r.bits.resp := rResp

      val arLenCounter = RegInit(0.U.asTypeOf(axi.ar.bits.len))

      val arSize = RegInit(0.U.asTypeOf(axi.ar.bits.size))
      val arBurstWire = axi.ar.bits.burst
      // ReadState machine

      switch(readState) {
        is(idle) {
          readState := raddr
          arReady := true.B
        }
        is(raddr) {
          when(axi.ar.fire) {
            readState := rdata
            rValid := true.B
            arReady := false.B
            rId := axi.r.bits.id
            arBurst := axi.ar.bits.burst
            arLen := axi.ar.bits.len
            arSize := axi.ar.bits.size
          }.otherwise(readState := readState)
        }
        is(rdata) {
          when(axi.r.fire && axi.r.bits.last) {
            rValid := false.B
            rReady := false.B
            arReady := true.B
            rLast := false.B
            readState := raddr
          }.otherwise(readState := readState)
        }
      }

      axi.r.bits.last := (arLenCounter === arLen && axi.r.fire)
      val dataWidth = axi.params.dataBits
      val arAddr = RegInit(0.U.asTypeOf(axi.ar.bits.addr))
      val arWrapSize = arLen * (dataWidth / 8).U
      val arWrapEn = (arAddr & arWrapSize) === arWrapSize

      // Handles read address increment
      when(axi.ar.fire) {
        when(axi.r.fire) {
          arLenCounter := 1.U
          when(
            arBurstWire === BurstType.fixed || (arBurstWire === BurstType.increment && !(axi.ar.bits.len === 0.U))
          ) {
            arAddr := axi.ar.bits.addr
          }
        }.otherwise({
          arLenCounter := 0.U
          arAddr := axi.ar.bits.addr
        })

      }
        .elsewhen(arLenCounter <= arLen && axi.r.fire) {
          arLenCounter := arLenCounter + 1.U
          switch(arBurst) {
            is(BurstType.fixed) {
              arAddr := arAddr
            }
            is(BurstType.increment) {
              arAddr := arAddr + (1.U << arSize)
            }
            is(BurstType.wrapped) {
              when(arWrapEn) {
                arAddr := arAddr - arWrapSize
              }.otherwise {
                arAddr := arAddr + (1.U << arSize)
              }
            }
          }

        }
      arAddr
    }
  }
  implicit class AxiLiteClientIsAxiLike(axi: AXILiteClient)
      extends AxiLike[AXILiteClient] {

    override def writeHandler(enabled: Bool) = {

      val dataWidth = axi.params.dataBits

      object WriteState extends ChiselEnum {
        val idle, waddr, wdata = Value
      }

      val awReady = RegInit(false.B)
      val wReady = RegInit(false.B)
      val bValid = RegInit(false.B)
      val bResp = RegInit(false.B)

      val awAddr = RegInit(0.U.asTypeOf(axi.aw.bits.addr))
      val writeState = RegInit(WriteState.idle)

      axi.aw.ready := awReady
      axi.w.ready := wReady && enabled
      axi.b.valid := bValid
      axi.b.bits.resp := bResp

      switch(writeState) {
        is(WriteState.idle) {
          awReady := true.B
          wReady := false.B
          writeState := WriteState.waddr
        }
        is(WriteState.waddr) {
          when(axi.aw.fire) {
            when(axi.w.fire) {
              bValid := true.B
              awReady := true.B
              wReady := false.B
              writeState := WriteState.waddr
            }.otherwise({
              when(axi.b.fire) {
                bValid := false.B
              }
              writeState := WriteState.wdata
              awReady := false.B
              wReady := true.B

            })
          }.otherwise({
            writeState := writeState
            when(axi.b.fire) {
              bValid := false.B
            }
          })
        }

        is(WriteState.wdata) {
          when(axi.w.fire) {
            writeState := WriteState.waddr
            bValid := true.B
            awReady := true.B
            wReady := false.B
          }.otherwise({
            writeState := writeState
            wReady := true.B
          })
        }
      }

      // Write address increment
      when(axi.aw.fire) {
        awAddr := axi.aw.bits.addr
      }

      awAddr

    }
    // override def readHandler(enabled: Bool): UInt = {
    //
    //   val sReadAddress :: sReadData :: Nil = util.Enum(2)
    //   val rstate = RegInit(sReadAddress)
    //   switch(rstate) {
    //     is(sReadAddress) {
    //       when(axi.ar.valid) {
    //         rstate := sReadData
    //       }
    //     }
    //     is(sReadData) {
    //       when(axi.r.ready) {
    //         rstate := sReadAddress
    //       }
    //     }
    //   }
    //
    //   axi.ar.ready := rstate === sReadAddress
    //   axi.r.valid := rstate === sReadData
    //   axi.r.bits.resp := 0.U
    //   axi.ar.bits.addr
    // }
    def readHandler(enabled: Bool) = {

      val idle :: raddr :: rdata :: Nil = util.Enum(3)

      val readState = RegInit(idle)

      val arReady = RegInit(false.B)
      val rValid = RegInit(false.B)
      val rReady = RegInit(false.B)
      val rResp = RegInit(false.B)

      axi.ar.ready := arReady && enabled
      axi.r.valid := rValid
      axi.r.bits.resp := rResp

      // ReadState machine

      switch(readState) {
        is(idle) {
          readState := raddr
          arReady := true.B
        }
        is(raddr) {
          when(axi.ar.fire) {
            readState := rdata
            rValid := true.B
            arReady := false.B
          }.otherwise(readState := readState)
        }
        is(rdata) {
          when(axi.r.fire) {
            rValid := false.B
            rReady := false.B
            arReady := true.B
            readState := raddr
          }.otherwise(readState := readState)
        }
      }

      val dataWidth = axi.params.dataBits
      val arAddr = RegInit(0.U.asTypeOf(axi.ar.bits.addr))

      // Handles read address increment
      when(axi.ar.fire) {
        arAddr := axi.ar.bits.addr
      }
      arAddr
    }
  }

  /** Master-side counterpart of the slave AxiLike handlers. The existing
    * AxiLike trait (writeHandler/readHandler returning the latched address) is
    * slave-shaped, so these master helpers live alongside as the master
    * counterpart rather than implementing that trait signature. Each helper
    * instantiates one single-beat, single-outstanding FSM (call once per
    * AXILiteMaster) and drives its own disjoint channels: writeHandler drives
    * aw/w/b, readHandler drives ar/r.
    */
  implicit class AXILiteMasterIsAxiLike(axi: AXILiteMaster) {

    /** Single-beat AXI-Lite write. Pulse `start` for one cycle; addr/data are
      * latched on start. Returns a one-cycle `done` strobe on B handshake.
      */
    def writeHandler(start: Bool, addr: UInt, data: UInt): Bool = {
      val sIdle :: sAw :: sW :: sB :: Nil = Enum(4)
      val st = RegInit(sIdle)
      val addrR = Reg(UInt(axi.params.addrBits.W))
      val dataR = Reg(UInt(axi.params.dataBits.W))
      val done = WireDefault(false.B)

      axi.aw.valid := st === sAw
      axi.aw.bits.addr := addrR
      axi.w.valid := st === sW
      axi.w.bits.data := dataR
      axi.w.bits.strb := Fill(axi.params.strbBits, 1.U)
      axi.b.ready := st === sB

      switch(st) {
        is(sIdle) { when(start) { addrR := addr; dataR := data; st := sAw } }
        is(sAw) { when(axi.aw.fire) { st := sW } }
        is(sW) { when(axi.w.fire) { st := sB } }
        is(sB) { when(axi.b.fire) { st := sIdle; done := true.B } }
      }
      done
    }

    /** Single-beat AXI-Lite read. Pulse `start` for one cycle; addr latched on
      * start. Returns (data, done) where data is valid on the done strobe.
      */
    def readHandler(start: Bool, addr: UInt): (UInt, Bool) = {
      val sIdle :: sAr :: sR :: Nil = Enum(3)
      val st = RegInit(sIdle)
      val addrR = Reg(UInt(axi.params.addrBits.W))
      val dataR = RegInit(0.U(axi.params.dataBits.W))
      val done = WireDefault(false.B)

      axi.ar.valid := st === sAr
      axi.ar.bits.addr := addrR
      axi.r.ready := st === sR

      switch(st) {
        is(sIdle) { when(start) { addrR := addr; st := sAr } }
        is(sAr) { when(axi.ar.fire) { st := sR } }
        is(sR) {
          when(axi.r.fire) {
            dataR := axi.r.bits.data; st := sIdle; done := true.B
          }
        }
      }
      // data valid live on the done cycle, held in dataR afterwards
      (Mux(done, axi.r.bits.data, dataR), done)
    }
  }
}
