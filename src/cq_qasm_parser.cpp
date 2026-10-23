#include "cq/qasm_parser.hpp"
#include "qasm_angle.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <cmath>
#include <cctype>
#include <algorithm>
#include <unordered_map>

namespace cq {

namespace {

constexpr size_t kMaxSourceBytes = 16u * 1024u * 1024u;
constexpr size_t kMaxLineBytes = 1u * 1024u * 1024u;
constexpr uint32_t kMaxRegisterSize = 1u << 20;

std::string trim(const std::string& str) {
    const size_t first = str.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    const size_t last = str.find_last_not_of(" \t\r\n");
    return str.substr(first, last - first + 1);
}

struct GateSpec {
    GateType type;
    int qubits;
    int params;
};

// The C-ABI parser accepts only gates the hybrid engine actually implements.
// Unknown names are errors; they are never skipped as identities.
const std::unordered_map<std::string, GateSpec>& gate_specs() {
    static const std::unordered_map<std::string, GateSpec> specs = {
        {"h", {GateType::H, 1, 0}},     {"s", {GateType::S, 1, 0}},
        {"sdg", {GateType::SDG, 1, 0}}, {"t", {GateType::T, 1, 0}},
        {"tdg", {GateType::TDG, 1, 0}}, {"x", {GateType::X, 1, 0}},
        {"y", {GateType::Y, 1, 0}},     {"z", {GateType::Z, 1, 0}},
        {"rz", {GateType::RZ, 1, 1}},   {"cx", {GateType::CX, 2, 0}},
        {"cnot", {GateType::CX, 2, 0}},
    };
    return specs;
}

}  // namespace

std::string Qasm3Parser::clean_line(const std::string& line) {
    std::string s = line;
    const size_t cpos = s.find("//");
    if (cpos != std::string::npos) s = s.substr(0, cpos);
    const size_t first = s.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    const size_t last = s.find_last_not_of(" \t\r\n");
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
    double value = 0.0;
    cq_hecs::AngleExpression evaluator(expr);
    return evaluator.evaluate(value) ? value : 0.0;
}

uint32_t Qasm3Parser::parse_qubit_ref(const std::string& ref, const ParsedCircuit& circ) {
    const size_t open_b = ref.find('[');
    if (open_b != std::string::npos) {
        const std::string reg = ref.substr(0, open_b);
        const size_t close_b = ref.find(']', open_b);
        if (close_b == std::string::npos) return UINT32_MAX;
        const std::string idx_str = ref.substr(open_b + 1, close_b - open_b - 1);
        const auto off_it = circ.qreg_offsets.find(reg);
        const auto size_it = circ.qreg_sizes.find(reg);
        if (off_it == circ.qreg_offsets.end() || size_it == circ.qreg_sizes.end()) {
            return UINT32_MAX;
        }
        try {
            const unsigned long idx = std::stoul(idx_str);
            if (idx >= size_it->second) return UINT32_MAX;
            return off_it->second + static_cast<uint32_t>(idx);
        } catch (...) {
            return UINT32_MAX;
        }
    }
    return UINT32_MAX;
}

uint32_t Qasm3Parser::parse_clbit_ref(const std::string& ref, const ParsedCircuit& circ) {
    const size_t open_b = ref.find('[');
    if (open_b != std::string::npos) {
        const std::string reg = ref.substr(0, open_b);
        const size_t close_b = ref.find(']', open_b);
        if (close_b == std::string::npos) return UINT32_MAX;
        const std::string idx_str = ref.substr(open_b + 1, close_b - open_b - 1);
        const auto off_it = circ.creg_offsets.find(reg);
        const auto size_it = circ.creg_sizes.find(reg);
        if (off_it == circ.creg_offsets.end() || size_it == circ.creg_sizes.end()) {
            return UINT32_MAX;
        }
        try {
            const unsigned long idx = std::stoul(idx_str);
            if (idx >= size_it->second) return UINT32_MAX;
            return off_it->second + static_cast<uint32_t>(idx);
        } catch (...) {
            return UINT32_MAX;
        }
    }
    return UINT32_MAX;
}

ParsedCircuit Qasm3Parser::parse_string(const std::string& source) {
    ParsedCircuit circ;

    if (source.size() > kMaxSourceBytes) {
        circ.errors.push_back("input exceeds the maximum supported QASM size");
        return circ;
    }

    std::istringstream stream(source);
    std::string line;
    int line_number = 0;

    while (std::getline(stream, line)) {
        ++line_number;
        if (line.size() > kMaxLineBytes) {
            circ.errors.push_back("line " + std::to_string(line_number) +
                                  ": line exceeds the maximum supported length");
            continue;
        }

        const std::string clean = clean_line(line);
        if (clean.empty()) continue;

        if (clean.back() != ';') {
            circ.errors.push_back("line " + std::to_string(line_number) +
                                  ": missing ';' terminator");
            continue;
        }

        std::stringstream ss(clean);
        std::string stmt;
        while (std::getline(ss, stmt, ';')) {
            const std::string s = clean_line(stmt);
            if (s.empty()) continue;

            auto tokens = tokenize(s);
            if (tokens.empty()) continue;

            const std::string& op_raw = tokens[0];
            std::string op = op_raw;
            std::transform(op.begin(), op.end(), op.begin(),
                           [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

            if (op == "openqasm" || op == "include" || op == "barrier") {
                continue;
            }

            // Register declarations: ``qreg q[N];`` or ``qubit[N] q;``.
            if ((op == "qreg" || op == "creg") && tokens.size() >= 2) {
                const std::string& ref = tokens[1];
                const size_t o_b = ref.find('[');
                const size_t c_b = ref.find(']');
                if (o_b == std::string::npos || c_b == std::string::npos || c_b < o_b) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": malformed register declaration: " + s);
                    continue;
                }
                const std::string name = ref.substr(0, o_b);
                uint32_t count = 0;
                try {
                    const unsigned long parsed =
                        std::stoul(ref.substr(o_b + 1, c_b - o_b - 1));
                    if (parsed == 0 || parsed > kMaxRegisterSize) {
                        circ.errors.push_back("line " + std::to_string(line_number) +
                                              ": invalid register size: " + s);
                        continue;
                    }
                    count = static_cast<uint32_t>(parsed);
                } catch (...) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": invalid register size: " + s);
                    continue;
                }
                if (name.empty()) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": missing register name: " + s);
                    continue;
                }
                auto& offsets = (op == "qreg") ? circ.qreg_offsets : circ.creg_offsets;
                auto& sizes = (op == "qreg") ? circ.qreg_sizes : circ.creg_sizes;
                if (offsets.count(name)) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": register declared twice: " + name);
                    continue;
                }
                offsets[name] = (op == "qreg") ? circ.num_qubits : circ.num_clbits;
                sizes[name] = count;
                if (op == "qreg") {
                    circ.num_qubits += count;
                } else {
                    circ.num_clbits += count;
                }
                continue;
            }

            QasmInstruction inst;
            std::vector<double> params;
            // Gate with optional parenthesised parameter. ``op_raw`` keeps the
            // original case so parameter text is preserved.
            std::string gate_name = op_raw;
            std::string param_text;
            const size_t paren = op_raw.find('(');
            if (paren != std::string::npos) {
                const size_t close = op_raw.find(')', paren);
                if (close == std::string::npos) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": unbalanced '(' in " + s);
                    continue;
                }
                param_text = op_raw.substr(paren + 1, close - paren - 1);
                gate_name = op_raw.substr(0, paren);
            }
            std::string gate_lower = gate_name;
            std::transform(gate_lower.begin(), gate_lower.end(), gate_lower.begin(),
                           [](unsigned char c) { return static_cast<char>(std::tolower(c)); });

            if (gate_lower == "measure") {
                // tokens: measure, qubit_ref, ->, clbit_ref
                if (tokens.size() < 4 || tokens[2] != "->") {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": malformed measure statement: " + s);
                    continue;
                }
                const uint32_t q = parse_qubit_ref(tokens[1], circ);
                const uint32_t c = parse_clbit_ref(tokens[3], circ);
                if (q == UINT32_MAX || c == UINT32_MAX) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": undeclared register or index out of range: " + s);
                    continue;
                }
                inst.type = GateType::MEASURE;
                inst.qubits.push_back(q);
                inst.clbits.push_back(c);
                circ.instructions.push_back(inst);
                continue;
            }

            const auto spec_it = gate_specs().find(gate_lower);
            if (spec_it == gate_specs().end()) {
                circ.errors.push_back("line " + std::to_string(line_number) +
                                      ": unsupported or unknown gate: " + gate_name);
                continue;
            }
            const GateSpec& spec = spec_it->second;

            if (!param_text.empty()) {
                double value = 0.0;
                cq_hecs::AngleExpression evaluator(param_text);
                if (!evaluator.evaluate(value)) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": invalid gate parameter: " + param_text);
                    continue;
                }
                params.push_back(value);
            }
            if (static_cast<int>(params.size()) != spec.params) {
                circ.errors.push_back("line " + std::to_string(line_number) +
                                      ": gate '" + gate_lower + "' expects " +
                                      std::to_string(spec.params) + " parameter(s)");
                continue;
            }

            if (tokens.size() < static_cast<size_t>(spec.qubits) + 1) {
                circ.errors.push_back("line " + std::to_string(line_number) +
                                      ": gate '" + gate_lower + "' has too few operands");
                continue;
            }

            bool operands_ok = true;
            for (int k = 0; k < spec.qubits; ++k) {
                const uint32_t q = parse_qubit_ref(tokens[static_cast<size_t>(k) + 1], circ);
                if (q == UINT32_MAX) {
                    circ.errors.push_back("line " + std::to_string(line_number) +
                                          ": undeclared register or index out of range: " +
                                          tokens[static_cast<size_t>(k) + 1]);
                    operands_ok = false;
                    break;
                }
                inst.qubits.push_back(q);
            }
            if (!operands_ok) continue;

            inst.type = spec.type;
            if (!params.empty()) {
                inst.angle = params[0];
                inst.angle_q32 = static_cast<uint32_t>(
                    (inst.angle / (2.0 * 3.141592653589793)) * 4294967296.0);
            }
            circ.instructions.push_back(inst);
        }
    }

    return circ;
}

ParsedCircuit Qasm3Parser::parse_file(const std::string& filepath) {
    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        ParsedCircuit circ;
        circ.errors.push_back("failed to open QASM file: " + filepath);
        return circ;
    }
    std::stringstream buffer;
    buffer << file.rdbuf();
    return parse_string(buffer.str());
}

} // namespace cq
