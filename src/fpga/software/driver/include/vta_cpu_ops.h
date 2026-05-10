#ifndef VTA_CPU_OPS_H_
#define VTA_CPU_OPS_H_

#include <cstdint>

struct NnQaddStep {
  std::uint32_t inpA, inpB, out, n_elems;
  float sA, sB, sC;
  std::int32_t zA, zB, zC;
};

struct NnConcatStep {
  std::uint32_t inp[4];
  std::uint32_t out;
  std::uint32_t n_rows;        /* H * W spatial positions (multiple of block) */
  std::uint32_t n_ch_per_inp;  /* channels per input branch (multiple of block) */
  int nb_inp;
  float scales[4];
  std::int32_t zps[4];
  float out_scale;
  std::int32_t out_zp;
  std::uint32_t block;         /* VTA block size (BLOCK_IN = BLOCK_OUT) */
};

struct NnDequantStep {
  std::uint32_t inp_addr;
  std::uint32_t n_elems;
  float scale;
  std::int32_t zp;
};

struct NnQuantStep {
  std::uint32_t out_addr;
  std::uint32_t n_elems;
  float scale;
  std::int32_t zp;
};

/* Format raw HWC input_nn.bin (loaded at raw_addr) into VTA INP block layout
   (written to inp_addr) by applying im2row with offset, padding, and stride. */
struct NnFormatInputStep {
  std::uint32_t raw_addr; /* scratch DDR addr of raw input_nn.bin (HWC flat) */
  std::uint32_t inp_addr; /* VTA INP address to write formatted result        */
  std::uint32_t tensor_ch; /* C - input channels */
  std::uint32_t tensor_h; /* H - input height                                 */
  std::uint32_t tensor_w; /* W - input width                                  */
  std::uint32_t kh, kw;   /* kernel height / width                            */
  std::uint32_t sh, sw;   /* stride height / width                            */
  std::int32_t pad[4];   /* {top, left, bottom, right}                       */
  std::int32_t offset_a; /* zero-point to subtract from raw values           */
  std::uint32_t out_h;   /* output height after im2row                       */
  std::uint32_t out_w;   /* output width  after im2row                       */
  std::uint32_t block;   /* VTA block size (BLOCK_IN = BLOCK_OUT)            */
};

/* Apply im2row to a previous VTA layer's OUT buffer (VTA block-tiled int8)
   and write the result into the current layer's INP buffer (VTA block im2row).
   Source layout: [N/B][C/B][B][B] with N=tensor_h*tensor_w, C=tensor_ch. */
struct NnIm2RowStep {
  std::uint32_t src_addr; /* previous layer OUT buffer (VTA block int8)       */
  std::uint32_t dst_addr; /* current layer INP buffer  (VTA block im2row int8)*/
  std::uint32_t tensor_ch; /* C - input channels                               */
  std::uint32_t tensor_h;  /* H - input height                                 */
  std::uint32_t tensor_w;  /* W - input width                                  */
  std::uint32_t kh, kw;    /* kernel height / width                            */
  std::uint32_t sh, sw;    /* stride height / width                            */
  std::int32_t  pad[4];    /* {top, left, bottom, right}                       */
  std::int32_t  offset_a;  /* zero-point to subtract from source values        */
  std::uint32_t out_h;     /* output height after im2row                       */
  std::uint32_t out_w;     /* output width  after im2row                       */
  std::uint32_t block;     /* VTA block size (BLOCK_IN = BLOCK_OUT)            */
};

/* In-place INT32→INT8 rescale of a VTA OUT buffer.
   Safe when vta_out_t is wider than int8_t: write byte i < read byte 4*(i+1). */
struct NnRescaleStep {
  std::uint32_t addr;    /* VTA OUT buffer: read as vta_out_t*, written as int8_t* in-place */
  std::uint32_t n_elems; /* number of vta_out_t elements                                    */
  float         scale;   /* ld.scale from dependency.csv                                    */
  std::int32_t  offset;  /* ld.offset_c (output zero-point)                                 */
};

namespace vta {

void run_qadd(const NnQaddStep &d);
void run_concat(const NnConcatStep &d);
void run_dequant(const NnDequantStep &d, float *out);
void run_quant(const NnQuantStep &d, const float *in);
void run_format_input(const NnFormatInputStep &d);
void run_im2row(const NnIm2RowStep &d);
void run_rescale(const NnRescaleStep &d);

} // namespace vta

#endif // VTA_CPU_OPS_H_
