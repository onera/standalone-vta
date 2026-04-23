/**
 * vta_cpu_ops.cc — ARM PS-side CPU operations for multi-layer VTA inference.
 *
 * All operations work directly on DDR addresses via reinterpret_cast and
 * flush the D-cache after writing to ensure coherency with the VTA PL fabric.
 */

#include <cmath>
#include <cstdint>
#include "../include/vta_cpu_ops.h"
extern "C" {
#include "xil_cache.h"
#include "xil_printf.h"
}

static inline std::int8_t clamp_i8(std::int32_t v) {
    return static_cast<std::int8_t>(v < -128 ? -128 : (v > 127 ? 127 : v));
}

namespace vta {

void run_qadd(const NnQaddStep &d)
{
    const auto *a = reinterpret_cast<const std::int8_t *>(
        static_cast<std::uintptr_t>(d.inpA));
    const auto *b = reinterpret_cast<const std::int8_t *>(
        static_cast<std::uintptr_t>(d.inpB));
    auto       *c = reinterpret_cast<std::int8_t *>(
        static_cast<std::uintptr_t>(d.out));

    for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
        float fa = d.sA * static_cast<float>(static_cast<std::int32_t>(a[i]) - d.zA);
        float fb = d.sB * static_cast<float>(static_cast<std::int32_t>(b[i]) - d.zB);
        std::int32_t q = static_cast<std::int32_t>(
            std::roundf((fa + fb) / d.sC)) + d.zC;
        c[i] = clamp_i8(q);
    }
    Xil_DCacheFlushRange(static_cast<UINTPTR>(d.out),
                         static_cast<INTPTR>(d.n_elems));
}

void run_concat(const NnConcatStep &d, float * /*tmp*/)
{
    auto *out = reinterpret_cast<std::int8_t *>(
        static_cast<std::uintptr_t>(d.out));

    std::uint32_t out_offset = 0u;
    for (int p = 0; p < d.nb_inp; ++p) {
        const auto *src = reinterpret_cast<const std::int8_t *>(
            static_cast<std::uintptr_t>(d.inp[p]));
        for (std::uint32_t e = 0u; e < d.n_elems_per_ch; ++e) {
            float f = d.scales[p] * static_cast<float>(
                static_cast<std::int32_t>(src[e]) - d.zps[p]);
            std::int32_t q = static_cast<std::int32_t>(
                std::roundf(f / d.out_scale)) + d.out_zp;
            out[out_offset++] = clamp_i8(q);
        }
    }
    Xil_DCacheFlushRange(static_cast<UINTPTR>(d.out),
                         static_cast<INTPTR>(out_offset));
}

void run_dequant(const NnDequantStep &d, float *out)
{
    const auto *src = reinterpret_cast<const std::int8_t *>(
        static_cast<std::uintptr_t>(d.inp_addr));
    for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
        out[i] = d.scale * static_cast<float>(
            static_cast<std::int32_t>(src[i]) - d.zp);
    }
    /* out is a CPU-allocated float buffer — no D-cache flush needed */
}

void run_quant(const NnQuantStep &d, const float *in)
{
    auto *dst = reinterpret_cast<std::int8_t *>(
        static_cast<std::uintptr_t>(d.out_addr));
    for (std::uint32_t i = 0u; i < d.n_elems; ++i) {
        std::int32_t q = static_cast<std::int32_t>(
            std::roundf(in[i] / d.scale)) + d.zp;
        dst[i] = clamp_i8(q);
    }
    Xil_DCacheFlushRange(static_cast<UINTPTR>(d.out_addr),
                         static_cast<INTPTR>(d.n_elems));
}

/* Streaming im2row: reads raw HWC input from DDR (scratch), writes VTA-blocked
   im2row result directly to the VTA INP address.  No intermediate allocation. */
void run_format_input(const NnFormatInputStep &d)
{
    const auto *raw = reinterpret_cast<const std::int8_t *>(
        static_cast<std::uintptr_t>(d.raw_addr));
    auto *out = reinterpret_cast<std::int8_t *>(
        static_cast<std::uintptr_t>(d.inp_addr));

    const std::uint32_t C  = d.tensor_ch;
    const std::uint32_t H  = d.tensor_h;
    const std::uint32_t W  = d.tensor_w;
    const std::uint32_t kH = d.kh;
    const std::uint32_t kW = d.kw;
    const std::uint32_t sh = d.sh;
    const std::int32_t  pt = d.pad[0];  /* top  */
    const std::int32_t  pl = d.pad[1];  /* left */
    const std::uint32_t oH = d.out_h;
    const std::uint32_t oW = d.out_w;

    /* im2row output shape: [oH*oW] rows × [C*kH*kW] cols — both multiples of 16 */
    const std::uint32_t N_rows   = oH * oW;
    const std::uint32_t K_cols   = C  * kH * kW;
    const std::uint32_t N_blocks = N_rows / 16u;
    const std::uint32_t K_blocks = K_cols / 16u;

    for (std::uint32_t obr = 0u; obr < N_blocks; ++obr) {
        for (std::uint32_t obc = 0u; obc < K_blocks; ++obc) {
            std::int8_t *blk = out + (obr * K_blocks + obc) * 256u;
            for (std::uint32_t r = 0u; r < 16u; ++r) {
                const std::uint32_t out_row = obr * 16u + r;
                const std::uint32_t h_out   = out_row / oW;
                const std::uint32_t w_out   = out_row % oW;
                for (std::uint32_t t = 0u; t < 16u; ++t) {
                    const std::uint32_t out_col = obc * 16u + t;
                    const std::uint32_t c_in    = out_col / (kH * kW);
                    const std::uint32_t k_rem   = out_col % (kH * kW);
                    const std::uint32_t ki      = k_rem / kW;
                    const std::uint32_t kj      = k_rem % kW;

                    const std::int32_t h_in = static_cast<std::int32_t>(h_out * sh + ki) - pt;
                    const std::int32_t w_in = static_cast<std::int32_t>(w_out * sh + kj) - pl;

                    std::int8_t val;
                    if (h_in >= 0 && h_in < static_cast<std::int32_t>(H) &&
                        w_in >= 0 && w_in < static_cast<std::int32_t>(W)) {
                        std::int32_t v = static_cast<std::int32_t>(
                            raw[static_cast<std::uint32_t>(h_in) * W * C +
                                static_cast<std::uint32_t>(w_in) * C + c_in]);
                        v -= d.offset_a;
                        val = clamp_i8(v);
                    } else {
                        /* padding: 0 in the offset-adjusted space */
                        val = static_cast<std::int8_t>(0);
                    }
                    blk[r * 16u + t] = val;
                }
            }
        }
    }

    Xil_DCacheFlushRange(static_cast<UINTPTR>(d.inp_addr),
                         static_cast<INTPTR>(N_blocks * K_blocks * 256u));
}

} // namespace vta
