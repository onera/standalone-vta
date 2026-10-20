// test_cpu_ops.cc - host unit test for the baremetal PS-side CPU ops.
//
// Compiles the REAL driver/src/vta_cpu_ops.cc for the host (against the stub
// vta_hw_config.h / xil_printf.h under test/host/) and checks each op against
// the functional simulator's header-only reference (cpu_functions.h), on
// seeded-random synthetic inputs over a table of shapes that stress the block
// layout: sub-block channel counts (C < BLOCK), non-block-multiple spatial
// dims, spatial padding (incl. asymmetric), strides, and nonzero zero-points.
//
// Oracles (all from cpu_functions.h):
//   run_qadd       <-> qlinear_add
//   run_concat     <-> qlinear_concat
//   run_dequant    <-> dequantize_linear
//   run_quant      <-> quantize_linear
//   run_rescale    <-> rescaling
//   run_im2row      <-> reshape(convert<inp>(block_src), ...)
//   run_format_input<-> reshape(convert<inp>(data_formatting(raw_hwc)), ...)
//   run_int32_chain  : no pad -> subtract_offset(convert<acc>(src))
//                      padded -> pad_matrix(subtract_offset(...), ..., -128)
//
// The ops cast their uint32 DRAM-address fields to pointers, so two scratch
// regions are mmap'd MAP_FIXED at low (32-bit-representable) addresses.
//
// The VTA datapath stub uses int32 elements; CPU activations and quantized
// operator outputs additionally exercise the compact int8 path.
//
// Build/run:  cd src/fpga/software && make test-cpu-ops

#include "cpu_functions.h" // fsim reference (header-only, free functions)
#include "vta_cpu_ops.h"   // driver structs + vta::run_* decls
#include "vta_hw_config.h" // stub: vta_*_t element types + VTA_BLOCK_SIZE

#include <cmath>
#include <cstring>
#include <cstdint>
#include <cstdio>
#include <random>
#include <string>
#include <sys/mman.h>
#include <vector>

