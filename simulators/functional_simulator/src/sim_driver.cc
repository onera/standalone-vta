/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/*!
 * \file sim_driver.cc
 * \brief VTA driver for simulated backend.
 */
#include "../include/driver.h" //<vta/driver.h>
#include "../config/hw_spec.h" //<vta/hw_spec.h>
#include "../external_lib/tvm/registry.h" //<tvm/runtime/registry.h>
#include "../include/sim_tlpp.h" //<vta/sim_tlpp.h>
#include <type_traits>
#include <mutex>
#include <map>
#include <unordered_map>
#include <cstring>
#include <sstream>

#include "../include/virtual_memory.h" //"../vmem/virtual_memory.h"

namespace vta {
namespace sim {

/*! \brief debug flag for skipping computation */
enum DebugFlagMask {
  kSkipExec = 1
};

/*!
 * \brief Helper class to pack and unpack bits
 *  Applies truncation when pack to low level bits.
 *
 * \tparam bits The number of bits in integer.
 * \note This implementation relies on little endian.
 */
template<uint32_t bits>
class BitPacker {
 public:
  explicit BitPacker(void* data) {
    //printf("\n SIM_DRIVER.CC: BitPacker() \n"); // (printf) ADDED
    data_ = static_cast<uint32_t*>(data);
  }

  uint32_t GetUnsigned(uint32_t index) const {
    //printf("\n SIM_DRIVER.CC: GetUnsigned() \n"); // (printf) ADDED
    if (bits == 32) {
      return data_[index];
    } else if (bits == 16) {
      return reinterpret_cast<uint16_t*>(data_)[index];
    } else if (bits == 8) {
      return reinterpret_cast<uint8_t*>(data_)[index];
    } else {
      uint32_t offset = index / kNumPackElem;
      uint32_t shift = index % kNumPackElem;
      return (data_[offset] >> shift) & kMask;
    }
  }

  int32_t GetSigned(uint32_t index) const {
    //printf("\n SIM_DRIVER.CC: GetSigned() \n"); // (printf) ADDED
    if (bits == 32) {
      return reinterpret_cast<int32_t*>(data_)[index];
    } else if (bits == 16) {
      return reinterpret_cast<int16_t*>(data_)[index];
    } else if (bits == 8) {
      return reinterpret_cast<int8_t*>(data_)[index];
    } else {
      uint32_t offset = index / kNumPackElem;
      uint32_t shift = (index % kNumPackElem) * bits;
      int32_t uvalue = static_cast<int32_t>(
          (data_[offset] >> shift) & kMask);
      int kleft = 32 - bits;
      return (uvalue << kleft) >> kleft;
    }
  }

  void SetUnsigned(uint32_t index, uint32_t value) {
    //printf("\n SIM_DRIVER.CC: SetUnsigned() \n"); // (printf) ADDED
    if (bits == 32) {
      data_[index] = value;
    } else if (bits == 16) {
      reinterpret_cast<uint16_t*>(data_)[index] = value;
    } else if (bits == 8) {
      reinterpret_cast<uint8_t*>(data_)[index] = value;
    } else {
      uint32_t offset = index / kNumPackElem;
      uint32_t shift = (index % kNumPackElem) * bits;
      data_[offset] &= (~(kMask << shift));
      data_[offset] |= (value & kMask) << shift;
    }
  }

  void SetSigned(uint32_t index, int32_t value) {
    //printf("\n SIM_DRIVER.CC: SetSigned() \n"); // (printf) ADDED
    if (bits == 32) {
      reinterpret_cast<int32_t*>(data_)[index] = value;
    } else if (bits == 16) {
      reinterpret_cast<int16_t*>(data_)[index] = value;
    } else if (bits == 8) {
      reinterpret_cast<int8_t*>(data_)[index] = value;
    } else {
      uint32_t offset = index / kNumPackElem;
      uint32_t shift = (index % kNumPackElem) * bits;
      data_[offset] &= (~(kMask << shift));
      data_[offset] |= static_cast<uint32_t>(value & kMask) << shift;
    }
  }

