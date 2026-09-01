#ifndef CQ_HECS_TRANSPILER_QASM3_PARSER_HPP
#define CQ_HECS_TRANSPILER_QASM3_PARSER_HPP

#include "bytecode.hpp"
#include "../core/cordic.hpp"
#include <string>
#include <vector>
#include <sstream>
#include <unordered_map>
#include <cctype>
#include <algorithm>
#include <stdexcept>
#include <cmath>

namespace cq_hecs {
namespace transpiler {

/**
 * @brief Parsed Quantum Circuit representation.
 */
struct QuantumCircuit {
    uint32_t num_qubits{0};
    uint32_t num_clbits{0};
    std::vector<J_QuantumOpcode> opcodes;
    std::unordered_map<std::string, uint32_t> qubit_map;
    std::unordered_map<std::string, uint32_t> clbit_map;

    void add_op(J_QuantumOpcode op) {
        opcodes.push_back(op);
    }
};

/**
 * @brief Robust OpenQASM 3.0 & 2.0 Lexer and Parser.
 */
class Qasm3Parser {
public:
    static QuantumCircuit parse(const std::string& qasm_source) {
        QuantumCircuit circuit;
        std::istringstream stream(qasm_source);
        std::string line;

        while (std::getline(stream, line)) {
            // Strip comments
            size_t comment_pos = line.find("//");
            if (comment_pos != std::string::npos) {
                line = line.substr(0, comment_pos);
            }
            comment_pos = line.find('#');
            if (comment_pos != std::string::npos) {
                line = line.substr(0, comment_pos);
            }

            // Trim leading/trailing whitespace
            line = trim(line);
            if (line.empty()) continue;

            // Handle multi-statement lines split by ';'
            std::vector<std::string> statements = split_statements(line);
            for (auto& stmt : statements) {
                stmt = trim(stmt);
                if (!stmt.empty()) {
                    parse_statement(stmt, circuit);
                }
            }
        }

        if (circuit.num_qubits == 0 && !circuit.qubit_map.empty()) {
            circuit.num_qubits = static_cast<uint32_t>(circuit.qubit_map.size());
        }

        return circuit;
    }

private:
    static std::string trim(const std::string& s) {
        size_t start = s.find_first_not_of(" \t\r\n");
        if (start == std::string::npos) return "";
        size_t end = s.find_last_not_of(" \t\r\n");
        return s.substr(start, end - start + 1);
    }

    static std::vector<std::string> split_statements(const std::string& line) {
        std::vector<std::string> stmts;
        std::string cur;
        for (char c : line) {
            if (c == ';') {
                stmts.push_back(cur);
                cur.clear();
            } else {
                cur += c;
            }
        }
        if (!cur.empty()) {
            stmts.push_back(cur);
        }
        return stmts;
    }

    static uint32_t parse_angle_expr(const std::string& expr) {
        std::string e = trim(expr);
        if (e.empty()) return 0;

        constexpr double PI_VAL = 3.14159265358979323846;
        double sign = 1.0;
        if (e.front() == '-') {
            sign = -1.0;
            e = trim(e.substr(1));
        } else if (e.front() == '+') {
            e = trim(e.substr(1));
        }

        double val = 0.0;
        if (e == "pi") {
            val = PI_VAL;
        } else if (e.find("pi/") != std::string::npos) {
            size_t idx = e.find("pi/");
            std::string denom_str = trim(e.substr(idx + 3));
            double denom = std::stod(denom_str);
            val = (denom != 0.0) ? (PI_VAL / denom) : 0.0;
        } else if (e.find("*pi/") != std::string::npos) {
            size_t mul_idx = e.find("*pi/");
            std::string num_str = trim(e.substr(0, mul_idx));
            std::string denom_str = trim(e.substr(mul_idx + 4));
            double num = std::stod(num_str);
            double denom = std::stod(denom_str);
            val = (denom != 0.0) ? ((num * PI_VAL) / denom) : 0.0;
        } else if (e.find("*pi") != std::string::npos) {
            size_t idx = e.find("*pi");
            std::string factor_str = trim(e.substr(0, idx));
            double factor = std::stod(factor_str);
            val = factor * PI_VAL;
        } else {
            try {
                val = std::stod(e);
            } catch (...) {
                val = 0.0;
            }
        }

        return core::radians_to_z32(sign * val);
    }

