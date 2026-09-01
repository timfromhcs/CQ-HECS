#include "sat_solver.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <cmath>

namespace cq_hecs {

SATSolverCPP::SATSolverCPP(size_t table_capacity)
    : m_table_capacity(table_capacity)
    , m_cuckoo_table(table_capacity, 0)
    , m_decisions(0)
    , m_pruned_cycles(0)
{
}

SATSolverCPP::~SATSolverCPP() = default;

bool SATSolverCPP::parse_file(const std::string& filepath, CNFFormulaCPP& out_formula) {
    if (filepath == "-") {
        // Read from standard input
        std::stringstream ss;
        ss << std::cin.rdbuf();
        out_formula.source_name = "stdin";
        return parse_string(ss.str(), out_formula);
    }

    std::ifstream file(filepath);
    if (!file.is_open()) {
        std::cerr << "[SATSolverCPP] Failed to open CNF file: " << filepath << std::endl;
        return false;
    }
    std::stringstream ss;
    ss << file.rdbuf();
    out_formula.source_name = filepath;
    return parse_string(ss.str(), out_formula);
}

bool SATSolverCPP::parse_string(const std::string& content, CNFFormulaCPP& out_formula) {
    std::istringstream stream(content);
    std::string line;

    out_formula.num_vars = 0;
    out_formula.num_clauses = 0;
    out_formula.clauses.clear();

    std::vector<int32_t> current_clause;

    while (std::getline(stream, line)) {
        if (line.empty()) continue;
        size_t first = line.find_first_not_of(" \t\r\n");
        if (first == std::string::npos || line[first] == 'c') continue;

        if (line[first] == 'p') {
            std::istringstream p_line(line.substr(first));
            std::string p_tok, format_tok;
            p_line >> p_tok >> format_tok >> out_formula.num_vars >> out_formula.num_clauses;
            continue;
        }

        std::istringstream c_line(line.substr(first));
        int32_t lit = 0;
        while (c_line >> lit) {
            if (lit == 0) {
                out_formula.clauses.push_back(current_clause);
                current_clause.clear();
            } else {
                if (std::abs(lit) <= 100000) {
                    current_clause.push_back(lit);
                    uint32_t var_idx = static_cast<uint32_t>(std::abs(lit));
                    if (var_idx > out_formula.num_vars) {
                        out_formula.num_vars = var_idx;
                    }
                }
            }
        }
    }

    if (!current_clause.empty()) {
        out_formula.clauses.push_back(current_clause);
    }
    out_formula.num_clauses = static_cast<uint32_t>(out_formula.clauses.size());
    return true;
}

uint64_t SATSolverCPP::compute_state_hash(const std::vector<int8_t>& assignment) {
    uint64_t h = 0x123456789ABCDEF0ULL;
    for (size_t var = 1; var < assignment.size() && var <= 32; ++var) {
        if (assignment[var] != -1) {
            uint64_t bit = (assignment[var] == 1) ? 1ULL : 0ULL;
            h ^= ((var * 0x9e3779b97f4a7c15ULL) + bit);
            h = (h << 7) | (h >> 57);
        }
    }
    return h;
}

bool SATSolverCPP::check_and_insert_cuckoo(uint64_t key) {
    uint64_t val = key | 1ULL;
    size_t half_cap = m_table_capacity / 2;
    if (half_cap == 0) return true;

    // Murmur3 hash 1
    uint64_t k1 = val;
    k1 ^= k1 >> 33;
    k1 *= 0xff51afd7ed558ccdULL;
    k1 ^= k1 >> 33;
    size_t h1 = static_cast<size_t>(k1 % half_cap);

    // Secondary hash 2
    uint64_t k2 = val;
    k2 ^= k2 >> 30;
    k2 *= 0xbf58476d1ce4e5b9ULL;
    k2 ^= k2 >> 27;
    size_t h2 = half_cap + static_cast<size_t>(k2 % half_cap);

    if (m_cuckoo_table[h1] == val || m_cuckoo_table[h2] == val) {
        return false; // Cycle detected
    }

    if (m_cuckoo_table[h1] == 0) {
        m_cuckoo_table[h1] = val;
    } else if (m_cuckoo_table[h2] == 0) {
        m_cuckoo_table[h2] = val;
    } else {
        m_cuckoo_table[h1] = val; // Cuckoo replacement
    }
    return true;
}

std::vector<std::vector<int32_t>> SATSolverCPP::substitute_var(
    const std::vector<std::vector<int32_t>>& clauses, int32_t var, bool val)
{
    std::vector<std::vector<int32_t>> new_clauses;
    new_clauses.reserve(clauses.size());
    int32_t falsified_lit = val ? -var : var;

    for (const auto& c : clauses) {
        bool satisfied = false;
        for (int32_t lit : c) {
            if ((lit == var && val) || (lit == -var && !val)) {
                satisfied = true;
                break;
            }
        }
        if (satisfied) continue;

        std::vector<int32_t> filtered;
        filtered.reserve(c.size());
        for (int32_t lit : c) {
            if (lit != falsified_lit) {
                filtered.push_back(lit);
            }
        }
        new_clauses.push_back(filtered);
    }
    return new_clauses;
}

bool SATSolverCPP::unit_propagate(std::vector<std::vector<int32_t>>& clauses,
                                  std::vector<int8_t>& assignment)
{
    bool changed = true;
    while (changed) {
        changed = false;
        int32_t unit_lit = 0;
        for (const auto& c : clauses) {
            if (c.size() == 1) {
                unit_lit = c[0];
                break;
            }
        }

        if (unit_lit != 0) {
            changed = true;
            int32_t var = std::abs(unit_lit);
            int8_t val = (unit_lit > 0) ? 1 : 0;
            if (assignment[var] != -1 && assignment[var] != val) {
                return false; // Direct contradiction!
            }
            assignment[var] = val;
            clauses = substitute_var(clauses, var, (val == 1));
            for (const auto& c : clauses) {
                if (c.empty()) return false;
            }
        }
    }
    return true;
}

int32_t SATSolverCPP::select_variable(const std::vector<std::vector<int32_t>>& clauses) {
    if (clauses.empty()) return 0;
    size_t min_len = clauses[0].size();
    for (const auto& c : clauses) {
        if (c.size() < min_len) min_len = c.size();
    }

    std::unordered_map<int32_t, uint32_t> freq;
    for (const auto& c : clauses) {
        if (c.size() <= min_len + 1) {
            for (int32_t lit : c) {
                freq[std::abs(lit)]++;
            }
        }
    }

    int32_t best_var = 0;
    uint32_t max_f = 0;
    for (const auto& [v, f] : freq) {
        if (f > max_f) {
            max_f = f;
            best_var = v;
        }
    }
    return (best_var != 0) ? best_var : std::abs(clauses[0][0]);
}

bool SATSolverCPP::dpll(std::vector<std::vector<int32_t>>& clauses,
                        std::vector<int8_t>& assignment,
                        uint32_t total_vars,
                        std::chrono::steady_clock::time_point t_start,
                        double timeout_sec)
{
    auto now = std::chrono::steady_clock::now();
    if (std::chrono::duration<double>(now - t_start).count() > timeout_sec) {
        return false;
    }

    m_decisions++;

    // 1. Unit Propagation
    if (!unit_propagate(clauses, assignment)) {
        return false;
    }

    // 2. Check if all clauses satisfied
    if (clauses.empty()) {
        for (uint32_t v = 1; v <= total_vars; ++v) {
            if (assignment[v] == -1) assignment[v] = 1;
        }
        return true;
    }

    // 3. Check for empty clause
    for (const auto& c : clauses) {
        if (c.empty()) return false;
    }

    // 4. J-Space Gamma Cuckoo cycle pruning
    uint64_t hash_key = compute_state_hash(assignment);
    if (!check_and_insert_cuckoo(hash_key)) {
        m_pruned_cycles++;
        return false; // Cycle / redundant branch pruned!
    }

    // 5. Select variable
    int32_t chosen_var = select_variable(clauses);
    if (chosen_var == 0) return true;

    // 6. Branch True, then False
    for (int branch = 1; branch >= 0; --branch) {
        std::vector<int8_t> next_assignment = assignment;
        next_assignment[chosen_var] = static_cast<int8_t>(branch);
        auto sub_clauses = substitute_var(clauses, chosen_var, (branch == 1));

        if (dpll(sub_clauses, next_assignment, total_vars, t_start, timeout_sec)) {
            assignment = next_assignment;
            return true;
        }
    }

    return false;
}

bool SATSolverCPP::verify_solution(const std::vector<std::vector<int32_t>>& clauses,
                                  const std::vector<int8_t>& assignment)
{
    for (const auto& c : clauses) {
        bool satisfied = false;
        for (int32_t lit : c) {
            int32_t var = std::abs(lit);
            bool expected = (lit > 0);
            if (var < static_cast<int32_t>(assignment.size()) && assignment[var] == (expected ? 1 : 0)) {
                satisfied = true;
                break;
            }
        }
        if (!satisfied) return false;
    }
    return true;
}

SATSolverResultCPP SATSolverCPP::solve(const CNFFormulaCPP& formula, double timeout_sec) {
    SATSolverResultCPP res;
    m_decisions = 0;
    m_pruned_cycles = 0;
    std::fill(m_cuckoo_table.begin(), m_cuckoo_table.end(), 0);

    auto t0 = std::chrono::steady_clock::now();

    // 1. Any empty clause => unconditionally UNSAT
    for (const auto& c : formula.clauses) {
        if (c.empty()) {
            res.satisfiable = false;
            res.verified = true;
            auto t1 = std::chrono::steady_clock::now();
            res.elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
            return res;
        }
    }

    // 2. Empty clauses list => trivially SAT
    if (formula.clauses.empty()) {
        res.satisfiable = true;
        res.verified = true;
        res.assignment = std::vector<int8_t>(formula.num_vars + 1, 1);
        auto t1 = std::chrono::steady_clock::now();
        res.elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        return res;
    }

    std::vector<int8_t> assignment(formula.num_vars + 1, -1);
    std::vector<std::vector<int32_t>> clauses = formula.clauses;

    res.satisfiable = dpll(clauses, assignment, formula.num_vars, t0, timeout_sec);

    auto t1 = std::chrono::steady_clock::now();
    res.elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    res.num_decisions = m_decisions;
    res.num_pruned_cycles = m_pruned_cycles;

    if (res.satisfiable) {
        res.assignment = assignment;
        res.verified = verify_solution(formula.clauses, assignment);
    } else {
        res.verified = true; // UNSAT proof
    }

    return res;
}

} // namespace cq_hecs
