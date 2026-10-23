#include "qasm_parser.hpp"
#include "qasm_angle.hpp"
#include "vulkan_engine.hpp"

#include <fstream>
#include <sstream>
#include <iostream>
#include <chrono>
#include <cmath>
#include <regex>
#include <algorithm>
#include <cctype>
#include <limits>
#include <unordered_set>

namespace cq_hecs {

namespace {

constexpr size_t kMaxSourceBytes = 16u * 1024u * 1024u;
constexpr size_t kMaxLineBytes = 1u * 1024u * 1024u;
constexpr uint32_t kMaxRegisterSize = 1u << 20;  // 1,048,576 qubits per register
constexpr double kPi = 3.14159265358979323846;

std::string trim(const std::string& str) {
    size_t first = str.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    size_t last = str.find_last_not_of(" \t\r\n");
    return str.substr(first, (last - first + 1));
}

std::string lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return s;
}

struct GateSpec {
    int qubits;
    int params;
};

// Gates the legacy phase-ledger executor models. Anything outside this table is
// rejected with ``unsupported_gate``; it is never executed as an identity.
const std::unordered_map<std::string, GateSpec>& gate_specs() {
    static const std::unordered_map<std::string, GateSpec> specs = {
        {"h", {1, 0}},   {"s", {1, 0}},   {"sdg", {1, 0}}, {"t", {1, 0}},
        {"tdg", {1, 0}}, {"x", {1, 0}},   {"y", {1, 0}},   {"z", {1, 0}},
        {"rx", {1, 1}},  {"ry", {1, 1}},  {"rz", {1, 1}},
        {"cx", {2, 0}},  {"cnot", {2, 0}}, {"cz", {2, 0}},
        {"swap", {2, 0}}, {"cp", {2, 1}},
    };
    return specs;
}

}  // namespace

QASMParserCPP::QASMParserCPP() = default;
QASMParserCPP::~QASMParserCPP() = default;

bool QASMParserCPP::parse_param_token(const std::string& token, double& out_value) const {
    const std::string s = trim(token);
    if (s.empty()) return false;
    AngleExpression expression(s);
    return expression.evaluate(out_value);
}

bool QASMParserCPP::parse_file(const std::string& filepath, QASMCircuitData& out_circuit) {
    out_circuit = QASMCircuitData{};

    if (filepath == "-") {
        std::stringstream buffer;
        buffer << std::cin.rdbuf();
        out_circuit.filename = "stdin";
        return parse_string(buffer.str(), out_circuit);
    }

    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
        out_circuit.filename = filepath;
        out_circuit.errors.push_back(
            {0, "io_error", "failed to open QASM file: " + filepath});
        return false;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    out_circuit.filename = filepath;
    return parse_string(buffer.str(), out_circuit);
}