 private:
  uint32_t* data_;
  static constexpr uint32_t kNumPackElem = 32 / bits;
  static constexpr uint32_t kMask = (1U << (bits >= 32U ? 31U : bits)) - 1U;
};

/*!
 * \brief DRAM memory manager
 *  Implements simple paging to allow physical address translation.
 */
using DRAM = ::vta::vmem::VirtualMemoryManager;

/*!
 * \brief Register file.
 * \tparam kBits Number of bits of one value.
 * \tparam kLane Number of lanes in one element.
 * \tparam kMaxNumElem Maximum number of element.
 */
template<int kBits, int kLane, int kMaxNumElem>
class SRAM {
 public:
  /*! \brief Bytes of single vector element */
  static const int kElemBytes = (kBits * kLane + 7) / 8;
  /*! \brief content data type */
  using DType = typename std::aligned_storage<kElemBytes, kElemBytes>::type;
  SRAM() {
    //printf("\n SIM_DRIVER.CC: SRAM() \n"); // (printf) ADDED
    data_ = new DType[kMaxNumElem];
    //printf("Data: %p \t kMaxNumElem: %d \n", data_, kMaxNumElem); // (printf) ADDED
  }
  ~SRAM() {
    delete [] data_;
  }
  // Get the i-th index
  void* BeginPtr(uint32_t index) {
    //printf("\n SIM_DRIVER.CC: BeginPtr() \n"); // (printf) ADDED
    CHECK_LT(index, kMaxNumElem);
    return &(data_[index]);
  }
  // Execute the load instruction on this SRAM
  void Load(const VTAMemInsn* op,
            DRAM* dram,
            uint64_t* load_counter,
            bool skip_exec) {
    //printf("\n SIM_DRIVER.CC: Load() \n"); // (printf) ADDED
    load_counter[0] += (op->x_size * op->y_size) * kElemBytes;
    if (skip_exec) return;
    DType* sram_ptr = data_ + op->sram_base;
    uint8_t* dram_ptr = static_cast<uint8_t*>(dram->GetAddr(
        op->dram_base * kElemBytes));
    uint64_t xtotal = op->x_size + op->x_pad_0 + op->x_pad_1;
    uint32_t ytotal = op->y_size + op->y_pad_0 + op->y_pad_1;
    uint64_t sram_end = op->sram_base + xtotal * ytotal;
    CHECK_LE(sram_end, kMaxNumElem);
    memset(sram_ptr, 0, kElemBytes * xtotal * op->y_pad_0);
    sram_ptr += xtotal * op->y_pad_0;

    for (uint32_t y = 0; y < op->y_size; ++y) {
      memset(sram_ptr, 0, kElemBytes * op->x_pad_0);
      sram_ptr += op->x_pad_0;
      memcpy(sram_ptr, dram_ptr, kElemBytes * op->x_size);
      sram_ptr += op->x_size;
      memset(sram_ptr, 0, kElemBytes * op->x_pad_1);
      sram_ptr += op->x_pad_1;
      dram_ptr += kElemBytes * op->x_stride;
    }
    memset(sram_ptr, 0, kElemBytes * xtotal * op->y_pad_1);
  }

  // This is for load 8bits to ACC only
  void Load_int8(const VTAMemInsn* op,
            DRAM* dram,
            uint64_t* load_counter,
            bool skip_exec) {
    //printf("\n SIM_DRIVER.CC: Load_int8() to ACC only \n"); // (printf) ADDED
    CHECK_EQ(kBits, VTA_ACC_WIDTH);

    // TODO(zhanghao): extend to other width
    CHECK_EQ(VTA_ACC_WIDTH, 32);
    CHECK_EQ(VTA_INP_WIDTH, 8);

    int factor = VTA_ACC_WIDTH / VTA_INP_WIDTH;
    load_counter[0] += (op->x_size * op->y_size) * kElemBytes;
    if (skip_exec) return;
    DType* sram_ptr = data_ + op->sram_base;
    int8_t* dram_ptr = static_cast<int8_t*>(dram->GetAddr(
        op->dram_base * kElemBytes / factor));
    uint64_t xtotal = op->x_size + op->x_pad_0 + op->x_pad_1;
    uint32_t ytotal = op->y_size + op->y_pad_0 + op->y_pad_1;
    uint64_t sram_end = op->sram_base + xtotal * ytotal;
    CHECK_LE(sram_end, kMaxNumElem);
    memset(sram_ptr, 0, kElemBytes * xtotal * op->y_pad_0);
    sram_ptr += xtotal * op->y_pad_0;

    for (uint32_t y = 0; y < op->y_size; ++y) {
      memset(sram_ptr, 0, kElemBytes * op->x_pad_0);
      sram_ptr += op->x_pad_0;

      int32_t* sram_ele_ptr = (int32_t*)sram_ptr;
      for (uint32_t x = 0; x < op->x_size * VTA_BATCH * VTA_BLOCK_OUT; ++x) {
        *(sram_ele_ptr + x) = (int32_t)*(dram_ptr + x);
      }
      sram_ptr += op->x_size;

      memset(sram_ptr, 0, kElemBytes * op->x_pad_1);
      sram_ptr += op->x_pad_1;

      // dram one element is 1 bytes rather than 4 bytes
      dram_ptr += kElemBytes / factor * op->x_stride;
    }
    memset(sram_ptr, 0, kElemBytes * xtotal * op->y_pad_1);
  }


