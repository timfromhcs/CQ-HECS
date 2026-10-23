#pragma once
#include <string>
#include <vector>
#include <memory>
#include <cstdint>
#include <unordered_map>

namespace cq_hecs {

class VulkanEngine;

struct QASMCommand {
    std::string name;
    std::vector<uint32_t> qubits;
    std::vector<uint32_t> clbits;
    std::vector<double> params;
    int line = 0;
};

struct QASMParseError {
    int line = 0;
    std::string category;
    std::string message;
};

struct QASMRegister {
    uint32_t offset = 0;
    uint32_t size = 0;
};

struct QASMCircuitData {
    uint32_t num_qubits = 0;
    uint32_t num_clbits = 0;
    std::vector<QASMCommand> commands;
    std::string filename;
    std::unordered_map<std::string, QASMRegister> qregs;
    std::unordered_map<std::string, QASMRegister> cregs;
    std::vector<QASMParseError> errors;

    bool ok() const noexcept { return errors.empty(); }
};

struct QASMExecutionResult {
    uint32_t gate_count = 0;
    uint32_t qubit_count = 0;
    double elapsed_ms = 0.0;
    double active_vram_mb = 0.0;
    bool success = false;
};

class QASMParserCPP {
public:
    QASMParserCPP();
    ~QASMParserCPP();

    // Strict OpenQASM 2.0 subset + 3.0 register declarations. Returns false and
    // fills ``out_circuit.errors`` when the input violates the documented
    // grammar. No invalid input is silently repaired, ignored or defaulted.
    bool parse_file(const std::string& filepath, QASMCircuitData& out_circuit);
    bool parse_string(const std::string& source, QASMCircuitData& out_circuit);

    QASMExecutionResult execute_on_vulkan(const QASMCircuitData& circuit, VulkanEngine& engine);

private:
    bool parse_param_token(const std::string& token, double& out_value) const;
};

} // namespace cq_hecs
