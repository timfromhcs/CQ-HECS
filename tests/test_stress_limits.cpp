#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <vector>
#include <chrono>
#include "cq/mps_sampler.hpp"
#include "cq_hecs/core/mps_simulator.hpp"

using namespace cq;
using namespace cq_hecs::core;

void test_300_qubits_deep_entanglement_walk() {
    std::cout << "[STRESS] Running 300-Qubit Deep Entanglement Walk (10,000 Gate Layers)...\n";

    const uint32_t N = 300;
    const uint32_t max_d = 16;
    MPSSimulator mps(N, max_d);

    // Apply 10,000 gate layers
    const uint32_t LAYERS = 10000;
    auto t0 = std::chrono::high_resolution_clock::now();

    for (uint32_t layer = 0; layer < LAYERS; ++layer) {
        uint32_t q = layer % (N - 1);
        // Single-qubit rotation
        mps.apply_h(q);
        // 2-Qubit nearest-neighbor entangler
        mps.apply_cx(q, q + 1);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    // Memory Profiler Verification: Strict ceiling <= 120 MB
    size_t total_bytes = mps.total_memory_bytes();
    double total_mb = static_cast<double>(total_bytes) / (1024.0 * 1024.0);

    std::cout << "  Executed " << (LAYERS * 2) << " gates across 300 qubits in: " << elapsed_ms << " ms\n";
    std::cout << "  Active MPS Memory: " << total_mb << " MB (Contract Ceiling: < 120.0 MB)\n";

    assert(total_mb < 120.0);
    std::cout << ">>> PASS: 300-Qubit deep walk strictly satisfied 120 MB memory governor.\n\n";
}

void test_1m_shots_fast_sampling() {
    std::cout << "[STRESS] Running 1,000,000 Shots Fast MPS Born-Rule Sampling Test...\n";

    const uint32_t N = 300;
    MPSSimulator mps(N, 16);
    mps.prepare_ghz_state();

    const uint32_t SHOTS = 1000000;
    double elapsed_ms = FastMPSSampler::benchmark_1m_shots(mps, SHOTS, 42);

    std::cout << "  1,000,000 Shots Generated in: " << elapsed_ms << " ms\n";
    std::cout << "  Sampling Throughput: " << (static_cast<double>(SHOTS) / (elapsed_ms / 1000.0) / 1e6) << " Mshots/sec\n";

    // Task 3.4 requirement: Sampling time under 200 ms
    assert(elapsed_ms < 200.0);
    std::cout << ">>> PASS: 1,000,000 Shots sampled in " << elapsed_ms << " ms (< 200 ms limit).\n\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Extreme Stress Limits & Fast-Sampling Suite\n";
    std::cout << "=================================================================\n\n";

    test_300_qubits_deep_entanglement_walk();
    test_1m_shots_fast_sampling();

    std::cout << "=================================================================\n";
    std::cout << " ALL EXTREME STRESS TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