  // Execute the store instruction on this SRAM apply trucation.
  // This relies on the elements is 32 bits
  template<int target_bits>
  void TruncStore(const VTAMemInsn* op, DRAM* dram) {
    //printf("\n SIM_DRIVER.CC: TruncStore() \n"); // (printf) ADDED
    CHECK_EQ(op->x_pad_0, 0);
    CHECK_EQ(op->x_pad_1, 0);
    CHECK_EQ(op->y_pad_0, 0);
    CHECK_EQ(op->y_pad_1, 0);
    int target_width = (target_bits * kLane + 7) / 8;
    BitPacker<kBits> src(data_ + op->sram_base);
    BitPacker<target_bits> dst(dram->GetAddr(op->dram_base * target_width));
    for (uint32_t y = 0; y < op->y_size; ++y) {
      for (uint32_t x = 0; x < op->x_size; ++x) {
        uint32_t sram_base = y * op->x_size + x;
        uint32_t dram_base = y * op->x_stride + x;
        for (int i = 0; i < kLane; ++i) {
          dst.SetSigned(dram_base * kLane + i,
                        src.GetSigned(sram_base * kLane +i));
        }
      }
    }
  }

 private:
  /*! \brief internal data content */
  DType* data_;
};


/*!
 * \brief Memory information of special memory region.
 *  Use MemoryInfo as its container type
 */
class Profiler {
 public:
  /*! \brief The memory load statistics */
  uint64_t inp_load_nbytes{0};
  /*! \brief The memory load statistics */
  uint64_t wgt_load_nbytes{0};
  /*! \brief The ACC memory load statistics */
  uint64_t acc_load_nbytes{0};
  /*! \brief The ACC memory load statistics */
  uint64_t uop_load_nbytes{0};
  /*! \brief The ACC memory load statistics */
  uint64_t out_store_nbytes{0};
  /*! \brief instr counter for gemm */
  uint64_t gemm_counter{0};
  /*! \brief instr counter for ALU ops */
  uint64_t alu_counter{0};
  /*! \brief set debug mode */
  int64_t debug_flag{0};
  /*! \brief clear the profiler */
  void Clear() {
    inp_load_nbytes = 0;
    wgt_load_nbytes = 0;
    acc_load_nbytes = 0;
    uop_load_nbytes = 0;
    out_store_nbytes = 0;
    gemm_counter = 0;
    alu_counter = 0;
  }
  /*! \return Whether we should skip execution. */
  bool SkipExec() const {
    //printf("\n SIM_DRIVER.CC: SkipExec() \n"); // (printf) ADDED
    return (debug_flag & DebugFlagMask::kSkipExec) != 0;
  }

  std::string AsJSON() {
    std::ostringstream os;
    os << "{\n"
       << " \"inp_load_nbytes\":" << inp_load_nbytes << ",\n"
       << " \"wgt_load_nbytes\":" << wgt_load_nbytes << ",\n"
       << " \"acc_load_nbytes\":" << acc_load_nbytes << ",\n"
       << " \"uop_load_nbytes\":" << uop_load_nbytes << ",\n"
       << " \"out_store_nbytes\":" << out_store_nbytes << ",\n"
       << " \"gemm_counter\":" << gemm_counter << ",\n"
       << " \"alu_counter\":" << alu_counter << "\n"
       <<"}\n";
    return os.str();
  }

  static Profiler* ThreadLocal() {
    //printf("\n SIM_DRIVER.CC: Profiler* ThreadLocal() \n"); // (printf) ADDED
    static thread_local Profiler inst;
    //printf("Return inst: %p \n", &inst); // (printf) ADDED
    return &inst;
  }
};


// Simulate device
// TODO(tqchen,thierry): queue based event driven simulation.
class Device {
 public:
  Device() {
    //printf("\n SIM_DRIVER.CC: Device() \n"); // (printf) ADDED
    prof_ = Profiler::ThreadLocal();
    dram_ = DRAM::Global();
    ptlpp = TlppVerify::Global();
    //printf("prof: %p \t dram: %p \t ptlpp: %p \n", prof_, dram_, ptlpp); // (printf) ADDED
  }

