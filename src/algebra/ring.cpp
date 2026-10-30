#include "cqhecs/algebra/ring.hpp"
#include "cq/checked_int.hpp"
#include <sstream>
#include <limits>
#include <iomanip>

namespace cqhecs {
namespace algebra {

using namespace cq::checked;

static constexpr double SQRT2_D = 1.41421356237309504880;

void ExactRingElement::reduce() noexcept {
    if (a == 0 && b == 0 && c == 0 && d == 0) {
        k = 0;
        return;
    }

    while (k > 0 && ((a & 1) == 0) && ((c & 1) == 0)) {
        int64_t next_a = b;
        int64_t next_b = a / 2;
        int64_t next_c = d;
        int64_t next_d = c / 2;

        a = next_a;
        b = next_b;
        c = next_c;
        d = next_d;
        --k;
    }
}

void ExactRingElement::expand_to_k(uint32_t target_k) {
    while (k < target_k) {
        // Multiply numerator by sqrt(2):
        // sqrt(2) * (x + y*sqrt(2)) = 2*y + x*sqrt(2)
        if (b > (std::numeric_limits<int64_t>::max() / 2) || b < (std::numeric_limits<int64_t>::min() / 2) ||
            d > (std::numeric_limits<int64_t>::max() / 2) || d < (std::numeric_limits<int64_t>::min() / 2)) {
            throw std::overflow_error("ExactRingElement::expand_to_k integer overflow");
        }

        int64_t next_a = 2 * b;
        int64_t next_b = a;
        int64_t next_c = 2 * d;
        int64_t next_d = c;

        a = next_a;
        b = next_b;
        c = next_c;
        d = next_d;
        ++k;
    }
}

ExactRingElement ExactRingElement::operator-() const {
    return ExactRingElement(neg(a), neg(b), neg(c), neg(d), k);
}

ExactRingElement ExactRingElement::operator+(const ExactRingElement& other) const {
    ExactRingElement left = *this;
    ExactRingElement right = other;

    uint32_t max_k = std::max(left.k, right.k);
    left.expand_to_k(max_k);
    right.expand_to_k(max_k);

    ExactRingElement res(
        add(left.a, right.a),
        add(left.b, right.b),
        add(left.c, right.c),
        add(left.d, right.d),
        max_k
    );
    res.reduce();
    return res;
}

ExactRingElement ExactRingElement::operator-(const ExactRingElement& other) const {
    ExactRingElement left = *this;
    ExactRingElement right = other;

    uint32_t max_k = std::max(left.k, right.k);
    left.expand_to_k(max_k);
    right.expand_to_k(max_k);

    ExactRingElement res(
        sub(left.a, right.a),
        sub(left.b, right.b),
        sub(left.c, right.c),
        sub(left.d, right.d),
        max_k
    );
    res.reduce();
    return res;
}

ExactRingElement ExactRingElement::operator*(int64_t scalar) const {
    ExactRingElement res(mul(a, scalar), mul(b, scalar), mul(c, scalar), mul(d, scalar), k);
    res.reduce();
    return res;
}

ExactRingElement ExactRingElement::operator*(const ExactRingElement& other) const {
    // Real and Imaginary expansion in Z[sqrt(2), i]
    // Re = (a1*a2 + 2*b1*b2 - c1*c2 - 2*d1*d2) + sqrt(2)*(a1*b2 + b1*a2 - c1*d2 - d1*c2)
    // Im = (a1*c2 + 2*b1*d2 + c1*a2 + 2*d1*b2) + sqrt(2)*(a1*d2 + b1*c2 + c1*b2 + d1*a2)
    
    int64_t re_rat = sub(sub(add(mul(a, other.a), mul(2, mul(b, other.b))), mul(c, other.c)),
                         mul(2, mul(d, other.d)));
    int64_t re_sq2 = sub(sub(add(mul(a, other.b), mul(b, other.a)), mul(c, other.d)), mul(d, other.c));

    int64_t im_rat = add(add(add(mul(a, other.c), mul(2, mul(b, other.d))), mul(c, other.a)),
                         mul(2, mul(d, other.b)));
    int64_t im_sq2 = add(add(add(mul(a, other.d), mul(b, other.c)), mul(c, other.b)), mul(d, other.a));

    ExactRingElement res(re_rat, re_sq2, im_rat, im_sq2, add_u32(k, other.k));
    res.reduce();
    return res;
}

bool ExactRingElement::operator==(const ExactRingElement& other) const noexcept {
    ExactRingElement x = *this;
    ExactRingElement y = other;
    x.reduce();
    y.reduce();

    // Reduced forms are unique: sqrt(2) divides the numerator exactly when a
    // and c are both even, so the minimal k is canonical. Comparing reduced
    // forms needs no rescaling, which previously could overflow and was then
    // reported as "not equal".
    return x.a == y.a && x.b == y.b && x.c == y.c && x.d == y.d && x.k == y.k;
}

ExactRingElement ExactRingElement::conj() const {
    return ExactRingElement(a, b, neg(c), neg(d), k);
}

ExactRingElement ExactRingElement::norm_sq() const {
    ExactRingElement res = (*this) * this->conj();
    res.reduce();
    return res;
}

bool ExactRingElement::is_zero() const noexcept {
    ExactRingElement tmp = *this;
    tmp.reduce();
    return tmp.a == 0 && tmp.b == 0 && tmp.c == 0 && tmp.d == 0;
}

bool ExactRingElement::is_one() const noexcept {
    ExactRingElement tmp = *this;
    tmp.reduce();
    return tmp.a == 1 && tmp.b == 0 && tmp.c == 0 && tmp.d == 0 && tmp.k == 0;
}

// Approximate export only; never used for equality. ldexp keeps the scale
// finite where pow(sqrt2, k) overflows to infinity for large k.
static double inverse_sqrt2_power(uint32_t k) {
    const double half = std::ldexp(1.0, -static_cast<int>(k / 2));
    return (k % 2 == 1) ? half / SQRT2_D : half;
}

double ExactRingElement::to_double_re() const noexcept {
    return (static_cast<double>(a) + static_cast<double>(b) * SQRT2_D) * inverse_sqrt2_power(k);
}

double ExactRingElement::to_double_im() const noexcept {
    return (static_cast<double>(c) + static_cast<double>(d) * SQRT2_D) * inverse_sqrt2_power(k);
}

double ExactRingElement::to_probability() const noexcept {
    double r = to_double_re();
    double i = to_double_im();
    return r * r + i * i;
}

std::string ExactRingElement::to_string() const {
    std::ostringstream ss;
    ss << "[(" << a << " + " << b << "√2) + i(" << c << " + " << d << "√2)] / 2^(" << k << "/2)";
    return ss.str();
}

} // namespace algebra
} // namespace cqhecs
