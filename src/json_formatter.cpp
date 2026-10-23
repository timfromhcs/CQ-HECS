#include "json_formatter.hpp"
#include <sstream>
#include <iomanip>

// The canonical version is injected by CMake from ``project(... VERSION ...)``.
// A stale fallback is used only for ad-hoc builds that bypass CMake.
#ifndef CQ_HECS_VERSION
#define CQ_HECS_VERSION "0.0.0-dev"
#endif

namespace cq_hecs {

static const char* kEnginePrefix = "CQ-HECS " CQ_HECS_VERSION;

static std::string escape_json(const std::string& s) {
    std::ostringstream o;
    for (char c : s) {
        if (c == '"') o << "\\\"";
        else if (c == '\\') o << "\\\\";
        else if (c == '\b') o << "\\b";
        else if (c == '\f') o << "\\f";
        else if (c == '\n') o << "\\n";
        else if (c == '\r') o << "\\r";
        else if (c == '\t') o << "\\t";
        else if (static_cast<unsigned char>(c) <= 0x1f) {
            o << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
        } else {
            o << c;
        }
    }
    return o.str();
}

std::string JSONFormatter::format_qasm_result(const std::string& circuit_name,
                                              const QASMExecutionResult& res,
                                              double active_vram_mb,
                                              double lambda_res)
{
    std::ostringstream ss;
    ss << "{\n"
       << "  \"engine\": \"" << kEnginePrefix << " QASM Phase-Ledger\",\n"
       << "  \"engine_class\": \"legacy_z8_phase_ledger\",\n"
       << "  \"statevector_simulation\": false,\n"
       << "  \"status\": \"" << (res.success ? "SUCCESS" : "FAILED") << "\",\n"
       << "  \"circuit\": \"" << escape_json(circuit_name) << "\",\n"
       << "  \"qubit_count\": " << res.qubit_count << ",\n"
       << "  \"gate_count\": " << res.gate_count << ",\n"
       << "  \"elapsed_ms\": " << std::fixed << std::setprecision(3) << res.elapsed_ms << ",\n"
       << "  \"active_vram_mb\": " << std::fixed << std::setprecision(3) << active_vram_mb << ",\n"
       << "  \"vram_budget_mb\": 120.0,\n"
       << "  \"vram_satisfied\": " << (active_vram_mb < 120.0 ? "true" : "false") << ",\n"
       << "  \"lambda_res\": " << std::fixed << std::setprecision(6) << lambda_res << "\n"
       << "}\n";
    return ss.str();
}

std::string JSONFormatter::format_qasm_parse_error(
    const std::string& circuit_name,
    const std::vector<QASMParseError>& errors)
{
    std::ostringstream ss;
    ss << "{\n"
       << "  \"engine\": \"" << kEnginePrefix << " QASM Phase-Ledger\",\n"
       << "  \"engine_class\": \"legacy_z8_phase_ledger\",\n"
       << "  \"statevector_simulation\": false,\n"
       << "  \"status\": \"ERROR\",\n"
       << "  \"error_category\": \"qasm_parse_error\",\n"
       << "  \"circuit\": \"" << escape_json(circuit_name) << "\",\n"
       << "  \"error_count\": " << errors.size() << ",\n"
       << "  \"errors\": [\n";
    for (size_t i = 0; i < errors.size(); ++i) {
        ss << "    {\"line\": " << errors[i].line
           << ", \"category\": \"" << escape_json(errors[i].category)
           << "\", \"message\": \"" << escape_json(errors[i].message) << "\"}";
        if (i + 1 < errors.size()) ss << ",";
        ss << "\n";
    }
    ss << "  ]\n}\n";
    return ss.str();
}

std::string JSONFormatter::format_sat_result(const CNFFormulaCPP& formula,
                                             const SATSolverResultCPP& res)
{
    std::ostringstream ss;
    ss << "{\n"
       << "  \"engine\": \"CQ-HECS " CQ_HECS_VERSION " SAT Engine\",\n"
       << "  \"status\": \"" << (res.satisfiable ? "SAT" : "UNSAT") << "\",\n"
       << "  \"source\": \"" << escape_json(formula.source_name) << "\",\n"
       << "  \"num_vars\": " << formula.num_vars << ",\n"
       << "  \"num_clauses\": " << formula.num_clauses << ",\n"
       << "  \"decisions\": " << res.num_decisions << ",\n"
       << "  \"pruned_cycles\": " << res.num_pruned_cycles << ",\n"
       << "  \"elapsed_ms\": " << std::fixed << std::setprecision(3) << res.elapsed_ms << ",\n"
       << "  \"verified\": " << (res.verified ? "true" : "false");

    if (res.satisfiable && !res.assignment.empty()) {
        ss << ",\n  \"assignment\": {\n";
        bool first = true;
        for (size_t v = 1; v < res.assignment.size(); ++v) {
            if (res.assignment[v] != -1) {
                if (!first) ss << ",\n";
                ss << "    \"" << v << "\": " << (res.assignment[v] == 1 ? "true" : "false");
                first = false;
            }
        }
        ss << "\n  }\n";
    } else {
        ss << "\n";
    }
    ss << "}\n";
    return ss.str();
}

std::string JSONFormatter::format_arx_result(const ARXBenchmarkResultCPP& res) {
    std::ostringstream ss;
    ss << "{\n"
       << "  \"engine\": \"CQ-HECS " CQ_HECS_VERSION " ARX Engine\",\n"
       << "  \"status\": \"" << (res.inverse_verified && res.carry_shadow_exact ? "SUCCESS" : "FAILED") << "\",\n"
       << "  \"primitive\": \"" << escape_json(res.primitive_name) << "\",\n"
       << "  \"rounds\": " << res.num_rounds << ",\n"
       << "  \"forward_verified\": " << (res.forward_verified ? "true" : "false") << ",\n"
       << "  \"inverse_verified\": " << (res.inverse_verified ? "true" : "false") << ",\n"
       << "  \"carry_shadow_exact\": " << (res.carry_shadow_exact ? "true" : "false") << ",\n"
       << "  \"path_pruning_ratio\": " << std::scientific << res.path_pruning_ratio << ",\n"
       << "  \"elapsed_ms\": " << std::fixed << std::setprecision(3) << res.elapsed_ms << ",\n"
       << "  \"throughput_ops_per_sec\": " << std::fixed << std::setprecision(1) << res.throughput_ops_per_sec << "\n"
       << "}\n";
    return ss.str();
}

std::string JSONFormatter::format_stress_result(uint64_t cycles,
                                                uint32_t qubits,
                                                double elapsed_sec,
                                                double active_vram_mb,
                                                bool leak_detected)
{
    std::ostringstream ss;
    double throughput = (elapsed_sec > 0.0) ? (cycles / elapsed_sec) : 0.0;
    ss << "{\n"
       << "  \"engine\": \"CQ-HECS " CQ_HECS_VERSION " Stress Harness\",\n"
       << "  \"status\": \"" << (!leak_detected && active_vram_mb < 120.0 ? "SUCCESS" : "FAILED") << "\",\n"
       << "  \"cycles\": " << cycles << ",\n"
       << "  \"qubits\": " << qubits << ",\n"
       << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(3) << elapsed_sec << ",\n"
       << "  \"cycles_per_sec\": " << std::fixed << std::setprecision(1) << throughput << ",\n"
       << "  \"active_vram_mb\": " << std::fixed << std::setprecision(3) << active_vram_mb << ",\n"
       << "  \"vram_ceiling_mb\": 120.0,\n"
       << "  \"vram_satisfied\": " << (active_vram_mb < 120.0 ? "true" : "false") << ",\n"
       << "  \"memory_leaks_detected\": " << (leak_detected ? "true" : "false") << "\n"
       << "}\n";
    return ss.str();
}

std::string JSONFormatter::format_test_matrix(const std::vector<std::pair<std::string, bool>>& tests) {
    std::ostringstream ss;
    size_t passed = 0;
    for (const auto& t : tests) {
        if (t.second) passed++;
    }

    ss << "{\n"
       << "  \"engine\": \"CQ-HECS " CQ_HECS_VERSION " Embedded Self-Test Matrix\",\n"
       << "  \"status\": \"" << (passed == tests.size() ? "SUCCESS" : "FAILED") << "\",\n"
       << "  \"total_tests\": " << tests.size() << ",\n"
       << "  \"passed\": " << passed << ",\n"
       << "  \"failed\": " << (tests.size() - passed) << ",\n"
       << "  \"tests\": [\n";

    for (size_t i = 0; i < tests.size(); ++i) {
        ss << "    {\"name\": \"" << escape_json(tests[i].first) << "\", \"passed\": " 
           << (tests[i].second ? "true" : "false") << "}";
        if (i + 1 < tests.size()) ss << ",";
        ss << "\n";
    }
    ss << "  ]\n}\n";
    return ss.str();
}

std::string JSONFormatter::format_error(const std::string& err_msg) {
    std::ostringstream ss;
    ss << "{\n"
       << "  \"status\": \"ERROR\",\n"
       << "  \"error\": \"" << escape_json(err_msg) << "\"\n"
       << "}\n";
    return ss.str();
}

} // namespace cq_hecs