    static uint32_t get_or_register_qubit(const std::string& q_str, QuantumCircuit& circuit) {
        std::string name = trim(q_str);
        auto it = circuit.qubit_map.find(name);
        if (it != circuit.qubit_map.end()) {
            return it->second;
        }

        // Try extracting index from format name[idx]
        size_t b_open = name.find('[');
        size_t b_close = name.find(']');
        if (b_open != std::string::npos && b_close != std::string::npos && b_close > b_open) {
            std::string num_str = name.substr(b_open + 1, b_close - b_open - 1);
            try {
                uint32_t idx = static_cast<uint32_t>(std::stoul(num_str));
                circuit.qubit_map[name] = idx;
                if (idx + 1 > circuit.num_qubits) {
                    circuit.num_qubits = idx + 1;
                }
                return idx;
            } catch (...) {}
        }

        uint32_t new_idx = static_cast<uint32_t>(circuit.qubit_map.size());
        circuit.qubit_map[name] = new_idx;
        if (new_idx + 1 > circuit.num_qubits) {
            circuit.num_qubits = new_idx + 1;
        }
        return new_idx;
    }

    static void parse_statement(const std::string& stmt, QuantumCircuit& circuit) {
        if (stmt.rfind("OPENQASM", 0) == 0 || stmt.rfind("include", 0) == 0) {
            return;
        }

        std::istringstream ss(stmt);
        std::string token;
        ss >> token;

        // Register declarations
        // OpenQASM 3.0: qubit[N] q; bit[N] c;
        // OpenQASM 2.0: qreg q[N]; creg c[N];
        if (token.rfind("qubit[", 0) == 0 || token == "qreg") {
            if (token == "qreg") {
                std::string reg;
                ss >> reg;
                size_t b_open = reg.find('[');
                size_t b_close = reg.find(']');
                if (b_open != std::string::npos && b_close != std::string::npos) {
                    uint32_t n = static_cast<uint32_t>(std::stoul(reg.substr(b_open + 1, b_close - b_open - 1)));
                    circuit.num_qubits = std::max(circuit.num_qubits, n);
                }
            } else {
                size_t b_open = token.find('[');
                size_t b_close = token.find(']');
                if (b_open != std::string::npos && b_close != std::string::npos) {
                    uint32_t n = static_cast<uint32_t>(std::stoul(token.substr(b_open + 1, b_close - b_open - 1)));
                    circuit.num_qubits = std::max(circuit.num_qubits, n);
                }
            }
            return;
        }

        if (token.rfind("bit[", 0) == 0 || token == "creg") {
            if (token == "creg") {
                std::string reg;
                ss >> reg;
                size_t b_open = reg.find('[');
                size_t b_close = reg.find(']');
                if (b_open != std::string::npos && b_close != std::string::npos) {
                    uint32_t n = static_cast<uint32_t>(std::stoul(reg.substr(b_open + 1, b_close - b_open - 1)));
                    circuit.num_clbits = std::max(circuit.num_clbits, n);
                }
            } else {
                size_t b_open = token.find('[');
                size_t b_close = token.find(']');
                if (b_open != std::string::npos && b_close != std::string::npos) {
                    uint32_t n = static_cast<uint32_t>(std::stoul(token.substr(b_open + 1, b_close - b_open - 1)));
                    circuit.num_clbits = std::max(circuit.num_clbits, n);
                }
            }
            return;
        }

        if (token == "barrier") {
            return;
        }

        // Measure statement: measure q[0] -> c[0];
        if (token == "measure") {
            std::string q_arg, arrow, c_arg;
            ss >> q_arg >> arrow >> c_arg;
            uint32_t q = get_or_register_qubit(q_arg, circuit);
            circuit.add_op(J_QuantumOpcode(OpCode::MEASURE, static_cast<uint8_t>(q)));
            return;
        }

        // Gate with parameters, e.g., rz(pi/4) q[0]; or u3(theta, phi, lambda) q[0];
        std::string gate_name = token;
        std::vector<uint32_t> parsed_angles;

        size_t paren_open = token.find('(');
        if (paren_open != std::string::npos) {
            gate_name = token.substr(0, paren_open);
            size_t paren_close = stmt.find(')', paren_open);
            if (paren_close != std::string::npos) {
                std::string params_str = stmt.substr(paren_open + 1, paren_close - paren_open - 1);
                std::stringstream p_ss(params_str);
                std::string p_tok;
                while (std::getline(p_ss, p_tok, ',')) {
                    parsed_angles.push_back(parse_angle_expr(p_tok));
                }
                // Advance ss past the closing paren
                std::string rest = trim(stmt.substr(paren_close + 1));
                ss = std::istringstream(rest);
            }
        }

        std::string args_str;
        std::getline(ss, args_str);
        args_str = trim(args_str);

        // Parse comma-separated qubit arguments
        std::vector<uint32_t> qubits;
        std::stringstream a_ss(args_str);
        std::string arg;
        while (std::getline(a_ss, arg, ',')) {
            arg = trim(arg);
            if (!arg.empty()) {
                qubits.push_back(get_or_register_qubit(arg, circuit));
            }
        }

        if (qubits.empty()) return;

        // Map gate name to OpCode
        std::string g_lower = gate_name;
        std::transform(g_lower.begin(), g_lower.end(), g_lower.begin(), ::tolower);

        if (g_lower == "h") {
            circuit.add_op(J_QuantumOpcode(OpCode::H, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "x") {
            circuit.add_op(J_QuantumOpcode(OpCode::X, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "y") {
            circuit.add_op(J_QuantumOpcode(OpCode::Y, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "z") {
            circuit.add_op(J_QuantumOpcode(OpCode::Z, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "s") {
            circuit.add_op(J_QuantumOpcode(OpCode::S, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "sdg") {
            circuit.add_op(J_QuantumOpcode(OpCode::SDG, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "t") {
            circuit.add_op(J_QuantumOpcode(OpCode::T, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "tdg") {
            circuit.add_op(J_QuantumOpcode(OpCode::TDG, static_cast<uint8_t>(qubits[0])));
        } else if (g_lower == "rz") {
            uint32_t p = parsed_angles.empty() ? 0 : parsed_angles[0];
            circuit.add_op(J_QuantumOpcode(OpCode::RZ, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, p));
        } else if (g_lower == "rx") {
            uint32_t p = parsed_angles.empty() ? 0 : parsed_angles[0];
            circuit.add_op(J_QuantumOpcode(OpCode::RX, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, p));
        } else if (g_lower == "ry") {
            uint32_t p = parsed_angles.empty() ? 0 : parsed_angles[0];
            circuit.add_op(J_QuantumOpcode(OpCode::RY, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, p));
        } else if (g_lower == "cx" || g_lower == "cnot") {
            if (qubits.size() >= 2) {
                circuit.add_op(J_QuantumOpcode(OpCode::CX, static_cast<uint8_t>(qubits[1]), static_cast<uint8_t>(qubits[0])));
            }
        } else if (g_lower == "swap") {
            if (qubits.size() >= 2) {
                circuit.add_op(J_QuantumOpcode(OpCode::SWAP, static_cast<uint8_t>(qubits[1]), static_cast<uint8_t>(qubits[0])));
            }
        } else if (g_lower == "u" || g_lower == "u3") {
            uint32_t theta = (parsed_angles.size() > 0) ? parsed_angles[0] : 0;
            uint32_t phi   = (parsed_angles.size() > 1) ? parsed_angles[1] : 0;
            uint32_t lam   = (parsed_angles.size() > 2) ? parsed_angles[2] : 0;
            circuit.add_op(J_QuantumOpcode(OpCode::U3, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, theta, phi, lam));
        } else if (g_lower == "u1") {
            uint32_t lam = parsed_angles.empty() ? 0 : parsed_angles[0];
            circuit.add_op(J_QuantumOpcode(OpCode::RZ, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, lam));
        } else if (g_lower == "u2") {
            uint32_t phi = (parsed_angles.size() > 0) ? parsed_angles[0] : 0;
            uint32_t lam = (parsed_angles.size() > 1) ? parsed_angles[1] : 0;
            // U2(phi, lambda) = RZ(phi) * RY(pi/2) * RZ(lambda)
            constexpr uint32_t PI_HALF = 0x40000000;
            circuit.add_op(J_QuantumOpcode(OpCode::RZ, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, lam));
            circuit.add_op(J_QuantumOpcode(OpCode::RY, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, PI_HALF));
            circuit.add_op(J_QuantumOpcode(OpCode::RZ, static_cast<uint8_t>(qubits[0]), 0, FLAG_NONE, phi));
        }
    }
};

} // namespace transpiler
} // namespace cq_hecs

#endif // CQ_HECS_TRANSPILER_QASM3_PARSER_HPP
