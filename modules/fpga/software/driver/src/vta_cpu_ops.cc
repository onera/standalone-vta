/**
 * vta_cpu_ops.cc - ARM PS-side CPU operations for multi-layer VTA inference.
 *
 * Pure compute on DDR addresses: each op mirrors the matching fsim CPU function
 * (cpu_functions.h / fsim_nn.cc) bit-for-bit. D-cache coherency is handled by
 * the caller (vta_nn.cc), not here.
 */

#include "../include/vta_cpu_ops.h"
#include "vta_hw_config.h"
#include <cmath>
#include <cstdint>
#include <cstdlib>
extern "C" {
#include "xil_printf.h"
}

static inline std::int8_t clamp_i8(std::int64_t v) {
  return static_cast<std::int8_t>(v < -128 ? -128 : (v > 127 ? 127 : v));
}

/* Element `i` of a producer OUT buffer, as the compact int8 value a downstream
   reshape consumes. scale == 0: the buffer was already compacted by a
   NN_STEP_RESCALE, read it straight as int8. scale != 0: the buffer still holds
   the raw int32 VTA output; requantize exactly as run_rescale would
   (clamp_i8(nearbyint(x*scale) + offset), double math) so the fused path is
   bit-identical to run_rescale followed by the reshape. */
static inline std::int64_t rescaled_src(std::uintptr_t base, std::uint32_t i,
                                        float scale, std::int32_t offset) {
  if (scale == 0.0f)
    return reinterpret_cast<const std::int8_t *>(base)[i];
  const auto *s32 = reinterpret_cast<const vta_out_t *>(base);
  return clamp_i8(static_cast<std::int64_t>(std::nearbyint(
                      static_cast<double>(s32[i]) *
                      static_cast<double>(scale))) +
                  offset);
}

/* Byte offset of activation element (row, ch) under each layout.

   blocked  ((row/B)*cblk + ch/B)*B*B + (row%B)*B + (ch%B)
   flat     row*(cblk*B) + ch

   They agree exactly when cblk == 1, which is why a mismatch stays invisible
   until a layer is more than one channel block wide.

   cblk is passed in rather than derived from a channel count, deliberately:
   deriving it costs an integer division, B is a runtime value so the compiler
   cannot turn that into a shift, and this sits in the innermost loop of every
   caller. */
static inline std::uint32_t act_off(std::uint32_t row, std::uint32_t ch,
                                    std::uint32_t cblk, std::uint32_t B,
                                    std::uint32_t layout) {
  if (layout == NN_LAYOUT_FLAT)
    return row * (cblk * B) + ch;
  return ((row / B) * cblk + ch / B) * B * B + (row % B) * B + (ch % B);
}

/* Offset of (row, ch) inside one concat branch. A `compact` branch stores its
   final partial row-block as (n_valid mod B) x B blocks instead of B x B. */
static inline std::uint32_t branch_off(std::uint32_t row, std::uint32_t ch,
                                       std::uint32_t cblk, std::uint32_t B,
                                       std::uint32_t n_valid, bool compact) {
  const std::uint32_t full = (n_valid / B) * B;
  if (!compact || row < full)
    return ((row / B) * cblk + ch / B) * B * B + (row % B) * B + (ch % B);
  const std::uint32_t tail = n_valid - full;
  return (n_valid / B) * cblk * B * B + ((ch / B) * tail + (row - full)) * B +
         (ch % B);
}

