#pragma once
#include <string>
#include <vector>
#include <memory>
#include <cstdint>

namespace cq_hecs {

class VulkanEngine;

struct QASMCommand {
    std::string name;
    std::vector<uint32_t> qubits;
    std::vector<double> params;
};

struct QASMCircuitData {
    uint32_t num_qubits = 0;
    uint32_t num_clbits = 0;
    std::vector<QASMCommand> commands;
    std::string filename;
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

    bool parse_file(const std::string& filepath, QASMCircuitData& out_circuit);
    bool parse_string(const std::string& source, QASMCircuitData& out_circuit);

    QASMExecutionResult execute_on_vulkan(const QASMCircuitData& circuit, VulkanEngine& engine);

private:
    double parse_param_token(const std::string& token);
};

} // namespace cq_hecs
