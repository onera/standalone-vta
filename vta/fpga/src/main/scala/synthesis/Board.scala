package fpga.synthesis

import com.fasterxml.jackson.databind.ObjectMapper
import scala.jdk.CollectionConverters._

final case class Board(
  name: String,
  part: String,
  boardPart: String,
  isVersal: Boolean,
  psIp: String,
  psCell: String,
  psPresetRule: String,
  psPresetConfig: String,
  boardRepo: String,
  plClockMhz: String,
  plClockProperty: String,
  cpu: String,
  psConfig: Seq[(String, String)], // ordered
  nocConfig: Seq[(String, String)], // ordered; empty => renderer uses defaults
  ports: Map[String, String],
  psClkAclks: Seq[String],
  addresses: Seq[(String, String, String, String)], // space, seg, offset, range
  addressExcludes: Seq[(String, String)]
)

object Board {
  private val mapper = new ObjectMapper()

  def load(path: String): Board = {
    val root = mapper.readTree(os.read(os.Path(path, os.pwd)))
    def str(k: String, default: String = ""): String =
      if (root.has(k) && !root.get(k).isNull) root.get(k).asText else default
    def orderedObj(k: String): Seq[(String, String)] =
      if (!root.has(k)) Nil
      else
        root
          .get(k)
          .properties()
          .iterator()
          .asScala
          .map(e => e.getKey -> e.getValue.asText)
          .toSeq
    val portsNode =
      if (root.has("ports") && !root.get("ports").isNull) root.get("ports")
      else sys.error(s"board JSON missing 'ports'")
    val ports = portsNode
      .properties()
      .asScala
      .filter(_.getValue.isTextual)
      .map(e => e.getKey -> e.getValue.asText)
      .toMap
    val psClkAclks =
      if (portsNode.has("ps_clk_aclks"))
        portsNode.get("ps_clk_aclks").elements().asScala.map(_.asText).toSeq
      else Nil
    val addressesNode =
      if (root.has("addresses") && !root.get("addresses").isNull)
        root.get("addresses")
      else sys.error(s"board JSON missing 'addresses'")
    val addresses = addressesNode
      .elements()
      .asScala
      .map { a =>
        (
          a.get("space").asText,
          a.get("seg").asText,
          a.get("offset").asText,
          a.get("range").asText
        )
      }
      .toSeq
    val excludes =
      if (!root.has("address_excludes")) Nil
      else
        root
          .get("address_excludes")
          .elements()
          .asScala
          .map(e => e.get("space").asText -> e.get("seg").asText)
          .toSeq
    Board(
      name = str("name"),
      part = str("part"),
      boardPart = str("board_part"),
      isVersal = root.has("is_versal") && root.get("is_versal").asBoolean,
      psIp = str("ps_ip"),
      psCell = str("ps_cell"),
      psPresetRule = str("ps_preset_rule"),
      psPresetConfig = str("ps_preset_config", "apply_board_preset 1"),
      boardRepo = str("board_repo"),
      plClockMhz = str("pl_clock_mhz"),
      plClockProperty = str("pl_clock_property"),
      cpu = str("cpu"),
      psConfig = orderedObj("ps_config"),
      nocConfig = orderedObj("noc_config"),
      ports = ports,
      psClkAclks = psClkAclks,
      addresses = addresses,
      addressExcludes = excludes
    )
  }
}