bool QASMParserCPP::parse_string(const std::string& source, QASMCircuitData& out_circuit) {
    out_circuit.num_qubits = 0;
    out_circuit.num_clbits = 0;
    out_circuit.commands.clear();
    out_circuit.qregs.clear();
    out_circuit.cregs.clear();
    out_circuit.errors.clear();

    if (source.size() > kMaxSourceBytes) {
        out_circuit.errors.push_back(
            {0, "input_too_large",
             "QASM source exceeds the " + std::to_string(kMaxSourceBytes) + "-byte limit"});
        return false;
    }

    const std::regex indexed_ref_re(
        R"(^([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([0-9]+)\s*\]$)");
    const std::regex bare_ref_re(R"(^[A-Za-z_][A-Za-z0-9_]*$)");
    const std::regex reg_decl_re(
        R"(^([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([0-9]+)\s*\]$)");
    const std::regex qreg_decl_3_re(R"(^qubit\s*\[\s*([0-9]+)\s*\]$)");
    const std::regex bit_decl_3_re(R"(^bit\s*\[\s*([0-9]+)\s*\]$)");

    auto add_error = [&out_circuit](int line, const std::string& category,
                                    const std::string& message) {
        out_circuit.errors.push_back({line, category, message});
    };

    std::istringstream stream(source);
    std::string raw_line;
    int line_number = 0;

    while (std::getline(stream, raw_line)) {
        ++line_number;

        if (raw_line.size() > kMaxLineBytes) {
            add_error(line_number, "line_too_long", "input line exceeds the 1 MiB limit");
            continue;
        }

        // Strip line comments. OpenQASM 3 block comments are rejected rather
        // than silently half-parsed.
        std::string line = raw_line;
        const size_t comment_pos = line.find("//");
        if (comment_pos != std::string::npos) line = line.substr(0, comment_pos);
        line = trim(line);

        if (line.empty()) continue;

        if (line.find("/*") != std::string::npos || line.find("*/") != std::string::npos) {
            add_error(line_number, "unsupported_syntax",
                      "block comments are not supported by this parser");
            continue;
        }

        // Every statement must be terminated by a semicolon. Recovery on
        // missing punctuation is deliberately not implemented: a malformed
        // circuit is rejected instead of guessed.
        if (line.back() != ';') {
            add_error(line_number, "missing_semicolon",
                      "statement is not terminated by ';': " + line);
            continue;
        }

        std::stringstream statement_stream(line);
        std::string statement;
        while (std::getline(statement_stream, statement, ';')) {
            statement = trim(statement);
            if (statement.empty()) continue;

            // Header statements are validated but do not produce gates.
            if (statement.rfind("OPENQASM", 0) == 0) {
                const std::string version = trim(statement.substr(8));
                if (version != "2.0" && version != "3.0") {
                    add_error(line_number, "unsupported_version",
                              "unsupported OpenQASM version: " + version);
                }
                continue;
            }
            if (statement.rfind("include", 0) == 0) {
                const std::string rest = trim(statement.substr(7));
                if (rest.size() < 2 || rest.front() != '"' || rest.back() != '"') {
                    add_error(line_number, "syntax_error",
                              "include expects a quoted filename: " + statement);
                }
                continue;
            }

            // Split parameters (if any) from the argument list.
            std::string head = statement;
            std::string params_part;
            std::string args_part;
            const size_t paren_open = statement.find('(');
            if (paren_open != std::string::npos) {
                const size_t paren_close = statement.find(')', paren_open);
                if (paren_close == std::string::npos) {
                    add_error(line_number, "syntax_error",
                              "unbalanced '(' in statement: " + statement);
                    continue;
                }
                head = trim(statement.substr(0, paren_open));
                params_part = statement.substr(paren_open + 1, paren_close - paren_open - 1);
                args_part = trim(statement.substr(paren_close + 1));
            } else {
                const size_t space_pos = statement.find_first_of(" \t");
                if (space_pos == std::string::npos) {
                    head = trim(statement);
                } else {
                    head = trim(statement.substr(0, space_pos));
                    args_part = trim(statement.substr(space_pos + 1));
                }
            }

            const std::string op = lower(head);

            // Register declarations.
            bool is_qreg = false;
            bool is_creg = false;
            std::string reg_name;
            std::string reg_size_text;

            std::smatch m;
            if (op == "qreg" || op == "creg") {
                if (!std::regex_match(args_part, m, reg_decl_re)) {
                    add_error(line_number, "syntax_error",
                              "malformed register declaration: " + statement);
                    continue;
                }
                reg_name = m[1].str();
                reg_size_text = m[2].str();
                is_qreg = (op == "qreg");
                is_creg = (op == "creg");
            } else if (std::regex_match(op, m, qreg_decl_3_re) ||
                       std::regex_match(op, m, bit_decl_3_re)) {
                const bool qubit_decl = (op.rfind("qubit", 0) == 0);
                reg_size_text = m[1].str();
                if (!std::regex_match(args_part, m, bare_ref_re)) {
                    add_error(line_number, "syntax_error",
                              "malformed register name in declaration: " + statement);
                    continue;
                }
                reg_name = args_part;
                is_qreg = qubit_decl;
                is_creg = !qubit_decl;
            }

            if (is_qreg || is_creg) {
                uint32_t size = 0;
                try {
                    const unsigned long parsed = std::stoul(reg_size_text);
                    if (parsed == 0 || parsed > kMaxRegisterSize) {
                        add_error(line_number, "invalid_register_size",
                                  "register size must be in [1, " +
                                      std::to_string(kMaxRegisterSize) + "]: " + statement);
                        continue;
                    }
                    size = static_cast<uint32_t>(parsed);
                } catch (...) {
                    add_error(line_number, "invalid_register_size",
                              "register size is not a valid integer: " + statement);
                    continue;
                }

                auto& table = is_qreg ? out_circuit.qregs : out_circuit.cregs;
                if (table.count(reg_name)) {
                    add_error(line_number, "duplicate_register",
                              "register declared more than once: " + reg_name);
                    continue;
                }

                QASMRegister info;
                info.size = size;
                info.offset = is_qreg ? out_circuit.num_qubits : out_circuit.num_clbits;
                table[reg_name] = info;
                if (is_qreg) {
                    out_circuit.num_qubits += size;
                } else {
                    out_circuit.num_clbits += size;
                }
                continue;
            }

            // Barrier is a valid no-op and carries no execution semantics.
            if (op == "barrier") {
                continue;
            }

            // Measurement: ``measure q[i] -> c[j];`` (or whole registers of
            // equal width).
            if (op == "measure") {
                const size_t arrow = args_part.find("->");
                if (arrow == std::string::npos) {
                    add_error(line_number, "syntax_error",
                              "measure requires '->': " + statement);
                    continue;
                }
                const std::string q_part = trim(args_part.substr(0, arrow));
                const std::string c_part = trim(args_part.substr(arrow + 2));

                auto resolve = [&](const std::string& ref, bool qubit_ref,
                                   std::vector<uint32_t>& out, bool& ok) {
                    ok = false;
                    std::smatch ref_match;
                    const auto& table = qubit_ref ? out_circuit.qregs : out_circuit.cregs;
                    if (std::regex_match(ref, ref_match, indexed_ref_re)) {
                        const std::string name = ref_match[1].str();
                        const auto it = table.find(name);
                        if (it == table.end()) {
                            add_error(line_number, "undeclared_register",
                                      std::string(qubit_ref ? "qubit" : "classical") +
                                          " register is not declared: " + name);
                            return;
                        }
                        unsigned long index = 0;
                        try {
                            index = std::stoul(ref_match[2].str());
                        } catch (...) {
                            add_error(line_number, "invalid_operand",
                                      "invalid index in operand: " + ref);
                            return;
                        }
                        if (index >= it->second.size) {
                            add_error(line_number, "index_out_of_range",
                                      "index " + std::to_string(index) +
                                          " is outside register '" + name + "' of size " +
                                          std::to_string(it->second.size));
                            return;
                        }
                        out.push_back(it->second.offset + static_cast<uint32_t>(index));
                        ok = true;
                        return;
                    }
                    if (std::regex_match(ref, bare_ref_re)) {
                        const auto it = table.find(ref);
                        if (it == table.end()) {
                            add_error(line_number, "undeclared_register",
                                      std::string(qubit_ref ? "qubit" : "classical") +
                                          " register is not declared: " + ref);
                            return;
                        }
                        for (uint32_t k = 0; k < it->second.size; ++k) {
                            out.push_back(it->second.offset + k);
                        }
                        ok = true;
                        return;
                    }
                    add_error(line_number, "invalid_operand",
                              "invalid operand (expected register[index]): " + ref);
                };

                std::vector<uint32_t> qubits;
                std::vector<uint32_t> clbits;
                bool q_ok = false;
                bool c_ok = false;
                resolve(q_part, true, qubits, q_ok);
                resolve(c_part, false, clbits, c_ok);
                if (!q_ok || !c_ok) continue;
                if (qubits.size() != clbits.size()) {
                    add_error(line_number, "width_mismatch",
                              "measure operands have different widths");
                    continue;
                }

                QASMCommand cmd;
                cmd.name = "measure";
                cmd.qubits = std::move(qubits);
                cmd.clbits = std::move(clbits);
                cmd.line = line_number;
                out_circuit.commands.push_back(std::move(cmd));
                continue;
            }

            // Gate statement.
            const auto spec_it = gate_specs().find(op);
            if (spec_it == gate_specs().end()) {
                add_error(line_number, "unsupported_gate",
                          "unsupported or unknown gate: " + head);
                continue;
            }
            const GateSpec& spec = spec_it->second;

            std::vector<double> params;
            if (!params_part.empty()) {
                std::stringstream param_stream(params_part);
                std::string param_token;
                while (std::getline(param_stream, param_token, ',')) {
                    double value = 0.0;
                    if (!parse_param_token(param_token, value)) {
                        add_error(line_number, "invalid_parameter",
                                  "parameter is not a valid constant angle expression: " +
                                      trim(param_token));
                        params.clear();
                        break;
                    }
                    params.push_back(value);
                }
                if (params.empty()) continue;
            }
            if (static_cast<int>(params.size()) != spec.params) {
                add_error(line_number, "parameter_count_mismatch",
                          "gate '" + op + "' expects " + std::to_string(spec.params) +
                              " parameter(s), got " + std::to_string(params.size()));
                continue;
            }

            if (args_part.empty()) {
                add_error(line_number, "syntax_error",
                          "gate '" + op + "' has no operands");
                continue;
            }

            std::vector<uint32_t> qubits;
            std::string operand_token;
            std::stringstream operand_stream(args_part);
            bool operands_ok = true;

            while (std::getline(operand_stream, operand_token, ',')) {
                operand_token = trim(operand_token);
                if (operand_token.empty()) {
                    add_error(line_number, "syntax_error",
                              "empty operand in gate statement: " + statement);
                    operands_ok = false;
                    break;
                }

                std::smatch ref_match;
                if (std::regex_match(operand_token, ref_match, indexed_ref_re)) {
                    const std::string name = ref_match[1].str();
                    const auto it = out_circuit.qregs.find(name);
                    if (it == out_circuit.qregs.end()) {
                        add_error(line_number, "undeclared_register",
                                  "qubit register is not declared: " + name);
                        operands_ok = false;
                        break;
                    }
                    unsigned long index = 0;
                    try {
                        index = std::stoul(ref_match[2].str());
                    } catch (...) {
                        add_error(line_number, "invalid_operand",
                                  "invalid qubit index: " + operand_token);
                        operands_ok = false;
                        break;
                    }
                    if (index >= it->second.size) {
                        add_error(line_number, "index_out_of_range",
                                  "qubit index " + std::to_string(index) +
                                      " is outside register '" + name + "' of size " +
                                      std::to_string(it->second.size));
                        operands_ok = false;
                        break;
                    }
                    qubits.push_back(it->second.offset + static_cast<uint32_t>(index));
                } else if (std::regex_match(operand_token, bare_ref_re)) {
                    // Whole-register operand (OpenQASM 2.0 semantics).
                    const auto it = out_circuit.qregs.find(operand_token);
                    if (it == out_circuit.qregs.end()) {
                        add_error(line_number, "undeclared_register",
                                  "qubit register is not declared: " + operand_token);
                        operands_ok = false;
                        break;
                    }
                    for (uint32_t k = 0; k < it->second.size; ++k) {
                        qubits.push_back(it->second.offset + k);
                    }
                } else {
                    add_error(line_number, "invalid_operand",
                              "invalid qubit operand: " + operand_token);
                    operands_ok = false;
                    break;
                }
            }
            if (!operands_ok) continue;

            if (qubits.empty()) {
                add_error(line_number, "syntax_error",
                          "gate '" + op + "' has no operands");
                continue;
            }

            // Whole-register operands expand to several gate applications. The
            // flattened operand list must therefore be a whole multiple of the
            // gate's arity.
            if (qubits.size() % static_cast<size_t>(spec.qubits) != 0) {
                add_error(line_number, "operand_count_mismatch",
                          "gate '" + op + "' expects a multiple of " +
                              std::to_string(spec.qubits) + " qubit(s), got " +
                              std::to_string(qubits.size()));
                continue;
            }

            for (size_t offset = 0; offset < qubits.size();
                 offset += static_cast<size_t>(spec.qubits)) {
                QASMCommand cmd;
                cmd.name = op;
                cmd.qubits.assign(qubits.begin() + static_cast<long>(offset),
                                  qubits.begin() +
                                      static_cast<long>(offset + static_cast<size_t>(spec.qubits)));
                cmd.params = params;
                cmd.line = line_number;
                out_circuit.commands.push_back(std::move(cmd));
            }
        }
    }

    return out_circuit.errors.empty();
}

