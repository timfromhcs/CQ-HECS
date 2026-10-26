// Contract tests for the CPU reference facade `cq_hecs::core::VulkanQpuEngine`.
//
// The historical defects here were (a) measurement opcodes being fed to the
// gate loop as if they were gates, and (b) silent success for unsupported
// operations. These tests pin the current contract:
//   * terminal MEASURE opcodes are accepted and do not mutate the state;
//   * gates after a measurement (mid-circuit measurement) are rejected;
//   * unsupported opcodes throw instead of being skipped;
//   * sampling draws from the evolved state and sums to the requested shots.

#ifdef NDEBUG
#undef NDEBUG
#endif

#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "cq_hecs/core/qpu_engine.hpp"

using cq_hecs::core::VulkanQpuEngine;
using cq_hecs::transpiler::FLAG_NONE;
using cq_hecs::transpiler::J_QuantumOpcode;
using cq_hecs::transpiler::OpCode;

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::abort();
    }
}

uint64_t total_shots(const std::map<std::string, uint32_t>& counts) {
    uint64_t total = 0;
    for (const auto& [bits, count] : counts) total += count;
    return total;
}

bool throws_invalid_argument(const std::vector<J_QuantumOpcode>& opcodes) {
    VulkanQpuEngine engine(3, 16);
    try {
        engine.execute_bytecode(opcodes);
    } catch (const std::invalid_argument&) {
        return true;
    }
    return false;
}

void test_statevector_measurement_is_terminal() {
    VulkanQpuEngine engine(3, 16);
    std::vector<J_QuantumOpcode> opcodes;
    opcodes.emplace_back(OpCode::H, uint8_t{0});
    opcodes.emplace_back(OpCode::CX, uint8_t{1}, uint8_t{0});
    opcodes.emplace_back(OpCode::MEASURE, uint8_t{0});
    opcodes.emplace_back(OpCode::MEASURE, uint8_t{1});
    opcodes.emplace_back(OpCode::MEASURE, uint8_t{2});
    engine.execute_bytecode(opcodes);  // must not throw

    const auto counts = engine.sample_counts(4096, 12345);
    require(total_shots(counts) == 4096, "sample_counts must sum to the requested shots");
    require(counts.size() == 2, "Bell pair with an idle third qubit has exactly two outcomes");
    for (const auto& [bits, count] : counts) {
        require(bits.size() == 3, "bitstring width must match the register width");
        require(count > 0, "reported counts must be positive");
        require(bits[0] == '0', "the idle qubit must remain |0> (qubit 0 is printed last)");
        require(bits[1] == bits[2], "Bell-pair bits must agree");
    }
}

void test_mid_circuit_measurement_is_rejected() {
    require(throws_invalid_argument({J_QuantumOpcode(OpCode::H, uint8_t{0}),
                                     J_QuantumOpcode(OpCode::MEASURE, uint8_t{0}),
                                     J_QuantumOpcode(OpCode::X, uint8_t{0})}),
            "a gate after MEASURE must be rejected as mid-circuit measurement");
}

void test_unsupported_opcode_is_rejected() {
    require(throws_invalid_argument(
                {J_QuantumOpcode(OpCode::RX, uint8_t{0}, uint8_t{0}, FLAG_NONE,
                                 0x10000000u)}),
            "unsupported opcode must throw instead of being silently skipped");
}

void test_mps_measurement_is_terminal() {
    // 256 qubits is the largest register addressable by the 8-bit
    // J_QuantumOpcode index fields.
    constexpr uint32_t kQubits = 256;
    VulkanQpuEngine engine(kQubits, 64);
    std::vector<J_QuantumOpcode> opcodes;
    opcodes.reserve(kQubits);
    opcodes.emplace_back(OpCode::H, uint8_t{0});
    for (uint32_t i = 0; i + 1 < kQubits; ++i) {
        opcodes.emplace_back(OpCode::CX, static_cast<uint8_t>(i + 1),
                             static_cast<uint8_t>(i));
    }
    for (uint32_t i = 0; i < kQubits; ++i) {
        opcodes.emplace_back(OpCode::MEASURE, static_cast<uint8_t>(i));
    }
    engine.execute_bytecode(opcodes);  // must not throw

    const auto counts = engine.sample_counts(256, 7);
    require(total_shots(counts) == 256, "MPS sample_counts must sum to the requested shots");
    require(counts.size() == 2, "GHZ-256 must yield exactly the all-zero/all-one outcomes");
    for (const auto& [bits, count] : counts) {
        (void)count;
        require(bits.size() == kQubits, "GHZ-256 bitstrings must be 256 bits wide");
        require(bits == std::string(kQubits, '0') || bits == std::string(kQubits, '1'),
                "GHZ-256 outcomes must be fully correlated");
    }
}

void test_unaddressable_qubit_index_is_rejected() {
    // The bytecode stores qubit indices in uint8_t. A q[256] operand must be
    // rejected instead of wrapping to q[0] and silently corrupting the circuit.
    VulkanQpuEngine engine(300, 64);
    bool threw = false;
    try {
        engine.execute_qasm(
            "OPENQASM 3.0;\nqubit[257] q;\nh q[256];\n");
    } catch (const std::out_of_range&) {
        threw = true;
    }
    require(threw, "qubit index 256 must be rejected, not truncated to 8 bits");
}

}  // namespace

int main() {
    test_statevector_measurement_is_terminal();
    test_mid_circuit_measurement_is_rejected();
    test_unsupported_opcode_is_rejected();
    test_mps_measurement_is_terminal();
    test_unaddressable_qubit_index_is_rejected();
    std::cout << "QPU reference facade contract: all checks passed" << std::endl;
    return 0;
}
