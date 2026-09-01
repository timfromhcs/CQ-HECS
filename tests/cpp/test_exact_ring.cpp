#include "cqhecs/algebra/ring.hpp"
#include <iostream>
#include <cassert>
#include <random>
#include <chrono>

using namespace cqhecs::algebra;

void test_exact_unitary_invariants() {
    std::cout << "[TEST] Running Exact Unitary Invariants in Z[1/sqrt(2), i]...\n";

    ExactMatrix2 I = ExactMatrix2::identity();
    ExactMatrix2 H = ExactMatrix2::hadamard();
    ExactMatrix2 S = ExactMatrix2::phase_s();
    ExactMatrix2 T = ExactMatrix2::phase_t();
    ExactMatrix2 T_dag = ExactMatrix2::phase_t_dagger();

    // 1. T * T_dag == I
    ExactMatrix2 T_prod = T * T_dag;
    assert(T_prod.is_identity());
    std::cout << "  >>> (T * T_dag == I) verified bit-exact.\n";

    // 2. H * H == I
    ExactMatrix2 H_prod = H * H;
    assert(H_prod.is_identity());
    std::cout << "  >>> (H * H == I) verified bit-exact.\n";

    // 3. S^4 == I
    ExactMatrix2 S2 = S * S;
    ExactMatrix2 S4 = S2 * S2;
    assert(S4.is_identity());
    std::cout << "  >>> (S^4 == I) verified bit-exact.\n";

    // 4. (H * T * H * T_dag) is unitary: U * U_dag == I
    ExactMatrix2 U = H * T * H * T_dag;
    assert(U.is_unitary());
    std::cout << "  >>> (H * T * H * T_dag is Unitary) verified bit-exact.\n";
}

void test_canonical_reduction_synthetic() {
    std::cout << "[TEST] Running Canonical Reduction against Synthetically Expanded Powers of 2^(k/2)...\n";

    // Start with a known base element
    ExactRingElement base(3, -2, 1, 5, 0);
    assert(base.k == 0);

    for (uint32_t expand_depth = 1; expand_depth <= 10; ++expand_depth) {
        ExactRingElement expanded = base;
        expanded.expand_to_k(expand_depth);
        assert(expanded.k == expand_depth);

        // Reduce back
        expanded.reduce();
        assert(expanded == base);
        assert(expanded.k == 0);
        assert(expanded.a == base.a);
        assert(expanded.b == base.b);
        assert(expanded.c == base.c);
        assert(expanded.d == base.d);
    }
    std::cout << "  >>> Canonical reduction verified exact across synthetic expansions.\n";
}

void test_multiplication_associativity_500k() {
    std::cout << "[TEST] Running Multiplication Associativity over 500,000 Elements...\n";
    auto t0 = std::chrono::high_resolution_clock::now();

    std::mt19937_64 rng(42);
    std::uniform_int_distribution<int64_t> coeff_dist(-5, 5);

    const size_t NUM_TRIPLETS = 500000;
    for (size_t i = 0; i < NUM_TRIPLETS; ++i) {
        ExactRingElement x(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), 1);
        ExactRingElement y(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), 1);
        ExactRingElement z(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), 1);

        ExactRingElement lhs = (x * y) * z;
        ExactRingElement rhs = x * (y * z);

        lhs.reduce();
        rhs.reduce();

        assert(lhs == rhs);
    }

    auto t1 = std::chrono::high_resolution_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "  >>> 500,000 Associativity checks passed in: " << ms << " ms (0 bit-errors).\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Exact Algebra & Ring Invariants Test Suite\n";
    std::cout << "=================================================================\n\n";

    test_exact_unitary_invariants();
    test_canonical_reduction_synthetic();
    test_multiplication_associativity_500k();

    std::cout << "\n=================================================================\n";
    std::cout << " ALL ALGEBRA TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
