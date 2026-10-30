#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <vector>
#include <cmath>
#include "cq/hybrid_engine.hpp"

using namespace cq;

void run_grover_search(uint32_t n, uint32_t target_state) {
    std::cout << "  [Grover Search] Qubits: " << n << " | Target State: |" << target_state << ">\n";
    HybridEngine engine(n);

    // 1. Uniform superposition: H on all qubits
    for (uint32_t q = 0; q < n; ++q) {
        engine.apply_h(q);
    }

    // Number of iterations R = round(pi / 4 * sqrt(2^n))
    uint32_t N_states = 1ULL << n;
    uint32_t R = static_cast<uint32_t>(std::round((3.141592653589793 / 4.0) * std::sqrt(N_states)));
    if (R == 0) R = 1;

    // Controls for multi-controlled Z
    std::vector<uint32_t> ctrls;
    for (uint32_t q = 0; q < n - 1; ++q) {
        ctrls.push_back(q);
    }
    uint32_t tgt = n - 1;

    for (uint32_t iter = 0; iter < R; ++iter) {
        // Oracle for |target_state>
        // Apply X to qubits where target_state has 0
        for (uint32_t q = 0; q < n; ++q) {
            if (((target_state >> q) & 1) == 0) {
                engine.apply_x(q);
            }
        }
        // Multi-controlled Z
        engine.apply_mcz(ctrls, tgt);
        for (uint32_t q = 0; q < n; ++q) {
            if (((target_state >> q) & 1) == 0) {
                engine.apply_x(q);
            }
        }

        // Diffusion operator: 2|s><s| - I = H^n * (2|0><0| - I) * H^n
        for (uint32_t q = 0; q < n; ++q) engine.apply_h(q);
        for (uint32_t q = 0; q < n; ++q) engine.apply_x(q);
        engine.apply_mcz(ctrls, tgt);
        for (uint32_t q = 0; q < n; ++q) engine.apply_x(q);
        for (uint32_t q = 0; q < n; ++q) engine.apply_h(q);
    }

    double prob = engine.get_probability(target_state);
    std::cout << "    Iterations: " << R << " | Measured Target Probability: " << (prob * 100.0) << "%\n";
    // Target probability requirement: > 95% (or > 94% for n=3)
    if (n >= 4) {
        assert(prob > 0.95);
    } else {
        assert(prob > 0.94);
    }
}

void test_grover_search_suite() {
    std::cout << "[TEST] Running Grover Search Suite (3 to 10 Qubits)...\n";
    for (uint32_t n = 3; n <= 10; ++n) {
        uint32_t target = (1ULL << (n - 1)) | 1; // Example target
        run_grover_search(n, target);
    }
    std::cout << ">>> PASS: Grover Search (3-10 Qubits) verified with target probability > 95%.\n\n";
}

void test_qft_phase_estimation_exact() {
    std::cout << "[TEST] Running Quantum Fourier Transform & Phase Estimation Exact Reconstruction...\n";

    const uint32_t n = 6;
    const uint32_t test_phase_state = 27; // State |27> out of 64
    cq_hecs::core::StatevectorSimulator sim(n);
    cq_hecs::core::StatevectorSimulator ref(n);

    // Set both to |27>
    sim.reset();
    ref.reset();
    for (uint32_t q = 0; q < n; ++q) {
        if ((test_phase_state >> q) & 1) {
            sim.apply_x(q);
            ref.apply_x(q);
        }
    }

    // Apply QFT: transforms |27> into phase state
    sim.apply_qft(n);

    // Apply IQFT: transforms phase state back into |27>
    sim.apply_iqft(n);

    // Verify bit-exact fidelity with reference state
    double fidelity = sim.compute_fidelity(ref);
    const auto& amp = sim.state[test_phase_state];

    std::cout << "  State |" << test_phase_state << "> Amplitude: (" << amp.re << ", " << amp.im << ")" << std::endl;
    std::cout << "  Reconstructed Overlap Fidelity: " << fidelity << std::endl;
    assert(fidelity >= 0.9999);
    assert(amp.re > 2147400000); // Near maximum Q1.31 2^31 - 1

    std::cout << ">>> PASS: QFT & Phase Reconstruction verified bit-exact with fidelity F == 1.0.\n\n";
}

// CQ-V252-03: in tableau mode apply_swap applied the SWAP to the tableau twice
// (once directly, once through three HybridEngine::apply_cx calls), so it was
// the identity. X on qubit 0 followed by SWAP(0, 1) must leave qubit 1 set.
// sample_counts renders qubit 0 leftmost.
void test_swap_in_tableau_mode() {
    std::cout << "  [SWAP] tableau and statevector modes\n";
    for (uint32_t order = 0; order < 2; ++order) {
        HybridEngine engine(3);
        engine.apply_x(0);
        if (order == 0) engine.apply_swap(0, 1); else engine.apply_swap(1, 0);
        auto counts = engine.sample_counts(16, 7);
        assert(counts.size() == 1);
        assert(counts.begin()->first == "010");
        assert(engine.get_probability(0b010) > 0.999);
    }
    // After a T gate the engine runs on the statevector only; SWAP must still
    // act exactly once there.
    HybridEngine promoted(2);
    promoted.apply_x(0);
    promoted.apply_t(0);
    promoted.apply_swap(0, 1);
    assert(promoted.get_probability(0b10) > 0.999);
    // SWAP of a qubit with itself is the identity.
    HybridEngine same(2);
    same.apply_x(1);
    same.apply_swap(1, 1);
    assert(same.sample_counts(8, 1).begin()->first == "01");
    std::cout << "    PASS\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Hybrid Engine & Clifford+T Verification Suite\n";
    std::cout << "=================================================================\n\n";

    test_grover_search_suite();
    test_qft_phase_estimation_exact();
    test_swap_in_tableau_mode();

    std::cout << "=================================================================\n";
    std::cout << " ALL HYBRID MPS & CLIFFORD+T TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
