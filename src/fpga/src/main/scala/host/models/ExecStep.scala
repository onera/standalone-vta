package fpga.host.models

/** One entry in nn_exec_steps[], with its index. Single source of truth for the
  * exec-step ordering shared by the exec-plan emitter
  * ([[fpga.host.transform.ExecPlanResolver]] / `HeaderRender.execPlan`) and the
  * CPU-debug map (which needs each CPU op's step_idx). Built by
  * [[fpga.host.transform.ExecSteps]].
  */
final case class ExecStep(stepIdx: Int, kind: String, layerName: String)