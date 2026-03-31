package vta.util

import chisel3.layer.Layer
import chisel3.layer.LayerConfig
import chisel3.layers.Verification

object UserDefined {

  implicit val root: Layer = Verification
  object Debug extends Layer(LayerConfig.Inline)
}