namespace vta {

void run_relayout(const NnRelayoutStep &d) {
  const auto *src =
      reinterpret_cast<const std::int8_t *>(static_cast<std::uintptr_t>(d.src_addr));

  /* One of the two sides is contiguous whichever way we are converting, so
     walk that side linearly and compute the other. */
  const std::uint32_t cblk = (d.n_ch + d.block - 1u) / d.block;

  if (d.to_flat) {
    /* Feeding a convolution's INP, in im2row's place: widen to vta_inp_t and
       remove the zero point, exactly as run_im2row does. */
    auto *dst =
        reinterpret_cast<vta_inp_t *>(static_cast<std::uintptr_t>(d.dst_addr));
    for (std::uint32_t row = 0u; row < d.n_rows; ++row)
      for (std::uint32_t ch = 0u; ch < d.n_ch; ++ch) {
        const std::int64_t v =
            static_cast<std::int64_t>(
                src[act_off(row, ch, cblk, d.block, NN_LAYOUT_BLOCKED)]) -
            d.offset_a;
        dst[row * d.n_ch + ch] = static_cast<vta_inp_t>(v);
      }
  } else {
    /* Publishing the layer's OUT, already made int8 by the rescale. */
    auto *dst =
        reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.dst_addr));
    for (std::uint32_t row = 0u; row < d.n_rows; ++row)
      for (std::uint32_t ch = 0u; ch < d.n_ch; ++ch)
        dst[act_off(row, ch, cblk, d.block, NN_LAYOUT_BLOCKED)] =
            src[row * d.n_ch + ch];
  }
}

void run_qadd(const NnQaddStep &d) {
  const auto *a = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.inpA));
  const auto *b = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.inpB));
  auto *c = reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.out));

  if (d.sC == 0.0f) {
    xil_printf("[vta] run_qadd: zero output scale\r\n");
    return;
  }
  /* fsim folds qadd into outC=nearbyint((X*sA+Y*sB)/sC) then rescale ×1.0 with
     offset zC. Done in one pass here (add zC, clamp int8) so qadd is complete
     with no trailing rescale step. */
  const float inv_sC = 1.0f / d.sC;
  for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
    float fa =
        d.sA * static_cast<float>(static_cast<std::int32_t>(a[i]) - d.zA);
    float fb =
        d.sB * static_cast<float>(static_cast<std::int32_t>(b[i]) - d.zB);
    std::int64_t q =
        static_cast<std::int64_t>(std::nearbyintf((fa + fb) * inv_sC)) + d.zC;
    c[i] = clamp_i8(q);
  }
}

/* Channel-concat.

   Specialised per layout rather than sharing one act_off-driven body. Both
   layouts have a contiguous run to copy - a whole 16x16 block under the
   block-tiled one, a whole branch's channels within a row under the flat one -
   and walking (row, channel) through act_off throws that away: it scatters the
   writes and blocks vectorisation. */
