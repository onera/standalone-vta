package fpga.synthesis.models

object GoldenSupport {

  def sandbox(parts: String*): os.Path = {
    val d = parts.foldLeft(os.pwd / "build")(_ / _)
    os.remove.all(d)
    os.makeDir.all(d)
    d
  }
}
