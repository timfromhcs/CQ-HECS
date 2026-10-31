#ifndef CQ_HECS_API_H
#define CQ_HECS_API_H

#define CQ_HECS_VERSION "3.5.0"

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef CQ_HECS_EXPORTS
    #define CQ_API __declspec(dllexport)
  #elif defined(CQ_HECS_STATIC)
    #define CQ_API
  #else
    #define CQ_API __declspec(dllimport)
  #endif
#else
  #if __GNUC__ >= 4
    #define CQ_API __attribute__((visibility("default")))
  #else
    #define CQ_API
  #endif
#endif

typedef struct cq_context cq_context_t;

typedef struct {
    uint32_t gate_count;
    uint32_t qubit_count;
    double elapsed_ms;
    double active_vram_mb;
    double lambda_res;
    int success;
} cq_result_t;

typedef struct {
    int satisfiable;       // 1 if SAT, 0 if UNSAT, -1 if timeout/error
    uint32_t num_vars;
    uint32_t num_clauses;
    uint32_t decisions;
    uint32_t pruned_cycles;
    double elapsed_ms;
    int verified;
    int8_t assignment[1024]; // 1 for true, 0 for false, -1 for unassigned
} cq_sat_result_t;

CQ_API cq_context_t* cq_create_context(uint32_t num_qubits, uint32_t bond_dim);
CQ_API int cq_execute_qasm(cq_context_t* ctx, const char* qasm_str, cq_result_t* out_result);
CQ_API int cq_solve_sat(const char* cnf_str, cq_sat_result_t* out_result);
CQ_API int cq_invert_arx(const char* primitive, uint32_t rounds, const uint64_t* target, uint64_t* out_preimage);
CQ_API void cq_destroy_context(cq_context_t* ctx);

CQ_API const char* cq_get_version(void);
CQ_API double cq_get_active_vram_mb(cq_context_t* ctx);

/* OMNIWAVE (experimental): one batched BCP evaluation pass on the Vulkan device.
 * Status word per (front, clause): 0 SAT, 1 CONFLICT, 2|(code<<2) UNIT, 3 OPEN;
 * bit-identical to cqhecs.omniwave.bcp.evaluate_batch. Returns 0 on success,
 * -2 if no Vulkan device is available, other values on invalid input or failure. */
CQ_API int cq_omniwave_bcp_eval(const uint32_t* offsets, const uint32_t* codes, uint32_t num_clauses,
                                const uint32_t* assigned, const uint32_t* values, uint32_t num_fronts,
                                uint32_t words, uint32_t* out_status);
/* Name of the Vulkan device used by the OMNIWAVE kernels; -2 if none. */
CQ_API int cq_omniwave_device_name(char* out, uint32_t capacity);
/* Release the lazily created OMNIWAVE Vulkan context. Safe to call repeatedly.
 * Call before process/library teardown so Vulkan objects are destroyed while the
 * loader and driver are still mapped. */
CQ_API void cq_omniwave_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif // CQ_HECS_API_H
