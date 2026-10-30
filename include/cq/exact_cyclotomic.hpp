#ifndef CQ_EXACT_CYCLOTOMIC_HPP
#define CQ_EXACT_CYCLOTOMIC_HPP

#include <cstdint>
#include <cmath>
#include <string>
#include <sstream>
#include <iostream>
#include <compare>
#include <cassert>

#include "cq/checked_int.hpp"

namespace cq {

/**
 * @brief Exact Arithmetic in the Giles-Selinger Ring Z[1/sqrt(2), i] == D[omega].
 * 
 * Represents complex numbers of the exact form:
 *   z = ( (a + b*sqrt(2)) + i*(c + d*sqrt(2)) ) / 2^(k/2)
 * where a, b, c, d in Z (int64_t) and k in N (uint32_t).
 * 
 * Every Clifford+T quantum gate has matrix elements strictly inside this ring.
 * Arithmetic is exact while every coefficient fits in int64_t and k in
 * uint32_t; any intermediate that does not fit throws std::overflow_error
 * (checked_int.hpp) instead of wrapping. The double conversions are an
 * approximate export and are never used for equality.
 */
class Cyclotomic8 {
public:
    int64_t a{0};
    int64_t b{0};
    int64_t c{0};
    int64_t d{0};
    uint32_t k{0};

    constexpr Cyclotomic8() noexcept = default;

    constexpr Cyclotomic8(int64_t a_, int64_t b_, int64_t c_, int64_t d_, uint32_t k_ = 0) noexcept
        : a(a_), b(b_), c(c_), d(d_), k(k_) {
        canonicalize();
    }

    // Common algebraic constants
    static constexpr Cyclotomic8 zero() noexcept { return Cyclotomic8(0, 0, 0, 0, 0); }
    static constexpr Cyclotomic8 one() noexcept  { return Cyclotomic8(1, 0, 0, 0, 0); }
    static constexpr Cyclotomic8 i_unit() noexcept { return Cyclotomic8(0, 0, 1, 0, 0); }
    static constexpr Cyclotomic8 inv_sqrt2() noexcept { return Cyclotomic8(1, 0, 0, 0, 1); } // 1 / sqrt(2)
    static constexpr Cyclotomic8 omega() noexcept { return Cyclotomic8(1, 0, 1, 0, 1); }     // e^(i*pi/4) = (1 + i)/sqrt(2)

    constexpr bool is_zero() const noexcept {
        return a == 0 && b == 0 && c == 0 && d == 0;
    }

    constexpr bool is_one() const noexcept {
        return a == 1 && b == 0 && c == 0 && d == 0 && k == 0;
    }

    /**
     * @brief Canonical reduction: factor out sqrt(2) from numerator and denominator when possible.
     * (2*b' + b*sqrt(2)) + i*(2*d' + d*sqrt(2)) = sqrt(2) * ( (b + b'*sqrt(2)) + i*(d + d'*sqrt(2)) )
     */
    constexpr void canonicalize() noexcept {
        if (is_zero()) {
            k = 0;
            return;
        }

        while (k > 0 && (a % 2 == 0) && (c % 2 == 0)) {
            int64_t new_a = b;
            int64_t new_b = a / 2;
            int64_t new_c = d;
            int64_t new_d = c / 2;
            a = new_a;
            b = new_b;
            c = new_c;
            d = new_d;
            --k;
        }
    }

    /**
     * @brief Scales the number to a target denominator exponent target_k >= k.
     */
    constexpr void scale_up(uint32_t target_k) {
        if (target_k <= k || is_zero()) return;
        uint32_t delta = target_k - k;
        uint32_t m = delta / 2;
        uint32_t r = delta % 2;

        if (r == 1) {
            int64_t na = checked::mul(2, b);
            int64_t nb = a;
            int64_t nc = checked::mul(2, d);
            int64_t nd = c;
            a = checked::shl(na, m);
            b = checked::shl(nb, m);
            c = checked::shl(nc, m);
            d = checked::shl(nd, m);
        } else {
            a = checked::shl(a, m);
            b = checked::shl(b, m);
            c = checked::shl(c, m);
            d = checked::shl(d, m);
        }
        k = target_k;
    }

    constexpr Cyclotomic8 operator+(const Cyclotomic8& rhs) const {
        if (is_zero()) return rhs;
        if (rhs.is_zero()) return *this;

        uint32_t max_k = (k > rhs.k) ? k : rhs.k;
        Cyclotomic8 lhs_scaled = *this;
        Cyclotomic8 rhs_scaled = rhs;
        lhs_scaled.scale_up(max_k);
        rhs_scaled.scale_up(max_k);

        Cyclotomic8 res(checked::add(lhs_scaled.a, rhs_scaled.a),
                        checked::add(lhs_scaled.b, rhs_scaled.b),
                        checked::add(lhs_scaled.c, rhs_scaled.c),
                        checked::add(lhs_scaled.d, rhs_scaled.d),
                        max_k);
        return res;
    }

