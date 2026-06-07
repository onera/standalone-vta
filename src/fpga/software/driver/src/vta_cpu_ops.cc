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
extern "C" {
#include "xil_printf.h"
}

static inline std::int8_t clamp_i8(std::int64_t v) {
  return static_cast<std::int8_t>(v < -128 ? -128 : (v > 127 ? 127 : v));
}

namespace vta {

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

/* Channel-concat for VTA block layout: for each row-block, copy each input's
   channel-blocks sequentially so output has the correct [rb, cb_A, cb_B, …]
   order. A simple flat append would be wrong for H*W > 16 (multiple
   row-blocks). */
void run_concat(const NnConcatStep &d) {
  if (d.out_scale == 0.0f) {
    xil_printf("[vta] run_concat: zero output scale\r\n");
    return;
  }
  auto *out =
      reinterpret_cast<std::int8_t *>(static_cast<std::uintptr_t>(d.out));

  const float inv_out_scale = 1.0f / d.out_scale;
  const std::uint32_t blk = d.block;
  const std::uint32_t blk2 = blk * blk;
  const std::uint32_t n_rb = d.n_rows / blk;
  const std::uint32_t n_cb = d.n_ch_per_inp / blk;
  const std::uint32_t tot_cb = n_cb * static_cast<std::uint32_t>(d.nb_inp);

  for (std::uint32_t rb = 0u; rb < n_rb; ++rb) {
    for (int p = 0; p < d.nb_inp; ++p) {
      const float rescale_p = d.scales[p] * inv_out_scale;
      const auto *src = reinterpret_cast<const std::int8_t *>(
                            static_cast<std::uintptr_t>(d.inp[p])) +
                        rb * n_cb * blk2;
      std::int8_t *dst =
          out + (rb * tot_cb + static_cast<std::uint32_t>(p) * n_cb) * blk2;
      for (std::uint32_t cb = 0u; cb < n_cb; ++cb) {
        const std::int8_t *s_blk = src + cb * blk2;
        std::int8_t *d_blk = dst + cb * blk2;
        for (std::uint32_t e = 0u; e < blk2; ++e) {
          std::int64_t q =
              static_cast<std::int64_t>(std::nearbyintf(
                  rescale_p *
                  static_cast<float>(static_cast<std::int32_t>(s_blk[e]) -
                                     d.zps[p]))) +
              d.out_zp;
          d_blk[e] = clamp_i8(q);
        }
      }
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
              /* spatial padding: 0 in the offset-adjusted space */
              val = static_cast<vta_inp_t>(0);
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
  const auto *src = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.src_addr));
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
  const std::uint32_t C_blocks = (C + B - 1u) / B; /* column-blocks in source */

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
              /* Source VTA block layout: row = h_in*W+w_in, col = c_in */
              const std::uint32_t row = static_cast<std::uint32_t>(h_in) * W +
                                        static_cast<std::uint32_t>(w_in);
              const std::uint32_t rb = row / B;
              const std::uint32_t rr = row % B;
              const std::uint32_t cb = c_in / B;
              const std::uint32_t cc = c_in % B;
              std::int64_t v = static_cast<std::int64_t>(
                  src[(rb * C_blocks + cb) * B * B + rr * B + cc]);
              v -= d.offset_a;
              val = static_cast<vta_inp_t>(v);
            } else {
              val = static_cast<vta_inp_t>(0); /* spatial padding */
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
  const auto *src = reinterpret_cast<const std::int8_t *>(
      static_cast<std::uintptr_t>(d.src_addr));
  auto *dst =
      reinterpret_cast<vta_acc_t *>(static_cast<std::uintptr_t>(d.dst_addr));

  const std::int32_t pt = d.pad[0], pl = d.pad[1], pb = d.pad[2], pr = d.pad[3];
  if (pt == 0 && pl == 0 && pb == 0 && pr == 0) {
    // No spatial padding: producer OUT and consumer ACC share the same block
    // layout, so a flat element-wise widen + offset reproduces fsim's no-pad
    // path (which also widens the channel/spatial block-pad slots).  n_elems
    // is the block-padded count ceil(H*W/B)*B * ceil(C/B)*B.
    for (std::uint32_t i = 0u; i < d.n_elems; ++i)
      dst[i] = static_cast<vta_acc_t>(static_cast<std::int32_t>(src[i]) -
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
          val = static_cast<vta_acc_t>(static_cast<std::int32_t>(src[soff]) -
                                       d.offset_a);
        } else {
          val = -128; /* spatial padding (pad_matrix fill, post-offset) */
        }
      }
      dst[doff] = val;
    }
  }
}

} // namespace vta