  int Run(vta_phy_addr_t insn_phy_addr,
          uint32_t insn_count,
          uint32_t wait_cycles) {
    //printf("\n SIM_DRIVER.CC: Device.Run(insn_phy_addr = %u, insn_count = %u, wait_cycles = %u) \n", insn_phy_addr, insn_count, wait_cycles); // (printf) ADDED
    VTAGenericInsn* insn = static_cast<VTAGenericInsn*>(
        dram_->GetAddr(insn_phy_addr));
    finish_counter_ = 0;
    for (uint32_t i = 0; i < insn_count; ++i) {
      printf("\nDEBUG Run: address insn (I%u) = %p",i, (insn+i)); //(printf) ADDED
      printf("\nDEBUG Run: insn->opcode = %u \n (0 = LOAD, \t 1 = STORE, \t 2 = GEMM, \t 3 = FINISH, \t 4 = ALU)\n",(insn+i)->opcode); //(printf) ADDED
      this->Run(insn + i); // Enqueue the instructions
    }
    this->TlppSynchronization(); // Start the execution

    // /* ADDED SECTION */
    // FILE * pFileDram; // ADDED
    // uint64_t dram_base = 0x00000020; // ADDED
    // uint8_t* dram_ptr = static_cast<uint8_t*>(dram_->GetAddr(dram_base * 256));
    // pFileDram = fopen("/home/afauregi/Documents/OUTPUT/dump_dram.bin", "wb"); // ADDED
    // printf("\nDEBUG: DUMP DRAM: size=%lu \n\t DRAM = %p \n\n", sizeof(dram_), dram_); // (printf) ADDED
    // fwrite(dram_ptr, 256, 1, pFileDram); // ADDED (ptr, size, count, stream)
    // fclose(pFileDram); // ADDED
    // /* END OF THE ADDED SECTION*/

    return 0;
  }

 private:
  static void Run_Insn(const VTAGenericInsn* insn, void * dev) {
    //printf("\n SIM_DRIVER.CC: (private) Device.Run_Insn(insn = %p, dev = %p) \n", insn, dev); // (printf) ADDED
    Device * device = reinterpret_cast<Device *> (dev);
    const VTAMemInsn* mem = reinterpret_cast<const VTAMemInsn*>(insn);
    const VTAGemInsn* gem = reinterpret_cast<const VTAGemInsn*>(insn);
    const VTAAluInsn* alu = reinterpret_cast<const VTAAluInsn*>(insn);
    switch (mem->opcode) {
      case VTA_OPCODE_LOAD: device->RunLoad(mem); break;
      case VTA_OPCODE_STORE: device->RunStore(mem); break;
      case VTA_OPCODE_GEMM: device->RunGEMM(gem); break;
      case VTA_OPCODE_ALU: device->RunALU(alu); break;
      case VTA_OPCODE_FINISH: ++(device->finish_counter_); break;
      default: {
        LOG(FATAL) << "Unknown op_code" << mem->opcode;
      }
    }
  }

 private:
  void Run(const VTAGenericInsn* insn) {
    //printf("\n SIM_DRIVER.CC: (private) Device.Run(insn = %p) \n", insn); // (printf) ADDED
    ptlpp->TlppPushInsn(insn);
  }

  void TlppSynchronization(void) {
    //printf("\n SIM_DRIVER.CC: (private) Device.TlppSynchronization() \n"); // (printf) ADDED
    ptlpp->TlppSynchronization(Run_Insn, reinterpret_cast<void *> (this));
  }

