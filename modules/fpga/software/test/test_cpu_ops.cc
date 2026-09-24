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
//   run_im2row      <-> reshape(convert<inp>(block_src), ...)
//   run_format_input<-> reshape(convert<inp>(data_formatting(raw_hwc)), ...)
//   run_int32_chain  : no pad -> subtract_offset(convert<acc>(src))
//                      padded -> pad_matrix(subtract_offset(...), ..., -128)
//
// The ops cast their uint32 DRAM-address fields to pointers, so two scratch
// regions are mmap'd MAP_FIXED at low (32-bit-representable) addresses.
//
// Exercises the 32-bit datapath only (stub vta_hw_config.h: int32 elements);
// the int8 datapath is out of scope here.
//
// Build/run:  cd src/fpga/software && make test-cpu-ops

#include "cpu_functions.h" // fsim reference (header-only, free functions)
#include "vta_cpu_ops.h"   // driver structs + vta::run_* decls
#include "vta_hw_config.h" // stub: vta_*_t element types + VTA_BLOCK_SIZE

#include <cmath>
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

// int32 producer-OUT values, in a realistic VTA accumulator range.
std::vector<std::int32_t> rand_i32(std::size_t n, std::mt19937 &rng, int lo,
                                   int hi) {
  std::uniform_int_distribution<int> d(lo, hi);
  std::vector<std::int32_t> v(n);
  for (auto &x : v)
    x = d(rng);
  return v;
}

