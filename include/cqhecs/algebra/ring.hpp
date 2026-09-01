#pragma once

#include <cstdint>
#include <string>
#include <stdexcept>
#include <cmath>
#include <iostream>

namespace cqhecs {
namespace algebra {

/**
 * @brief Element of the cyclotomic dyadic ring Z[1/sqrt(2), i].
 * 
 * Represents exact quantum amplitudes of the form:
 *   alpha = ((a + b*sqrt(2)) + i*(c + d*sqrt(2))) / 2^(k/2)
 * where a, b, c, d are int64_t and k is uint32_t.
 * 
 * Guarantees zero floating-point drift in all Clifford+T quantum operations.
 */
class ExactRingElement {
public:
    int64_t a{0}; // Real rational component
    int64_t b{0}; // Real sqrt(2) component
    int64_t c{0}; // Imag rational component
    int64_t d{0}; // Imag sqrt(2) component
    uint32_t k{0}; // Denominator exponent: 2^(k/2)

    constexpr ExactRingElement() noexcept = default;

    constexpr ExactRingElement(int64_t a_, int64_t b_, int64_t c_, int64_t d_, uint32_t k_ = 0) noexcept
        : a(a_), b(b_), c(c_), d(d_), k(k_) {
        // Post-construction reduction
    }

    // Static constructors for basic ring constants
    static constexpr ExactRingElement zero() noexcept {
        return ExactRingElement(0, 0, 0, 0, 0);
    }

    static constexpr ExactRingElement one() noexcept {
        return ExactRingElement(1, 0, 0, 0, 0);
    }

    static constexpr ExactRingElement i_unit() noexcept {
        return ExactRingElement(0, 0, 1, 0, 0);
    }

    static constexpr ExactRingElement inv_sqrt2() noexcept {
        return ExactRingElement(1, 0, 0, 0, 1);
    }

    // omega = e^(i*pi/4) = (1 + i) / sqrt(2)
    static constexpr ExactRingElement omega() noexcept {
        return ExactRingElement(1, 0, 1, 0, 1);
    }

    // omega_dagger = e^(-i*pi/4) = (1 - i) / sqrt(2)
    static constexpr ExactRingElement omega_dagger() noexcept {
        return ExactRingElement(1, 0, -1, 0, 1);
    }

    // Canonical reduction: divide out factors of sqrt(2) when (a & 1) == 0 and (c & 1) == 0
    void reduce() noexcept;

    // Expand exponent to target k by multiplying numerator by sqrt(2) repeatedly
    void expand_to_k(uint32_t target_k);

    // Operator overloads
    ExactRingElement operator+(const ExactRingElement& other) const;
    ExactRingElement operator-(const ExactRingElement& other) const;
    ExactRingElement operator*(const ExactRingElement& other) const;
    ExactRingElement operator-() const noexcept;

    ExactRingElement operator*(int64_t scalar) const;

    bool operator==(const ExactRingElement& other) const noexcept;
    bool operator!=(const ExactRingElement& other) const noexcept {
        return !(*this == other);
    }

    // Exact complex conjugate
    ExactRingElement conj() const noexcept;

    // Exact squared norm |alpha|^2
    ExactRingElement norm_sq() const;

    // Check if element is identically zero
    bool is_zero() const noexcept;

    // Check if element is identically one
    bool is_one() const noexcept;

    // Floating-point conversions (strictly for logging and assertions)
    double to_double_re() const noexcept;
    double to_double_im() const noexcept;
    double to_probability() const noexcept;

    std::string to_string() const;
};

/**
 * @brief 2x2 Unitary Matrix over the Giles-Selinger Ring Z[1/sqrt(2), i].
 */
struct ExactMatrix2 {
    ExactRingElement m[2][2];

    ExactMatrix2() {
        m[0][0] = ExactRingElement::one();
        m[0][1] = ExactRingElement::zero();
        m[1][0] = ExactRingElement::zero();
        m[1][1] = ExactRingElement::one();
    }

    ExactMatrix2(const ExactRingElement& m00, const ExactRingElement& m01,
                 const ExactRingElement& m10, const ExactRingElement& m11) {
        m[0][0] = m00; m[0][1] = m01;
        m[1][0] = m10; m[1][1] = m11;
    }

    ExactMatrix2 operator*(const ExactMatrix2& other) const {
        ExactMatrix2 res;
        for (int r = 0; r < 2; ++r) {
            for (int c = 0; c < 2; ++c) {
                ExactRingElement sum = (m[r][0] * other.m[0][c]) + (m[r][1] * other.m[1][c]);
                sum.reduce();
                res.m[r][c] = sum;
            }
        }
        return res;
    }

    ExactMatrix2 dagger() const noexcept {
        return ExactMatrix2(
            m[0][0].conj(), m[1][0].conj(),
            m[0][1].conj(), m[1][1].conj()
        );
    }

    bool is_identity() const noexcept {
        ExactRingElement z00 = m[0][0]; z00.reduce();
        ExactRingElement z01 = m[0][1]; z01.reduce();
        ExactRingElement z10 = m[1][0]; z10.reduce();
        ExactRingElement z11 = m[1][1]; z11.reduce();
        return z00.is_one() && z01.is_zero() && z10.is_zero() && z11.is_one();
    }

    bool is_unitary() const {
        ExactMatrix2 prod = (*this) * dagger();
        return prod.is_identity();
    }

    // Standard Quantum Gates
    static ExactMatrix2 identity() {
        return ExactMatrix2();
    }

    static ExactMatrix2 pauli_x() {
        return ExactMatrix2(
            ExactRingElement::zero(), ExactRingElement::one(),
            ExactRingElement::one(),  ExactRingElement::zero()
        );
    }

    static ExactMatrix2 pauli_y() {
        return ExactMatrix2(
            ExactRingElement::zero(), -ExactRingElement::i_unit(),
            ExactRingElement::i_unit(), ExactRingElement::zero()
        );
    }

    static ExactMatrix2 pauli_z() {
        return ExactMatrix2(
            ExactRingElement::one(),  ExactRingElement::zero(),
            ExactRingElement::zero(), -ExactRingElement::one()
        );
    }

    static ExactMatrix2 hadamard() {
        // H = 1/sqrt(2) * [[1, 1], [1, -1]]
        ExactRingElement p = ExactRingElement::inv_sqrt2();
        ExactRingElement m = -ExactRingElement::inv_sqrt2();
        return ExactMatrix2(p, p, p, m);
    }

    static ExactMatrix2 phase_s() {
        return ExactMatrix2(
            ExactRingElement::one(),  ExactRingElement::zero(),
            ExactRingElement::zero(), ExactRingElement::i_unit()
        );
    }

    static ExactMatrix2 phase_s_dagger() {
        return ExactMatrix2(
            ExactRingElement::one(),  ExactRingElement::zero(),
            ExactRingElement::zero(), -ExactRingElement::i_unit()
        );
    }

    static ExactMatrix2 phase_t() {
        return ExactMatrix2(
            ExactRingElement::one(),  ExactRingElement::zero(),
            ExactRingElement::zero(), ExactRingElement::omega()
        );
    }

    static ExactMatrix2 phase_t_dagger() {
        return ExactMatrix2(
            ExactRingElement::one(),  ExactRingElement::zero(),
            ExactRingElement::zero(), ExactRingElement::omega_dagger()
        );
    }
};

} // namespace algebra
} // namespace cqhecs
