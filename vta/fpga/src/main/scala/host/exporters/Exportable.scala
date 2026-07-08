package fpga.host.exporters

import os.Path

trait Exportable[T] {
  def export(t: T, path: os.Path): Unit
}

object Exportable {

  /** Build an `Exportable[T]` from a write function, for artifacts that do more
    * than write `path` (e.g. the SD manifest also stages binaries).
    */
  def apply[T](write: (T, os.Path) => Unit): Exportable[T] =
    new Exportable[T] {
      def export(t: T, path: os.Path): Unit = write(t, path)
    }

  trait Instances {

    implicit class IsExportable[T](t: T)(implicit exportable: Exportable[T]) {
      def export(path: os.Path) = exportable.export(t, path)
    }
    implicit def emittableIsExportable[T](implicit
      emittable: Emittable[T]
    ): Exportable[T] =
      new Exportable[T] {
        def export(t: T, path: Path): Unit = {
          os.write.over(path, emittable.emit(t))
        }
      }
  }
}
