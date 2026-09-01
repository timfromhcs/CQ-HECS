#include "cq_hecs_api.h"
#include "vulkan_engine.hpp"
#include "qasm_parser.hpp"
#include "sat_solver.hpp"
#include "arx_engine.hpp"
#include <cstring>
#include <memory>
#include <iostream>

struct cq_context {
    uint32_t num_qubits;
    uint32_t bond_dim;
    std::unique_ptr<cq_hecs::VulkanEngine> engine;
};

extern "C" {

CQ_API cq_context_t* cq_create_context(uint32_t num_qubits, uint32_t bond_dim) {
    auto ctx = new cq_context();
    ctx->num_qubits = num_qubits > 0 ? num_qubits : 300;
    ctx->bond_dim = bond_dim > 0 ? bond_dim : 64;
    ctx->engine = std::make_unique<cq_hecs::VulkanEngine>();

    if (ctx->engine->initialize()) {
        ctx->engine->allocate_300q_mps(ctx->bond_dim);
    }
    return ctx;
}

CQ_API int cq_execute_qasm(cq_context_t* ctx, const char* qasm_str, cq_result_t* out_result) {
    if (!ctx || !qasm_str || !out_result) return 1;

    cq_hecs::QASMParserCPP parser;
    cq_hecs::QASMCircuitData circuit;
    if (!parser.parse_string(qasm_str, circuit)) {
        return 1;
    }

    cq_hecs::QASMExecutionResult res = parser.execute_on_vulkan(circuit, *ctx->engine);
    out_result->gate_count = res.gate_count;
    out_result->qubit_count = res.qubit_count;
    out_result->elapsed_ms = res.elapsed_ms;
    out_result->active_vram_mb = static_cast<double>(ctx->engine->get_active_vram_bytes()) / (1024.0 * 1024.0);
    out_result->lambda_res = 0.0;
    out_result->success = res.success ? 1 : 0;
    return res.success ? 0 : 1;
}

CQ_API int cq_solve_sat(const char* cnf_str, cq_sat_result_t* out_result) {
    if (!cnf_str || !out_result) return 1;

    cq_hecs::SATSolverCPP solver(8192);
    cq_hecs::CNFFormulaCPP formula;
    if (!solver.parse_string(cnf_str, formula)) {
        return 1;
    }

    cq_hecs::SATSolverResultCPP res = solver.solve(formula, 10.0);
    out_result->satisfiable = res.satisfiable ? 1 : 0;
    out_result->num_vars = formula.num_vars;
    out_result->num_clauses = formula.num_clauses;
    out_result->decisions = static_cast<uint32_t>(res.num_decisions);
    out_result->pruned_cycles = static_cast<uint32_t>(res.num_pruned_cycles);
    out_result->elapsed_ms = res.elapsed_ms;
    out_result->verified = res.verified ? 1 : 0;

    std::memset(out_result->assignment, -1, sizeof(out_result->assignment));
    if (res.satisfiable) {
        for (size_t v = 1; v < res.assignment.size() && v < 1024; ++v) {
            out_result->assignment[v] = res.assignment[v];
        }
    }
    // Solver semantics: 0 for SAT, 10 for UNSAT
    return res.satisfiable ? 0 : 10;
}

CQ_API int cq_invert_arx(const char* primitive, uint32_t rounds, const uint64_t* target, uint64_t* out_preimage) {
    (void)rounds;
    if (!primitive || !target || !out_preimage) return 1;

    cq_hecs::ARXEngineCPP arx;
    if (std::strcmp(primitive, "blake2b") == 0) {
        uint64_t a = target[0], b = target[1], c = target[2], d = target[3];
        arx.blake2b_g_backward(a, b, c, d, 0x1234, 0x5678);
        out_preimage[0] = a; out_preimage[1] = b; out_preimage[2] = c; out_preimage[3] = d;
        return 0;
    } else if (std::strcmp(primitive, "chacha20") == 0) {
        uint32_t a = static_cast<uint32_t>(target[0]);
        uint32_t b = static_cast<uint32_t>(target[1]);
        uint32_t c = static_cast<uint32_t>(target[2]);
        uint32_t d = static_cast<uint32_t>(target[3]);
        arx.chacha20_qr_backward(a, b, c, d);
        out_preimage[0] = a; out_preimage[1] = b; out_preimage[2] = c; out_preimage[3] = d;
        return 0;
    } else if (std::strcmp(primitive, "sha256") == 0) {
        uint32_t wt = static_cast<uint32_t>(target[0]);
        uint32_t wt2 = static_cast<uint32_t>(target[1]);
        uint32_t wt7 = static_cast<uint32_t>(target[2]);
        uint32_t wt15 = static_cast<uint32_t>(target[3]);
        out_preimage[0] = arx.sha256_invert_step(wt, wt2, wt7, wt15);
        return 0;
    }
    return 1;
}

CQ_API void cq_destroy_context(cq_context_t* ctx) {
    if (ctx) {
        if (ctx->engine) {
            ctx->engine->free_mps();
        }
        delete ctx;
    }
}

CQ_API const char* cq_get_version(void) {
    return "4.5.0";
}

CQ_API double cq_get_active_vram_mb(cq_context_t* ctx) {
    if (!ctx || !ctx->engine) return 0.0;
    return static_cast<double>(ctx->engine->get_active_vram_bytes()) / (1024.0 * 1024.0);
}

} // extern "C"
