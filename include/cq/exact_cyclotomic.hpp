#ifndef CQ_EXACT_CYCLOTOMIC_HPP
#define CQ_EXACT_CYCLOTOMIC_HPP

#include <cstdint>
#include <cmath>
#include <string>
#include <sstream>
#include <iostream>
#include <compare>
#include <cassert>

namespace cq {

/**
 * @brief Exact Arithmetic in the Giles-Selinger Ring Z[1/sqrt(2), i] == D[omega].
 * 
 * Represents complex numbers of the exact form:
 *   z = ( (a + b*sqrt(2)) + i*(c + d*sqrt(2)) ) / 2^(k/2)
 * where a, b, c, d in Z (int64_t) and k in N (uint32_t).
 * 
 * Every Clifford+T quantum gate has matrix elements strictly inside this ring.
 * All operations (+, -, *, conjugate, norm) are 100% bit-exact with zero IEEE-754 drift.
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
    constexpr void scale_up(uint32_t target_k) noexcept {
        if (target_k <= k || is_zero()) return;
        uint32_t delta = target_k - k;
        uint32_t m = delta / 2;
        uint32_t r = delta % 2;

        if (r == 1) {
            int64_t na = 2 * b;
            int64_t nb = a;
            int64_t nc = 2 * d;
            int64_t nd = c;
            a = na << m;
            b = nb << m;
            c = nc << m;
            d = nd << m;
        } else {
            a <<= m;
            b <<= m;
            c <<= m;
            d <<= m;
        }
        k = target_k;
    }

    constexpr Cyclotomic8 operator+(const Cyclotomic8& rhs) const noexcept {
        if (is_zero()) return rhs;
        if (rhs.is_zero()) return *this;

        uint32_t max_k = (k > rhs.k) ? k : rhs.k;
        Cyclotomic8 lhs_scaled = *this;
        Cyclotomic8 rhs_scaled = rhs;
        lhs_scaled.scale_up(max_k);
        rhs_scaled.scale_up(max_k);

        Cyclotomic8 res(lhs_scaled.a + rhs_scaled.a,
                        lhs_scaled.b + rhs_scaled.b,
                        lhs_scaled.c + rhs_scaled.c,
                        lhs_scaled.d + rhs_scaled.d,
                        max_k);
        return res;
    }

    constexpr Cyclotomic8 operator-(const Cyclotomic8& rhs) const noexcept {
        if (rhs.is_zero()) return *this;
        if (is_zero()) return Cyclotomic8(-rhs.a, -rhs.b, -rhs.c, -rhs.d, rhs.k);

        uint32_t max_k = (k > rhs.k) ? k : rhs.k;
        Cyclotomic8 lhs_scaled = *this;
        Cyclotomic8 rhs_scaled = rhs;
        lhs_scaled.scale_up(max_k);
        rhs_scaled.scale_up(max_k);

        Cyclotomic8 res(lhs_scaled.a - rhs_scaled.a,
                        lhs_scaled.b - rhs_scaled.b,
                        lhs_scaled.c - rhs_scaled.c,
                        lhs_scaled.d - rhs_scaled.d,
                        max_k);
        return res;
    }

    constexpr Cyclotomic8 operator*(const Cyclotomic8& rhs) const noexcept {
        if (is_zero() || rhs.is_zero()) return zero();

        // Real: (a1 + b1*sqrt2)(a2 + b2*sqrt2) - (c1 + d1*sqrt2)(c2 + d2*sqrt2)
        int64_t res_a = a * rhs.a + 2 * b * rhs.b - (c * rhs.c + 2 * d * rhs.d);
        int64_t res_b = a * rhs.b + b * rhs.a - (c * rhs.d + d * rhs.c);

        // Imag: (a1 + b1*sqrt2)(c2 + d2*sqrt2) + (c1 + d1*sqrt2)(a2 + b2*sqrt2)
        int64_t res_c = a * rhs.c + 2 * b * rhs.d + (c * rhs.a + 2 * d * rhs.b);
        int64_t res_d = a * rhs.d + b * rhs.c + (c * rhs.b + d * rhs.a);

        uint32_t res_k = k + rhs.k;
        return Cyclotomic8(res_a, res_b, res_c, res_d, res_k);
    }

    constexpr Cyclotomic8 conj() const noexcept {
        return Cyclotomic8(a, b, -c, -d, k);
    }

    constexpr Cyclotomic8 norm_sq() const noexcept {
        return (*this) * conj();
    }

    constexpr bool operator==(const Cyclotomic8& rhs) const noexcept {
        if (k == rhs.k) {
            return a == rhs.a && b == rhs.b && c == rhs.c && d == rhs.d;
        }
        uint32_t max_k = (k > rhs.k) ? k : rhs.k;
        Cyclotomic8 lhs_s = *this;
        Cyclotomic8 rhs_s = rhs;
        lhs_s.scale_up(max_k);
        rhs_s.scale_up(max_k);
        return lhs_s.a == rhs_s.a && lhs_s.b == rhs_s.b &&
               lhs_s.c == rhs_s.c && lhs_s.d == rhs_s.d;
    }

    constexpr bool operator!=(const Cyclotomic8& rhs) const noexcept {
        return !(*this == rhs);
    }

    double to_double_re() const noexcept {
        constexpr double SQRT2 = 1.414213562373095048801688724209698;
        double denom = std::pow(SQRT2, static_cast<double>(k));
        return (static_cast<double>(a) + static_cast<double>(b) * SQRT2) / denom;
    }

    double to_double_im() const noexcept {
        constexpr double SQRT2 = 1.414213562373095048801688724209698;
        double denom = std::pow(SQRT2, static_cast<double>(k));
        return (static_cast<double>(c) + static_cast<double>(d) * SQRT2) / denom;
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

    constexpr ExactMatrix2x2 adjoint() const noexcept {
        return ExactMatrix2x2(m00.conj(), m10.conj(),
                              m01.conj(), m11.conj());
    }

    constexpr ExactMatrix2x2 operator*(const ExactMatrix2x2& rhs) const noexcept {
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