  void RunLoad(const VTAMemInsn* op) {
    //printf("\n SIM_DRIVER.CC: (private) Device.RunLoad(op = %p) \n", op); // (printf) ADDED
    if (op->x_size == 0) return;
    if (op->memory_type == VTA_MEM_ID_INP) {
      inp_.Load(op, dram_, &(prof_->inp_load_nbytes), prof_->SkipExec());

      /* ADDED SECTION TO PRINT THE INPUT */
      #if DUMP_MEM==true
        // FWRITE to write the binary content in a file
        FILE * pFileInp; // ADDED
        printf("\nINP op->x_size: \t %u \t op->y_size: \t %u \t => Element to load = %u (%d-Byte element) \n\n", op->x_size, op->y_size, 16 * op->x_size * op->y_size, VTA_INP_WIDTH/8); // (printf) ADDED
        pFileInp = fopen("/home/afauregi/Documents/OUTPUT/dump_inp.bin", "ab"); // ADDED
        fwrite(inp_.BeginPtr(0), VTA_INP_WIDTH/8, 16*(op->x_size * op->y_size), pFileInp); // ADDED (ptr, size, count, stream)
        fclose(pFileInp); // ADDED
      #endif
      /* END OF ADDED SECTION */

    } else if (op->memory_type == VTA_MEM_ID_WGT) {
      wgt_.Load(op, dram_, &(prof_->wgt_load_nbytes), prof_->SkipExec());

      /* ADDED SECTION TO PRINT THE WEIGHT */
      #if DUMP_MEM==true
        // FWRITE to write the binary content in a file
        FILE * pFileWgt; // ADDED
        printf("\nWGT op->x_size: \t %u \t op->y_size: \t %u \t => Element to load = %u (%d-Byte element) \n\n", op->x_size, op->y_size, 256 * op->x_size * op->y_size, VTA_WGT_WIDTH/8); // ADDED
        pFileWgt = fopen("/home/afauregi/Documents/OUTPUT/dump_wgt.bin", "ab"); // ADDED
        fwrite(wgt_.BeginPtr(0), VTA_WGT_WIDTH/8, 256*(op->x_size * op->y_size), pFileWgt); // ADDED (ptr, size, count, stream)
        fclose(pFileWgt); // ADDED
      #endif
      /* END OF ADDED SECTION */

    } else if (op->memory_type == VTA_MEM_ID_ACC) {
      acc_.Load(op, dram_, &(prof_->acc_load_nbytes), prof_->SkipExec());
    } else if (op->memory_type == VTA_MEM_ID_UOP) {
      // always load in uop, since uop is stateful
      // subsequent non-debug mode exec can depend on it.
      uop_.Load(op, dram_, &(prof_->uop_load_nbytes), false);

      /* ADDED SECTION TO PRINT THE UOP */
      #if DUMP_MEM==true
        // FWRITE to write the binary content in a file
        FILE * pFileUop; // ADDED
        printf("\nUOP op->x_size: \t %u \t op->y_size: \t %u \t => Element to load = %u (%d-Byte element) \n\n", op->x_size, op->y_size, op->x_size * op->y_size, VTA_UOP_WIDTH/8); // (printf) ADDED
        pFileUop = fopen("/home/afauregi/Documents/OUTPUT/dump_uop.bin", "ab"); // ADDED
        fwrite(uop_.BeginPtr(0), sizeof(VTAUop), op->x_size * op->y_size, pFileUop); // ADDED (VTA_UOP_WIDTH/8)
        fclose(pFileUop); // ADDED
      #endif
      /* END OF ADDED SECTION */

    } else if (op->memory_type == VTA_MEM_ID_ACC_8BIT) {
      printf("\nWARNING: LOAD_INT8 executed => memory not dumped!\n\n"); // (printf) ADDED
      acc_.Load_int8(op, dram_, &(prof_->acc_load_nbytes), prof_->SkipExec());
    } else {
      LOG(FATAL) << "Unknown memory_type=" << op->memory_type;
    }
  }

  void RunStore(const VTAMemInsn* op) {
    //printf("\n SIM_DRIVER.CC: (private) Device.RunStore(op = %p) \n", op); // (printf) ADDED
    if (op->x_size == 0) return;
    if (op->memory_type == VTA_MEM_ID_OUT) {
      prof_->out_store_nbytes += (
          op->x_size * op->y_size * VTA_BATCH * VTA_BLOCK_OUT * VTA_OUT_WIDTH / 8);
      if (!prof_->SkipExec()) {
        acc_.TruncStore<VTA_OUT_WIDTH>(op, dram_);
      }

      /* ADDED SECTION TO PRINT THE ACCUMULATOR (before Truncation) */ 
      #if DUMP_MEM==true
        // => TEMPO, try to dump in 1 Byte (acc_.TruncStore<VTA_OUT_WIDTH>)
        // FWRITE to write the binary content in a file
        FILE * pFileAcc; // ADDED
        printf("\nACC op->x_size: \t %u \t op->y_size: \t %u \t => Element to load = %u (%d-Byte element) \n\n", op->x_size, op->y_size, 16 * op->x_size * op->y_size, VTA_ACC_WIDTH/8); // (printf) ADDED
        pFileAcc = fopen("/home/afauregi/Documents/OUTPUT/dump_acc.bin", "ab"); // ADDED
        fwrite(acc_.BeginPtr(0), VTA_ACC_WIDTH/8, 16*(op->x_size * op->y_size), pFileAcc); // ADDED (ptr, size, count, stream)
        fclose(pFileAcc); // ADDED
      #endif
      /* END OF ADDED SECTION */

      /* ADDED SECTION TO PRINT THE OUTPUT */ 
      #if DUMP_MEM==true
        // FWRITE to write the binary content in a file
        FILE * pFileOut; // ADDED
        printf("\nOUT op->x_size: \t %u \t op->y_size: \t %u \t => Element to load = %u (%d-Byte element) \n\n", op->x_size, op->y_size, 16 * op->x_size * op->y_size, VTA_OUT_WIDTH/8); // (printf) ADDED
        pFileOut = fopen("/home/afauregi/Documents/OUTPUT/dump_out.bin", "ab"); // ADDED
        //fwrite(dram_, VTA_OUT_WIDTH/8, 16*(op->x_size * op->y_size), pFileOut); // ADDED (ptr, size, count, stream) // Size=VTA_OUT_WIDTH/8
        fwrite(dram_, 1, sizeof(dram_), pFileOut); // ADDED (ptr, size, count, stream) // Size=VTA_OUT_WIDTH/8
        fclose(pFileOut); // ADDED
      #endif
      /* END OF ADDED SECTION */

    } else {
      LOG(FATAL) << "Store do not support memory_type="
                 << op->memory_type;
    }
  }