void run_concat(const NnConcatStep &d) {
  if (d.out_scale == 0.0f) {
    xil_printf("[vta] run_concat: zero output scale\r\n");
    return;
  }
  auto *out =
      reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.out));

  const float inv_out_scale = 1.0f / d.out_scale;
  const std::uint32_t blk = d.block;

  for (int p = 0; p < d.nb_inp; ++p) {
    const float rescale_p = d.scales[p] * inv_out_scale;
    const std::int32_t zp = d.zps[p];
    const auto *src = reinterpret_cast<const std::int8_t *>(
        static_cast<std::uintptr_t>(d.inp[p]));

    const std::uint32_t n_valid = d.n_rows_valid ? d.n_rows_valid : d.n_rows;
    const bool compact_p =
        ((d.compact_mask >> static_cast<std::uint32_t>(p)) & 1u) != 0u &&
        (n_valid % blk) != 0u;

    /* One requantized element, the arithmetic being identical either way. */
    auto conv = [&](std::int8_t v) {
      const std::int64_t q =
          static_cast<std::int64_t>(std::nearbyintf(
              rescale_p *
              static_cast<float>(static_cast<std::int32_t>(v) - zp))) +
          d.out_zp;
      return clamp_i8(q);
    };

    if (d.layout == NN_LAYOUT_FLAT) {
      /* Each branch owns a contiguous span of every output row. */
      const std::uint32_t tot_ch =
          d.n_ch_per_inp * static_cast<std::uint32_t>(d.nb_inp);
      const std::uint32_t ch0 = static_cast<std::uint32_t>(p) * d.n_ch_per_inp;
      for (std::uint32_t row = 0u; row < d.n_rows; ++row) {
        const std::int8_t *s = src + row * d.n_ch_per_inp;
        std::int8_t *o = out + row * tot_ch + ch0;
        for (std::uint32_t c = 0u; c < d.n_ch_per_inp; ++c)
          o[c] = conv(s[c]);
      }
    } else if (!compact_p && d.n_ch_per_inp % blk == 0u) {
      /* Block-tiled: within each row-block the branches follow one another a
         channel-block at a time, so a whole blk*blk block is contiguous in
         both source and destination. */
      const std::uint32_t blk2 = blk * blk;
      const std::uint32_t n_rb = d.n_rows / blk;
      const std::uint32_t n_cb = d.n_ch_per_inp / blk;
      const std::uint32_t tot_cb = n_cb * static_cast<std::uint32_t>(d.nb_inp);
      for (std::uint32_t rb = 0u; rb < n_rb; ++rb) {
        const std::int8_t *s = src + rb * n_cb * blk2;
        std::int8_t *o =
            out + (rb * tot_cb + static_cast<std::uint32_t>(p) * n_cb) * blk2;
        for (std::uint32_t e = 0u; e < n_cb * blk2; ++e)
          o[e] = conv(s[e]);
      }
    } else {
      /* Block-tiled with branch boundaries inside a block: gather element by
         element. */
      const std::uint32_t cblk_in = (d.n_ch_per_inp + blk - 1u) / blk;
      const std::uint32_t tot_ch =
          d.n_ch_per_inp * static_cast<std::uint32_t>(d.nb_inp);
      const std::uint32_t cblk_out = (tot_ch + blk - 1u) / blk;
      const std::uint32_t ch0 = static_cast<std::uint32_t>(p) * d.n_ch_per_inp;
      const std::uint32_t rows = compact_p ? n_valid : d.n_rows;
      for (std::uint32_t row = 0u; row < rows; ++row)
        for (std::uint32_t c = 0u; c < d.n_ch_per_inp; ++c)
          out[act_off(row, ch0 + c, cblk_out, blk, NN_LAYOUT_BLOCKED)] =
              conv(src[branch_off(row, c, cblk_in, blk, n_valid, compact_p)]);
    }
  }
}

void run_dequant(const NnDequantStep &d, float *out) {
  const auto *src = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.inp_addr));
  for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
    out[i] =
        d.scale * static_cast<float>(static_cast<std::int32_t>(src[i]) - d.zp);
  }
  /* out is a CPU-allocated float buffer - no D-cache flush needed */
}

void run_quant(const NnQuantStep &d, const float *in) {
  if (d.scale == 0.0f) {
    xil_printf("[vta] run_quant: zero scale\r\n");
    return;
  }
  auto *dst =
      reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.out_addr));
  const float inv_scale = 1.0f / d.scale;
  for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
    std::int64_t q =
        static_cast<std::int64_t>(std::nearbyintf(in[i] * inv_scale)) + d.zp;
    dst[i] = clamp_i8(q);
  }
}

/* Streaming im2row: reads raw HWC input from DDR (scratch), writes VTA-blocked
   im2row result directly to the VTA INP address.  No intermediate allocation.
 */
