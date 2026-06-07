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
  std::uint32_t n_rows; /* H * W spatial positions (multiple of block) */
  std::uint32_t
      n_ch_per_inp; /* channels per input branch (multiple of block) */
  int nb_inp;
  float scales[4];
  std::int32_t zps[4];
  float out_scale;
  std::int32_t out_zp;
  std::uint32_t block; /* VTA block size (BLOCK_IN = BLOCK_OUT) */
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
  std::int32_t pad[4];    /* {top, left, bottom, right}                       */
  std::int32_t offset_a;  /* zero-point to subtract from raw values           */
  std::uint32_t out_h;    /* output height after im2row                       */
  std::uint32_t out_w;    /* output width  after im2row                       */
  std::uint32_t block;    /* VTA block size (BLOCK_IN = BLOCK_OUT)            */
};

/* Apply im2row to a previous VTA layer's OUT buffer (VTA block-tiled int8)
   and write the result into the current layer's INP buffer (VTA block im2row).
   Source layout: [N/B][C/B][B][B] with N=tensor_h*tensor_w, C=tensor_ch. */
struct NnIm2RowStep {
  std::uint32_t src_addr; /* previous layer OUT buffer (VTA block int8)       */
  std::uint32_t dst_addr; /* current layer INP buffer  (VTA block im2row int8)*/
  std::uint32_t tensor_ch; /* C - input channels */
  std::uint32_t tensor_h; /* H - input height                                 */
  std::uint32_t tensor_w; /* W - input width                                  */
  std::uint32_t kh, kw;   /* kernel height / width                            */
  std::uint32_t sh, sw;   /* stride height / width                            */
  std::int32_t pad[4];    /* {top, left, bottom, right}                       */
  std::int32_t offset_a;  /* zero-point to subtract from source values        */
  std::uint32_t out_h;    /* output height after im2row                       */
  std::uint32_t out_w;    /* output width  after im2row                       */
  std::uint32_t block;    /* VTA block size (BLOCK_IN = BLOCK_OUT)            */
};

/* In-place INT32→INT8 rescale of a VTA OUT buffer.
   Safe when vta_out_t is wider than int8_t: write byte i < read byte 4*(i+1).
 */
struct NnRescaleStep {
  std::uint32_t addr; /* VTA OUT buffer: read as vta_out_t*, written as int8_t*
                         in-place */
  std::uint32_t n_elems; /* number of vta_out_t elements */
  float scale;           /* ld.scale from dependency.csv           */
  std::int32_t offset;   /* ld.offset_c (output zero-point)   */
};

/* Feed an int32/ALU (maxpool) layer's ACC input from the producer's OUT.
   The producer's OUT has already been rescaled in-place to compact int8 by the
   preceding NN_STEP_RESCALE, so the source is int8.  This widens each int8 to
   int32 (sign-extend) and subtracts the consumer's zero-point, writing the
   layer's ACC buffer - the runtime equivalent of the functional simulator's
   int32 chaining (fsim_nn.cc: convert_vector_type<int32> + subtract_offset).
   Spatial padding (pad != {0,0,0,0}) is not yet implemented (warned, skipped).
 */
struct NnInt32ChainStep {
  std::uint32_t src_addr; /* producer OUT buffer (compact int8, post-rescale) */
  std::uint32_t dst_addr; /* this layer's ACC buffer (int32) */
  std::uint32_t n_elems; /* element count = tensor_ch*tensor_h*tensor_w       */
  std::int32_t offset_a; /* zero-point to subtract from source values         */
  std::int32_t pad[4];   /* {top, left, bottom, right}; nonzero not supported */
  std::uint32_t
      tensor_ch; /* C - input channels (for padding, when supported)  */
  std::uint32_t tensor_h; /* H - input height */
  std::uint32_t tensor_w; /* W - input width */
};

enum NnStepType {
  NN_STEP_VTA = 0,
  NN_STEP_QADD = 1,
  NN_STEP_CONCAT = 2,
  NN_STEP_DEQUANT = 3,
  NN_STEP_QUANT = 4,
  NN_STEP_FORMAT_INPUT = 5,
  NN_STEP_IM2ROW = 6,
  NN_STEP_RESCALE = 7,
  NN_STEP_INT32_CHAIN = 8,
};

struct NnVtaStep {
  int layer_idx;
};

struct NnExecStep {
  NnStepType type;
  const char *name;
  union {
    NnVtaStep vta;
    NnQaddStep qadd;
    NnConcatStep concat;
    NnDequantStep dequant;
    NnQuantStep quant;
    NnFormatInputStep format_input;
    NnIm2RowStep im2row;
    NnRescaleStep rescale;
    NnInt32ChainStep int32_chain;
  };
};
namespace vta {

void run_qadd(const NnQaddStep &d);
void run_concat(const NnConcatStep &d);
void run_dequant(const NnDequantStep &d, float *out);
void run_quant(const NnQuantStep &d, const float *in);
void run_format_input(const NnFormatInputStep &d);
void run_im2row(const NnIm2RowStep &d);
void run_rescale(const NnRescaleStep &d);
void run_int32_chain(const NnInt32ChainStep &d);

} // namespace vta

#endif // VTA_CPU_OPS_H_
