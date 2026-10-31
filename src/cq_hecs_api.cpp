#include "cq_hecs_api.h"
#include "vulkan_engine.hpp"
#include "qasm_parser.hpp"
#include "sat_solver.hpp"
#include "arx_engine.hpp"
#include "cq_hecs/vulkan/vulkan_buffer.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"
#include <mutex>
#include <vector>
#include <cstring>
#include <memory>
#include <iostream>

struct cq_context {
    uint32_t num_qubits;
    uint32_t bond_dim;
    std::unique_ptr<cq_hecs::VulkanEngine> engine;
};

namespace {

// One lazily created Vulkan context for the OMNIWAVE kernels. initialize() picks
// the device by the shared device policy; failure is reported, never hidden.
std::mutex g_omniwave_mutex;
std::unique_ptr<cq_hecs::VulkanContext> g_omniwave_ctx;
bool g_omniwave_tried = false;

cq_hecs::VulkanContext* omniwave_context() {
    if (!g_omniwave_tried) {
        g_omniwave_tried = true;
        auto ctx = std::make_unique<cq_hecs::VulkanContext>();
        if (ctx->initialize()) g_omniwave_ctx = std::move(ctx);
    }
    return g_omniwave_ctx.get();
}

bool upload(cq_hecs::VulkanContext& ctx, cq_hecs::VulkanBuffer& buf, const void* data, size_t bytes) {
    size_t size = bytes > 0 ? bytes : 4;  // zero-sized storage buffers are not allowed
    if (!buf.allocate(ctx.get_device(), ctx.get_physical_device(), static_cast<VkDeviceSize>(size),
                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                      VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                      ctx.get_memory_manager())) {
        return false;
    }
    if (data && bytes) buf.copy_to_buffer(data, bytes);
    return true;
}

}  // namespace

extern "C" {

CQ_API int cq_omniwave_device_name(char* out, uint32_t capacity) {
    if (!out || capacity == 0) return 1;
    std::lock_guard<std::mutex> lock(g_omniwave_mutex);
    cq_hecs::VulkanContext* ctx = omniwave_context();
    if (!ctx) { out[0] = '\0'; return -2; }
    std::string name = ctx->get_device_name();
    const size_t n = name.size() < capacity - 1 ? name.size() : capacity - 1;
    std::memcpy(out, name.data(), n);
    out[n] = 0;
    return 0;
}

CQ_API void cq_omniwave_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_omniwave_mutex);
    g_omniwave_ctx.reset();
    g_omniwave_tried = false;
}

CQ_API int cq_omniwave_bcp_eval(const uint32_t* offsets, const uint32_t* codes, uint32_t num_clauses,
                                const uint32_t* assigned, const uint32_t* values, uint32_t num_fronts,
                                uint32_t words, uint32_t* out_status) {
    if (!offsets || !assigned || !values || !out_status || num_clauses == 0 || num_fronts == 0 || words == 0) {
        return 1;
    }
    if (num_fronts > 65535u) return 2;
    std::lock_guard<std::mutex> lock(g_omniwave_mutex);
    cq_hecs::VulkanContext* ctx = omniwave_context();
    if (!ctx) return -2;  // no Vulkan device: the caller must use the CPU reference
    const size_t lits = offsets[num_clauses];
    const size_t front_words = static_cast<size_t>(num_fronts) * words;
    const size_t cells = static_cast<size_t>(num_fronts) * num_clauses;
    cq_hecs::VulkanBuffer b_off, b_codes, b_assigned, b_values, b_status;
    if (!upload(*ctx, b_off, offsets, (num_clauses + 1) * sizeof(uint32_t)) ||
        !upload(*ctx, b_codes, codes, lits * sizeof(uint32_t)) ||
        !upload(*ctx, b_assigned, assigned, front_words * sizeof(uint32_t)) ||
        !upload(*ctx, b_values, values, front_words * sizeof(uint32_t)) ||
        !upload(*ctx, b_status, nullptr, cells * sizeof(uint32_t))) {
        return -3;
    }
    if (!ctx->dispatch_omniwave_bcp(b_off, b_codes, b_assigned, b_values, b_status, num_clauses, num_fronts, words)) {
        return -4;
    }
    b_status.copy_from_buffer(out_status, cells * sizeof(uint32_t));
    return 0;
}


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

    *out_result = cq_result_t{};
    cq_hecs::QASMParserCPP parser;
    cq_hecs::QASMCircuitData circuit;
    if (!parser.parse_string(qasm_str, circuit) || !circuit.ok()) {
        // -3 is the documented "invalid circuit input" status. The result is
        // zeroed and success remains 0; no partial circuit is executed.
        return -3;
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
    return CQ_HECS_VERSION;
}

CQ_API double cq_get_active_vram_mb(cq_context_t* ctx) {
    if (!ctx || !ctx->engine) return 0.0;
    return static_cast<double>(ctx->engine->get_active_vram_bytes()) / (1024.0 * 1024.0);
}

} // extern "C"
