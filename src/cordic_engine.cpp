#include "cq_hecs/cordic_engine.hpp"
#include <cmath>
#include <numbers>

namespace cq_hecs {

bool CordicEngine::s_lut_initialized = false;
std::array<uint32_t, CordicEngine::CORDIC_ITERATIONS> CordicEngine::s_angle_lut{};

void CordicEngine::init_lut() {
    if (s_lut_initialized) return;
    for (uint32_t i = 0; i < CORDIC_ITERATIONS; ++i) {
        double tan_val = std::pow(2.0, -static_cast<double>(i));
        double angle_rad = std::atan(tan_val);
        s_angle_lut[i] = PhaseRingZ32::from_radians(angle_rad);
    }
    s_lut_initialized = true;
}

const std::array<uint32_t, CordicEngine::CORDIC_ITERATIONS>& CordicEngine::get_angle_lut() {
    init_lut();
    return s_angle_lut;
}

CordicEngine::CordicEngine() {
    init_lut();
}

static inline int64_t fixed_mul(int64_t a, int64_t b) {
    // Q30 * Q30 -> Q30
    return (a * b) >> 30;
}

// Compute exact reversible lifting factors p = tan(theta/2) and q = sin(theta)
static inline void get_lifting_factors(double theta, int64_t& out_p, int64_t& out_q) {
    double tan_half = std::tan(theta / 2.0);
    double sin_val = std::sin(theta);
    out_p = static_cast<int64_t>(std::round(tan_half * static_cast<double>(ComplexFixed::SCALE)));
    out_q = static_cast<int64_t>(std::round(sin_val * static_cast<double>(ComplexFixed::SCALE)));
}

void CordicEngine::rotate(int64_t& x, int64_t& y, uint32_t phase_angle) const {
    if (phase_angle == 0) return;

    // Handle quadrant reductions bit-exactly
    uint32_t quad = phase_angle >> 30; // Top 2 bits: 0, 1, 2, 3
    uint32_t rem_phase = phase_angle & 0x3FFFFFFFu;

    // Quadrant shift
    if (quad == 1) {
        // +90 deg: (x, y) -> (-y, x)
        int64_t tx = x;
        x = -y;
        y = tx;
    } else if (quad == 2) {
        // +180 deg: (x, y) -> (-x, -y)
        x = -x;
        y = -y;
    } else if (quad == 3) {
        // +270 deg: (x, y) -> (y, -x)
        int64_t tx = x;
        x = y;
        y = -tx;
    }

    if (rem_phase == 0) return;

    double theta = PhaseRingZ32::to_radians(rem_phase);
    int64_t p = 0, q = 0;
    get_lifting_factors(theta, p, q);

    // 3-step reversible integer lifting:
    // 1. x1 = x0 - (y0 * p) / SCALE
    // 2. y1 = y0 + (x1 * q) / SCALE
    // 3. x2 = x1 - (y1 * p) / SCALE
    x -= fixed_mul(y, p);
    y += fixed_mul(x, q);
    x -= fixed_mul(y, p);
}

void CordicEngine::rotate_inverse(int64_t& x, int64_t& y, uint32_t phase_angle) const {
    if (phase_angle == 0) return;

    uint32_t quad = phase_angle >> 30;
    uint32_t rem_phase = phase_angle & 0x3FFFFFFFu;

    if (rem_phase != 0) {
        double theta = PhaseRingZ32::to_radians(rem_phase);
        int64_t p = 0, q = 0;
        get_lifting_factors(theta, p, q);

        // Exact inverse lifting in reverse order:
        // 1. x1 = x2 + (y1 * p) / SCALE
        // 2. y0 = y1 - (x1 * q) / SCALE
        // 3. x0 = x1 + (y0 * p) / SCALE
        x += fixed_mul(y, p);
        y -= fixed_mul(x, q);
        x += fixed_mul(y, p);
    }

    // Inverse quadrant shift
    if (quad == 1) {
        // Inverse of +90 is -90 (+270): (x, y) -> (y, -x)
        int64_t tx = x;
        x = y;
        y = -tx;
    } else if (quad == 2) {
        // Inverse of +180 is +180: (x, y) -> (-x, -y)
        x = -x;
        y = -y;
    } else if (quad == 3) {
        // Inverse of +270 is +90: (x, y) -> (-y, x)
        int64_t tx = x;
        x = -y;
        y = tx;
    }
}

void CordicEngine::phase_shift(ComplexFixed& z, uint32_t phase_angle) const {
    // z' = z * e^{i * theta}
    // (real + i * imag) * (cos + i * sin) = (real*cos - imag*sin) + i*(real*sin + imag*cos)
    // Exactly 2D rotation of (real, imag) by phase_angle!
    rotate(z.real, z.imag, phase_angle);
}

void CordicEngine::phase_shift_inverse(ComplexFixed& z, uint32_t phase_angle) const {
    rotate_inverse(z.real, z.imag, phase_angle);
}

void CordicEngine::apply_pauli_x(ComplexFixed& amp0, ComplexFixed& amp1) const {
    std::swap(amp0, amp1);
}

void CordicEngine::apply_pauli_y(ComplexFixed& amp0, ComplexFixed& amp1) const {
    // Y |0> = i |1>, Y |1> = -i |0>
    ComplexFixed old0 = amp0;
    // amp0 = -i * amp1 = (amp1.imag, -amp1.real)
    amp0.real = amp1.imag;
    amp0.imag = -amp1.real;
    // amp1 = i * old0 = (-old0.imag, old0.real)
    amp1.real = -old0.imag;
    amp1.imag = old0.real;
}

void CordicEngine::apply_pauli_z(ComplexFixed& /*amp0*/, ComplexFixed& amp1) const {
    amp1.real = -amp1.real;
    amp1.imag = -amp1.imag;
}

void CordicEngine::apply_s(ComplexFixed& /*amp0*/, ComplexFixed& amp1) const {
    phase_shift(amp1, PhaseRingZ32::PI_OVER_2);
}

void CordicEngine::apply_s_dagger(ComplexFixed& /*amp0*/, ComplexFixed& amp1) const {
    phase_shift_inverse(amp1, PhaseRingZ32::PI_OVER_2);
}

void CordicEngine::apply_t(ComplexFixed& /*amp0*/, ComplexFixed& amp1) const {
    phase_shift(amp1, PhaseRingZ32::PI_OVER_4);
}

void CordicEngine::apply_t_dagger(ComplexFixed& /*amp0*/, ComplexFixed& amp1) const {
    phase_shift_inverse(amp1, PhaseRingZ32::PI_OVER_4);
}

void CordicEngine::apply_hadamard(ComplexFixed& amp0, ComplexFixed& amp1) const {
    // Hadamard H = (X + Z) / sqrt(2)
    // In reversible integer lifting:
    // H = R_y(pi/2) followed by Pauli Z
    apply_ry(amp0, amp1, PhaseRingZ32::PI_OVER_2);
    apply_pauli_z(amp0, amp1);
}

void CordicEngine::apply_hadamard_inverse(ComplexFixed& amp0, ComplexFixed& amp1) const {
    // Inverse of H: H^\dagger = H
    // Reverse order of operations: Z then Ry_inverse(pi/2)
    apply_pauli_z(amp0, amp1);
    apply_ry_inverse(amp0, amp1, PhaseRingZ32::PI_OVER_2);
}

void CordicEngine::apply_rx(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    // Rx(theta) = cos(theta/2) I - i sin(theta/2) X
    // Rotates (amp0.real, -amp1.imag) and (amp0.imag, amp1.real)
    uint32_t half_angle = phase_angle >> 1;
    // real parts mix with -imag parts
    rotate(amp0.real, amp1.imag, half_angle);
    rotate(amp1.real, amp0.imag, half_angle);
}

void CordicEngine::apply_rx_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    uint32_t half_angle = phase_angle >> 1;
    rotate_inverse(amp1.real, amp0.imag, half_angle);
    rotate_inverse(amp0.real, amp1.imag, half_angle);
}

void CordicEngine::apply_ry(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    // Ry(theta) = cos(theta/2) I - sin(theta/2) Y
    // Rotates (amp0.real, amp1.real) and (amp0.imag, amp1.imag)
    uint32_t half_angle = phase_angle >> 1;
    rotate(amp0.real, amp1.real, half_angle);
    rotate(amp0.imag, amp1.imag, half_angle);
}

void CordicEngine::apply_ry_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    uint32_t half_angle = phase_angle >> 1;
    rotate_inverse(amp0.imag, amp1.imag, half_angle);
    rotate_inverse(amp0.real, amp1.real, half_angle);
}

void CordicEngine::apply_rz(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    // Rz(theta): amp0 -> amp0 * e^{-i theta/2}, amp1 -> amp1 * e^{+i theta/2}
    uint32_t half_angle = phase_angle >> 1;
    phase_shift_inverse(amp0, half_angle);
    phase_shift(amp1, half_angle);
}

void CordicEngine::apply_rz_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const {
    uint32_t half_angle = phase_angle >> 1;
    phase_shift_inverse(amp1, half_angle);
    phase_shift(amp0, half_angle);
}

} // namespace cq_hecs
