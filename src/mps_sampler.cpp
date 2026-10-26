#include "cq/mps_sampler.hpp"
#include <chrono>
#include <cmath>
#include <iostream>
#include <random>

namespace cq {

std::map<std::string, uint32_t> FastMPSSampler::sample_counts(
    const cq_hecs::core::MPSSimulator& mps,
    uint32_t num_shots,
    uint64_t seed
) {
    // The canonical-GHZ fast path lives in MPSSimulator::sample_counts and is
    // selected only after an exact tensor check. Every other state is sampled
    // with right-environment conditional probabilities, so a state that merely
    // has bond dimension two is never assumed to be GHZ.
    return mps.sample_counts(num_shots, seed);
}

double FastMPSSampler::benchmark_1m_shots(
    const cq_hecs::core::MPSSimulator& mps,
    uint32_t num_shots,
    uint64_t seed
) {
    auto start = std::chrono::high_resolution_clock::now();
    auto counts = sample_counts(mps, num_shots, seed);
    auto end = std::chrono::high_resolution_clock::now();

    double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
    return elapsed_ms;
}

} // namespace cq
