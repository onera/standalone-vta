"""Emitters for the per-layer / per-CPU-op isolation-check artifacts."""

import os
from typing import Dict, List, Tuple

from .config import ConfigParams, _elem_bytes
from .model import DependencyInfo, LayerInfo, _align_page, hex32, ref_input_path, ref_input_y_path, ref_output_path
from .layout import scratch_addr

def assign_layer_check_regions(
    layers: List[LayerInfo],
    dep_info: DependencyInfo,
    ddr_base: int,
    ref_dir: str,
    base_top: int,
) -> int:
    """Lay out the golden bins (in/out + insn/uop) in a reserved DRAM region.

    Regions start at base_top (the first free address above all VTA buffers,
    raw-input scratch, and CPU-op scratch) and grow page-aligned upward, so they
    never collide with live data.  Populates the in_ref/out_ref fields (fsim
    golden activations) and the insn_ref/uop_ref fields (a second copy of each
    layer's instruction/uop .bin) of each LayerInfo.  The golden input
    destination is the layer's INP buffer for im2row layers and its ACC buffer
    for int32 layers (matching fsim's dump, fsim_nn.cc:650-666).  Returns the new
    free-top address.
    """
    alloc_ptr = _align_page(base_top)

    for layer in layers:
        suffix = layer.suffix
        ld = dep_info.layers.get(suffix)
        reshape = ld.reshape_info if ld else "im2row"

        if reshape == "im2row":
            dst_buf = layer.mem["INP"]
        else:
            # int32 (maxpool / direct-acc layers): the input arrives via ACC and
            # IS the region the layer's LACC reads (== acc_phys). The static ACC
            # placeholder is not pre-loaded for these layers (see
            # _is_runtime_acc), so this golden copy is the sole writer of ACC.
            dst_buf = layer.mem["ACC"]
        layer.in_dst_addr = ddr_base + dst_buf.offset
        if reshape != "im2row" and dst_buf.size == 0:
            print(
                f"WARNING: int32 layer '{suffix}' has no ACC region"
                f" - golden input has nowhere to land"
            )

        # Golden output (raw OUT, pre-rescale) - compared against board OUT.
        out_file = ref_output_path(ref_dir, suffix)
        if os.path.isfile(out_file):
            size = os.path.getsize(out_file)
            if size > layer.mem["OUT"].size:
                print(
                    f"WARNING: {out_file} ({size} B) larger than OUT buffer"
                    f" ({layer.mem['OUT'].size} B) for layer '{suffix}'"
                )
            layer.out_ref_file = out_file
            layer.out_ref_addr = alloc_ptr
            layer.out_ref_size = size
            alloc_ptr += _align_page(size)
        else:
            print(
                f"WARNING: golden output not found: {out_file}"
                f" - layer '{suffix}' output will not be checked"
            )

        # Golden input - copied into in_dst_addr before the layer runs.
        in_file = ref_input_path(ref_dir, suffix)
        if os.path.isfile(in_file):
            size = os.path.getsize(in_file)
            if size > dst_buf.size:
                print(
                    f"WARNING: {in_file} ({size} B) larger than destination"
                    f" buffer ({dst_buf.size} B) for layer '{suffix}'"
                )
            layer.in_ref_file = in_file
            layer.in_ref_addr = alloc_ptr
            layer.in_ref_size = size
            alloc_ptr += _align_page(size)
        else:
            print(
                f"WARNING: golden input not found: {in_file}"
                f" - layer '{suffix}' will run on its preloaded buffer"
            )

        # Golden copies of the instruction / micro-op streams - the same
        # compiler .bin used for the live INSN/UOP sections, embedded a second
        # time at a reserved address.  Comparing live-vs-golden before the layer
        # runs catches a prior layer clobbering these static bytes in DDR.  The
        # golden size is the *actual stream length* (the .bin file size); the
        # live INSN region the VTA fetches is exactly insn_count*16 (== file
        # size) and the live UOP buffer is page-padded but only the first
        # file-size bytes are ever fetched, so the padded tail is not compared.
        for buf_type, addr_attr, size_attr in (
            ("INSN", "insn_ref_addr", "insn_ref_size"),
            ("UOP", "uop_ref_addr", "uop_ref_size"),
        ):
            mem = layer.mem.get(buf_type)
            bin_path = layer.bin_files.get(buf_type)
            if mem is None or mem.size == 0 or not bin_path:
                continue
            if not os.path.isfile(bin_path):
                print(
                    f"WARNING: {buf_type} binary not found for layer '{suffix}':"
                    f" {bin_path} - golden {buf_type.lower()} check skipped"
                )
                continue
            fsize = os.path.getsize(bin_path)
            if fsize > mem.size:
                print(
                    f"WARNING: {buf_type} bin for layer '{suffix}' is {fsize} B"
                    f" but live buffer is only {mem.size} B - golden check would"
                    f" read past the buffer; skipped"
                )
                continue
            setattr(layer, addr_attr, alloc_ptr)
            setattr(layer, size_attr, fsize)
            alloc_ptr += _align_page(fsize)

        # Dual-operand isolation is not wired up (no such VTA layer in current
        # nets; nb_inp==2 int32 is the CPU qadd path).
        y_file = ref_input_y_path(ref_dir, suffix)
        if os.path.isfile(y_file):
            print(
                f"WARNING: {y_file} exists but dual-operand (accY) isolation is"
                f" not implemented - layer '{suffix}' second input is ignored"
            )

    return alloc_ptr
