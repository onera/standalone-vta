package fpga.host.exporters

trait Emittable[T] {
  def emit(t: T): String
}

object Emittable {

  /** Build an `Emittable[T]` from a plain render function. Lets each instance be
    * a one-liner: `implicit val x: Emittable[T] = Emittable(SomeRender.foo)`.
    */
  def apply[T](render: T => String): Emittable[T] =
    new Emittable[T] {
      def emit(t: T): String = render(t)
    }

  trait Instances {

    implicit class IsEmittable[T](t: T)(implicit emittable: Emittable[T]) {
      def emit() = emittable.emit(t)
    }
  }
}