void run_format_input(const NnFormatInputStep &d) {
  const auto *raw = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.raw_addr));
  auto *out =
      reinterpret_cast<vta_inp_t *>(static_cast<std::uintptr_t>(d.inp_addr));

  const std::uint32_t C = d.tensor_ch;
  const std::uint32_t H = d.tensor_h;
  const std::uint32_t W = d.tensor_w;
  const std::uint32_t kH = d.kh;
  const std::uint32_t kW = d.kw;
  const std::uint32_t sh = d.sh;
  const std::uint32_t sw = d.sw;
  const std::int32_t pt = d.pad[0]; /* top  */
  const std::int32_t pl = d.pad[1]; /* left */
  const std::uint32_t oH = d.out_h;
  const std::uint32_t oW = d.out_w;
  const std::uint32_t B = d.block;

  /* im2row: [oH*oW] rows × [C*kH*kW] cols.  Block counts round UP: fsim's
     matrix_padding pads to a block multiple (filling 0) before splitting, so
     the output is ceil(N/B) x ceil(K/B) blocks even when the dims are not. */
  const std::uint32_t N_rows = oH * oW;
  const std::uint32_t K_cols = C * kH * kW;
  const std::uint32_t N_blocks = (N_rows + B - 1u) / B;
  const std::uint32_t K_blocks = (K_cols + B - 1u) / B;

  for (std::uint32_t obr = 0u; obr < N_blocks; ++obr) {
    for (std::uint32_t obc = 0u; obc < K_blocks; ++obc) {
      vta_inp_t *blk = out + (obr * K_blocks + obc) * B * B;
      /* t outer so the ÷(kH*kW) and ÷kW divisions (non-power-of-2)
         are computed once per column element instead of once per cell. */
      for (std::uint32_t t = 0u; t < B; ++t) {
        const std::uint32_t out_col = obc * B + t;
        const std::uint32_t c_in = out_col / (kH * kW);
        const std::uint32_t k_rem = out_col % (kH * kW);
        const std::uint32_t ki = k_rem / kW;
        const std::uint32_t kj = k_rem % kW;
        for (std::uint32_t r = 0u; r < B; ++r) {
          const std::uint32_t out_row = obr * B + r;

          vta_inp_t val;
          if (out_row >= N_rows || out_col >= K_cols) {
            /* block-padding region (matrix_padding fill) */
            val = static_cast<vta_inp_t>(0);
          } else {
            const std::uint32_t h_out = out_row / oW;
            const std::uint32_t w_out = out_row % oW;
            const std::int32_t h_in =
                static_cast<std::int32_t>(h_out * sh + ki) - pt;
            const std::int32_t w_in =
                static_cast<std::int32_t>(w_out * sw + kj) - pl;
            if (h_in >= 0 && h_in < static_cast<std::int32_t>(H) && w_in >= 0 &&
                w_in < static_cast<std::int32_t>(W)) {
              std::int64_t v = static_cast<std::int64_t>(
                  raw[static_cast<std::uint32_t>(h_in) * W * C +
                      static_cast<std::uint32_t>(w_in) * C + c_in]);
              v -= d.offset_a;
              val = static_cast<vta_inp_t>(v);
            } else {
              /* spatial padding: 0 in the offset-adjusted space, or the zero
                 point itself once the offset has been folded into the bias */
              val = static_cast<vta_inp_t>(d.pad_value);
            }
          }
          blk[r * B + t] = val;
        }
      }
    }
  }
}

/* Apply im2row to a VTA OUT block-tiled source (previous layer) and write the
   im2row-tiled result to a VTA INP buffer.  Same kernel as run_format_input()
   except the source element is read from VTA block layout instead of HWC flat.
   Source layout: element (h_in, w_in, c_in) is at block [row/B][col/B] at
   position [row%B][col%B], where row = h_in*W + w_in, col = c_in. */