def gen_debug_map(
    layers: List[LayerInfo],
    out_path: str,
) -> None:
    """Generate nn_debug_map.h: the vta::DebugLayerDesc nn_debug[] table.

    One entry per VTA layer (indices match nn_layers[]).  Layers whose golden
    bins were missing get zero sizes and are skipped at runtime.
    """
    L: List[str] = []
    L.append("/* Auto-generated by gen_nn_baremetal.py - DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "vta_nn_debug.h"')
    L.append("")
    L.append(f"#define NN_NUM_DEBUG {len(layers)}")
    L.append("")
    L.append("static const vta::DebugLayerDesc nn_debug[NN_NUM_DEBUG] = {")

    for i, layer in enumerate(layers):
        L.append(f'    /* layer {i}  suffix="{layer.suffix}" */')
        L.append("    {")
        L.append(f"        .layer_idx     = {i}u,")
        L.append(f"        .in_ref_phys   = {hex32(layer.in_ref_addr)},")
        L.append(f"        .in_ref_bytes  = {hex32(layer.in_ref_size)},")
        L.append(f"        .in_dst_phys   = {hex32(layer.in_dst_addr)},")
        L.append(f"        .out_ref_phys  = {hex32(layer.out_ref_addr)},")
        L.append(f"        .out_ref_bytes = {hex32(layer.out_ref_size)},")
        L.append(f"        .insn_ref_phys  = {hex32(layer.insn_ref_addr)},")
        L.append(f"        .insn_ref_bytes = {hex32(layer.insn_ref_size)},")
        L.append(f"        .uop_ref_phys   = {hex32(layer.uop_ref_addr)},")
        L.append(f"        .uop_ref_bytes  = {hex32(layer.uop_ref_size)},")
        L.append(f'        .name          = "{layer.suffix}",')
        L.append("    }" + ("," if i < len(layers) - 1 else ""))

    L.append("};")
    L.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] Debug map written to {out_path}")