// The compact int8 a fused reshape must reproduce: exactly run_rescale
// (double math, nearbyint, +offset, clamp to int8), matching rescaled_src().
std::vector<std::int8_t> apply_rescale(const std::vector<std::int32_t> &s32,
                                       float scale, int roff) {
  std::vector<std::int8_t> out(s32.size());
  for (std::size_t i = 0; i < s32.size(); ++i) {
    std::int64_t q = static_cast<std::int64_t>(std::nearbyint(
                         static_cast<double>(s32[i]) *
                         static_cast<double>(scale))) +
                     roff;
    out[i] = static_cast<std::int8_t>(q < -128 ? -128 : (q > 127 ? 127 : q));
  }
  return out;
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

// ---- int32_chain with the producer rescale FUSED in (src is raw int32 OUT) --
void test_chain_fused(const ChainCfg &c, std::mt19937 &rng, float scale,
                      int roff) {
  const int B = VTA_BLOCK_SIZE;
  const bool padded = c.pt || c.pl || c.pb || c.pr;
  const std::size_t srcN =
      static_cast<std::size_t>(ru(c.H * c.W, B)) * ru(c.C, B);
  auto s32 = rand_i32(srcN, rng, -30000, 30000);

  auto i8 = apply_rescale(s32, scale, roff);
  std::vector<std::int32_t> ref;
  if (!padded) {
    ref = subtract_offset(convert_vector_type<std::int32_t>(i8), c.off);
  } else {
    ref = pad_matrix<std::int32_t>(
        subtract_offset(convert_vector_type<std::int32_t>(i8), c.off), c.C, c.H,
        c.W, B, {c.pt, c.pl, c.pb, c.pr}, -128);
  }

  auto *src = reinterpret_cast<std::int32_t *>(kSrc);
  for (std::size_t i = 0; i < srcN; ++i)
    src[i] = s32[i];
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
  st.rescale_scale = scale;
  st.rescale_offset = roff;
  vta::run_int32_chain(st);

  char nm[96];
  std::snprintf(nm, sizeof(nm),
                "int32_chain+rescale C=%d %dx%d pad{%d,%d,%d,%d} s=%.4g o=%d",
                c.C, c.H, c.W, c.pt, c.pl, c.pb, c.pr,
                static_cast<double>(scale), roff);
  check(nm, ref);
}

// ---- im2row with the producer rescale FUSED in (src is raw int32 OUT) ------
void test_im2row_fused(const ConvCfg &c, std::mt19937 &rng, float scale,
                       int roff) {
  const int B = VTA_BLOCK_SIZE;
  const int oH = out_dim(c.H, c.pt, c.pb, c.kh, c.sh);
  const int oW = out_dim(c.W, c.pl, c.pr, c.kw, c.sw);
  const std::size_t n = static_cast<std::size_t>(ru(c.H * c.W, B)) * ru(c.C, B);
  auto s32 = rand_i32(n, rng, -30000, 30000);

  // oracle: run_rescale(s32) -> int8, then the ordinary im2row reshape.
  auto i8 = apply_rescale(s32, scale, roff);
  auto ref = reshape<std::int32_t>(convert_vector_type<std::int32_t>(i8), B, 1,
                                   c.C, c.H, c.W, {c.kh, c.kw}, c.sh,
                                   {c.pt, c.pl, c.pb, c.pr}, true, c.off, c.sw);

  // driver: source region holds the raw int32 OUT.
  auto *src = reinterpret_cast<std::int32_t *>(kSrc);
  for (std::size_t i = 0; i < n; ++i)
    src[i] = s32[i];
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
  st.rescale_scale = scale;
  st.rescale_offset = roff;
  vta::run_im2row(st);

  char nm[96];
  std::snprintf(nm, sizeof(nm), "im2row+rescale C=%d %dx%d k%dx%d s=%.4g o=%d",
                c.C, c.H, c.W, c.kh, c.kw, static_cast<double>(scale), roff);
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
  check_f(nm, ref);
}

// ---- flat activation layout ------------------------------------------------
// The direct-convolution lowering reads and writes activations flat, while
// every other op uses the block-tiled form. These check the flat paths against
// the blocked ones, which the tests above already tie to the fsim reference:
// converting the input and running the flat path must reproduce, byte for
// byte, what the blocked path produces from the same data. A pure round-trip
// would not catch an op that reads a consistent but wrong layout.

void report(const std::string &name, std::size_t n, std::size_t bad) {
  std::printf("  %-44s ref=%-6zu mm=%-5zu %s\n", name.c_str(), n, bad,
              bad ? "FAIL" : "PASS");
  if (bad)
    ++g_failures;
}

std::uint32_t blocked_off(std::uint32_t row, std::uint32_t ch,
                          std::uint32_t n_ch, std::uint32_t B) {
  const std::uint32_t cblk = (n_ch + B - 1u) / B;
  return ((row / B) * cblk + ch / B) * B * B + (row % B) * B + (ch % B);
}

void test_relayout(std::uint32_t rows, std::uint32_t ch, std::mt19937 &rng) {
  const std::uint32_t B = VTA_BLOCK_SIZE;
  // The blocked side pads the rows out to whole row-blocks - the producer's
  // OUT always does - while the flat side is dense, so the two sides differ in
  // size whenever the row count is not a block multiple.
  const std::uint32_t n_flat = rows * ch;
  const std::uint32_t n_blocked = ((rows + B - 1u) / B) * B * ch;
  const std::int32_t off = -7;

  std::vector<std::int8_t> blocked(n_blocked);
  for (auto &v : blocked)
    v = static_cast<std::int8_t>(rng() % 251) - 125;

  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  std::copy(blocked.begin(), blocked.end(), src);

  NnRelayoutStep fwd{};
  fwd.src_addr = kSrc;
  fwd.dst_addr = kDst;
  fwd.n_rows = rows;
  fwd.n_ch = ch;
  fwd.block = B;
  fwd.to_flat = 1u;
  fwd.offset_a = off;
  vta::run_relayout(fwd);

  // to_flat feeds a convolution's INP: it widens to vta_inp_t and removes the
  // zero point, exactly as the im2row it stands in for does.
  std::size_t bad = 0;
  const auto *wide = reinterpret_cast<const vta_inp_t *>(kDst);
  for (std::uint32_t r = 0; r < rows; ++r)
    for (std::uint32_t c = 0; c < ch; ++c) {
      const vta_inp_t want = static_cast<vta_inp_t>(
          static_cast<std::int32_t>(blocked[blocked_off(r, c, ch, B)]) - off);
      if (wide[r * ch + c] != want)
        ++bad;
    }

  // The other direction publishes the layer's already-rescaled int8 OUT, so it
  // is int8 both sides and takes no offset. Feed it the flat image of the same
  // data and require the original blocked buffer back.
  for (std::uint32_t r = 0; r < rows; ++r)
    for (std::uint32_t c = 0; c < ch; ++c)
      src[r * ch + c] = blocked[blocked_off(r, c, ch, B)];
  NnRelayoutStep back{};
  back.src_addr = kSrc;
  back.dst_addr = kDst;
  back.n_rows = rows;
  back.n_ch = ch;
  back.block = B;
  back.to_flat = 0u;
  auto *narrow = reinterpret_cast<std::int8_t *>(kDst);
  std::fill(narrow, narrow + n_blocked, static_cast<std::int8_t>(0));
  vta::run_relayout(back);
  for (std::uint32_t r = 0; r < rows; ++r)
    for (std::uint32_t c = 0; c < ch; ++c) {
      const std::uint32_t o = blocked_off(r, c, ch, B);
      if (narrow[o] != blocked[o])
        ++bad;
    }

  char nm[96];
  std::snprintf(nm, sizeof(nm), "relayout %ux%u (%u channel blocks)", rows, ch,
                (ch + B - 1u) / B);
  report(nm, n_flat * 2, bad);
}

void test_concat_flat(std::uint32_t rows, std::uint32_t ch_per, int nb,
                      std::mt19937 &rng) {
  const std::uint32_t B = VTA_BLOCK_SIZE;
  const std::uint32_t tot = ch_per * static_cast<std::uint32_t>(nb);
  const std::uint32_t per = rows * ch_per;

  std::vector<std::vector<std::int8_t>> branch(nb,
                                               std::vector<std::int8_t>(per));
  for (auto &b : branch)
    for (auto &v : b)
      v = static_cast<std::int8_t>(rng() % 251) - 125;

  NnConcatStep st{};
  st.out = kDst;
  st.n_rows = rows;
  st.n_ch_per_inp = ch_per;
  st.nb_inp = nb;
  st.out_scale = 0.5f;
  st.out_zp = -3;
  st.block = B;
  for (int i = 0; i < nb; ++i) {
    st.inp[i] = static_cast<std::uint32_t>(kSrc + i * per);
    st.scales[i] = 0.25f * static_cast<float>(i + 1);
    st.zps[i] = i - 1;
  }

  // blocked reference
  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  for (int i = 0; i < nb; ++i)
    std::copy(branch[i].begin(), branch[i].end(), src + i * per);
  st.layout = NN_LAYOUT_BLOCKED;
  vta::run_concat(st);
  std::vector<std::int8_t> ref(reinterpret_cast<std::int8_t *>(kDst),
                               reinterpret_cast<std::int8_t *>(kDst) +
                                   rows * tot);

  // same data converted to flat, through the flat path
  for (int i = 0; i < nb; ++i)
    for (std::uint32_t r = 0; r < rows; ++r)
      for (std::uint32_t c = 0; c < ch_per; ++c)
        src[i * per + r * ch_per + c] =
            branch[i][blocked_off(r, c, ch_per, B)];
  st.layout = NN_LAYOUT_FLAT;
  vta::run_concat(st);

  const auto *got = reinterpret_cast<const std::int8_t *>(kDst);
  std::size_t bad = 0;
  for (std::uint32_t r = 0; r < rows; ++r)
    for (std::uint32_t c = 0; c < tot; ++c)
      if (got[r * tot + c] != ref[blocked_off(r, c, tot, B)])
        ++bad;

  char nm[96];
  std::snprintf(nm, sizeof(nm), "concat flat %ux%u x%d", rows, ch_per, nb);
  report(nm, rows * tot, bad);
}

void test_im2row_flat(const ConvCfg &c, std::mt19937 &rng) {
  const std::uint32_t B = VTA_BLOCK_SIZE;
  const std::uint32_t oh = out_dim(c.H, c.pt, c.pb, c.kh, c.sh);
  const std::uint32_t ow = out_dim(c.W, c.pl, c.pr, c.kw, c.sw);
  const std::uint32_t cb = (c.C + B - 1u) / B;
  const std::uint32_t rows = c.H * c.W;
  const std::uint32_t chp = cb * B;
  const std::uint32_t n = ((rows + B - 1u) / B) * B * chp;

  std::vector<std::int8_t> blocked(n, 0);
  for (auto &v : blocked)
    v = static_cast<std::int8_t>(rng() % 251) - 125;

  NnIm2RowStep st{};
  st.src_addr = kSrc;
  st.dst_addr = kDst;
  st.tensor_ch = c.C;
  st.tensor_h = c.H;
  st.tensor_w = c.W;
  st.kh = c.kh;
  st.kw = c.kw;
  st.sh = c.sh;
  st.sw = c.sw;
  st.pad[0] = c.pt; st.pad[1] = c.pl; st.pad[2] = c.pb; st.pad[3] = c.pr;
  st.offset_a = c.off;
  st.out_h = oh;
  st.out_w = ow;
  st.block = B;

  auto *src = reinterpret_cast<std::int8_t *>(kSrc);
  std::copy(blocked.begin(), blocked.end(), src);
  st.src_layout = NN_LAYOUT_BLOCKED;
  vta::run_im2row(st);
  const std::uint32_t out_n =
      ((oh * ow + B - 1u) / B) * B * (((c.C * c.kh * c.kw) + B - 1u) / B) * B;
  std::vector<vta_inp_t> ref(reinterpret_cast<vta_inp_t *>(kDst),
                             reinterpret_cast<vta_inp_t *>(kDst) + out_n);

  for (std::uint32_t r = 0; r < rows; ++r)
    for (std::uint32_t ch = 0; ch < chp; ++ch)
      src[r * chp + ch] = blocked[blocked_off(r, ch, chp, B)];
  st.src_layout = NN_LAYOUT_FLAT;
  vta::run_im2row(st);

  const auto *got = reinterpret_cast<const vta_inp_t *>(kDst);
  std::size_t bad = 0;
  for (std::uint32_t i = 0; i < out_n; ++i)
    if (got[i] != ref[i])
      ++bad;

  char nm[96];
  std::snprintf(nm, sizeof(nm), "im2row flat-src C=%u %ux%u k%ux%u", c.C, c.H,
                c.W, c.kh, c.kw);
  report(nm, out_n, bad);
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

  // Fused producer-rescale path (src = raw int32 OUT). Scales/offsets from real
  // lenet5 boundaries: conv->maxpool (~7.75e-4, -128) and the identity 1.0/0
  // rescale a maxpool emits before the next conv's im2row.
  std::printf("== fused rescale: run_im2row (src int32) ==\n");
  for (const auto &c : conv) {
    test_im2row_fused(c, rng, 7.751231e-4f, -128);
    test_im2row_fused(c, rng, 1.0f, 0);
    test_im2row_fused(c, rng, 1.6434737e-3f, -128);
  }
  std::printf("== fused rescale: run_int32_chain (src int32) ==\n");
  for (const auto &c : chain) {
    test_chain_fused(c, rng, 7.751231e-4f, -128);
    test_chain_fused(c, rng, 1.0f, 0);
  }

  // square stride only (fsim conv_transpose is scalar-stride); mix of
  // block-aligned / sub-block channels, with and without bias and top/left pad.
  const ConvTCfg convt[] = {
      {3, 4, 4, 5, 2, 2, 0, 0, 0, 0, 1},   // sub-block Cin/Cout, k2 s2
      {16, 3, 3, 16, 2, 2, 0, 0, 0, 0, 1}, // exact block
      {6, 5, 5, 8, 3, 2, 1, 1, 1, 1, 1},   // k3 s2 with top/left pad
      {8, 4, 4, 4, 2, 2, 0, 0, 0, 0, 0},   // no bias
      {20, 2, 2, 10, 4, 2, 1, 1, 1, 1, 1}, // multi-block Cin, k4 s2, pad
      {1, 4, 4, 3, 2, 2, 0, 0, 0, 0, 1},   // single input channel
      {20, 3, 3, 24, 2, 2, 0, 0, 0, 0, 1}, // multi-block Cout, partial row block
  };
  std::printf("== run_convtranspose vs fsim conv_transpose<float> ==\n");
  for (const auto &c : convt)
    test_convtranspose(c, rng);

  std::printf("== flat activation layout ==\n");
  test_relayout(16, 16, rng);
  test_relayout(64, 48, rng);
  test_relayout(25, 32, rng);
  test_relayout(80, 96, rng);
  test_concat_flat(32, 16, 2, rng);
  test_concat_flat(64, 32, 3, rng);
  test_concat_flat(16, 48, 2, rng);
  for (const auto &c : conv)
    test_im2row_flat(c, rng);

  std::printf("\n%s (%d failing config%s)\n",
              g_failures ? "FAILED" : "ALL PASS", g_failures,
              g_failures == 1 ? "" : "s");
  return g_failures ? 1 : 0;
}
