package vta.util

import chisel3.layer.Layer
import chisel3.layer.LayerConfig
import chisel3.layers.Verification

object UserDefined {

  implicit val root: Layer = Verification
  object DebugLayer extends Layer(LayerConfig.Inline)
}
