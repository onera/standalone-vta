package vta.parsers

import vta.models.CompilerOutputModel.{DependencyInfo,LayerDependency}

import scala.io.Source

object Dependency {

  private def toInt(s: String, default: Int = 0): Int =
    try s.trim.toInt
    catch { case _: NumberFormatException => default }

  private def toDouble(s: String, default: Double = 0.0): Double =
    try s.trim.toDouble
    catch { case _: NumberFormatException => default }

  /** Parse `dependency.csv` content. */
  def parse(source: Source): DependencyInfo = {
    val rows = source.getLines()
      .map(_.split(",", -1).map(_.trim))
      .filter(row => row.nonEmpty && row(0).nonEmpty)
      .toVector

    val executionOrder = rows
      .collect {
        case row if row.length >= 3 && scala.util.Try(row(0).toInt).isSuccess =>
          (row(0).toInt, row(1), row(2))
      }
      .sortBy(_._1)

    val imageRow = rows.find(_(0) == "image")
    val imageH =
      imageRow.map(r => if (r.length > 1) toInt(r(1)) else 0).getOrElse(0)
    val imageW =
      imageRow.map(r => if (r.length > 2) toInt(r(2)) else 0).getOrElse(0)

    val outputLayer = rows
      .find(_(0) == "output")
      .map(r => if (r.length > 1) r(1) else "")
      .getOrElse("")

    val skipKeys = Set("nb_steps", "image", "output")
    val layers = rows.collect {
      case row
          if scala.util.Try(row(0).toInt).isFailure &&
            !skipKeys.contains(row(0)) &&
            row.length >= 30 =>
        val key = row(0)
        val nbInp = toInt(row(29))
        val deps = (0 until nbInp).flatMap(k =>
          if (30 + k < row.length) Some(row(30 + k)) else None
        )
        key -> LayerDependency(
          processor = row(1),
          reshapeInfo = row(2),
          offsetA = toInt(row(3)),
          scaleA = toDouble(row(4)),
          offsetB = toInt(row(5)),
          scaleB = toDouble(row(6)),
          offsetU = toInt(row(7)),
          scaleU = toDouble(row(8)),
          offsetV = toInt(row(9)),
          scaleV = toDouble(row(10)),
          tensorCh = toInt(row(11)),
          tensorH = toInt(row(12)),
          tensorW = toInt(row(13)),
          kh = toInt(row(14)),
          kw = toInt(row(15)),
          sh = toInt(row(16)),
          sw = toInt(row(17)),
          pad =
            (toInt(row(18)), toInt(row(19)), toInt(row(20)), toInt(row(21))),
          outCh = toInt(row(22)),
          outH = toInt(row(23)),
          outW = toInt(row(24)),
          offsetC = toInt(row(25)),
          scaleC = toDouble(row(26)),
          scale = toDouble(row(27)),
          nbInp = nbInp,
          deps = deps
        )
    }.toMap

    DependencyInfo(
      executionOrder = executionOrder,
      layers = layers,
      imageH = imageH,
      imageW = imageW,
      outputLayer = outputLayer
    )
  }
}
