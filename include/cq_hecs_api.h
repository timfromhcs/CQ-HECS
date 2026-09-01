#ifndef CQ_HECS_API_H
#define CQ_HECS_API_H

#define CQ_HECS_VERSION "0.2.0"

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

#ifdef __cplusplus
}
#endif

#endif // CQ_HECS_API_H
