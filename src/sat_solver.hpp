#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>
#include <optional>
#include <chrono>

namespace cq_hecs {

struct CNFFormulaCPP {
    uint32_t num_vars = 0;
    uint32_t num_clauses = 0;
    std::vector<std::vector<int32_t>> clauses;
    std::string source_name;
};

struct SATSolverResultCPP {
    bool satisfiable = false;
    std::vector<int8_t> assignment; // 1: true, 0: false, -1: unassigned (1-indexed, size num_vars + 1)
    uint64_t num_decisions = 0;
    uint64_t num_pruned_cycles = 0;
    double elapsed_ms = 0.0;
    bool verified = false;
};

class SATSolverCPP {
public:
    explicit SATSolverCPP(size_t table_capacity = 8192);
    ~SATSolverCPP();

    bool parse_file(const std::string& filepath, CNFFormulaCPP& out_formula);
    bool parse_string(const std::string& content, CNFFormulaCPP& out_formula);

    SATSolverResultCPP solve(const CNFFormulaCPP& formula, double timeout_sec = 10.0);

private:
    bool dpll(std::vector<std::vector<int32_t>>& clauses,
              std::vector<int8_t>& assignment,
              uint32_t total_vars,
              std::chrono::steady_clock::time_point t_start,
              double timeout_sec);

    bool unit_propagate(std::vector<std::vector<int32_t>>& clauses,
                        std::vector<int8_t>& assignment);

    static std::vector<std::vector<int32_t>> substitute_var(
        const std::vector<std::vector<int32_t>>& clauses, int32_t var, bool val);

    static int32_t select_variable(const std::vector<std::vector<int32_t>>& clauses);

    uint64_t compute_state_hash(const std::vector<int8_t>& assignment);
    bool check_and_insert_cuckoo(uint64_t key);
    bool verify_solution(const std::vector<std::vector<int32_t>>& clauses,
                         const std::vector<int8_t>& assignment);

    size_t m_table_capacity;
    std::vector<uint64_t> m_cuckoo_table;
    uint64_t m_decisions;
    uint64_t m_pruned_cycles;
};

} // namespace cq_hecs
