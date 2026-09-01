#include "cqhecs/stabilizer/tableau.hpp"
#include <iostream>
#include <cassert>
#include <chrono>
#include <vector>

using namespace cqhecs::stabilizer;

void test_1000q_ghz_stabilizers() {
    std::cout << "[TEST] Running 1,000-Qubit GHZ State Preparation & Stabilizer Verification...\n";
    const uint32_t N = 1000;
    StabilizerTableau tab(N);

    auto t0 = std::chrono::high_resolution_clock::now();

    // Prepare GHZ State: (|00...0> + |11...1>) / sqrt(2)
    tab.apply_h(0);
    for (uint32_t i = 0; i < N - 1; ++i) {
        tab.apply_cx(i, i + 1);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "  Prepared 1,000-Qubit GHZ in: " << ms << " ms.\n";

    // 1. Verify all 999 Z_i Z_{i+1} stabilizers
    for (uint32_t i = 0; i < N - 1; ++i) {
        bool sat = tab.is_stabilizer_satisfied({}, {i, i + 1}, 0);
        assert(sat && "Z_i Z_{i+1} must be an exact stabilizer (+1 eigenvalue)");
    }
    std::cout << "  >>> All 999 Z_i Z_{i+1} stabilizers verified.\n";

    // 2. Verify X_0 ... X_{N-1} stabilizer
    std::vector<uint32_t> all_qubits(N);
    for (uint32_t i = 0; i < N; ++i) all_qubits[i] = i;
    bool sat_x = tab.is_stabilizer_satisfied(all_qubits, {}, 0);
    assert(sat_x && "X_0...X_{N-1} must be an exact stabilizer (+1 eigenvalue)");
    std::cout << "  >>> X_0...X_{N-1} global stabilizer verified.\n";

    // 3. Symplectic invariants
    assert(tab.verify_symplectic_invariants());
    std::cout << "  >>> Symplectic invariants preserved on 1,000-Qubit GHZ.\n";
}

void test_10000q_clifford_walk() {
    std::cout << "[TEST] Running 10,000-Qubit Clifford Random Walk (10,000 Gate Layers)...\n";
    const uint32_t N = 10000;
    const uint32_t GATES = 10000;

    auto t0 = std::chrono::high_resolution_clock::now();

    StabilizerTableau tab(N);
    std::mt19937_64 rng(1337);
    std::uniform_int_distribution<uint32_t> q_dist(0, N - 1);
    std::uniform_int_distribution<int> gate_dist(0, 2);

    for (uint32_t g = 0; g < GATES; ++g) {
        int gtype = gate_dist(rng);
        uint32_t q1 = q_dist(rng);
        if (gtype == 0) {
            tab.apply_h(q1);
        } else if (gtype == 1) {
            tab.apply_s(q1);
        } else {
            uint32_t q2 = (q1 + 1) % N;
            tab.apply_cx(q1, q2);
        }
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "  Executed 10,000 Clifford gates across 10,000 qubits in: " << ms << " ms.\n";

    // Verify symplectic inner product invariant
    assert(tab.verify_symplectic_invariants());
    std::cout << "  >>> Symplectic commutator invariance strictly preserved across 10,000 Qubits.\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Stabilizer Tableau Extreme Verification Suite\n";
    std::cout << "=================================================================\n\n";

    test_1000q_ghz_stabilizers();
    test_10000q_clifford_walk();

    std::cout << "\n=================================================================\n";
    std::cout << " ALL STABILIZER EXTREME TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