void run_im2row(const NnIm2RowStep &d) {
  const std::uintptr_t src_base = static_cast<std::uintptr_t>(d.src_addr);
  auto *out =
      reinterpret_cast<vta_inp_t *>(static_cast<std::uintptr_t>(d.dst_addr));

  const std::uint32_t C = d.tensor_ch;
  const std::uint32_t H = d.tensor_h;
  const std::uint32_t W = d.tensor_w;
  const std::uint32_t kH = d.kh;
  const std::uint32_t kW = d.kw;
  const std::uint32_t sh = d.sh;
  const std::uint32_t sw = d.sw;
  const std::int32_t pt = d.pad[0]; /* top  */
  const std::int32_t pl = d.pad[1]; /* left */
  const std::uint32_t oH = d.out_h;
  const std::uint32_t oW = d.out_w;
  const std::uint32_t B = d.block;

  const std::uint32_t N_rows = oH * oW;
  const std::uint32_t K_cols = C * kH * kW;
  /* Block counts round UP: fsim's matrix_padding pads rows/cols to a block
     multiple (filling 0) before splitting, so the output has ceil(N/B) x
     ceil(K/B) blocks even when N_rows / K_cols are not multiples of B. */
  const std::uint32_t N_blocks = (N_rows + B - 1u) / B;
  const std::uint32_t K_blocks = (K_cols + B - 1u) / B;
  /* Source channel-blocks also round up: the producer OUT stores ceil(C/B)
     column-blocks (matches fsim's to_blocks(block_col = ceil(C/B))).  The old
     truncating C/B collapsed to 0 for C < B, aliasing every spatial row-block
     to block 0 - wrong for any layer with fewer channels than the block size.
   */
  /* The producer stores ceil(C/B) column-blocks, so the source's padded
     channel count is C_blocks*B under either layout. */
  const std::uint32_t C_blocks = (C + B - 1u) / B;

  for (std::uint32_t obr = 0u; obr < N_blocks; ++obr) {
    for (std::uint32_t obc = 0u; obc < K_blocks; ++obc) {
      vta_inp_t *blk = out + (obr * K_blocks + obc) * B * B;
      for (std::uint32_t t = 0u; t < B; ++t) {
        const std::uint32_t out_col = obc * B + t;
        const std::uint32_t c_in = out_col / (kH * kW);
        const std::uint32_t k_rem = out_col % (kH * kW);
        const std::uint32_t ki = k_rem / kW;
        const std::uint32_t kj = k_rem % kW;
        for (std::uint32_t r = 0u; r < B; ++r) {
          const std::uint32_t out_row = obr * B + r;

          vta_inp_t val;
          if (out_row >= N_rows || out_col >= K_cols) {
            /* block-padding region (matrix_padding fill) */
            val = static_cast<vta_inp_t>(0);
          } else {
            const std::uint32_t h_out = out_row / oW;
            const std::uint32_t w_out = out_row % oW;
            const std::int32_t h_in =
                static_cast<std::int32_t>(h_out * sh + ki) - pt;
            const std::int32_t w_in =
                static_cast<std::int32_t>(w_out * sw + kj) - pl;
            if (h_in >= 0 && h_in < static_cast<std::int32_t>(H) && w_in >= 0 &&
                w_in < static_cast<std::int32_t>(W)) {
              /* Source activation: row = h_in*W + w_in, col = c_in, in
                 whichever layout the producer wrote. */
              const std::uint32_t row = static_cast<std::uint32_t>(h_in) * W +
                                        static_cast<std::uint32_t>(w_in);
              std::int64_t v = rescaled_src(
                  src_base,
                  act_off(row, c_in, C_blocks, B, d.src_layout),
                  d.rescale_scale, d.rescale_offset);
              v -= d.offset_a;
              val = static_cast<vta_inp_t>(v);
            } else {
              val = static_cast<vta_inp_t>(d.pad_value); /* spatial padding */
            }
          }
          blk[r * B + t] = val;
        }
      }
    }
  }
}

void run_rescale(const NnRescaleStep &d) {
  const auto *src =
      reinterpret_cast<const vta_out_t *>(static_cast<std::uintptr_t>(d.addr));
  auto *dst =
      reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.addr));
  for (std::uint32_t i = 0u; i < d.n_elems; ++i)
    dst[i] = clamp_i8(
        static_cast<std::int64_t>(std::nearbyint(
            static_cast<double>(src[i]) * static_cast<double>(d.scale))) +
        d.offset);
}