def gen_cpu_debug_map(
    dep_info: DependencyInfo,
    layers: List[LayerInfo],
    cfg: ConfigParams,
    out_path: str,
    suffix_to_idx: Dict[str, int],
    ddr_base: int,
    comp_dir: str,
) -> None:
    """Generate nn_cpu_debug_map.h: the DebugCpuStep nn_cpu_debug[] table.

    One entry per CPU step whose output buffer equals a VTA layer's golden
    input dump (FORMAT_INPUT / IM2ROW / INT32_CHAIN).  Other CPU ops
    (rescale / qadd / concat / dequant / quant) are absent from the table;
    the isolation runner (run_nn_cpu_debug) simply has nothing to replay for
    them.

    The step_idx field is the index of the corresponding entry in
    nn_exec_steps[] - the same counter gen_exec_plan_header() uses when
    emitting the plan, replayed here so lookups stay in sync.  Requires
    --emit-layer-check to have populated each consumer LayerInfo's in_ref_*
    fields.

    Isolation-mode source fields (src_ref_*, src_dst_phys) preload each op's
    INPUT with a known-good golden so a bad upstream layer does not cascade:
      - format_input: the raw image lives at raw_phys (loaded by the debugger);
        src_dst == src_ref == raw_phys (self-referential - the driver skips the
        copy but still invalidates the region).
      - im2row / int32_chain: the source is the producing layer's OUT buffer,
        read after that layer's in-place rescale.  The golden is the producer's
        out_ref (pre-rescale output<suffix>.bin); the runtime replays the
        producer rescale before the reshape.  Requires --emit-layer-check to
        have embedded the producer out_ref; absent that the fields stay 0 and
        the runtime falls back to the preloaded buffer.
    """
    inp_bytes = _elem_bytes(cfg.log_inp_width)
    acc_bytes = _elem_bytes(cfg.log_acc_width)
    log_out_width = cfg.log_out_width
    raw_phys = scratch_addr(layers, ddr_base)
    input_nn_path = os.path.join(comp_dir, "input_nn.bin")
    raw_size = os.path.getsize(input_nn_path) if os.path.isfile(input_nn_path) else 0

    # Replicate the FORMAT_INPUT / IM2ROW / INT32_CHAIN classification from
    # gen_exec_plan_header() so we know which VTA layers get a preceding
    # injected step.
    format_input_layers: set = set()
    im2row_layers: set = set()
    int32_chain_layers: set = set()
    for _, processor, layer_name in dep_info.execution_order:
        if processor != "vta":
            continue
        ld = dep_info.layers.get(layer_name)
        if not ld:
            continue
        if ld.reshape_info == "im2row":
            if ld.deps and ld.deps[0] == "image":
                format_input_layers.add(layer_name)
            else:
                im2row_layers.add(layer_name)
        elif ld.reshape_info == "int32":
            int32_chain_layers.add(layer_name)

    # (step_idx, kind, name, out_phys, out_bytes, ref_phys, ref_bytes,
    #  elem_bytes, src_ref_phys, src_ref_bytes, src_dst_phys)
    entries: List[Tuple[int, str, str, int, int, int, int, int, int, int, int]] = []
    skipped: List[str] = []
    emitted = 0

    def _src_isolation(kind: str, layer_name: str) -> Tuple[int, int, int]:
        """Resolve (src_ref_phys, src_ref_bytes, src_dst_phys) for one op.

        Returns (0, 0, 0) when no golden source is available; the runtime then
        falls back to whatever is preloaded in the source buffer.
        """
        if kind == "format_input":
            # Raw image is loaded to raw_phys by the debugger; the source buffer
            # already holds the golden, so point src at it (self-referential).
            if raw_size == 0:
                return (0, 0, 0)
            return (raw_phys, raw_size, raw_phys)
        # im2row / int32_chain: source is the producing layer's OUT buffer; the
        # golden is that producer's out_ref (pre-rescale output<suffix>.bin).
        ld = dep_info.layers.get(layer_name)
        dep_name = ld.deps[0] if (ld and ld.deps) else ""
        prod_idx = suffix_to_idx.get(dep_name, -1)
        if prod_idx < 0:
            return (0, 0, 0)
        producer = layers[prod_idx]
        if producer.out_ref_size == 0:
            return (0, 0, 0)
        src_dst = ddr_base + producer.mem["OUT"].offset
        return (producer.out_ref_addr, producer.out_ref_size, src_dst)

    for _, processor, layer_name in dep_info.execution_order:
        # --- FORMAT_INPUT / IM2ROW / INT32_CHAIN injection (before VTA step) ---
        if processor == "vta":
            consumer_idx = suffix_to_idx.get(layer_name, -1)
            consumer = layers[consumer_idx] if consumer_idx >= 0 else None

            def _record(kind: str, name: str, elem_bytes: int) -> None:
                if consumer is None or consumer.in_ref_size == 0:
                    skipped.append(f"{name} (no golden input embedded)")
                    return
                src_ref_phys, src_ref_bytes, src_dst_phys = _src_isolation(
                    kind, layer_name
                )
                if src_ref_bytes == 0:
                    skipped.append(f"{name} (no upstream golden - isolation fallback)")
                entries.append((
                    emitted, kind, name,
                    consumer.in_dst_addr, consumer.in_ref_size,
                    consumer.in_ref_addr, consumer.in_ref_size,
                    elem_bytes,
                    src_ref_phys, src_ref_bytes, src_dst_phys,
                ))

            if layer_name in format_input_layers:
                _record("format_input", f"format_{layer_name}", inp_bytes)
                emitted += 1
            elif layer_name in im2row_layers:
                _record("im2row", f"im2row_{layer_name}", inp_bytes)
                emitted += 1
            elif layer_name in int32_chain_layers:
                _record("int32_chain", f"int32_chain_{layer_name}", acc_bytes)
                emitted += 1

        # --- The step itself ---
        if processor == "vta":
            emitted += 1
            if log_out_width > 3:
                emitted += 1  # injected rescale step (not checked)
        elif processor in ("qadd", "concat", "dequant", "quant"):
            emitted += 1
        else:
            emitted += 1  # unsupported -> stub VTA step still counted

    # Emit the header.
    L: List[str] = []
    L.append("/* Auto-generated by gen_nn_baremetal.py - DO NOT EDIT */")
    L.append("#pragma once")
    L.append('#include "vta_cpu_ops_debug.h"')
    L.append("")
    L.append("/*")
    L.append(" * Coverage: only CPU ops whose output buffer equals a VTA layer's")
    L.append(" * golden INP/ACC dump are checked (FORMAT_INPUT / IM2ROW / INT32_CHAIN).")
    L.append(" * Other CPU ops (rescale / qadd / concat / dequant / quant) are")
    L.append(" * absent from the table and silently skipped at runtime.")
    L.append(" *")
    L.append(" * Isolation-mode source fields (src_ref_*, src_dst_phys) preload each")
    L.append(" * op's INPUT with a known-good golden (raw image for format_input, the")
    L.append(" * producer layer's pre-rescale out_ref for im2row/int32_chain) so a bad")
    L.append(" * upstream layer does not cascade.  The runtime replays the producer")
    L.append(" * rescale before the reshape.  Entries left at 0 (no embedded golden,")
    L.append(" * e.g. --emit-layer-check not run) fall back to the preloaded buffer.")
    if skipped:
        L.append(" *")
        L.append(" * Skipped at codegen:")
        for s in skipped:
            L.append(f" *   - {s}")
    L.append(" */")
    L.append("")
    L.append(f"#define NN_NUM_CPU_DEBUG {len(entries)}u")
    L.append("")
    if not entries:
        # C++ requires at least one element for an array; zero-initialised stub
        # is harmless because NN_NUM_CPU_DEBUG == 0 so the runtime never reads
        # it.  Keeps the apps that reference nn_cpu_debug[] compiling.
        L.append("static const vta::DebugCpuStep nn_cpu_debug[1] = {};")
    else:
        L.append("static const vta::DebugCpuStep nn_cpu_debug[NN_NUM_CPU_DEBUG] = {")
        for i, e in enumerate(entries):
            (step_idx, kind, name, out_phys, out_bytes,
             ref_phys, ref_bytes, elem_bytes,
             src_ref_phys, src_ref_bytes, src_dst_phys) = e
            comma = "," if i < len(entries) - 1 else ""
            L.append(f"    /* {kind} */")
            L.append("    {")
            L.append(f"        .step_idx      = {step_idx}u,")
            L.append(f"        .out_phys      = {hex32(out_phys)},")
            L.append(f"        .out_bytes     = {hex32(out_bytes)},")
            L.append(f"        .ref_phys      = {hex32(ref_phys)},")
            L.append(f"        .ref_bytes     = {hex32(ref_bytes)},")
            L.append(f"        .elem_bytes    = std::uint16_t({elem_bytes}u),")
            L.append(f"        ._pad          = std::uint16_t(0u),")
            L.append(f"        .src_ref_phys  = {hex32(src_ref_phys)},")
            L.append(f"        .src_ref_bytes = {hex32(src_ref_bytes)},")
            L.append(f"        .src_dst_phys  = {hex32(src_dst_phys)},")
            L.append(f'        .name          = "{name}",')
            L.append(f"    }}{comma}")
        L.append("};")
    L.append("")
    with open(out_path, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"[gen] CPU debug map written to {out_path} ({len(entries)} entries)")
