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
    //: False when the formula itself violates the documented limits.
    bool input_valid = true;
    //: True when the search hit its wall-clock budget. Never reported as UNSAT.
    bool timed_out = false;
    //: Human-readable reason when ``input_valid`` is false or the search timed out.
    std::string error;
};

class SATSolverCPP {
public:
    //: Parser ceilings. A syntactically legal but unmaterialisable claim is not
    //: accepted: rejecting it before allocation keeps the CLI from turning a
    //: hostile header into an OOM or an out-of-bounds assignment index.
    static constexpr uint32_t MAX_VARIABLES = 1000000u;
    static constexpr uint32_t MAX_CLAUSES = 4000000u;
    static constexpr size_t MAX_CLAUSE_LITERALS = 1000000u;
    static constexpr size_t MAX_INPUT_BYTES = 64ull * 1024ull * 1024ull;

    explicit SATSolverCPP(size_t table_capacity = 8192);
    ~SATSolverCPP();

    // ``error`` (when supplied) receives a one-line reason on failure. It never
    // contains the whole input, which may be arbitrary hostile data.
    bool parse_file(const std::string& filepath, CNFFormulaCPP& out_formula,
                    std::string* error = nullptr);
    bool parse_string(const std::string& content, CNFFormulaCPP& out_formula,
                      std::string* error = nullptr);

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
    bool m_timed_out = false;
};

} // namespace cq_hecs
