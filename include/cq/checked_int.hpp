#ifndef CQ_CHECKED_INT_HPP
#define CQ_CHECKED_INT_HPP

// Checked int64/uint32 arithmetic for the exact rings (GEMINI.md 3.4).
// Every operation either returns the exact result or throws
// std::overflow_error; none relies on signed overflow, which is undefined.

#include <cstdint>
#include <limits>
#include <stdexcept>

namespace cq {
namespace checked {

[[noreturn]] inline void overflow(const char* what) {
    throw std::overflow_error(what);
}

constexpr int64_t add(int64_t x, int64_t y) {
    if ((y > 0 && x > std::numeric_limits<int64_t>::max() - y) ||
        (y < 0 && x < std::numeric_limits<int64_t>::min() - y)) {
        overflow("exact ring: int64 addition overflow");
    }
    return x + y;
}

constexpr int64_t sub(int64_t x, int64_t y) {
    if ((y < 0 && x > std::numeric_limits<int64_t>::max() + y) ||
        (y > 0 && x < std::numeric_limits<int64_t>::min() + y)) {
        overflow("exact ring: int64 subtraction overflow");
    }
    return x - y;
}

constexpr int64_t neg(int64_t x) {
    if (x == std::numeric_limits<int64_t>::min()) {
        overflow("exact ring: negation of INT64_MIN");
    }
    return -x;
}

constexpr int64_t mul(int64_t x, int64_t y) {
    constexpr int64_t max = std::numeric_limits<int64_t>::max();
    constexpr int64_t min = std::numeric_limits<int64_t>::min();
    const bool bad = x > 0 ? (y > 0 ? x > max / y : y < min / x)
                           : (y > 0 ? x < min / y : (x != 0 && y < max / x));
    if (bad) overflow("exact ring: int64 multiplication overflow");
    return x * y;
}

// x * 2^shift, refusing anything that does not fit.
constexpr int64_t shl(int64_t x, uint32_t shift) {
    if (x == 0) return 0;
    if (shift >= 63) overflow("exact ring: shift by 63 or more");
    return mul(x, static_cast<int64_t>(int64_t{1} << shift));
}

constexpr uint32_t add_u32(uint32_t x, uint32_t y) {
    if (x > std::numeric_limits<uint32_t>::max() - y) {
        overflow("exact ring: denominator exponent overflow");
    }
    return x + y;
}

}  // namespace checked
}  // namespace cq

#endif  // CQ_CHECKED_INT_HPP