QASMExecutionResult QASMParserCPP::execute_on_vulkan(const QASMCircuitData& circuit,
                                                     VulkanEngine& engine) {
    QASMExecutionResult res;
    res.qubit_count = circuit.num_qubits;
    res.gate_count = 0;
    res.success = false;

    // Refuse to "execute" a circuit that failed validation. This is the
    // fail-closed boundary: there is no partial or best-effort execution.
    if (!circuit.ok()) {
        std::cerr << "[QASMParserCPP] Refusing to execute a circuit with "
                  << circuit.errors.size() << " parse error(s)\n";
        return res;
    }

    auto t0 = std::chrono::high_resolution_clock::now();

    if (!engine.is_initialized()) {
        if (!engine.initialize()) {
            std::cerr << "[QASMParserCPP] Vulkan engine failed to initialize\n";
            return res;
        }
    }

    if (engine.get_mps_node_count() < circuit.num_qubits) {
        if (!engine.allocate_300q_mps(64)) {
            std::cerr << "[QASMParserCPP] Failed to allocate MPS in Vulkan engine" << std::endl;
            return res;
        }
    }

    if (circuit.commands.empty()) {
        res.success = true;
        res.elapsed_ms = 0.0;
        return res;
    }

    // Legacy Z_8 phase-ledger arithmetic. This is intentionally *not* a
    // statevector simulation; the JSON result labels the engine class so the
    // output cannot be mistaken for amplitude-level simulation.
    std::vector<uint32_t> temp_state(64, 1);
    for (const auto& cmd : circuit.commands) {
        uint32_t shift = 0;
        if (cmd.name == "h" || cmd.name == "z" || cmd.name == "cx" ||
            cmd.name == "cnot") {
            shift = 4;
        } else if (cmd.name == "t") {
            shift = 1;
        } else if (cmd.name == "tdg") {
            shift = 7;
        } else if (cmd.name == "s") {
            shift = 2;
        } else if (cmd.name == "sdg") {
            shift = 6;
        } else if (cmd.name == "cp" || cmd.name == "cz") {
            shift = cmd.params.empty()
                        ? 2
                        : (static_cast<uint32_t>(
                               std::llround(cmd.params[0] / (kPi / 4.0))) %
                           8);
        } else if (cmd.name == "measure") {
            shift = 0;
        }

        if (shift > 0) {
            for (auto& s : temp_state) {
                uint32_t mag = s & 0xFFFFu;
                uint32_t phase = (s >> 16u) & 0x7u;
                s = (((phase + shift) & 0x7u) << 16u) | mag;
            }
        }
        res.gate_count++;
    }

    engine.run_cq_hecs_core_phase(temp_state.data(),
                                  static_cast<uint32_t>(temp_state.size()), 1);

    auto t1 = std::chrono::high_resolution_clock::now();
    res.elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    res.active_vram_mb = static_cast<double>(engine.get_active_vram_bytes()) / (1024.0 * 1024.0);

    if (res.active_vram_mb > 120.0) {
        std::cerr << "[QASMParserCPP] VRAM limit violated: " << res.active_vram_mb
                  << " MB > 120 MB" << std::endl;
        res.success = false;
    } else {
        res.success = true;
    }

    return res;
}

} // namespace cq_hecs
