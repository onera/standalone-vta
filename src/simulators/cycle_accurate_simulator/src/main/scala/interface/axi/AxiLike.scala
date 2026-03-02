package vta.interface.axi

import chisel3._
import chisel3.util.{is, switch}

trait AxiLike[T <: Data] {
  def writeHandler(enabled: Bool): UInt

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
      val awBurst = RegInit(0.U)
      val bId = RegInit(0.U.asTypeOf(axi.b.bits.id))

      val awLenCounter = RegInit(0.U.asTypeOf(axi.aw.bits.len))
      val awAddr = RegInit(0.U.asTypeOf(axi.aw.bits.addr))
      val awWrapSize = awLen * (dataWidth / 8).U
      val awWrapEn = (awAddr & awWrapSize) === awWrapSize
      val writeState = RegInit(WriteState.idle)

      axi.aw.ready := awReady
      axi.w.ready := wReady && enabled
      axi.b.valid := bValid
      axi.b.bits.resp := bResp
      axi.b.bits.id := bId

      val awBurstWire = axi.aw.bits.burst
      // axi.aw.bits.len := awLen
      val addrLSB = (dataWidth / 32) + 1

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
            awBurstWire === 0.U || (awBurstWire === 1.U && !(axi.aw.bits.len === 0.U))
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
            is(0.U) {
              awAddr := awAddr
            }
            is(1.U) {
              awAddr := awAddr + 1.U
            }
            is(2.U) {
              when(awWrapEn) {
                awAddr := awAddr - awWrapSize
              }.otherwise {
                awAddr := awAddr + 1.U
              }
            }
            is(3.U) {
              awAddr := awAddr
            }

          }
        }

      awAddr

    }
    def readHandler(enabled: Bool) = {

      val idle :: raddr :: rdata :: Nil = util.Enum(3)

      val readState = RegInit(idle)

      val arReady = RegInit(false.B)
      val arLen = RegInit(0.U.asTypeOf(axi.ar.bits.len))
      val arBurst = RegInit(0.U)
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
      val addrWidth = axi.params.addrBits
      val arAddr = RegInit(0.U.asTypeOf(axi.ar.bits.addr))
      val arWrapSize = arLen * (dataWidth / 8).U
      val arWrapEn = (arAddr & arWrapSize) === arWrapSize

      // Handles read address increment
      when(axi.ar.fire) {
        when(axi.r.fire) {
          arLenCounter := 1.U
          when(
            arBurstWire === 0.U || (arBurstWire === 1.U && !(axi.ar.bits.len === 0.U))
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
            is(0.U) {
              arAddr := arAddr
            }
            is(1.U) {
              arAddr := arAddr + 1.U
            }
            is(2.U) {
              when(arWrapEn) {
                arAddr := arAddr - arWrapSize
              }.otherwise {
                arAddr := arAddr + 1.U
              }
            }
            is(3.U) {
              arAddr := arAddr
            }

          }

        }
      arAddr
    }
  }
}
