#pragma once
#include <cstdint>
#include <array>
#include <cmath>
#include <numbers>

namespace cq_hecs {

/// @brief Fixed-Point Integer Phase Ring (Z_{2^32})
/// 2^32 corresponds to exactly 2*pi radians.
/// Arithmetic in this ring is mathematically closed, cyclic, and exact.
struct PhaseRingZ32 {
    static constexpr uint32_t ZERO       = 0x00000000u; // 0
    static constexpr uint32_t PI_OVER_4  = 0x20000000u; // pi/4  (T gate)
    static constexpr uint32_t PI_OVER_2  = 0x40000000u; // pi/2  (S gate)
    static constexpr uint32_t THREE_PI_4 = 0x60000000u; // 3pi/4
    static constexpr uint32_t PI_VAL     = 0x80000000u; // pi    (Z gate)
    static constexpr uint32_t FIVE_PI_4  = 0xA0000000u; // 5pi/4
    static constexpr uint32_t THREE_PI_2 = 0xC0000000u; // 3pi/2 (S-dagger)
    static constexpr uint32_t SEVEN_PI_4 = 0xE0000000u; // 7pi/4 (T-dagger)

    static inline uint32_t from_radians(double radians) {
        constexpr double TWO_PI = 6.28318530717958647692;
        double rem = std::fmod(radians, TWO_PI);
        if (rem < 0.0) rem += TWO_PI;
        double norm = rem / TWO_PI;
        return static_cast<uint32_t>(norm * 4294967296.0);
    }

    static inline double to_radians(uint32_t phase) {
        constexpr double TWO_PI = 6.28318530717958647692;
        return (static_cast<double>(phase) / 4294967296.0) * TWO_PI;
    }

    static constexpr uint32_t add(uint32_t a, uint32_t b) {
        return a + b;
    }

    static constexpr uint32_t sub(uint32_t a, uint32_t b) {
        return a - b;
    }

    static constexpr uint32_t negate(uint32_t a) {
        return 0u - a;
    }
};

/// @brief Complex amplitude in fixed-point representation (Real, Imag)
/// Represented as signed 64-bit integers with Q30 scaling
struct ComplexFixed {
    int64_t real = 0;
    int64_t imag = 0;

    static constexpr int64_t SCALE = 1LL << 30; // Q30 fixed point (1.0 == 2^30)

    constexpr bool operator==(const ComplexFixed& o) const = default;

    static inline ComplexFixed from_double(double r, double i) {
        return ComplexFixed{
            static_cast<int64_t>(std::round(r * static_cast<double>(SCALE))),
            static_cast<int64_t>(std::round(i * static_cast<double>(SCALE)))
        };
    }

    constexpr double to_double_real() const {
        return static_cast<double>(real) / static_cast<double>(SCALE);
    }

    constexpr double to_double_imag() const {
        return static_cast<double>(imag) / static_cast<double>(SCALE);
    }
};

/// @brief Bit-Exact Integer CORDIC Compute Engine
/// Operates directly on the Z_{2^32} phase ring and fixed-point coordinates.
/// Guarantees bit-exact reversibility U^\dagger U = I.
class CordicEngine {
public:
    static constexpr uint32_t CORDIC_ITERATIONS = 31;

    CordicEngine();

    /// @brief Rotate a 2D fixed-point vector (x, y) by angle in Z_{2^32}
    /// Forward rotation using reversible integer lifting micro-steps
    void rotate(int64_t& x, int64_t& y, uint32_t phase_angle) const;

    /// @brief Inverse rotate a 2D fixed-point vector (x, y) by angle in Z_{2^32}
    /// Bit-exact inverse satisfying rotate_inverse(rotate(x, y, theta), theta) == (x, y)
    void rotate_inverse(int64_t& x, int64_t& y, uint32_t phase_angle) const;

    /// @brief Rotate a complex amplitude by phase angle: z' = z * e^{i * theta}
    void phase_shift(ComplexFixed& z, uint32_t phase_angle) const;

    /// @brief Inverse rotate a complex amplitude: z' = z * e^{-i * theta}
    void phase_shift_inverse(ComplexFixed& z, uint32_t phase_angle) const;

    /// @brief Apply single-qubit Clifford+T gates bit-exactly
    void apply_pauli_x(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_pauli_y(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_pauli_z(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_hadamard(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_hadamard_inverse(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_s(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_s_dagger(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_t(ComplexFixed& amp0, ComplexFixed& amp1) const;
    void apply_t_dagger(ComplexFixed& amp0, ComplexFixed& amp1) const;

    /// @brief Arbitrary axis rotations Rx, Ry, Rz using CORDIC micro-rotations
    void apply_rx(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;
    void apply_rx_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;
    void apply_ry(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;
    void apply_ry_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;
    void apply_rz(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;
    void apply_rz_inverse(ComplexFixed& amp0, ComplexFixed& amp1, uint32_t phase_angle) const;

    /// @brief Get precomputed CORDIC angle table for Z_{2^32}
    static const std::array<uint32_t, CORDIC_ITERATIONS>& get_angle_lut();

private:
    static void init_lut();
    static bool s_lut_initialized;
    static std::array<uint32_t, CORDIC_ITERATIONS> s_angle_lut;
};

} // namespace cq_hecs