namespace {

constexpr std::uintptr_t kSrc = 0x20000000u;
constexpr std::uintptr_t kDst = 0x30000000u;
constexpr std::size_t kRegion = 1u << 23; // 8 MiB each, ample for the configs

int g_failures = 0;

unsigned ru(unsigned x, unsigned b) { return ((x + b - 1u) / b) * b; }

std::vector<std::int8_t> rand_i8(std::size_t n, std::mt19937 &rng) {
  std::uniform_int_distribution<int> d(-128, 127);
  std::vector<std::int8_t> v(n);
  for (auto &x : v)
    x = static_cast<std::int8_t>(d(rng));
  return v;
}

std::vector<float> rand_f(std::size_t n, std::mt19937 &rng) {
  std::uniform_real_distribution<float> d(-2.0f, 2.0f);
  std::vector<float> v(n);
  for (auto &x : v)
    x = d(rng);
  return v;
}

// Compare driver output (int32 at DST) against the reference vector.
void check(const std::string &name, const std::vector<std::int32_t> &ref) {
  const auto *got = reinterpret_cast<const std::int32_t *>(kDst);
  int mm = 0;
  for (std::size_t i = 0; i < ref.size(); ++i) {
    if (got[i] != ref[i]) {
      if (mm < 3)
        std::printf("    [%zu] got=%d exp=%d\n", i, got[i], ref[i]);
      ++mm;
    }
  }
  std::printf("  %-44s ref=%-6zu mm=%-5d %s\n", name.c_str(), ref.size(), mm,
              mm ? "FAIL" : "PASS");
  if (mm)
    ++g_failures;
}

// Compare an int8 result at an explicit emulated DDR address.
void check_i8_at(const std::string &name, const std::vector<std::int8_t> &ref,
                 std::uintptr_t address) {
  const auto *got = reinterpret_cast<const std::int8_t *>(address);
  int mm = 0;
  for (std::size_t i = 0; i < ref.size(); ++i) {
    if (got[i] != ref[i]) {
      if (mm < 3)
        std::printf("    [%zu] got=%d exp=%d\n", i, static_cast<int>(got[i]),
                    static_cast<int>(ref[i]));
      ++mm;
    }
  }
  std::printf("  %-44s ref=%-6zu mm=%-5d %s\n", name.c_str(), ref.size(), mm,
              mm ? "FAIL" : "PASS");
  if (mm)
    ++g_failures;
}

void check_i8(const std::string &name, const std::vector<std::int8_t> &ref) {
  check_i8_at(name, ref, kDst);
}

// Compare driver float output (at DST) against the reference vector.  The op
// mirrors the reference arithmetic in the same order, so the match is expected
// to be exact; a tiny tolerance guards against benign FP-contraction
// differences.
void check_f(const std::string &name, const std::vector<float> &ref) {
  const auto *got = reinterpret_cast<const float *>(kDst);
  int mm = 0;
  float maxd = 0.0f;
  for (std::size_t i = 0; i < ref.size(); ++i) {
    float dd = std::fabs(got[i] - ref[i]);
    if (dd > maxd)
      maxd = dd;
    if (dd > 1e-3f) {
      if (mm < 3)
        std::printf("    [%zu] got=%g exp=%g\n", i, got[i], ref[i]);
      ++mm;
    }
  }
  std::printf("  %-44s ref=%-6zu mm=%-5d maxd=%.3g %s\n", name.c_str(),
              ref.size(), mm, maxd, mm ? "FAIL" : "PASS");
  if (mm)
    ++g_failures;
}

// Float CPU ops use an explicitly ordered float32 contract, so require the
// exact IEEE-754 bit pattern instead of a numerical tolerance.
void check_f_bits(const std::string &name, const std::vector<float> &ref) {
  const auto *got = reinterpret_cast<const float *>(kDst);
  int mm = 0;
  for (std::size_t i = 0; i < ref.size(); ++i) {
    std::uint32_t got_bits = 0u, ref_bits = 0u;
    std::memcpy(&got_bits, &got[i], sizeof(got_bits));
    std::memcpy(&ref_bits, &ref[i], sizeof(ref_bits));
    if (got_bits != ref_bits) {
      if (mm < 3)
        std::printf("    [%zu] got=%g (0x%08x) exp=%g (0x%08x)\n", i,
                    got[i], got_bits, ref[i], ref_bits);
      ++mm;
    }
  }
  std::printf("  %-44s ref=%-6zu mm=%-5d %s\n", name.c_str(), ref.size(), mm,
              mm ? "FAIL" : "PASS");
  if (mm)
    ++g_failures;
}

void test_qadd() {
  constexpr int B = VTA_BLOCK_SIZE;
  // Use one complete row block so all physical values are logical values. The
  // separate layout tests cover partial spatial blocks.
  std::vector<std::int8_t> flat_a(B * B), flat_b(B * B);
  for (int i = 0; i < B * B; ++i) {
    flat_a[i] = static_cast<std::int8_t>(-39 + i);
    flat_b[i] = static_cast<std::int8_t>(26 - i);
  }
  auto blocked_a = data_formatting(flat_a, B, B, B, true);
  auto blocked_b = data_formatting(flat_b, B, B, B, true);
  const std::vector<int> shape = {1, B, B, 1};
  const float sA = 0.011274928227066994f;
  const float sB = 0.011537629179656506f;
  const float sC = 0.01993020437657833f;
  auto ref = qlinear_add(blocked_a, blocked_b, shape, shape, sA, -128, sB,
                         -128, sC, -128, B);

  auto *a = reinterpret_cast<std::int8_t *>(kSrc);
  auto *b = reinterpret_cast<std::int8_t *>(kSrc + 0x100000u);
  std::copy(blocked_a.begin(), blocked_a.end(), a);
  std::copy(blocked_b.begin(), blocked_b.end(), b);
  NnQaddStep st{};
  st.inpA = static_cast<std::uint32_t>(kSrc);
  st.inpB = static_cast<std::uint32_t>(kSrc + 0x100000u);
  st.out = static_cast<std::uint32_t>(kDst);
  st.n_elems = static_cast<std::uint32_t>(ref.size());
  st.sA = sA;
  st.sB = sB;
  st.sC = sC;
  st.zA = -128;
  st.zB = -128;
  st.zC = -128;
  vta::run_qadd(st);
  check_i8("qadd precomputed ratios (QYolo tie)", ref);
}

void test_concat() {
  constexpr int B = VTA_BLOCK_SIZE;
  constexpr int H = B;
  std::vector<std::int8_t> flat_a(B * H), flat_b(B * H);
  for (int i = 0; i < B * H; ++i) {
    flat_a[i] = static_cast<std::int8_t>((i % 31) - 15);
    flat_b[i] = static_cast<std::int8_t>(15 - (i % 29));
  }
  auto blocked_a = data_formatting(flat_a, H, B, B, true);
  auto blocked_b = data_formatting(flat_b, H, B, B, true);
  std::vector<std::vector<std::int8_t>> inputs = {blocked_a, blocked_b};
  std::vector<std::vector<int>> shapes = {{1, B, H, 1}, {1, B, H, 1}};
  std::vector<float> scales = {0.25f, 1.0f};
  std::vector<std::int32_t> zps = {-3, 5};
  auto ref = qlinear_concat(inputs, shapes, scales, zps, 0.5f, -1, 1, B);

  std::copy(blocked_a.begin(), blocked_a.end(),
            reinterpret_cast<std::int8_t *>(kSrc));
  std::copy(blocked_b.begin(), blocked_b.end(),
            reinterpret_cast<std::int8_t *>(kSrc + 0x100000u));
  NnConcatStep st{};
  st.inp[0] = static_cast<std::uint32_t>(kSrc);
  st.inp[1] = static_cast<std::uint32_t>(kSrc + 0x100000u);
  st.out = static_cast<std::uint32_t>(kDst);
  st.n_rows = H;
  st.channels[0] = B;
  st.channels[1] = B;
  st.stored_rows[0] = H;
  st.stored_rows[1] = H;
  st.n_out_elems = static_cast<std::uint32_t>(ref.size());
  st.nb_inp = 2;
  st.scales[0] = scales[0];
  st.scales[1] = scales[1];
  st.zps[0] = zps[0];
  st.zps[1] = zps[1];
  st.out_scale = 0.5f;
  st.out_zp = -1;
  st.block = B;
  vta::run_concat(st);
  check_i8("concat per-branch precomputed multiplier", ref);
}

/** Checks channel repacking, partial row layouts, and physical output padding. */
void test_concat_unequal(const std::vector<int> &channels, int rows,
                         bool mixed_layouts, std::mt19937 &rng) {
  const int B = VTA_BLOCK_SIZE;
  std::vector<std::vector<std::int8_t>> inputs;
  std::vector<std::vector<int>> shapes;
  std::vector<float> scales;
  std::vector<std::int32_t> zps;
  NnConcatStep st{};
  st.out = static_cast<std::uint32_t>(kDst);
  st.n_rows = rows;
  st.nb_inp = static_cast<int>(channels.size());
  st.out_scale = 0.03125f;
  st.out_zp = -7;
  st.block = B;
  for (std::size_t p = 0; p < channels.size(); ++p) {
    const bool square = !mixed_layouts || p % 2 == 0;
    auto logical = rand_i8(rows * channels[p], rng);
    inputs.push_back(data_formatting(logical, rows, channels[p], B, square));
    shapes.push_back({1, channels[p], rows, 1});
    scales.push_back(0.011274928227066994f * static_cast<float>(p + 1));
    zps.push_back(-11 + static_cast<int>(p) * 9);
    const auto address = kSrc + p * 0x100000u;
    std::copy(inputs.back().begin(), inputs.back().end(),
              reinterpret_cast<std::int8_t *>(address));
    st.inp[p] = static_cast<std::uint32_t>(address);
    st.channels[p] = channels[p];
    st.stored_rows[p] = square ? ru(rows, B) : rows;
    st.scales[p] = scales.back();
    st.zps[p] = zps.back();
  }
  auto ref = qlinear_concat(inputs, shapes, scales, zps,
                            st.out_scale, st.out_zp, 1, B);
  st.n_out_elems = static_cast<std::uint32_t>(ref.size());
  auto *out = reinterpret_cast<std::int8_t *>(kDst);
  std::fill(out, out + ref.size() + 1, static_cast<std::int8_t>(77));
  vta::run_concat(st);
  const std::string name = "concat unequal C, rows=" + std::to_string(rows) +
      (mixed_layouts ? " mixed row padding" : " square padding");
  check_i8(name, ref);
  if (out[ref.size()] != 77) {
    std::printf("    FAIL: concat writes beyond its physical output\n");
    ++g_failures;
  }
}

void test_dequant_quant() {
  const std::vector<std::int8_t> quantized = {-128, -5, -1, 0, 3, 17, 127};
  std::copy(quantized.begin(), quantized.end(),
            reinterpret_cast<std::int8_t *>(kSrc));
  NnDequantStep dequant{};
  dequant.inp_addr = static_cast<std::uint32_t>(kSrc);
  dequant.n_elems = static_cast<std::uint32_t>(quantized.size());
  dequant.scale = 0.125f;
  dequant.zp = -3;
  auto dequant_ref = dequantize_linear(quantized, dequant.scale, dequant.zp);
  vta::run_dequant(dequant, reinterpret_cast<float *>(kDst));
  check_f_bits("dequant explicit float32", dequant_ref);

  const std::vector<float> values = {-1000.0f, -0.625f, -0.375f, 0.375f,
                                     0.625f, 1000.0f};
  NnQuantStep quant{};
  quant.out_addr = static_cast<std::uint32_t>(kDst);
  quant.n_elems = static_cast<std::uint32_t>(values.size());
  quant.scale = 0.25f;
  quant.zp = 1;
  auto quant_ref_i32 = quantize_linear(values, quant.scale, quant.zp);
  auto quant_ref = convert_vector_type<std::int8_t>(quant_ref_i32);
  vta::run_quant(quant, values.data());
  check_i8("quant reciprocal + nearest-even", quant_ref);
}

void test_rescale() {
  const std::vector<std::int32_t> values = {-1000, -5, -3, 3, 5, 1000};
  auto *src = reinterpret_cast<std::int32_t *>(kSrc);
  std::copy(values.begin(), values.end(), src);
  NnRescaleStep st{};
  st.addr = static_cast<std::uint32_t>(kSrc);
  st.n_elems = static_cast<std::uint32_t>(values.size());
  st.scale = 0.5f;
  st.offset = -1;
  auto ref = rescaling(values, static_cast<double>(st.scale), st.offset);
  vta::run_rescale(st);
  check_i8_at("int32 accumulator rescale", ref, kSrc);
}

struct ConvCfg {
  int C, H, W, kh, kw, sh, sw, pt, pl, pb, pr, off;
};

int out_dim(int in, int pa, int pb_, int k, int s) {
  return (in + pa + pb_ - k) / s + 1;
}

// ---- im2row: source is a producer's block-tiled OUT -----------------------
void test_im2row(const ConvCfg &c, std::mt19937 &rng) {
  const int B = VTA_BLOCK_SIZE;
  const int oH = out_dim(c.H, c.pt, c.pb, c.kh, c.sh);
  const int oW = out_dim(c.W, c.pl, c.pr, c.kw, c.sw);
  const std::size_t n = static_cast<std::size_t>(ru(c.H * c.W, B)) * ru(c.C, B);
  auto s8 = rand_i8(n, rng);

  // oracle
  auto ref = reshape<std::int32_t>(convert_vector_type<std::int32_t>(s8), B, 1,
                                   c.C, c.H, c.W, {c.kh, c.kw}, c.sh,
                                   {c.pt, c.pl, c.pb, c.pr}, true, c.off, c.sw);

  // driver
  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  for (std::size_t i = 0; i < n; ++i)
    src[i] = s8[i];
  NnIm2RowStep st{};
  st.src_addr = static_cast<std::uint32_t>(kSrc);
  st.dst_addr = static_cast<std::uint32_t>(kDst);
  st.tensor_ch = c.C;
  st.tensor_h = c.H;
  st.tensor_w = c.W;
  st.kh = c.kh;
  st.kw = c.kw;
  st.sh = c.sh;
  st.sw = c.sw;
  st.pad[0] = c.pt;
  st.pad[1] = c.pl;
  st.pad[2] = c.pb;
  st.pad[3] = c.pr;
  st.offset_a = c.off;
  st.out_h = oH;
  st.out_w = oW;
  st.block = B;
  vta::run_im2row(st);

  char nm[96];
  std::snprintf(nm, sizeof(nm),
                "im2row C=%d %dx%d k%dx%d s%d,%d pad{%d,%d,%d,%d}", c.C, c.H,
                c.W, c.kh, c.kw, c.sh, c.sw, c.pt, c.pl, c.pb, c.pr);
  check(nm, ref);
}

// ---- format_input: source is the raw HWC image ----------------------------
void test_format(const ConvCfg &c, std::mt19937 &rng) {
  const int B = VTA_BLOCK_SIZE;
  const int oH = out_dim(c.H, c.pt, c.pb, c.kh, c.sh);
  const int oW = out_dim(c.W, c.pl, c.pr, c.kw, c.sw);
  const std::size_t n = static_cast<std::size_t>(c.H) * c.W * c.C;
  auto s8 = rand_i8(n, rng);

  // oracle: block the raw [N][C] tensor, then reshape (which de-blocks it).
  auto blocked = data_formatting<std::int32_t>(
      convert_vector_type<std::int32_t>(s8), c.H * c.W, c.C, B, true);
  auto ref =
      reshape<std::int32_t>(blocked, B, 1, c.C, c.H, c.W, {c.kh, c.kw}, c.sh,
                            {c.pt, c.pl, c.pb, c.pr}, true, c.off, c.sw);

  // driver
  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  for (std::size_t i = 0; i < n; ++i)
    src[i] = s8[i];
  NnFormatInputStep st{};
  st.raw_addr = static_cast<std::uint32_t>(kSrc);
  st.inp_addr = static_cast<std::uint32_t>(kDst);
  st.tensor_ch = c.C;
  st.tensor_h = c.H;
  st.tensor_w = c.W;
  st.kh = c.kh;
  st.kw = c.kw;
  st.sh = c.sh;
  st.sw = c.sw;
  st.pad[0] = c.pt;
  st.pad[1] = c.pl;
  st.pad[2] = c.pb;
  st.pad[3] = c.pr;
  st.offset_a = c.off;
  st.out_h = oH;
  st.out_w = oW;
  st.block = B;
  vta::run_format_input(st);

  char nm[96];
  std::snprintf(nm, sizeof(nm),
                "format C=%d %dx%d k%dx%d s%d,%d pad{%d,%d,%d,%d}", c.C, c.H,
                c.W, c.kh, c.kw, c.sh, c.sw, c.pt, c.pl, c.pb, c.pr);
  check(nm, ref);
}

struct ChainCfg {
  int C, H, W, pt, pl, pb, pr, off;
};

// ---- int32_chain: producer OUT (block) -> maxpool ACC ---------------------
void test_chain(const ChainCfg &c, std::mt19937 &rng) {
  const int B = VTA_BLOCK_SIZE;
  const bool padded = c.pt || c.pl || c.pb || c.pr;
  const std::size_t srcN =
      static_cast<std::size_t>(ru(c.H * c.W, B)) * ru(c.C, B);
  auto s8 = rand_i8(srcN, rng);

  std::vector<std::int32_t> ref;
  if (!padded) {
    ref = subtract_offset(convert_vector_type<std::int32_t>(s8), c.off);
  } else {
    ref = pad_matrix<std::int32_t>(
        subtract_offset(convert_vector_type<std::int32_t>(s8), c.off), c.C, c.H,
        c.W, B, {c.pt, c.pl, c.pb, c.pr}, -128);
  }

  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  for (std::size_t i = 0; i < srcN; ++i)
    src[i] = s8[i];
  NnInt32ChainStep st{};
  st.src_addr = static_cast<std::uint32_t>(kSrc);
  st.dst_addr = static_cast<std::uint32_t>(kDst);
  st.n_elems = static_cast<std::uint32_t>(ref.size());
  st.offset_a = c.off;
  st.pad[0] = c.pt;
  st.pad[1] = c.pl;
  st.pad[2] = c.pb;
  st.pad[3] = c.pr;
  st.tensor_ch = c.C;
  st.tensor_h = c.H;
  st.tensor_w = c.W;
  vta::run_int32_chain(st);

  char nm[96];
  std::snprintf(nm, sizeof(nm),
                "int32_chain C=%d %dx%d pad{%d,%d,%d,%d} off=%d", c.C, c.H, c.W,
                c.pt, c.pl, c.pb, c.pr, c.off);
  check(nm, ref);
}

// ---- convtranspose: float deconvolution vs fsim conv_transpose<float>() -----
struct ConvTCfg {
  int Cin, Hin, Win, Cout, k, stride, pt, pl, pb, pr, bias;
};

// ONNX ConvTranspose output dim (output_padding = 0, dilation = 1).
int outdim_ct(int in, int s, int k, int pa, int pb_) {
  return (in - 1) * s - (pa + pb_) + k;
}

void test_convtranspose(const ConvTCfg &c, std::mt19937 &rng) {
  const int B = VTA_BLOCK_SIZE;
  const int Hout = outdim_ct(c.Hin, c.stride, c.k, c.pt, c.pb);
  const int Wout = outdim_ct(c.Win, c.stride, c.k, c.pl, c.pr);

  // Block-tiled float input (pad slots are ignored by both sides). Passed as a
  // pointer, so it lives on the heap, not at a 32-bit DRAM address.
  const std::size_t in_n =
      static_cast<std::size_t>(ru(c.Hin * c.Win, B)) * ru(c.Cin, B);
  auto inv = rand_f(in_n, rng);
  auto wv = rand_f(static_cast<std::size_t>(c.Cin) * c.Cout * c.k * c.k, rng);
  std::vector<float> bv = c.bias ? rand_f(c.Cout, rng) : std::vector<float>{};

  // oracle (fsim reference)
  auto ref = conv_transpose<float>(inv, wv, bv, 1, c.Cin, c.Hin, c.Win, c.Cout,
                                   Hout, Wout, c.k, c.k, c.stride,
                                   {c.pt, c.pl, c.pb, c.pr}, B);

  // weights + bias go into the kSrc region (the op reads them via DRAM
  // address).
  auto *wdst = reinterpret_cast<float *>(kSrc);
  for (std::size_t i = 0; i < wv.size(); ++i)
    wdst[i] = wv[i];
  const std::uintptr_t bias_addr =
      kSrc + ((wv.size() * sizeof(float) + 63u) & ~std::uintptr_t(63u));
  if (c.bias) {
    auto *bdst = reinterpret_cast<float *>(bias_addr);
    for (int i = 0; i < c.Cout; ++i)
      bdst[i] = bv[i];
  }

  NnConvTransposeStep st{};
  st.wgt_addr = static_cast<std::uint32_t>(kSrc);
  st.bias_addr = static_cast<std::uint32_t>(bias_addr);
  st.has_bias = c.bias ? 1u : 0u;
  st.tensor_ch = c.Cin;
  st.tensor_h = c.Hin;
  st.tensor_w = c.Win;
  st.out_ch = c.Cout;
  st.out_h = Hout;
  st.out_w = Wout;
  st.kh = c.k;
  st.kw = c.k;
  st.stride = c.stride;
  st.pad[0] = c.pt;
  st.pad[1] = c.pl;
  st.pad[2] = c.pb;
  st.pad[3] = c.pr;
  st.block = B;
  st.n_out_elems = static_cast<std::uint32_t>(ref.size());

  vta::run_convtranspose(st, inv.data(), reinterpret_cast<float *>(kDst));

  char nm[96];
  std::snprintf(nm, sizeof(nm),
                "convT Cin=%d %dx%d->Cout=%d k%d s%d pad{%d,%d} b%d", c.Cin,
                c.Hin, c.Win, c.Cout, c.k, c.stride, c.pt, c.pl, c.bias);
  check_f_bits(nm, ref);
}

} // namespace

