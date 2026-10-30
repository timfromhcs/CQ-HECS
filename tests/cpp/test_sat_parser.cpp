// Native DIMACS parser / solver contract tests.
//
// Regression coverage for defects found by adversarial probing:
//   * a negative header count crashed with an access violation,
//   * a huge declared variable count hung while allocating,
//   * literals above 100000 were silently dropped, turning a SAT formula into
//     an "UNSAT" empty clause,
//   * a timeout was reported as UNSAT,
//   * the cycle-pruning hash ignored variables above index 32.

#include <cstdint>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include "sat_solver.hpp"

using namespace cq_hecs;

static int failures = 0;

static void check(bool condition, const std::string& label) {
    if (condition) {
        std::cout << "  [PASS] " << label << "\n";
    } else {
        std::cout << "  [FAIL] " << label << "\n";
        ++failures;
    }
}

static bool rejects(const std::string& source, const std::string& label) {
    SATSolverCPP solver(1024);
    CNFFormulaCPP formula;
    std::string error;
    const bool parsed = solver.parse_string(source, formula, &error);
    const bool ok = !parsed && !error.empty();
    if (!ok) std::cout << "    (accepted or empty error: " << label << ")\n";
    return ok;
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS [Contract]: DIMACS parser and solver hardening\n";
    std::cout << "=================================================================\n";

    // --- accepted formulas -------------------------------------------------
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        check(solver.parse_string("", formula, &error),
              "empty input is an empty, trivially SAT formula");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified && res.input_valid && !res.timed_out,
              "empty formula solves SAT and verified");
    }
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        const std::string cnf = "p cnf 4 3\n1 2 -3 0\n-1 3 4 0\n-2 -4 1 0\n";
        check(solver.parse_string(cnf, formula, &error), "valid DIMACS parses");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified, "valid DIMACS solves SAT");
    }
    {
        // Formerly dropped: |literal| > 100000.
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        check(solver.parse_string("p cnf 100001 1\n100001 0\n", formula, &error),
              "literal 100001 is accepted, not silently dropped");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified && formula.num_vars == 100001,
              "literal 100001 solves SAT (formerly reported UNSAT)");
    }
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        check(solver.parse_string("p cnf 3 1\n1 1 2 0\n", formula, &error),
              "duplicate literals parse");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified, "duplicate literals solve SAT");
    }
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        check(solver.parse_string("p cnf 2 1\n1 -1 0\n", formula, &error),
              "tautology parses");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified, "tautology solves SAT");
    }
    {
        // Cycle pruning must not ignore variables above index 32.
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        const std::string cnf = "p cnf 40 2\n40 39 0\n-40 -39 0\n";
        check(solver.parse_string(cnf, formula, &error), "40-variable XOR parses");
        auto res = solver.solve(formula);
        check(res.satisfiable && res.verified,
              "40-variable XOR is SAT (hash covers vars > 32)");
    }

    // --- rejected formulas -------------------------------------------------
    check(rejects("p cnf -1 1\n1 0\n", "negative variable count"),
          "negative variable count is rejected");
    check(rejects("p cnf 100000000 1\n1 0\n", "huge variable count"),
          "variable count above the ceiling is rejected");
    check(rejects("p cnf 2 100000000\n1 0\n", "huge clause count"),
          "clause count above the ceiling is rejected");
    check(rejects("p cnf 2 1\n1 2\n", "unterminated clause"),
          "clause not terminated by 0 is rejected");
    check(rejects("p cnf 2 one\n", "malformed header count"),
          "malformed header is rejected");
    check(rejects("p cnf\n", "bare header"),
          "bare header is rejected");
    check(rejects("p cnf 2 1\n1 two 0\n", "non-numeric literal"),
          "non-numeric literal is rejected");
    check(rejects("p cnf 2 1\n2000000 0\n", "literal above ceiling"),
          "literal above the variable ceiling is rejected");
    check(rejects("p cnf 2 1\n3 0\n", "declared variable count"),
          "literal above the declared variable count is rejected");
    check(rejects("p cnf 2 1\n1 0\np cnf 2 1\n1 0\n", "duplicate header"),
          "duplicate header is rejected");

    // --- timeout is not UNSAT ---------------------------------------------
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        std::string error;
        // A formula with decisions available: 8 vars, 16 three-literal clauses.
        std::string cnf = "p cnf 8 16\n";
        for (int i = 1; i <= 8; ++i) {
            for (int k = 0; k < 2; ++k) {
                cnf += std::to_string(i) + " " +
                       std::to_string((i % 8) + 1) + " " +
                       std::to_string(((i + 2) % 8) + 1) + " 0\n";
            }
        }
        check(solver.parse_string(cnf, formula, &error), "timeout fixture parses");
        auto res = solver.solve(formula, 0.0);
        check(res.timed_out && !res.verified && !res.error.empty(),
              "zero-budget solve reports a timeout, not UNSAT");
    }

    // --- defensive solve() validation -------------------------------------
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP formula;
        formula.num_vars = 2;
        formula.clauses = {{3, -3}};  // literal outside declared range
        auto res = solver.solve(formula);
        check(!res.input_valid && !res.error.empty(),
              "out-of-range literal is refused before allocation");
    }

    // --- exhaustive differential against brute force ----------------------
    // Pruning uses exact assignment keys; a tiny memo capacity (1) and a large
    // one must both agree with brute force on every instance.
    {
        std::mt19937 rng(20261030u);
        int mismatches = 0;
        for (int round = 0; round < 400; ++round) {
            const uint32_t n = 1 + rng() % 9;
            const uint32_t m = 1 + rng() % (4 * n);
            CNFFormulaCPP formula;
            formula.num_vars = n;
            for (uint32_t c = 0; c < m; ++c) {
                std::vector<int32_t> clause;
                const uint32_t width = 1 + rng() % (n < 3 ? n : 3);
                while (clause.size() < width) {
                    const int32_t v = static_cast<int32_t>(1 + rng() % n);
                    bool seen = false;
                    for (int32_t lit : clause) seen = seen || (lit == v || lit == -v);
                    if (!seen) clause.push_back((rng() & 1u) ? v : -v);
                }
                formula.clauses.push_back(clause);
            }
            formula.num_clauses = m;
            bool expected = false;
            for (uint32_t bits = 0; bits < (1u << n) && !expected; ++bits) {
                bool all = true;
                for (const auto& clause : formula.clauses) {
                    bool any = false;
                    for (int32_t lit : clause) {
                        const bool value = (bits >> (std::abs(lit) - 1)) & 1u;
                        any = any || (value == (lit > 0));
                    }
                    all = all && any;
                }
                expected = all;
            }
            for (size_t capacity : {static_cast<size_t>(1), static_cast<size_t>(4096)}) {
                SATSolverCPP solver(capacity);
                auto res = solver.solve(formula, 30.0);
                if (res.timed_out || !res.verified || res.satisfiable != expected) ++mismatches;
            }
        }
        check(mismatches == 0, "400 random CNFs agree with brute force (memo capacity 1 and 4096)");
    }

    std::cout << "-----------------------------------------------------------------\n";
    if (failures == 0) {
        std::cout << ">>> [PASS] DIMACS parser/solver contract: all checks passed.\n";
        return 0;
    }
    std::cerr << ">>> [FAIL] " << failures << " DIMACS parser/solver check(s) failed.\n";
    return 1;
}