void run_int32_chain(const NnInt32ChainStep &d) {
  // The producer's OUT is compact int8 in every config - quantized by the
  // preceding CPU RESCALE step when OUT is wider than int8, or directly by the
  // VTA store when OUT is already int8.  Read it as int8 and widen
  // (sign-extend) into the consumer's int32 ACC, subtracting the zero-point.
  // Mirrors fsim_nn.cc's convert_vector_type<acc_dtype> +
  // subtract_offset(offset_a), and (when padded) cpu_functions.h's
  // pad_matrix(..., pad_value = -128).
  const std::uintptr_t src_base = static_cast<std::uintptr_t>(d.src_addr);
  auto *dst =
      reinterpret_cast<vta_acc_t *>(static_cast<std::uintptr_t>(d.dst_addr));

  const std::int32_t pt = d.pad[0], pl = d.pad[1], pb = d.pad[2], pr = d.pad[3];
  if (pt == 0 && pl == 0 && pb == 0 && pr == 0) {
    // No spatial padding: producer OUT and consumer ACC share the same block
    // layout, so a flat element-wise widen + offset reproduces fsim's no-pad
    // path (which also widens the channel/spatial block-pad slots).  n_elems
    // is the block-padded count ceil(H*W/B)*B * ceil(C/B)*B.
    for (std::uint32_t i = 0u; i < d.n_elems; ++i)
      dst[i] = static_cast<vta_acc_t>(
          static_cast<std::int32_t>(rescaled_src(
              src_base, i, d.rescale_scale, d.rescale_offset)) -
          d.offset_a);
    return;
  }

  // Spatial padding: rebuild the [C][H][W] map, pad spatially with -128 (int8
  // min == -inf for the downstream max-pool), and re-block to the padded
  // [newN][C] layout.  Mirrors pad_matrix exactly: real cells = src - offset_a,
  // spatial-pad cells = -128, channel-pad and N-block-pad slots = 0.
  const std::int32_t B = VTA_BLOCK_SIZE;
  const std::uint32_t C = d.tensor_ch, H = d.tensor_h, W = d.tensor_w;
  const std::uint32_t C_blocks = (C + B - 1) / B;
  const std::uint32_t C_pad = C_blocks * B;
  const std::uint32_t newH = H + pt + pb;
  const std::uint32_t newW = W + pl + pr;
  const std::uint32_t newN = newH * newW;
  const std::uint32_t newN_pad = ((newN + B - 1) / B) * B; /* isSquare rows */

  for (std::uint32_t n_out = 0u; n_out < newN_pad; ++n_out) {
    const std::uint32_t nb = n_out / B, nr = n_out % B;
    for (std::uint32_t c = 0u; c < C_pad; ++c) {
      const std::uint32_t doff =
          (nb * C_blocks + c / B) * B * B + nr * B + (c % B);
      vta_acc_t val;
      if (n_out >= newN || c >= C) {
        val = 0; /* N-block-pad / channel-pad slot (matrix_padding fill) */
      } else {
        const std::uint32_t h_out = n_out / newW;
        const std::uint32_t w_out = n_out % newW;
        const std::int32_t h_in = static_cast<std::int32_t>(h_out) - pt;
        const std::int32_t w_in = static_cast<std::int32_t>(w_out) - pl;
        if (h_in >= 0 && h_in < static_cast<std::int32_t>(H) && w_in >= 0 &&
            w_in < static_cast<std::int32_t>(W)) {
          const std::uint32_t n_in = static_cast<std::uint32_t>(h_in) * W +
                                     static_cast<std::uint32_t>(w_in);
          const std::uint32_t soff = ((n_in / B) * C_blocks + c / B) * B * B +
                                     (n_in % B) * B + (c % B);
          val = static_cast<vta_acc_t>(
              static_cast<std::int32_t>(rescaled_src(
                  src_base, soff, d.rescale_scale, d.rescale_offset)) -
              d.offset_a);
        } else {
          val = -128; /* spatial padding (pad_matrix fill, post-offset) */
        }
      }
      dst[doff] = val;
    }
  }
}

/* Floating-point ConvTranspose (deconvolution), bit-for-bit equal to fsim's
   cpu_functions.h conv_transpose<float>().  in/out are the runtime float_buf:
   `in` is the producer's block-tiled (Hin*Win)xCin matrix, `out` the
   block-tiled (Hout*Wout)xCout matrix (d.n_out_elems floats, block-padded).
   Weights/bias are read from DDR float addresses.  We scatter directly into the
   block-tiled output instead of building a dense tensor: each logical cell
   (orow,c_out) maps to exactly one block offset and the accumulation order
   matches the reference, so the float result is identical; block-pad slots stay
   0 from the zero-init (which reproduces data_formatting's zero padding). */
