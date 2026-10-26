#include <iostream>
#include <cassert>
#include <chrono>
#include <cmath>

#include "cq_hecs/tensor_network.hpp"
#include "cq_hecs/lattice.hpp"

using namespace cq_hecs;

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS [Deterministic Audit]: GHZ-300 Parity Diagnostic\n";
    std::cout << " Lattice: 6 x 5 x 10 (300 Qubits) | Shots: 50,000 Seeded Samples\n";
    std::cout << "=================================================================\n\n";

    // 1. Initialize Vulkan context and engine
    auto vulkan = std::make_shared<VulkanContext>();
    vulkan->initialize();

    VRTS300Engine engine(vulkan);

    // 2. Construct 300-qubit GHZ state across the 6x5x10 lattice
    std::cout << "[Step 1] Constructing 300-qubit GHZ state across 6x5x10 lattice...\n";
    auto start_time = std::chrono::high_resolution_clock::now();

    engine.construct_ghz300();

    auto construct_time = std::chrono::high_resolution_clock::now();
    std::cout << "         GHZ-300 construction completed in "
              << std::chrono::duration<double, std::milli>(construct_time - start_time).count() << " ms.\n";
    std::cout << "         Entanglement gates recorded: " << engine.get_gate_count() << " (1 H + 299 CNOTs)\n\n";

    // 3. Draw seeded measurement shots from the compact GHZ representation
    const uint32_t NUM_SHOTS = 50000;
    std::cout << "[Step 2] Sampling " << NUM_SHOTS << " shots from the GHZ-300 state...\n";

    auto [non_parity_shots, zero_state_shots] = engine.measure_parity_shots(NUM_SHOTS);
    uint64_t one_state_shots = NUM_SHOTS - zero_state_shots - non_parity_shots;

    auto measure_time = std::chrono::high_resolution_clock::now();
    std::cout << "         Measurement completed in "
              << std::chrono::duration<double, std::milli>(measure_time - construct_time).count() << " ms.\n\n";

    // 4. Assert: perfect correlation rules out non-parity outcomes; the
    //    |0...0>/|1...1> split is binomial, so allow 5 sigma around N/2
    //    (sigma = sqrt(N * 0.5 * 0.5) = sqrt(N)/2).
    const uint64_t expected_half = NUM_SHOTS / 2;
    const double tolerance = 5.0 * std::sqrt(static_cast<double>(NUM_SHOTS) * 0.25);
    const auto deviation = static_cast<double>(zero_state_shots > expected_half
                                                   ? zero_state_shots - expected_half
                                                   : expected_half - zero_state_shots);

    std::cout << "[Step 3] Verifying correlation invariant and binomial split...\n";
    std::cout << "         Non-Parity Shots Observed:       " << non_parity_shots << " (Required: 0)\n";
    std::cout << "         |0>^{\\otimes 300} Shots:           " << zero_state_shots
              << " (Expected ~" << expected_half << ")\n";
    std::cout << "         |1>^{\\otimes 300} Shots:           " << one_state_shots
              << " (Expected ~" << expected_half << ")\n";
    std::cout << "         |zero - N/2|:                     " << deviation
              << " (5-sigma tolerance: " << tolerance << ")\n";

    if (non_parity_shots != 0) {
        std::cerr << ">>> [FAIL] GHZ-300 parity invariant violated: "
                  << non_parity_shots << " non-parity shots.\n";
        return 1;
    }
    if (zero_state_shots + one_state_shots != NUM_SHOTS) {
        std::cerr << ">>> [FAIL] Shot accounting mismatch: "
                  << zero_state_shots << " + " << one_state_shots
                  << " != " << NUM_SHOTS << ".\n";
        return 1;
    }
    if (deviation > tolerance) {
        std::cerr << ">>> [FAIL] GHZ-300 split deviates by " << deviation
                  << " shots, exceeding the 5-sigma tolerance of "
                  << tolerance << ".\n";
        return 1;
    }

    std::cout << "\n>>> [PASS] GHZ-300 CORRELATION INVARIANT HELD; SPLIT CONSISTENT WITH 50/50.\n";
    return 0;
}
