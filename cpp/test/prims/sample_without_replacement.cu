/*
 * Copyright (c) 2019, NVIDIA CORPORATION.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include <gtest/gtest.h>
#include "random/rng.h"
#include "test_utils.h"

namespace MLCommon {
namespace Random {

// Terminology:
// SWoR - Sample Without Replacement

template <typename T>
struct SWoRInputs {
  int len, sampledLen;
  GeneratorType gtype;
  unsigned long long int seed;
};

template <typename T>
::std::ostream& operator<<(::std::ostream& os, const SWoRInputs<T>& dims) {
  return os;
}

template <typename T>
class SWoRTest : public ::testing::TestWithParam<SWoRInputs<T>> {
 protected:
  void SetUp() override {
    params = ::testing::TestWithParam<SWoRInputs<T>>::GetParam();
    CUDA_CHECK(cudaStreamCreate(&stream));
    allocator.reset(new defaultDeviceAllocator);
    Rng r(params.seed, params.gtype);
    allocate(in, params.len);
    allocate(out, params.sampledLen);
    allocate(outIdx, params.sampledLen);
    h_outIdx.resize(params.sampledLen);
    rng.sampledWithoutReplacement(out, outIdx, in, wts, params.sampledLen,
                                  params.len, allocator, stream);
    updateHost(&(h_outIdx[0]), outIdx, stream);
  }

  void TearDown() override {
    CUDA_CHECK(cudaStreamDestroy(stream));
    CUDA_CHECK(cudaFree(in));
    CUDA_CHECK(cudaFree(out));
    CUDA_CHECK(cudaFree(outIdx));
  }

 protected:
  SWoRInputs<T> params;
  T *in, *out;
  int* outIdx;
  std::vector<int> h_outIdx;
  cudaStream_t stream;
  std::shared_ptr<deviceAllocator> allocator;
};

///@todo: come up with a way to test the sampling distribution itself

typedef SWoRTest<float> SWoRTestF;
const std::vector<SWoRInputs<float>> inputsf = {
  {1024, 512, GenPhilox, 1234ULL},
  {1024, 1024, GenPhilox, 1234ULL},
  {1024, 512 + 1, GenPhilox, 1234ULL},
  {1024, 1024 + 1, GenPhilox, 1234ULL},
  {1024, 512 + 2, GenPhilox, 1234ULL},
  {1024, 1024 + 2, GenPhilox, 1234ULL},
  {1024 + 1, 512, GenPhilox, 1234ULL},
  {1024 + 1, 1024, GenPhilox, 1234ULL},
  {1024 + 1, 512 + 1, GenPhilox, 1234ULL},
  {1024 + 1, 1024 + 1, GenPhilox, 1234ULL},
  {1024 + 1, 512 + 2, GenPhilox, 1234ULL},
  {1024 + 1, 1024 + 2, GenPhilox, 1234ULL},
  {1024 + 2, 512, GenPhilox, 1234ULL},
  {1024 + 2, 1024, GenPhilox, 1234ULL},
  {1024 + 2, 512 + 1, GenPhilox, 1234ULL},
  {1024 + 2, 1024 + 1, GenPhilox, 1234ULL},
  {1024 + 2, 512 + 2, GenPhilox, 1234ULL},
  {1024 + 2, 1024 + 2, GenPhilox, 1234ULL},

  {1024, 512, GenTaps, 1234ULL},
  {1024, 1024, GenTaps, 1234ULL},
  {1024, 512 + 1, GenTaps, 1234ULL},
  {1024, 1024 + 1, GenTaps, 1234ULL},
  {1024, 512 + 2, GenTaps, 1234ULL},
  {1024, 1024 + 2, GenTaps, 1234ULL},
  {1024 + 1, 512, GenTaps, 1234ULL},
  {1024 + 1, 1024, GenTaps, 1234ULL},
  {1024 + 1, 512 + 1, GenTaps, 1234ULL},
  {1024 + 1, 1024 + 1, GenTaps, 1234ULL},
  {1024 + 1, 512 + 2, GenTaps, 1234ULL},
  {1024 + 1, 1024 + 2, GenTaps, 1234ULL},
  {1024 + 2, 512, GenTaps, 1234ULL},
  {1024 + 2, 1024, GenTaps, 1234ULL},
  {1024 + 2, 512 + 1, GenTaps, 1234ULL},
  {1024 + 2, 1024 + 1, GenTaps, 1234ULL},
  {1024 + 2, 512 + 2, GenTaps, 1234ULL},
  {1024 + 2, 1024 + 2, GenTaps, 1234ULL},

  {1024, 512, GenKiss99, 1234ULL},
  {1024, 1024, GenKiss99, 1234ULL},
  {1024, 512 + 1, GenKiss99, 1234ULL},
  {1024, 1024 + 1, GenKiss99, 1234ULL},
  {1024, 512 + 2, GenKiss99, 1234ULL},
  {1024, 1024 + 2, GenKiss99, 1234ULL},
  {1024 + 1, 512, GenKiss99, 1234ULL},
  {1024 + 1, 1024, GenKiss99, 1234ULL},
  {1024 + 1, 512 + 1, GenKiss99, 1234ULL},
  {1024 + 1, 1024 + 1, GenKiss99, 1234ULL},
  {1024 + 1, 512 + 2, GenKiss99, 1234ULL},
  {1024 + 1, 1024 + 2, GenKiss99, 1234ULL},
  {1024 + 2, 512, GenKiss99, 1234ULL},
  {1024 + 2, 1024, GenKiss99, 1234ULL},
  {1024 + 2, 512 + 1, GenKiss99, 1234ULL},
  {1024 + 2, 1024 + 1, GenKiss99, 1234ULL},
  {1024 + 2, 512 + 2, GenKiss99, 1234ULL},
  {1024 + 2, 1024 + 2, GenKiss99, 1234ULL}};

TEST_P(SWoRTestF, Result) {
  // indices must be in the given range
  for (int i = 0; i < params.sampledLen; ++i) {
    auto val = h_outIdx[i];
    ASSERT_TRUE(0 <= val && val < params.len)
      << "out-of-range index @i=" << i << " val=" << val
      << " sampledLen=" << sampledLen;
  }
  // indices should not repeat
  std::set<int> occurence;
  for (int i = 0; i < params.sampledLen; ++i) {
    ASSERT_TRUE(occurence.find(val) == occurence.end())
      << "repeated index @i=" << i << " idx=" << val;
    occurence.insert(val);
  }
}
INSTANTIATE_TEST_CASE_P(SWoRTests, SWoRTestF, ::testing::ValuesIn(inputsf));

typedef SWoRTest<double> SWoRTestD;
const std::vector<SWoRInputs<double>> inputsd = {
  {1024, 512, GenPhilox, 1234ULL},
  {1024, 1024, GenPhilox, 1234ULL},
  {1024, 512 + 1, GenPhilox, 1234ULL},
  {1024, 1024 + 1, GenPhilox, 1234ULL},
  {1024, 512 + 2, GenPhilox, 1234ULL},
  {1024, 1024 + 2, GenPhilox, 1234ULL},
  {1024 + 1, 512, GenPhilox, 1234ULL},
  {1024 + 1, 1024, GenPhilox, 1234ULL},
  {1024 + 1, 512 + 1, GenPhilox, 1234ULL},
  {1024 + 1, 1024 + 1, GenPhilox, 1234ULL},
  {1024 + 1, 512 + 2, GenPhilox, 1234ULL},
  {1024 + 1, 1024 + 2, GenPhilox, 1234ULL},
  {1024 + 2, 512, GenPhilox, 1234ULL},
  {1024 + 2, 1024, GenPhilox, 1234ULL},
  {1024 + 2, 512 + 1, GenPhilox, 1234ULL},
  {1024 + 2, 1024 + 1, GenPhilox, 1234ULL},
  {1024 + 2, 512 + 2, GenPhilox, 1234ULL},
  {1024 + 2, 1024 + 2, GenPhilox, 1234ULL},

  {1024, 512, GenTaps, 1234ULL},
  {1024, 1024, GenTaps, 1234ULL},
  {1024, 512 + 1, GenTaps, 1234ULL},
  {1024, 1024 + 1, GenTaps, 1234ULL},
  {1024, 512 + 2, GenTaps, 1234ULL},
  {1024, 1024 + 2, GenTaps, 1234ULL},
  {1024 + 1, 512, GenTaps, 1234ULL},
  {1024 + 1, 1024, GenTaps, 1234ULL},
  {1024 + 1, 512 + 1, GenTaps, 1234ULL},
  {1024 + 1, 1024 + 1, GenTaps, 1234ULL},
  {1024 + 1, 512 + 2, GenTaps, 1234ULL},
  {1024 + 1, 1024 + 2, GenTaps, 1234ULL},
  {1024 + 2, 512, GenTaps, 1234ULL},
  {1024 + 2, 1024, GenTaps, 1234ULL},
  {1024 + 2, 512 + 1, GenTaps, 1234ULL},
  {1024 + 2, 1024 + 1, GenTaps, 1234ULL},
  {1024 + 2, 512 + 2, GenTaps, 1234ULL},
  {1024 + 2, 1024 + 2, GenTaps, 1234ULL},

  {1024, 512, GenKiss99, 1234ULL},
  {1024, 1024, GenKiss99, 1234ULL},
  {1024, 512 + 1, GenKiss99, 1234ULL},
  {1024, 1024 + 1, GenKiss99, 1234ULL},
  {1024, 512 + 2, GenKiss99, 1234ULL},
  {1024, 1024 + 2, GenKiss99, 1234ULL},
  {1024 + 1, 512, GenKiss99, 1234ULL},
  {1024 + 1, 1024, GenKiss99, 1234ULL},
  {1024 + 1, 512 + 1, GenKiss99, 1234ULL},
  {1024 + 1, 1024 + 1, GenKiss99, 1234ULL},
  {1024 + 1, 512 + 2, GenKiss99, 1234ULL},
  {1024 + 1, 1024 + 2, GenKiss99, 1234ULL},
  {1024 + 2, 512, GenKiss99, 1234ULL},
  {1024 + 2, 1024, GenKiss99, 1234ULL},
  {1024 + 2, 512 + 1, GenKiss99, 1234ULL},
  {1024 + 2, 1024 + 1, GenKiss99, 1234ULL},
  {1024 + 2, 512 + 2, GenKiss99, 1234ULL},
  {1024 + 2, 1024 + 2, GenKiss99, 1234ULL}};

TEST_P(SWoRTestD, Result) {
  // indices must be in the given range
  for (int i = 0; i < params.sampledLen; ++i) {
    auto val = h_outIdx[i];
    ASSERT_TRUE(0 <= val && val < params.len)
      << "out-of-range index @i=" << i << " val=" << val
      << " sampledLen=" << sampledLen;
  }
  // indices should not repeat
  std::set<int> occurence;
  for (int i = 0; i < params.sampledLen; ++i) {
    ASSERT_TRUE(occurence.find(val) == occurence.end())
      << "repeated index @i=" << i << " idx=" << val;
    occurence.insert(val);
  }
}
INSTANTIATE_TEST_CASE_P(SWoRTests, SWoRTestD, ::testing::ValuesIn(inputsd));

}  // end namespace Random
}  // end namespace MLCommon