int main() {
  void *s =
      mmap(reinterpret_cast<void *>(kSrc), kRegion, PROT_READ | PROT_WRITE,
           MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
  void *d =
      mmap(reinterpret_cast<void *>(kDst), kRegion, PROT_READ | PROT_WRITE,
           MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0);
  if (s == MAP_FAILED || d == MAP_FAILED) {
    std::perror("mmap");
    return 2;
  }

  std::mt19937 rng(0xC0FFEE);

  std::printf("== quantized arithmetic contract ==\n");
  test_qadd();
  test_concat();
  test_concat_unequal({64, 128, 32, 32}, 16, false, rng);
  test_concat_unequal({128, 192, 96, 64}, 4, false, rng);
  test_concat_unequal({3, 17, 5}, 19, true, rng);
  test_concat_unequal({48, 16}, 1, true, rng);
  test_concat_unequal({3, 5, 1, 17}, 33, true, rng);
  test_dequant_quant();
  test_rescale();

  // C: 1 (image), 3, 6 (sub-block), 16 (exact), 20 (partial multi-block), 120.
  const ConvCfg conv[] = {
      {6, 5, 5, 3, 3, 1, 1, 0, 0, 0, 0, 7},
      {1, 6, 6, 3, 3, 1, 1, 0, 0, 0, 0, 5},
      {3, 6, 6, 3, 3, 1, 1, 1, 1, 1, 1, -3},
      {16, 7, 7, 5, 5, 1, 1, 2, 2, 2, 2, 11},
      {20, 4, 5, 3, 3, 2, 2, 0, 0, 0, 0, -5},
      {1, 28, 28, 5, 5, 1, 1, 2, 2, 2, 2, -128}, // LeNet conv1 shape
      {120, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, -128},
  };
  const ChainCfg chain[] = {
      {6, 28, 28, 0, 0, 0, 0, 0},  // MaxPool2 shape (N multiple of B)
      {16, 10, 10, 0, 0, 0, 0, 0}, // MaxPool4 shape (N not multiple of B)
      {20, 5, 5, 0, 0, 0, 0, 3},   {120, 1, 1, 0, 0, 0, 0, -128},
      {6, 5, 5, 1, 1, 1, 1, 7}, // padded (no real net needs it yet)
      {20, 4, 3, 2, 1, 0, 1, -5},  {32, 2, 2, 1, 1, 1, 1, 0},
      {16, 7, 7, 3, 3, 3, 3, 11},
  };

  std::printf("== run_im2row vs fsim reshape ==\n");
  for (const auto &c : conv)
    test_im2row(c, rng);
  std::printf("== run_format_input vs fsim reshape(data_formatting) ==\n");
  for (const auto &c : conv)
    test_format(c, rng);
  std::printf("== run_int32_chain vs fsim subtract_offset / pad_matrix ==\n");
  for (const auto &c : chain)
    test_chain(c, rng);

  // square stride only (fsim conv_transpose is scalar-stride); mix of
  // block-aligned / sub-block channels, with and without bias and top/left pad.
  const ConvTCfg convt[] = {
      {3, 4, 4, 5, 2, 2, 0, 0, 0, 0, 1},   // sub-block Cin/Cout, k2 s2
      {16, 3, 3, 16, 2, 2, 0, 0, 0, 0, 1}, // exact block
      {6, 5, 5, 8, 3, 2, 1, 1, 1, 1, 1},   // k3 s2 with top/left pad
      {8, 4, 4, 4, 2, 2, 0, 0, 0, 0, 0},   // no bias
      {20, 2, 2, 10, 4, 2, 1, 1, 1, 1, 1}, // multi-block Cin, k4 s2, pad
      {1, 4, 4, 3, 2, 2, 0, 0, 0, 0, 1},   // single input channel
  };
  std::printf("== run_convtranspose vs fsim conv_transpose<float> ==\n");
  for (const auto &c : convt)
    test_convtranspose(c, rng);

  std::printf("\n%s (%d failing config%s)\n",
              g_failures ? "FAILED" : "ALL PASS", g_failures,
              g_failures == 1 ? "" : "s");
  return g_failures ? 1 : 0;
}
