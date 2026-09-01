#include <iostream>
#include <vector>
#include <cassert>
#include "vulkan_engine.hpp"
#include "entropy_harvester.hpp"
#include "tiered_storage.hpp"
#include "qasm_parser.hpp"
#include "sat_solver.hpp"
#include "arx_engine.hpp"

#ifdef _WIN32
#define _CRTDBG_MAP_ALLOC
#include <stdlib.h>
#include <crtdbg.h>
#endif

using namespace cq_hecs;

int main() {
#if defined(_WIN32) && defined(_DEBUG)
    _CrtSetDbgFlag(_CRTDBG_ALLOC_MEM_DF | _CRTDBG_LEAK_CHECK_DF);
#endif

    std::cout << "[CPP Self-Test] Testing ARX Engine Boundary Values...\n";
    {
        ARXEngineCPP arx;
        uint64_t a = 0ULL, b = 0xFFFFFFFFFFFFFFFFULL;
        uint64_t sx = 0, cs = 0;
        ARXEngineCPP::linearize_add_64(a, b, sx, cs);
        if ((sx + cs) != (a + b)) return 1;

        uint64_t a2 = 0x7FFFFFFFFFFFFFFFULL, b2 = 0x8000000000000000ULL;
        ARXEngineCPP::linearize_add_64(a2, b2, sx, cs);
        if ((sx + cs) != (a2 + b2)) return 1;

        auto b_blake = arx.benchmark_blake2b(100);
        if (!b_blake.inverse_verified || !b_blake.carry_shadow_exact) return 1;
    }

    std::cout << "[CPP Self-Test] Testing SAT Solver Empty / Trivial Clauses...\n";
    {
        SATSolverCPP solver(1024);
        CNFFormulaCPP empty_formula;
        auto res_empty = solver.solve(empty_formula);
        if (!res_empty.satisfiable) return 1;

        CNFFormulaCPP unsat_formula;
        unsat_formula.num_vars = 1;
        unsat_formula.clauses.push_back({}); // empty clause
        auto res_unsat = solver.solve(unsat_formula);
        if (res_unsat.satisfiable) return 1;
    }

    std::cout << "[CPP Self-Test] Testing QASM Parser Graceful Degradation...\n";
    {
        QASMParserCPP parser;
        QASMCircuitData circuit;
        bool ok = parser.parse_string("// Only comments\n\n", circuit);
        if (!ok || !circuit.commands.empty()) {
            std::cerr << "Failed comment test: ok=" << ok << ", size=" << circuit.commands.size() << "\n";
            return 1;
        }

        bool ok_malformed = parser.parse_string("OPENQASM 2.0;\nqreg q[10];\ncp(invalid) q[0], q[1];\n", circuit);
        if (!ok_malformed || circuit.commands.size() != 1) {
            std::cerr << "Failed malformed test: ok=" << ok_malformed << ", size=" << circuit.commands.size() << "\n";
            return 1;
        }
    }

    std::cout << "[CPP Self-Test] Testing Tiered Storage Swap File Re-entry...\n";
    {
        for (int i = 0; i < 3; ++i) {
            TieredStorageGovernor gov(120ULL * 1024ULL * 1024ULL, L"cq_test_swap.bin");
            std::vector<uint8_t> dummy(64 * 1024, 0xEE);
            uint32_t p = gov.allocate_page(dummy.size(), dummy.data());
            gov.evict_page_to_cold_storage(p);
            void* r = gov.fetch_page_to_memory(p);
            if (r == nullptr) return 1;
            gov.free_page(p);
        }
    }

    std::cout << "[CPP Self-Test] ALL NATIVE C++ HARDENING CHECKS PASSED.\n";
    return 0;
}
