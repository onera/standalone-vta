package vta.util

import chisel3._
import chisel3.layer.Layer
import chisel3.layers.Verification
import chisel3.layer.LayerConfig
import chisel3.layer.DefaultOutputDir

object DebugLayer extends Layer(LayerConfig.Extract())
