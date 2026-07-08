package fpga.host.utils

/** Format a Double exactly as CPython's repr()/str() would, so generated C
  * sources are byte-identical to the Python tool. CPython uses fixed notation
  * for decimal exponent in [-4, 16), scientific otherwise (signed, >=2 exp
  * digits, bare mantissa when one significant digit).
  */
object PyFmt {
  def float(x: Double): String = {
    if (x == 0.0)
      return if (java.lang.Double.doubleToRawLongBits(x) != 0L) "-0.0"
      else "0.0"
    val neg = x < 0
    val ax = math.abs(x)
    val js = java.lang.Double.toString(ax) // shortest round-trip
    val (mant, exp) =
      if (js.indexOf('E') >= 0) { val a = js.split("E"); (a(0), a(1).toInt) }
      else (js, 0)
    val dot = mant.indexOf('.')
    val intPart = mant.substring(0, dot)
    val fracPart = mant.substring(dot + 1)
    val intIsZero = intPart.forall(_ == '0')
    val decExp =
      if (!intIsZero) (intPart.length - 1) + exp
      else -(fracPart.takeWhile(_ == '0').length + 1) + exp
    val trimmed =
      (intPart + fracPart)
        .dropWhile(_ == '0')
        .reverse
        .dropWhile(_ == '0')
        .reverse
    val digits = if (trimmed.isEmpty) "0" else trimmed
    val body =
      if (decExp < -4 || decExp >= 16) sci(digits, decExp)
      else fixed(digits, decExp)
    if (neg) "-" + body else body
  }

  private def fixed(digits: String, decExp: Int): String =
    if (decExp >= 0) {
      if (decExp + 1 >= digits.length)
        digits + ("0" * (decExp + 1 - digits.length)) + ".0"
      else
        digits.substring(0, decExp + 1) + "." + digits.substring(decExp + 1)
    } else "0." + ("0" * (-decExp - 1)) + digits

  private def sci(digits: String, decExp: Int): String = {
    val mant =
      if (digits.length == 1) digits else digits.head + "." + digits.tail
    val e = math.abs(decExp)
    val es = if (e < 10) f"0$e" else e.toString
    s"${mant}e${if (decExp < 0) "-" else "+"}$es"
  }
}
