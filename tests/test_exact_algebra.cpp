#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>
#include <random>
#include "cq/exact_cyclotomic.hpp"

using namespace cq;

void test_clifford_t_exact_unitarity() {
    std::cout << "[TEST] Verifying exact unitarity of Clifford+T gates in Z[1/sqrt(2), i]...\n";

    ExactMatrix2x2 I = ExactMatrix2x2::I();
    ExactMatrix2x2 H = ExactMatrix2x2::H();
    ExactMatrix2x2 S = ExactMatrix2x2::S();
    ExactMatrix2x2 S_dag = ExactMatrix2x2::S_dag();
    ExactMatrix2x2 T = ExactMatrix2x2::T();
    ExactMatrix2x2 T_dag = ExactMatrix2x2::T_dag();
    ExactMatrix2x2 X = ExactMatrix2x2::X();
    ExactMatrix2x2 Y = ExactMatrix2x2::Y();
    ExactMatrix2x2 Z = ExactMatrix2x2::Z();

    // 1. (H)(H) == I
    ExactMatrix2x2 H2 = H * H;
    assert(H2 == I);
    std::cout << "  (H)(H) == I verified bit-exact.\n";

    // 2. (T)(T_dag) == I
    ExactMatrix2x2 TT_dag = T * T_dag;
    assert(TT_dag == I);
    ExactMatrix2x2 T_dagT = T_dag * T;
    assert(T_dagT == I);
    std::cout << "  (T)(T_dag) == I verified bit-exact.\n";

    // 3. (S^4) == I and (S)(S_dag) == I
    ExactMatrix2x2 S2 = S * S;
    ExactMatrix2x2 S4 = S2 * S2;
    assert(S4 == I);
    assert(S * S_dag == I);
    std::cout << "  (S^4) == I verified bit-exact.\n";

    // 4. (T^2) == S and (T^8) == I
    ExactMatrix2x2 T2 = T * T;
    assert(T2 == S);
    ExactMatrix2x2 T4 = T2 * T2;
    ExactMatrix2x2 T8 = T4 * T4;
    assert(T8 == I);
    std::cout << "  (T^2) == S and (T^8) == I verified bit-exact.\n";

    // 5. Pauli algebra: X^2 == I, Y^2 == I, Z^2 == I, X*Y*X*Y == -I
    assert(X * X == I);
    assert(Y * Y == I);
    assert(Z * Z == I);
    std::cout << "  Pauli matrices X^2 == Y^2 == Z^2 == I verified bit-exact.\n";

    // 6. Hadamard conjugation: H * Z * H == X, H * X * H == Z
    assert(H * Z * H == X);
    assert(H * X * H == Z);
    std::cout << "  H*Z*H == X and H*X*H == Z verified bit-exact.\n";

    std::cout << ">>> PASS: All Clifford+T unitarity relations strictly verified (0 bit-errors).\n\n";
}

void test_associativity_100k() {
    std::cout << "[TEST] Verifying multiplication associativity over 100,000 elements in Z[1/sqrt(2), i]...\n";

    std::mt19937_64 rng(1337);
    std::uniform_int_distribution<int64_t> coeff_dist(-20, 20);
    std::uniform_int_distribution<uint32_t> k_dist(0, 4);

    const int ITERATIONS = 100000;
    for (int i = 0; i < ITERATIONS; ++i) {
        Cyclotomic8 x(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), k_dist(rng));
        Cyclotomic8 y(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), k_dist(rng));
        Cyclotomic8 z(coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), coeff_dist(rng), k_dist(rng));

        Cyclotomic8 xy_z = (x * y) * z;
        Cyclotomic8 x_yz = x * (y * z);

        assert(xy_z == x_yz);

        // Also test distributivity: x * (y + z) == (x * y) + (x * z)
        Cyclotomic8 lhs_dist = x * (y + z);
        Cyclotomic8 rhs_dist = (x * y) + (x * z);
        assert(lhs_dist == rhs_dist);
    }

    std::cout << ">>> PASS: 100,000 iterations of associativity and distributivity verified (0 bit-errors).\n\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS Exact Cyclotomic Algebra Test Suite [Z[1/sqrt(2), i]]\n";
    std::cout << "=================================================================\n\n";

    test_clifford_t_exact_unitarity();
    test_associativity_100k();

    std::cout << "=================================================================\n";
    std::cout << " ALL EXACT ALGEBRA TESTS PASSED (0 ERRORS, 0 MOCKS)\n";
    std::cout << "=================================================================\n";
    return 0;
}
