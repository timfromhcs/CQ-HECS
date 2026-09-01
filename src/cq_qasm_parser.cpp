#include "cq/qasm_parser.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>

namespace cq {

std::string Qasm3Parser::clean_line(const std::string& line) {
    std::string s = line;
    size_t cpos = s.find("//");
    if (cpos != std::string::npos) s = s.substr(0, cpos);
    cpos = s.find('#');
    if (cpos != std::string::npos) s = s.substr(0, cpos);
    size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    size_t last = s.find_last_not_of(" \t\r\n");
    return s.substr(first, last - first + 1);
}

std::vector<std::string> Qasm3Parser::tokenize(const std::string& stmt) {
    std::vector<std::string> tokens;
    std::string cur;
    for (char ch : stmt) {
        if (ch == ' ' || ch == '\t' || ch == ',' || ch == ';') {
            if (!cur.empty()) {
                tokens.push_back(cur);
                cur.clear();
            }
        } else {
            cur += ch;
        }
    }
    if (!cur.empty()) tokens.push_back(cur);
    return tokens;
}

double Qasm3Parser::parse_angle(const std::string& expr) {
    if (expr.empty()) return 0.0;
    const double PI_VAL = 3.14159265358979323846;
    if (expr == "pi") return PI_VAL;
    if (expr.find("pi/") != std::string::npos) {
        std::string d = expr.substr(expr.find("pi/") + 3);
        try {
            double denom = std::stod(d);
            if (denom != 0.0) return PI_VAL / denom;
        } catch (...) {}
    }
    try {
        return std::stod(expr);
    } catch (...) {
        return 0.0;
    }
}

uint32_t Qasm3Parser::parse_qubit_ref(const std::string& ref, const ParsedCircuit& circ) {
    size_t open_b = ref.find('[');
    if (open_b != std::string::npos) {
        std::string reg = ref.substr(0, open_b);
        size_t close_b = ref.find(']', open_b);
        std::string idx_str = ref.substr(open_b + 1, close_b - open_b - 1);
        uint32_t idx = static_cast<uint32_t>(std::stoul(idx_str));
        auto it = circ.qreg_offsets.find(reg);
        if (it != circ.qreg_offsets.end()) {
            return it->second + idx;
        }
        return idx;
    }
    auto it = circ.qreg_offsets.find(ref);
    if (it != circ.qreg_offsets.end()) return it->second;
    try {
        return static_cast<uint32_t>(std::stoul(ref));
    } catch (...) {
        return 0;
    }
}

uint32_t Qasm3Parser::parse_clbit_ref(const std::string& ref, const ParsedCircuit& circ) {
    size_t open_b = ref.find('[');
    if (open_b != std::string::npos) {
        std::string reg = ref.substr(0, open_b);
        size_t close_b = ref.find(']', open_b);
        std::string idx_str = ref.substr(open_b + 1, close_b - open_b - 1);
        uint32_t idx = static_cast<uint32_t>(std::stoul(idx_str));
        auto it = circ.creg_offsets.find(reg);
        if (it != circ.creg_offsets.end()) {
            return it->second + idx;
        }
        return idx;
    }
    auto it = circ.creg_offsets.find(ref);
    if (it != circ.creg_offsets.end()) return it->second;
    try {
        return static_cast<uint32_t>(std::stoul(ref));
    } catch (...) {
        return 0;
    }
}

ParsedCircuit Qasm3Parser::parse_string(const std::string& source) {
    ParsedCircuit circ;
    std::istringstream stream(source);
    std::string line;

    while (std::getline(stream, line)) {
        std::string clean = clean_line(line);
        if (clean.empty()) continue;

        // Split statements by semicolon
        std::stringstream ss(clean);
        std::string stmt;
        while (std::getline(ss, stmt, ';')) {
            std::string s = clean_line(stmt);
            if (s.empty()) continue;

            auto tokens = tokenize(s);
            if (tokens.empty()) continue;

            const std::string& op = tokens[0];

            if (op == "OPENQASM" || op == "include" || op == "barrier") {
                continue;
            }

            // Qubit register declaration: qubit[N] q; or qreg q[N];
            if (op.rfind("qubit[", 0) == 0 && tokens.size() >= 2) {
                size_t c_bracket = op.find(']');
                uint32_t count = std::stoul(op.substr(6, c_bracket - 6));
                std::string name = tokens[1];
                circ.qreg_offsets[name] = circ.num_qubits;
                circ.num_qubits += count;
                continue;
            }
            if (op == "qreg" && tokens.size() >= 2) {
                std::string ref = tokens[1];
                size_t o_b = ref.find('[');
                size_t c_b = ref.find(']');
                std::string name = ref.substr(0, o_b);
                uint32_t count = std::stoul(ref.substr(o_b + 1, c_b - o_b - 1));
                circ.qreg_offsets[name] = circ.num_qubits;
                circ.num_qubits += count;
                continue;
            }

            // Classical register declaration: bit[N] c; or creg c[N];
            if (op.rfind("bit[", 0) == 0 && tokens.size() >= 2) {
                size_t c_bracket = op.find(']');
                uint32_t count = std::stoul(op.substr(4, c_bracket - 4));
                std::string name = tokens[1];
                circ.creg_offsets[name] = circ.num_clbits;
                circ.num_clbits += count;
                continue;
            }
            if (op == "creg" && tokens.size() >= 2) {
                std::string ref = tokens[1];
                size_t o_b = ref.find('[');
                size_t c_b = ref.find(']');
                std::string name = ref.substr(0, o_b);
                uint32_t count = std::stoul(ref.substr(o_b + 1, c_b - o_b - 1));
                circ.creg_offsets[name] = circ.num_clbits;
                circ.num_clbits += count;
                continue;
            }

            // Gate parsing
            QasmInstruction inst;
            if (op == "h" && tokens.size() >= 2) {
                inst.type = GateType::H;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "s" && tokens.size() >= 2) {
                inst.type = GateType::S;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "sdg" && tokens.size() >= 2) {
                inst.type = GateType::SDG;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "t" && tokens.size() >= 2) {
                inst.type = GateType::T;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "tdg" && tokens.size() >= 2) {
                inst.type = GateType::TDG;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "x" && tokens.size() >= 2) {
                inst.type = GateType::X;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "y" && tokens.size() >= 2) {
                inst.type = GateType::Y;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "z" && tokens.size() >= 2) {
                inst.type = GateType::Z;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if ((op == "cx" || op == "cnot") && tokens.size() >= 3) {
                inst.type = GateType::CX;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
                inst.qubits.push_back(parse_qubit_ref(tokens[2], circ));
            } else if (op == "swap" && tokens.size() >= 3) {
                inst.type = GateType::SWAP;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
                inst.qubits.push_back(parse_qubit_ref(tokens[2], circ));
            } else if (op.rfind("rz(", 0) == 0 && tokens.size() >= 2) {
                inst.type = GateType::RZ;
                size_t c_p = op.find(')');
                std::string arg = op.substr(3, c_p - 3);
                inst.angle = parse_angle(arg);
                inst.angle_q32 = static_cast<uint32_t>((inst.angle / (2.0 * 3.141592653589793)) * 4294967296.0);
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
            } else if (op == "measure" && tokens.size() >= 4 && tokens[2] == "->") {
                inst.type = GateType::MEASURE;
                inst.qubits.push_back(parse_qubit_ref(tokens[1], circ));
                inst.clbits.push_back(parse_clbit_ref(tokens[3], circ));
            } else {
                continue;
            }

            circ.instructions.push_back(inst);
        }
    }

    return circ;
}

ParsedCircuit Qasm3Parser::parse_file(const std::string& filepath) {
    std::ifstream file(filepath);
    if (!file.is_open()) return ParsedCircuit();
    std::stringstream buffer;
    buffer << file.rdbuf();
    return parse_string(buffer.str());
}

} // namespace cq