    constexpr Cyclotomic8 operator-(const Cyclotomic8& rhs) const {
        if (rhs.is_zero()) return *this;
        if (is_zero()) {
            return Cyclotomic8(checked::neg(rhs.a), checked::neg(rhs.b),
                               checked::neg(rhs.c), checked::neg(rhs.d), rhs.k);
        }

        uint32_t max_k = (k > rhs.k) ? k : rhs.k;
        Cyclotomic8 lhs_scaled = *this;
        Cyclotomic8 rhs_scaled = rhs;
        lhs_scaled.scale_up(max_k);
        rhs_scaled.scale_up(max_k);

        Cyclotomic8 res(checked::sub(lhs_scaled.a, rhs_scaled.a),
                        checked::sub(lhs_scaled.b, rhs_scaled.b),
                        checked::sub(lhs_scaled.c, rhs_scaled.c),
                        checked::sub(lhs_scaled.d, rhs_scaled.d),
                        max_k);
        return res;
    }

    constexpr Cyclotomic8 operator*(const Cyclotomic8& rhs) const {
        using namespace checked;
        if (is_zero() || rhs.is_zero()) return zero();

        // Real: (a1 + b1*sqrt2)(a2 + b2*sqrt2) - (c1 + d1*sqrt2)(c2 + d2*sqrt2)
        int64_t res_a = sub(add(mul(a, rhs.a), mul(2, mul(b, rhs.b))),
                            add(mul(c, rhs.c), mul(2, mul(d, rhs.d))));
        int64_t res_b = sub(add(mul(a, rhs.b), mul(b, rhs.a)),
                            add(mul(c, rhs.d), mul(d, rhs.c)));

        // Imag: (a1 + b1*sqrt2)(c2 + d2*sqrt2) + (c1 + d1*sqrt2)(a2 + b2*sqrt2)
        int64_t res_c = add(add(mul(a, rhs.c), mul(2, mul(b, rhs.d))),
                            add(mul(c, rhs.a), mul(2, mul(d, rhs.b))));
        int64_t res_d = add(add(mul(a, rhs.d), mul(b, rhs.c)),
                            add(mul(c, rhs.b), mul(d, rhs.a)));

        return Cyclotomic8(res_a, res_b, res_c, res_d, add_u32(k, rhs.k));
    }

    constexpr Cyclotomic8 conj() const {
        return Cyclotomic8(a, b, checked::neg(c), checked::neg(d), k);
    }

    constexpr Cyclotomic8 norm_sq() const {
        return (*this) * conj();
    }

    /// Equality on canonical forms. The minimal-k representation is unique
    /// (sqrt(2) divides the numerator iff a and c are even), so no rescaling
    /// is needed and equality can never overflow.
    constexpr bool operator==(const Cyclotomic8& rhs) const noexcept {
        Cyclotomic8 x = *this;
        Cyclotomic8 y = rhs;
        x.canonicalize();
        y.canonicalize();
        return x.k == y.k && x.a == y.a && x.b == y.b && x.c == y.c && x.d == y.d;
    }

    constexpr bool operator!=(const Cyclotomic8& rhs) const noexcept {
        return !(*this == rhs);
    }

    // Approximate export only. ldexp keeps 2^(-k/2) finite where pow(sqrt2, k)
    // would overflow to infinity for large k.
    double to_double_re() const noexcept {
        constexpr double SQRT2 = 1.414213562373095048801688724209698;
        return (static_cast<double>(a) + static_cast<double>(b) * SQRT2) * inverse_sqrt2_power();
    }

    double to_double_im() const noexcept {
        constexpr double SQRT2 = 1.414213562373095048801688724209698;
        return (static_cast<double>(c) + static_cast<double>(d) * SQRT2) * inverse_sqrt2_power();
    }

    double inverse_sqrt2_power() const noexcept {
        constexpr double INV_SQRT2 = 0.707106781186547524400844362104849;
        const double half = std::ldexp(1.0, -static_cast<int>(k / 2));
        return (k % 2 == 1) ? half * INV_SQRT2 : half;
    }

    std::string to_string() const {
        std::ostringstream ss;
        ss << "((" << a << " + " << b << "*sqrt2) + i*(" << c << " + " << d << "*sqrt2)) / 2^(" << k << "/2)";
        return ss.str();
    }
};

/**
 * @brief 2x2 Matrix over the Giles-Selinger Ring Z[1/sqrt(2), i].
 */
struct ExactMatrix2x2 {
    Cyclotomic8 m00, m01;
    Cyclotomic8 m10, m11;

