#ifndef CQ_HECS_TRANSPILER_BYTECODE_HPP
#define CQ_HECS_TRANSPILER_BYTECODE_HPP

#include <cstdint>
#include <vector>
#include <string>

namespace cq_hecs {
namespace transpiler {

/**
 * @brief Opcodes for the J-Quantum Virtual Machine.
 */
enum class OpCode : uint8_t {
    NOP         = 0x00,
    H           = 0x01,
    X           = 0x02,
    Y           = 0x03,
    Z           = 0x04,
    S           = 0x05,
    SDG         = 0x06,
    T           = 0x07,
    TDG         = 0x08,
    RZ          = 0x09,
    RX          = 0x0A,
    RY          = 0x0B,
    CX          = 0x0C,
    SWAP        = 0x0D,
    MEASURE     = 0x0E,
    U3          = 0x0F,
    MCWF_DAMP   = 0x10,
    MCWF_DEPHASE= 0x11,
    BARRIER     = 0x12
};

enum OpFlags : uint8_t {
    FLAG_NONE    = 0x00,
    FLAG_FUSED   = 0x01,
    FLAG_INVERSE = 0x02,
    FLAG_NOISE   = 0x04,
    FLAG_ROUTED  = 0x08
};

/**
 * @brief 128-bit aligned J_QuantumOpcode struct (System Invariant).
 * Exactly 16 bytes.
 */
struct alignas(16) J_QuantumOpcode {
    uint8_t op_type{0};     // OpCode cast to uint8_t
    uint8_t target_q{0};    // Target qubit index (0-255)
    uint8_t control_q{0};   // Control qubit index (for 2-qubit operations)
    uint8_t flags{0};       // OpFlags bitmask
    uint32_t phase1{0};     // Primary phase angle in Z_{2^32}
    uint32_t phase2{0};     // Secondary phase angle in Z_{2^32} (for U3 phi)
    uint32_t phase3{0};     // Tertiary phase angle in Z_{2^32} (for U3 lambda) or padding

    constexpr J_QuantumOpcode() noexcept = default;

    constexpr J_QuantumOpcode(OpCode op, uint8_t target, uint8_t control = 0,
                             uint8_t f = FLAG_NONE, uint32_t p1 = 0,
                             uint32_t p2 = 0, uint32_t p3 = 0) noexcept
        : op_type(static_cast<uint8_t>(op)), target_q(target), control_q(control),
          flags(f), phase1(p1), phase2(p2), phase3(p3) {}

    OpCode get_opcode() const noexcept {
        return static_cast<OpCode>(op_type);
    }
};

static_assert(sizeof(J_QuantumOpcode) == 16, "J_QuantumOpcode must be exactly 128 bits (16 bytes)");

} // namespace transpiler
} // namespace cq_hecs

#endif // CQ_HECS_TRANSPILER_BYTECODE_HPP
