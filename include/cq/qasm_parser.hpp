#ifndef CQ_QASM_PARSER_HPP
#define CQ_QASM_PARSER_HPP

#include <string>
#include <vector>
#include <cstdint>
#include <unordered_map>
#include <memory>

namespace cq {

enum class GateType {
    H,
    S,
    SDG,
    T,
    TDG,
    X,
    Y,
    Z,
    CX,
    SWAP,
    RZ,
    RX,
    RY,
    MEASURE,
    BARRIER
};

struct QasmInstruction {
    GateType type;
    std::vector<uint32_t> qubits;
    std::vector<uint32_t> clbits;
    double angle{0.0};
    uint32_t angle_q32{0}; // Phase in Z_{2^32}
};

struct ParsedCircuit {
    uint32_t num_qubits{0};
    uint32_t num_clbits{0};
    std::vector<QasmInstruction> instructions;
    std::unordered_map<std::string, uint32_t> qreg_offsets;
    std::unordered_map<std::string, uint32_t> creg_offsets;

    bool is_pure_clifford() const noexcept {
        for (const auto& inst : instructions) {
            if (inst.type == GateType::T || inst.type == GateType::TDG ||
                inst.type == GateType::RZ || inst.type == GateType::RX ||
                inst.type == GateType::RY) {
                return false;
            }
        }
        return true;
    }
};

class Qasm3Parser {
public:
    static ParsedCircuit parse_string(const std::string& source);
    static ParsedCircuit parse_file(const std::string& filepath);

private:
    static std::string clean_line(const std::string& line);
    static std::vector<std::string> tokenize(const std::string& stmt);
    static uint32_t parse_qubit_ref(const std::string& ref, const ParsedCircuit& circ);
    static uint32_t parse_clbit_ref(const std::string& ref, const ParsedCircuit& circ);
    static double parse_angle(const std::string& expr);
};

} // namespace cq

#endif // CQ_QASM_PARSER_HPP
