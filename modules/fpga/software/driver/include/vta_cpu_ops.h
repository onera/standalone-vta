#ifndef VTA_CPU_OPS_H_
#define VTA_CPU_OPS_H_

#include <cstdint>

struct NnQaddStep {
  std::uint32_t inpA, inpB, out, n_elems;
  float sA, sB, sC;
  std::int32_t zA, zB, zC;
};

/* Activation layout. Everything except a direct convolution reads and writes
   the block-tiled form; a direct convolution reads and writes the flat one.
   The two coincide when the matrix is one channel block wide, which is why
   mixing them goes unnoticed on narrow layers. */
enum NnLayout {
  NN_LAYOUT_BLOCKED = 0,
  NN_LAYOUT_FLAT = 1,
};

struct NnConcatStep {
  std::uint32_t inp[4];
  std::uint32_t out;
  std::uint32_t n_rows; /* H * W spatial positions (multiple of block) */
  std::uint32_t
      n_ch_per_inp; /* channels per input branch, not padded */
  int nb_inp;
  float scales[4];
  std::int32_t zps[4];
  float out_scale;
  std::int32_t out_zp;
  std::uint32_t block; /* VTA block size (BLOCK_IN = BLOCK_OUT) */
  /* Layout of every branch and of the output; concat is channel-wise, so it is
     the one non-elementwise CPU op whose result depends on it. Last, so an
     initialiser that omits it gets NN_LAYOUT_BLOCKED - which is what every
     emitted plan wants today. */
  std::uint32_t layout;
  /* Unpadded row count, read by compact branches; 0 means n_rows. */
  std::uint32_t n_rows_valid;
  /* Bit p set when branch p stores its final partial row-block compactly, as
     (n_rows_valid mod block) x block blocks, instead of padding it. */
  std::uint32_t compact_mask;
};

/* Convert one activation between the block-tiled and flat layouts.

   Emitted only at a layout boundary - where a direct convolution meets an
   operator that has not moved to the flat layout. It is one pass over the
   activation, where the im2row it replaces writes kH*kW times as much, so a
   boundary is far cheaper than the pass it displaces; back-to-back direct
   convolutions need no step here at all. */
struct NnRelayoutStep {
  std::uint32_t src_addr;
  std::uint32_t dst_addr;
  std::uint32_t n_rows;  /* H*W, the spatial positions                       */
  std::uint32_t n_ch;    /* channels, padded to a block multiple             */
  std::uint32_t block;   /* VTA block size                                   */
  std::uint32_t to_flat; /* 1: block-tiled -> flat.  0: flat -> block-tiled  */
  /* The two directions do not move the same element type, because they sit at
     different points in the pipeline.

     to_flat feeds a convolution's INP, exactly where im2row would have: it
     reads the producer's compact int8 activation and writes vta_inp_t,
     subtracting the zero point on the way, so it must widen. Treating it as a
     byte copy silently writes int8 into a 32-bit buffer.

     from-flat takes the layer's own OUT after the rescale has made it int8
     and hands it to consumers, so it is int8 to int8 and offset_a is unused. */
  std::int32_t offset_a;
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
  /* Fused rescale of the producer's OUT: 0 => src is already compact int8
     (a preceding NN_STEP_RESCALE ran). Nonzero => src is the raw int32 OUT and
     each element is requantized clamp_i8(nearbyint(x*rescale_scale)+
     rescale_offset) before use - identical to run_rescale then this step. */
  float rescale_scale;
  std::int32_t rescale_offset;
  /* Layout of the *source* activation. The im2row matrix this writes is always
     block-tiled - it is consumed by a GEMM, not by a convolution. */
  std::uint32_t src_layout;
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
   With spatial padding (pad != {0,0,0,0}) it rebuilds the padded, re-blocked
   matrix, filling padded positions with -128 (int8 min, i.e. -inf for the
   max-pool that consumes it), as fsim's pad_matrix does.
 */
struct NnInt32ChainStep {
  std::uint32_t src_addr; /* producer OUT buffer (compact int8, post-rescale) */
  std::uint32_t dst_addr; /* this layer's ACC buffer (int32) */
  std::uint32_t n_elems; /* element count = tensor_ch*tensor_h*tensor_w       */
  std::int32_t offset_a; /* zero-point to subtract from source values         */
  std::int32_t pad[4];   /* {top, left, bottom, right}                        */
  std::uint32_t
      tensor_ch; /* C - input channels (for padding)                  */
  std::uint32_t tensor_h; /* H - input height */
  std::uint32_t tensor_w; /* W - input width */
  /* Fused rescale of the producer's OUT (see NnIm2RowStep). 0 => src is compact
     int8; nonzero => src is the raw int32 OUT, requantized before widening. */
  float rescale_scale;
  std::int32_t rescale_offset;
};

/* Floating-point ConvTranspose (transposed convolution / deconvolution).
   A CPU-only op: the PL never reads its weights/bias, so they live in plain DDR
   loaded via the same static-load path as VTA buffers (elf/incbin + Tcl dow).
   It runs in float between a NN_STEP_DEQUANT and a NN_STEP_QUANT, reading and
   writing the runtime float_buf (passed as pointers, not DDR addresses), so the
   numeric path mirrors fsim's cpu_functions.h conv_transpose<float>() exactly.
   The input float_buf is the producer's block-tiled (Hin*Win)xCin matrix; the
   output float_buf is the block-tiled (Hout*Wout)xCout matrix. Single stride
   (sh==sw) as in fsim; only pad[top]/pad[left] affect the scatter. */
struct NnConvTransposeStep {
  std::uint32_t wgt_addr;  /* DDR float32 weights, ONNX [Cin][Cout][KH][KW] */
  std::uint32_t bias_addr; /* DDR float32 bias [Cout]; valid iff has_bias    */
  std::uint32_t has_bias;
  std::uint32_t tensor_ch; /* Cin  */
  std::uint32_t tensor_h;  /* Hin  */
  std::uint32_t tensor_w;  /* Win  */
  std::uint32_t out_ch;    /* Cout */
  std::uint32_t out_h;     /* Hout */
  std::uint32_t out_w;     /* Wout */
  std::uint32_t kh, kw;
  std::uint32_t
      stride;          /* single stride; fsim conv_transpose is scalar-stride */
  std::int32_t pad[4]; /* {top, left, bottom, right}; only top/left used     */
  std::uint32_t block; /* VTA block size                                     */
  std::uint32_t n_out_elems; /* block-padded float count of the output buffer */
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
  NN_STEP_CONVTRANSPOSE = 9,
  NN_STEP_RELAYOUT = 10,
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
    NnConvTransposeStep convtranspose;
    NnRelayoutStep relayout;
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
void run_relayout(const NnRelayoutStep &d);
/* in/out are the runtime float_buf (block-tiled float); wgt/bias come from the
   DDR addresses in d.  out must hold d.n_out_elems floats. */
void run_convtranspose(const NnConvTransposeStep &d, const float *in,
                       float *out);

} // namespace vta

#endif // VTA_CPU_OPS_H_