    constexpr ExactMatrix2x2() noexcept
        : m00(Cyclotomic8::one()),  m01(Cyclotomic8::zero()),
          m10(Cyclotomic8::zero()), m11(Cyclotomic8::one()) {}

    constexpr ExactMatrix2x2(Cyclotomic8 a, Cyclotomic8 b,
                             Cyclotomic8 c, Cyclotomic8 d) noexcept
        : m00(a), m01(b), m10(c), m11(d) {}

    // Identity gate
    static constexpr ExactMatrix2x2 I() noexcept {
        return ExactMatrix2x2(Cyclotomic8::one(),  Cyclotomic8::zero(),
                              Cyclotomic8::zero(), Cyclotomic8::one());
    }

    // Hadamard gate: 1/sqrt(2) * [[1, 1], [1, -1]]
    static constexpr ExactMatrix2x2 H() noexcept {
        Cyclotomic8 inv = Cyclotomic8::inv_sqrt2();
        Cyclotomic8 neg_inv(-1, 0, 0, 0, 1);
        return ExactMatrix2x2(inv, inv, inv, neg_inv);
    }

    // S Phase gate: [[1, 0], [0, i]]
    static constexpr ExactMatrix2x2 S() noexcept {
        return ExactMatrix2x2(Cyclotomic8::one(), Cyclotomic8::zero(),
                              Cyclotomic8::zero(), Cyclotomic8::i_unit());
    }

    // S-dagger gate: [[1, 0], [0, -i]]
    static constexpr ExactMatrix2x2 S_dag() noexcept {
        return ExactMatrix2x2(Cyclotomic8::one(), Cyclotomic8::zero(),
                              Cyclotomic8::zero(), Cyclotomic8(0, 0, -1, 0, 0));
    }

    // T gate: [[1, 0], [0, e^(i*pi/4)]]
    static constexpr ExactMatrix2x2 T() noexcept {
        return ExactMatrix2x2(Cyclotomic8::one(), Cyclotomic8::zero(),
                              Cyclotomic8::zero(), Cyclotomic8::omega());
    }

    // T-dagger gate: [[1, 0], [0, e^(-i*pi/4)]]
    static constexpr ExactMatrix2x2 T_dag() noexcept {
        Cyclotomic8 omega_dag(1, 0, -1, 0, 1);
        return ExactMatrix2x2(Cyclotomic8::one(), Cyclotomic8::zero(),
                              Cyclotomic8::zero(), omega_dag);
    }

    // Pauli X: [[0, 1], [1, 0]]
    static constexpr ExactMatrix2x2 X() noexcept {
        return ExactMatrix2x2(Cyclotomic8::zero(), Cyclotomic8::one(),
                              Cyclotomic8::one(),  Cyclotomic8::zero());
    }

    // Pauli Y: [[0, -i], [i, 0]]
    static constexpr ExactMatrix2x2 Y() noexcept {
        return ExactMatrix2x2(Cyclotomic8::zero(), Cyclotomic8(0, 0, -1, 0, 0),
                              Cyclotomic8::i_unit(), Cyclotomic8::zero());
    }

    // Pauli Z: [[1, 0], [0, -1]]
    static constexpr ExactMatrix2x2 Z() noexcept {
        return ExactMatrix2x2(Cyclotomic8::one(), Cyclotomic8::zero(),
                              Cyclotomic8::zero(), Cyclotomic8(-1, 0, 0, 0, 0));
    }

    constexpr ExactMatrix2x2 adjoint() const {
        return ExactMatrix2x2(m00.conj(), m10.conj(),
                              m01.conj(), m11.conj());
    }

    constexpr ExactMatrix2x2 operator*(const ExactMatrix2x2& rhs) const {
        return ExactMatrix2x2(
            m00 * rhs.m00 + m01 * rhs.m10,
            m00 * rhs.m01 + m01 * rhs.m11,
            m10 * rhs.m00 + m11 * rhs.m10,
            m10 * rhs.m01 + m11 * rhs.m11
        );
    }

    constexpr bool operator==(const ExactMatrix2x2& rhs) const noexcept {
        return m00 == rhs.m00 && m01 == rhs.m01 &&
               m10 == rhs.m10 && m11 == rhs.m11;
    }

    constexpr bool operator!=(const ExactMatrix2x2& rhs) const noexcept {
        return !(*this == rhs);
    }
};

} // namespace cq

#endif // CQ_EXACT_CYCLOTOMIC_HPP
