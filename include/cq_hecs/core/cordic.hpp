#ifndef CQ_HECS_CORE_CORDIC_HPP
#define CQ_HECS_CORE_CORDIC_HPP

#include "types.hpp"
#include <cstdint>
#include <array>

namespace cq_hecs {
namespace core {

/**
 * @brief Precalculated CORDIC angles in Z_{2^32} phase ring (2^32 == 2*pi).
 * 
 * Each entry is round(arctan(2^-i) / (2*pi) * 2^32).
 */
inline constexpr std::array<uint32_t, 16> CORDIC_ANGLES = {
    536870912u, // i = 0:  arctan(1)   = pi/4       (0x20000000)
    316933406u, // i = 1:  arctan(1/2) = 0.463647 rad (0x12E4051E)
    167458907u, // i = 2:  arctan(1/4) = 0.244978 rad (0x09FA309B)
     85004756u, // i = 3:  arctan(1/8) = 0.124354 rad (0x0510FE14)
     42667327u, // i = 4:  arctan(1/16)              (0x028B0D3F)
     21354465u, // i = 5:  arctan(1/32)              (0x0145D7E1)
     10679848u, // i = 6:  arctan(1/64)              (0x00A2F988)
      5340245u, // i = 7:  arctan(1/128)             (0x00517DE5)
      2670163u, // i = 8:  arctan(1/256)             (0x0028BF03)
      1335086u, // i = 9:  arctan(1/512)             (0x00145F8E)
       667544u, // i = 10: arctan(1/1024)            (0x000A2FC8)
       333772u, // i = 11: arctan(1/2048)            (0x000517E4)
       166886u, // i = 12: arctan(1/4096)            (0x00028BF2)
        83443u, // i = 13: arctan(1/8192)            (0x000145F9)
        41722u, // i = 14: arctan(1/16384)           (0x0000A2FC)
        20861u  // i = 15: arctan(1/32768)           (0x0000517E)
};

/**
 * @brief CORDIC scaling factor K_16 in Q1.31 format.
 * prod_{i=0}^15 1/sqrt(1 + 2^(-2i)) = 0.607252935008881256...
 * In Q1.31: round(K * 2^31) = 1304065744 = 0x4DBA75D0
 */
inline constexpr int32_t CORDIC_K_Q31 = 1304065744;

/**
 * @brief Bit-exact phase rotation of state amplitude in Q1.31 format using CORDIC.
 * 
 * Computes: state' = state * e^(i * phase_q32)
 * 
 * Invariants:
 * - When phase_q32 == 0 (mod 2^32), state' == state bit-identically (zero drift).
 * - Multiples of pi/2 (0x40000000, 0x80000000, 0xC0000000) are exact quadrant swaps.
 * - Intermediate angles use 16-iteration CORDIC shift-add.
 */
static inline ComplexQ31 cordic_rotate(ComplexQ31 state, uint32_t phase_q32) noexcept {
    if (phase_q32 == 0) {
        return state;
    }

    // Decompose into quadrant and residual angle in [0, pi/2)
    uint32_t quad = phase_q32 >> 30; // 0: [0, pi/2), 1: [pi/2, pi), 2: [pi, 3pi/2), 3: [3pi/2, 2pi)
    uint32_t rem = phase_q32 & 0x3FFFFFFFu;

    int32_t x = state.re;
    int32_t y = state.im;

    // Quadrant rotation
    if (quad == 1) {
        // e^(i * pi/2) = i: (x + iy)*i = -y + ix
        int32_t tx = x;
        x = (y == static_cast<int32_t>(-0x80000000LL)) ? 0x7FFFFFFF : -y;
        y = tx;
    } else if (quad == 2) {
        // e^(i * pi) = -1: -(x + iy) = -x - iy
        x = (x == static_cast<int32_t>(-0x80000000LL)) ? 0x7FFFFFFF : -x;
        y = (y == static_cast<int32_t>(-0x80000000LL)) ? 0x7FFFFFFF : -y;
    } else if (quad == 3) {
        // e^(i * 3pi/2) = -i: (x + iy)*(-i) = y - ix
        int32_t tx = x;
        x = y;
        y = (tx == static_cast<int32_t>(-0x80000000LL)) ? 0x7FFFFFFF : -tx;
    }

    if (rem == 0) {
        return ComplexQ31{x, y};
    }

    // 16-step CORDIC rotation on remaining angle
    int64_t cx = x;
    int64_t cy = y;
    int64_t z = static_cast<int64_t>(rem);

    for (size_t i = 0; i < 16; ++i) {
        int64_t dx = cx >> i;
        int64_t dy = cy >> i;
        uint32_t angle = CORDIC_ANGLES[i];

        if (z >= 0) {
            cx -= dy;
            cy += dx;
            z -= angle;
        } else {
            cx += dy;
            cy -= dx;
            z += angle;
        }
    }

    // Scale back by K_16 factor in Q1.31 using 64-bit accumulator to avoid overflow from CORDIC gain
    int64_t scaled_x = (cx * CORDIC_K_Q31) >> 31;
    int64_t scaled_y = (cy * CORDIC_K_Q31) >> 31;

    if (scaled_x > 0x7FFFFFFFLL) scaled_x = 0x7FFFFFFFLL;
    if (scaled_x < -0x80000000LL) scaled_x = -0x80000000LL;
    if (scaled_y > 0x7FFFFFFFLL) scaled_y = 0x7FFFFFFFLL;
    if (scaled_y < -0x80000000LL) scaled_y = -0x80000000LL;

    return ComplexQ31{static_cast<int32_t>(scaled_x), static_cast<int32_t>(scaled_y)};
}

/**
 * @brief Converts radians (double) to Z_{2^32} phase angle.
 */
static inline uint32_t radians_to_z32(double rad) noexcept {
    constexpr double TWO_PI = 6.283185307179586476925286766559;
    double normalized = std::fmod(rad, TWO_PI);
    if (normalized < 0.0) normalized += TWO_PI;
    return static_cast<uint32_t>(std::round((normalized / TWO_PI) * 4294967296.0));
}

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_CORDIC_HPP