  void RunGEMM(const VTAGemInsn* op) {
    //printf("\n SIM_DRIVER.CC: (private) Device.RunGEMM(op = %p) \n", op); // (printf) ADDED
    //printf("\nDEBUG RunGemm: op->reset_reg = %u (0 = no reset, 1+ = reset)\n", op->reset_reg); // (printf) ADDED
    if (!op->reset_reg) {
      //printf("\nDEBUG RunGemm: NO RESET!\n");
      prof_->gemm_counter += op->iter_out * op->iter_in * (op->uop_end - op->uop_bgn);
      if (prof_->SkipExec()) return;
      for (uint32_t y = 0; y < op->iter_out; ++y) {
        for (uint32_t x = 0; x < op->iter_in; ++x) {
          for (uint32_t uindex = op->uop_bgn; uindex < op->uop_end; ++uindex) {
            VTAUop* uop_ptr = static_cast<VTAUop*>(uop_.BeginPtr(uindex));
            // Read in memory indices
            uint32_t acc_idx = uop_ptr->dst_idx;
            uint32_t inp_idx = uop_ptr->src_idx;
            uint32_t wgt_idx = uop_ptr->wgt_idx;
            //printf("\nDEBUG RunGEMM: (UOP VALUE)\n\t acc_idx = %u \t inp_idx = %u \t wgt_inp = %u \n", acc_idx, inp_idx, wgt_idx); // (printf) ADDED

            acc_idx += y * op->dst_factor_out + x * op->dst_factor_in;
            inp_idx += y * op->src_factor_out + x * op->src_factor_in;
            wgt_idx += y * op->wgt_factor_out + x * op->wgt_factor_in;
            //printf("\nDEBUG RunGEMM: (INSTRUCTION)\n\t LP = (%u, %u) \t acc_factor = (%u, %u) \t src_factor = (%u, %u) \t wgt_factor = (%u, %u) \n", op->iter_out, op->iter_in, op->dst_factor_out, op->dst_factor_in, op->src_factor_out, op->src_factor_in, op->wgt_factor_out, op->wgt_factor_in); // (printf) ADDED
            //printf("\nDEBUG RunGEMM: (CURRENT IDX)\n\t acc_idx = %u \t inp_idx = %u \t wgt_inp = %u \n", acc_idx, inp_idx, wgt_idx); // (printf) ADDED

            BitPacker<VTA_ACC_WIDTH> acc(acc_.BeginPtr(acc_idx));
            BitPacker<VTA_INP_WIDTH> inp(inp_.BeginPtr(inp_idx));
            BitPacker<VTA_WGT_WIDTH> wgt(wgt_.BeginPtr(wgt_idx));

            // gemm loop
            printf("\nDEBUG GeMM operation: lp_0=%d, lp_1=%d, uop_idx=%d \n\t acc_idx=%d, inp_idx=%d, wgt_idx=%d\n", y, x, uindex, acc_idx, inp_idx, wgt_idx); // (printf) ADDED
            //printf("\nDEBUG RunGEMM: (GeMM loop ACC)\n"); // (printf) ADDED
            for (uint32_t i = 0; i < VTA_BATCH; ++i) {
              for (uint32_t j = 0; j < VTA_BLOCK_OUT; ++j) {
                uint32_t acc_offset = i * VTA_BLOCK_OUT + j;
                int32_t sum = acc.GetSigned(acc_offset);
                for (uint32_t k = 0; k < VTA_BLOCK_IN; ++k) {
                  sum +=
                      inp.GetSigned(i * VTA_BLOCK_IN + k) *
                      wgt.GetSigned(j * VTA_BLOCK_IN + k);
                }
                acc.SetSigned(acc_offset, sum);
                //printf("\t %d", sum); // (printf) ADDED
              }
              //printf("\n"); //(printf) ADDED
            }
          }
        }
      }
    } else {
      if (prof_->SkipExec()) return;
      // reset
      for (uint32_t y = 0; y < op->iter_out; ++y) {
        for (uint32_t x = 0; x < op->iter_in; ++x) {
          for (uint32_t uindex = op->uop_bgn; uindex < op->uop_end; ++uindex) {
            VTAUop* uop_ptr = static_cast<VTAUop*>(uop_.BeginPtr(uindex));
            uint32_t acc_idx = uop_ptr->dst_idx;
            acc_idx += y * op->dst_factor_out + x * op->dst_factor_in;
            BitPacker<VTA_ACC_WIDTH> acc(acc_.BeginPtr(acc_idx));
            //printf("\nDEBUG RunGEMM: (UOP reset VALUE)\n\t acc_idx = %u \n", acc_idx); // (printf) ADDED
            for (uint32_t i = 0; i < VTA_BATCH * VTA_BLOCK_OUT; ++i) {
              acc.SetSigned(i, 0);
            }
          }
        }
      }
    }
  }

