package vta.util

import chisel3._
import chisel3.layer.Layer
import chisel3.layers.Verification
import chisel3.layer.LayerConfig

object UserDefined {

  implicit val root: Layer = Verification
  object Debug extends Layer(LayerConfig.Inline)
}
