#ifndef CQ_HECS_CORE_TYPES_HPP
#define CQ_HECS_CORE_TYPES_HPP

#include <cstdint>
#include <cmath>
#include <compare>

namespace cq_hecs {
namespace core {

/**
 * @brief Complex amplitude in Q1.31 fixed-point format (Zero-Float System Invariant).
 * 
 * 1 sign bit, 31 fractional bits.
 * Range: [-1.0, 1.0 - 2^-31].
 * Maximum value: 0x7FFFFFFF (+0.9999999995343387)
 * Minimum value: -0x80000000 (-1.0000000000000000)
 */
struct alignas(8) ComplexQ31 {
    int32_t re{0};
    int32_t im{0};

    constexpr ComplexQ31() noexcept = default;
    constexpr ComplexQ31(int32_t r, int32_t i) noexcept : re(r), im(i) {}

    static constexpr int32_t ONE_VAL = 0x7FFFFFFF;
    static constexpr int32_t INV_SQRT2_VAL = 1518500250; // round(1/sqrt(2) * 2^31) = 0x5A82799A

    static constexpr ComplexQ31 zero() noexcept { return ComplexQ31{0, 0}; }
    static constexpr ComplexQ31 one() noexcept { return ComplexQ31{ONE_VAL, 0}; }
    static constexpr ComplexQ31 i_unit() noexcept { return ComplexQ31{0, ONE_VAL}; }
    static constexpr ComplexQ31 inv_sqrt2() noexcept { return ComplexQ31{INV_SQRT2_VAL, 0}; }

    constexpr bool operator==(const ComplexQ31& o) const noexcept {
        return re == o.re && im == o.im;
    }

    constexpr bool operator!=(const ComplexQ31& o) const noexcept {
        return !(*this == o);
    }

    double to_double() const noexcept {
        return static_cast<double>(re) / 2147483647.0;
    }
};

static_assert(sizeof(ComplexQ31) == 8, "ComplexQ31 must be exactly 8 bytes (alignas 8)");

/**
 * @brief Saturating Q1.31 multiplication with 64-bit accumulator.
 */
static inline int32_t q31_mul(int32_t a, int32_t b) noexcept {
    int64_t prod = (static_cast<int64_t>(a) * static_cast<int64_t>(b)) >> 31;
    if (prod > 0x7FFFFFFFLL) return 0x7FFFFFFF;
    if (prod < -0x80000000LL) return static_cast<int32_t>(-0x80000000LL);
    return static_cast<int32_t>(prod);
}

/**
 * @brief Saturating Q1.31 addition.
 */
static inline int32_t q31_add(int32_t a, int32_t b) noexcept {
    int64_t sum = static_cast<int64_t>(a) + static_cast<int64_t>(b);
    if (sum > 0x7FFFFFFFLL) return 0x7FFFFFFF;
    if (sum < -0x80000000LL) return static_cast<int32_t>(-0x80000000LL);
    return static_cast<int32_t>(sum);
}

/**
 * @brief Saturating Q1.31 subtraction.
 */
static inline int32_t q31_sub(int32_t a, int32_t b) noexcept {
    int64_t diff = static_cast<int64_t>(a) - static_cast<int64_t>(b);
    if (diff > 0x7FFFFFFFLL) return 0x7FFFFFFF;
    if (diff < -0x80000000LL) return static_cast<int32_t>(-0x80000000LL);
    return static_cast<int32_t>(diff);
}

/**
 * @brief Complex multiplication in Q1.31 with saturation: (a + ib)(c + id) = (ac - bd) + i(ad + bc)
 */
static inline ComplexQ31 complex_mul(ComplexQ31 x, ComplexQ31 y) noexcept {
    int64_t re_part = (static_cast<int64_t>(x.re) * y.re - static_cast<int64_t>(x.im) * y.im) >> 31;
    int64_t im_part = (static_cast<int64_t>(x.re) * y.im + static_cast<int64_t>(x.im) * y.re) >> 31;
    if (re_part > 0x7FFFFFFFLL) re_part = 0x7FFFFFFFLL;
    if (re_part < -0x80000000LL) re_part = -0x80000000LL;
    if (im_part > 0x7FFFFFFFLL) im_part = 0x7FFFFFFFLL;
    if (im_part < -0x80000000LL) im_part = -0x80000000LL;
    return ComplexQ31{static_cast<int32_t>(re_part), static_cast<int32_t>(im_part)};
}

/**
 * @brief Complex addition in Q1.31 with saturation.
 */
static inline ComplexQ31 complex_add(ComplexQ31 a, ComplexQ31 b) noexcept {
    return ComplexQ31{q31_add(a.re, b.re), q31_add(a.im, b.im)};
}

/**
 * @brief Complex subtraction in Q1.31 with saturation.
 */
static inline ComplexQ31 complex_sub(ComplexQ31 a, ComplexQ31 b) noexcept {
    return ComplexQ31{q31_sub(a.re, b.re), q31_sub(a.im, b.im)};
}

/**
 * @brief Complex conjugate: a - ib
 */
static inline ComplexQ31 complex_conj(ComplexQ31 z) noexcept {
    return ComplexQ31{z.re, (z.im == static_cast<int32_t>(-0x80000000LL)) ? 0x7FFFFFFF : -z.im};
}

/**
 * @brief Squared norm |z|^2 in Q1.31 format.
 */
static inline int32_t complex_norm_sq(ComplexQ31 z) noexcept {
    int64_t r2 = (static_cast<int64_t>(z.re) * z.re) >> 31;
    int64_t i2 = (static_cast<int64_t>(z.im) * z.im) >> 31;
    int64_t total = r2 + i2;
    if (total > 0x7FFFFFFFLL) return 0x7FFFFFFF;
    return static_cast<int32_t>(total);
}

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_TYPES_HPP