void run_convtranspose(const NnConvTransposeStep &d, const float *in,
                       float *out) {
  const auto *onnx_wgt =
      reinterpret_cast<const float *>(static_cast<std::uintptr_t>(d.wgt_addr));
  const float *bias = d.has_bias ? reinterpret_cast<const float *>(
                                       static_cast<std::uintptr_t>(d.bias_addr))
                                 : nullptr;

  const std::uint32_t B = d.block;
  const std::uint32_t Cin = d.tensor_ch, Hin = d.tensor_h, Win = d.tensor_w;
  const std::uint32_t Cout = d.out_ch, Hout = d.out_h, Wout = d.out_w;
  const std::uint32_t kh = d.kh, kw = d.kw, stride = d.stride;
  const std::int32_t pt = d.pad[0]; /* top  */
  const std::int32_t pl = d.pad[1]; /* left */

  const std::uint32_t in_cblk = (Cin + B - 1u) / B;   /* input col-blocks  */
  const std::uint32_t out_cblk = (Cout + B - 1u) / B; /* output col-blocks */
  const std::uint32_t out_rows = Hout * Wout;

  /* Repack ONNX's [Cin][Cout][KH][KW] weights to [KH][KW][Cin][Cout], so that
     output channels, walked innermost below, are contiguous. */
  auto *wgt =
      static_cast<float *>(std::malloc(sizeof(float) * Cin * Cout * kh * kw));
  if (wgt == nullptr) {
    xil_printf("run_convtranspose: out of memory\r\n");
    return;
  }
  for (std::uint32_t ci = 0u; ci < Cin; ++ci)
    for (std::uint32_t co = 0u; co < Cout; ++co)
      for (std::uint32_t y = 0u; y < kh; ++y)
        for (std::uint32_t x = 0u; x < kw; ++x)
          wgt[((y * kw + x) * Cin + ci) * Cout + co] =
              onnx_wgt[((ci * Cout + co) * kh + y) * kw + x];

  /* Gather path: with stride == kernel and no padding, each output cell has a
     single source pixel and tap (h_in = h_out/stride, ky = h_out%stride), so
     each output position is accumulated once in a local buffer instead of
     being swept once per input channel. The adds happen in the same order as
     in the scatter below, bias last, so the result is identical. */
  constexpr std::uint32_t kCtMaxCout = 512u;
  const bool oneToOne = (d.stride == kh && d.stride == kw && pt == 0 &&
                         pl == 0 && d.pad[2] == 0 && d.pad[3] == 0 &&
                         Cout <= kCtMaxCout);
  if (oneToOne) {
    float acc[kCtMaxCout];
    for (std::uint32_t orow = 0u; orow < out_rows; ++orow) {
      const std::uint32_t h_out = orow / Wout, w_out = orow % Wout;
      const std::uint32_t h_in = h_out / stride, ky = h_out % stride;
      const std::uint32_t w_in = w_out / stride, kx = w_out % stride;
      const std::uint32_t srow = h_in * Win + w_in;

      for (std::uint32_t j = 0u; j < Cout; ++j)
        acc[j] = 0.0f;

      for (std::uint32_t c_in = 0u; c_in < Cin; ++c_in) {
        const std::uint32_t s_off = ((srow / B) * in_cblk + c_in / B) * B * B +
                                    (srow % B) * B + (c_in % B);
        const float v = in[s_off];
        if (v == 0.0f)
          continue;
        const float *wp = wgt + ((ky * kw + kx) * Cin + c_in) * Cout;
        for (std::uint32_t j = 0u; j < Cout; ++j)
          acc[j] += v * wp[j];
      }

      float *obase = out + (orow / B) * out_cblk * B * B + (orow % B) * B;
      for (std::uint32_t cb = 0u; cb < out_cblk; ++cb) {
        float *op = obase + cb * B * B;
        const std::uint32_t n = (Cout - cb * B) < B ? (Cout - cb * B) : B;
        for (std::uint32_t j = 0u; j < n; ++j)
          op[j] = acc[cb * B + j] + (bias ? bias[cb * B + j] : 0.0f);
        for (std::uint32_t j = n; j < B; ++j)
          op[j] = 0.0f;
      }
    }
    const std::uint32_t padded_rows = (out_rows + B - 1u) / B * B;
    for (std::uint32_t orow = out_rows; orow < padded_rows; ++orow) {
      float *obase = out + (orow / B) * out_cblk * B * B + (orow % B) * B;
      for (std::uint32_t cb = 0u; cb < out_cblk; ++cb)
        for (std::uint32_t j = 0u; j < B; ++j)
          obase[cb * B * B + j] = 0.0f;
    }
    std::free(wgt);
    return;
  }

  for (std::uint32_t i = 0u; i < d.n_out_elems; ++i)
    out[i] = 0.0f;

  /* 1. Scatter-accumulate over c_in,h_in,w_in,ky,kx,c_out. A source pixel
     reaches each output cell at most once, so the order of the adds on a cell
     depends only on c_in,h_in,w_in. */
  for (std::uint32_t c_in = 0u; c_in < Cin; ++c_in) {
    for (std::uint32_t h_in = 0u; h_in < Hin; ++h_in) {
      for (std::uint32_t w_in = 0u; w_in < Win; ++w_in) {
        const std::uint32_t srow = h_in * Win + w_in;
        const std::uint32_t s_off = ((srow / B) * in_cblk + c_in / B) * B * B +
                                    (srow % B) * B + (c_in % B);
        const float input_val = in[s_off];
        if (input_val == 0.0f)
          continue; /* numerically a no-op; kept for reference parity */

        for (std::uint32_t ky = 0u; ky < kh; ++ky) {
          const std::int32_t h_out =
              static_cast<std::int32_t>(h_in * stride + ky) - pt;
          if (h_out < 0 || h_out >= static_cast<std::int32_t>(Hout))
            continue;
          for (std::uint32_t kx = 0u; kx < kw; ++kx) {
            const std::int32_t w_out =
                static_cast<std::int32_t>(w_in * stride + kx) - pl;
            if (w_out < 0 || w_out >= static_cast<std::int32_t>(Wout))
              continue;

            const std::uint32_t orow =
                static_cast<std::uint32_t>(h_out) * Wout +
                static_cast<std::uint32_t>(w_out);
            /* Everything below is fixed for this output position. */
            float *obase =
                out + (orow / B) * out_cblk * B * B + (orow % B) * B;
            const float *wbase = wgt + ((ky * kw + kx) * Cin + c_in) * Cout;

            for (std::uint32_t cb = 0u; cb < out_cblk; ++cb) {
              float *op = obase + cb * B * B;
              const float *wp = wbase + cb * B;
              const std::uint32_t n =
                  (Cout - cb * B) < B ? (Cout - cb * B) : B;
              for (std::uint32_t j = 0u; j < n; ++j)
                op[j] += input_val * wp[j];
            }
          }
        }
      }
    }
  }

  /* 2. Bias broadcast over all real (orow, c_out) cells. */
  if (bias) {
    for (std::uint32_t orow = 0u; orow < out_rows; ++orow) {
      float *obase = out + (orow / B) * out_cblk * B * B + (orow % B) * B;
      for (std::uint32_t cb = 0u; cb < out_cblk; ++cb) {
        float *op = obase + cb * B * B;
        const float *bp = bias + cb * B;
        const std::uint32_t n = (Cout - cb * B) < B ? (Cout - cb * B) : B;
        for (std::uint32_t j = 0u; j < n; ++j)
          op[j] += bp[j];
      }
    }
  }
  std::free(wgt);
}

} // namespace vta
