#pragma once
#include <string>
#include <vector>
#include <cstdint>
#include "qasm_parser.hpp"
#include "sat_solver.hpp"
#include "arx_engine.hpp"

namespace cq_hecs {

class JSONFormatter {
public:
    static std::string format_qasm_result(const std::string& circuit_name,
                                          const QASMExecutionResult& res,
                                          double active_vram_mb,
                                          double lambda_res);

    static std::string format_sat_result(const CNFFormulaCPP& formula,
                                         const SATSolverResultCPP& res);

    static std::string format_arx_result(const ARXBenchmarkResultCPP& res);

    static std::string format_stress_result(uint64_t cycles,
                                            uint32_t qubits,
                                            double elapsed_sec,
                                            double active_vram_mb,
                                            bool leak_detected);

    static std::string format_test_matrix(const std::vector<std::pair<std::string, bool>>& tests);

    static std::string format_error(const std::string& err_msg);
};

} // namespace cq_hecs
