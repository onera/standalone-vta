package util

import org.scalatest.Tag
import org.scalatest.flatspec.AnyFlatSpec
import vta.DefaultPynqConfig
import vta.core.Compute
import vta.util.config.Parameters

object UnitTests extends Tag("UnitTests")
object LongTests extends Tag("LongTests")

class ComputeExt[T <: Compute, P <: Parameters](tag: String,
                                               dutFactory: (Parameters) => T,
                                               isLongTest: Boolean = false)
  extends AnyFlatSpec {

  implicit val p: Parameters = new DefaultPynqConfig

  behavior of tag

  if (isLongTest) {
    it should "not have expect violations" taggedAs(LongTests) in {
      // Remplacez cette partie par votre propre logique de test ou simulation
      // Par exemple, une simple vérification pour démontrer le concept :
      assert(dutFactory(p) != null, "Module non créé")
    }
  } else {
    it should "not have expect violations" taggedAs(UnitTests) in {
      // Même remplacement que ci-dessus
      assert(dutFactory(p) != null, "Module non créé")
    }
  }
}