  void RunALU(const VTAAluInsn* op) {
    //printf("\n SIM_DRIVER.CC: (private) Device.RunALU(op = %p) \n", op); // (printf) ADDED
    if (op->use_imm) {
      RunALU_<true>(op);
    } else {
      RunALU_<false>(op);
    }
  }

  template<bool use_imm>
  void RunALU_(const VTAAluInsn* op) {
    //printf("\n SIM_DRIVER.CC: (template use_imm) Device.RunALU(op = %p) \n", op); // (printf) ADDED
    switch (op->alu_opcode) {
      case VTA_ALU_OPCODE_ADD: {
        return RunALULoop<use_imm>(op, [](int32_t x, int32_t y) {
            return x + y;
          });
      }
      case VTA_ALU_OPCODE_MAX: {
        return RunALULoop<use_imm>(op, [](int32_t x, int32_t y) {
            return std::max(x, y);
          });
      }
      case VTA_ALU_OPCODE_MIN: {
        return RunALULoop<use_imm>(op, [](int32_t x, int32_t y) {
            return std::min(x, y);
          });
      }
      case VTA_ALU_OPCODE_SHR: {
        return RunALULoop<use_imm>(op, [](int32_t x, int32_t y) {
            if (y >= 0) {
              return x >> y;
            } else {
              return x << (-y);
            }
          });
      }
      case VTA_ALU_OPCODE_MUL: {
        return RunALULoop<use_imm>(op, [](int32_t x, int32_t y) {
            return x * y;
          });
      }
      default: {
        LOG(FATAL) << "Unknown ALU code " << op->alu_opcode;
      }
    }
  }

  template<bool use_imm, typename F>
  void RunALULoop(const VTAAluInsn* op, F func) {
    //printf("\n SIM_DRIVER.CC: (template use_imm + func) Device.RunALULoop(op = %p, func = ?) \n", op); // (printf) ADDED
    prof_->alu_counter += op->iter_out * op->iter_in * (op->uop_end - op->uop_bgn);
    if (prof_->SkipExec()) return;
    for (int y = 0; y < op->iter_out; ++y) {
      for (int x = 0; x < op->iter_in; ++x) {
        for (int k = op->uop_bgn; k < op->uop_end; ++k) {
          // Read micro op
          VTAUop* uop_ptr = static_cast<VTAUop*>(uop_.BeginPtr(k));
          uint32_t dst_index = uop_ptr->dst_idx;
          uint32_t src_index = uop_ptr->src_idx;
          dst_index += y * op->dst_factor_out + x * op->dst_factor_in;
          src_index += y * op->src_factor_out + x * op->src_factor_in;
          BitPacker<VTA_ACC_WIDTH> dst(acc_.BeginPtr(dst_index));
          BitPacker<VTA_ACC_WIDTH> src(acc_.BeginPtr(src_index));
          for (int k = 0; k < VTA_BATCH * VTA_BLOCK_OUT; ++k) {
            if (use_imm) {
              dst.SetSigned(k, func(dst.GetSigned(k), op->imm));
            } else {
              dst.SetSigned(k, func(dst.GetSigned(k), src.GetSigned(k)));
            }
          }
        }
      }
    }
  }
  // the finish counter
  int finish_counter_{0};
  // Prof_
  Profiler* prof_;
  // The DRAM interface
  DRAM* dram_;
  TlppVerify* ptlpp;
  // The SRAM
  SRAM<VTA_INP_WIDTH, VTA_BATCH * VTA_BLOCK_IN, VTA_INP_BUFF_DEPTH> inp_;
  SRAM<VTA_WGT_WIDTH, VTA_BLOCK_IN * VTA_BLOCK_OUT, VTA_WGT_BUFF_DEPTH> wgt_;
  SRAM<VTA_ACC_WIDTH, VTA_BATCH * VTA_BLOCK_OUT, VTA_ACC_BUFF_DEPTH> acc_;
  SRAM<VTA_UOP_WIDTH, 1, VTA_UOP_BUFF_DEPTH> uop_;
};

using tvm::runtime::TVMRetValue;
using tvm::runtime::TVMArgs;

TVM_REGISTER_GLOBAL("vta.simulator.profiler_clear")
.set_body([](TVMArgs args, TVMRetValue* rv) {
    //printf("\n SIM_DRIVER.CC: TVM_REGISTER_GLOBAL.profiler_clear() \n"); // (printf) ADDED
    Profiler::ThreadLocal()->Clear();
  });
TVM_REGISTER_GLOBAL("vta.simulator.profiler_status")
.set_body([](TVMArgs args, TVMRetValue* rv) {
    //printf("\n SIM_DRIVER.CC: TVM_REGISTER_GLOBAL.profiler_status() \n"); // (printf) ADDED
    *rv = Profiler::ThreadLocal()->AsJSON();
  });
TVM_REGISTER_GLOBAL("vta.simulator.profiler_debug_mode")
.set_body([](TVMArgs args, TVMRetValue* rv) {
    //printf("\n SIM_DRIVER.CC: TVM_REGISTER_GLOBAL.profiler_debug_mode() \n"); // (printf) ADDED
    Profiler::ThreadLocal()->debug_flag = args[0];
  });
}  // namespace sim
}  // namespace vta

