#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <vector>
#include <random>
#include <chrono>
#include "cq/stabilizer_tableau.hpp"

using namespace cq;

void test_ghz_1000_qubits_stabilizer() {
    std::cout << "[TEST] Running 1,000 Qubits GHZ State Preparation on Stabilizer Tableau...\n";

    const uint32_t N = 1000;
    StabilizerTableau tab(N);

    // GHZ Circuit: H(0), then CX(i, i+1) for i in 0..N-2
    auto start = std::chrono::high_resolution_clock::now();
    tab.apply_h(0);
    for (uint32_t i = 0; i < N - 1; ++i) {
        tab.apply_cx(i, i + 1);
    }
    auto end = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
    std::cout << "  1,000 Qubit GHZ Circuit executed in: " << elapsed_ms << " ms\n";

    // Invariant 1: Symplectic Commutation Relations
    assert(tab.verify_symplectic_invariants());
    std::cout << "  Symplectic invariants verified strictly for 1,000 qubits.\n";

    // Invariant 2: Verify all Z_i Z_{i+1} are stabilizers with eigenvalue +1
    uint32_t num_words = tab.num_words;
    for (uint32_t i = 0; i < N - 1; ++i) {
        std::vector<uint64_t> px(num_words, 0);
        std::vector<uint64_t> pz(num_words, 0);
        // Z_i Z_{i+1}
        pz[i / 64] |= (1ULL << (i % 64));
        pz[(i + 1) / 64] |= (1ULL << ((i + 1) % 64));

        assert(tab.is_stabilizer_satisfied(px, pz, 0));
    }
    std::cout << "  All 999 Z_i Z_{i+1} stabilizers verified with eigenvalue +1.\n";

    // Invariant 3: Verify X_0 X_1 ... X_{N-1} is stabilizer with eigenvalue +1
    std::vector<uint64_t> all_x(num_words, 0);
    std::vector<uint64_t> all_z(num_words, 0);
    for (uint32_t i = 0; i < N; ++i) {
        all_x[i / 64] |= (1ULL << (i % 64));
    }
    assert(tab.is_stabilizer_satisfied(all_x, all_z, 0));
    std::cout << "  All-qubit parity operator X_0...X_{N-1} verified with eigenvalue +1.\n";

    // Measure qubit 0: outcome b in {0, 1}
    std::mt19937_64 rng(42);
    uint8_t b0 = tab.measure(0, &rng);
    std::cout << "  Measured qubit 0 -> " << int(b0) << "\n";

    // Now all other 999 qubits must deterministically collapse to b0!
    for (uint32_t i = 1; i < N; ++i) {
        uint8_t bi = tab.measure(i, &rng);
        assert(bi == b0);
    }
    std::cout << "  All 999 subsequent measurements perfectly correlated with b0=" << int(b0) << ".\n";

    std::cout << ">>> PASS: 1,000 Qubits GHZ State stabilizer verification completed with 0 errors.\n\n";
}

void test_random_clifford_5000_qubits() {
    std::cout << "[TEST] Running 5,000 Qubits Random Clifford Circuit (Commutator Invariant Test)...\n";

    const uint32_t N = 5000;
    StabilizerTableau tab(N);

    std::mt19937_64 rng(999);
    std::uniform_int_distribution<uint32_t> q_dist(0, N - 1);
    std::uniform_int_distribution<uint32_t> gate_dist(0, 3);

    const int NUM_GATES = 10000;
    auto start = std::chrono::high_resolution_clock::now();
    for (int g = 0; g < NUM_GATES; ++g) {
        uint32_t gate = gate_dist(rng);
        uint32_t q1 = q_dist(rng);
        if (gate == 0) {
            tab.apply_h(q1);
        } else if (gate == 1) {
            tab.apply_s(q1);
        } else if (gate == 2) {
            tab.apply_x(q1);
        } else {
            uint32_t q2 = (q1 + 1) % N;
            tab.apply_cx(q1, q2);
        }
    }
    auto end = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
    std::cout << "  5,000 Qubits with 10,000 Clifford gates executed in: " << elapsed_ms << " ms\n";

    // Analytical Invariant Test: Verify all 5,000 stabilizers and destabilizers preserve symplectic grammar
    assert(tab.verify_symplectic_invariants());
    std::cout << "  >>> PASS: Symplectic commutator invariants [S_i, S_j]=0 and <D_i, S_j>=delta_{ij} verified 100% bit-exact across 5,000 qubits.\n\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Bit-Parallel Stabilizer Tableau Verification Suite\n";
    std::cout << "=================================================================\n\n";

    test_ghz_1000_qubits_stabilizer();
    test_random_clifford_5000_qubits();

    std::cout << "=================================================================\n";
    std::cout << " ALL STABILIZER TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