void* VTAMemAlloc(size_t size, int cached) {
  void* add_mem = vta::sim::DRAM::Global()->Alloc(size); // ADDED
  //printf("\n SIM_DRIVER.CC: VTAMemAlloc(size = %lu, cached = %d) => MemAlloc = %p \n", size, cached, add_mem); // (printf) ADDED
  return add_mem; //vta::sim::DRAM::Global()->Alloc(size);
}

void VTAMemFree(void* buf) {
  //printf("\n SIM_DRIVER.CC: VTAMemFree(buf = %p) \n", buf); // (printf) ADDED
  vta::sim::DRAM::Global()->Free(buf);
}

vta_phy_addr_t VTAMemGetPhyAddr(void* buf) {
  vta_phy_addr_t vta_phy_addr = vta::sim::DRAM::Global()->GetPhyAddr(buf); // ADDED
  //printf("\n SIM_DRIVER.CC: VTAMemGetPhyAddr(buf = %p) => add = %u \n", buf, vta_phy_addr); // (printf) ADDED
  return vta_phy_addr; //vta::sim::DRAM::Global()->GetPhyAddr(buf);
}

void VTAMemCopyFromHost(void* dst, const void* src, size_t size) {
  //printf("\n SIM_DRIVER.CC: VTAMemCopyFromHost(dst = %p, src = %p, size = %lu) \n", dst, src, size); // (printf) ADDED
  memcpy(dst, src, size);
}

void VTAMemCopyToHost(void* dst, const void* src, size_t size) {
  //printf("\n SIM_DRIVER.CC: VTAMemCopyToHost(dst = %p, src = %p, size = %lu) \n", dst, src, size); // (printf) ADDED
  memcpy(dst, src, size);
}

void VTAFlushCache(void* vir_addr, vta_phy_addr_t phy_addr, int size) {
  //printf("\n SIM_DRIVER.CC: VTAFlushCache() - DO NOTHING \n"); // (printf) ADDED
}

void VTAInvalidateCache(void* vir_addr, vta_phy_addr_t phy_addr, int size) {
  //printf("\n SIM_DRIVER.CC: VTAInvalidateCache() - DO NOTHING \n"); // (printf) ADDED
}

VTADeviceHandle VTADeviceAlloc() {
  VTADeviceHandle handle = new vta::sim::Device(); // ADDED
  //printf("\n SIM_DRIVER.CC: VTADeviceAlloc() => handle = %p \n", handle); // (printf) ADDED
  return handle; //new vta::sim::Device();
}

void VTADeviceFree(VTADeviceHandle handle) {
  //printf("\n SIM_DRIVER.CC: VTADeviceFree(VTADeviceHandle = %p) \n", handle); // (printf) ADDED
  delete static_cast<vta::sim::Device*>(handle);
}

int VTADeviceRun(VTADeviceHandle handle,
                 vta_phy_addr_t insn_phy_addr,
                 uint32_t insn_count,
                 uint32_t wait_cycles) {
  //printf("\n SIM_DRIVER.CC: VTADeviceRun(VTADeviceHandle = %p, insn_phy_addr = %u, insn_count = %u, wait_cycles = %u) \n", handle, insn_phy_addr, insn_count, wait_cycles); // (printf) ADDED
  return static_cast<vta::sim::Device*>(handle)->Run(
      insn_phy_addr, insn_count, wait_cycles);
}

void VTAProgram(const char* bitstream) {
  //printf("\n SIM_DRIVER.CC: VTAProgram() - DO NOTHING \n"); // (printf) ADDED
}

/* ADDED FUNCTION */
int CheckTestDriver(int value){ // ADDED
  printf("CheckTestDriver() successfully tested! \n\r"); // ADDED
  return value + 1; // ADDED
} // ADDED
/* END ADDED FUNCTION */

