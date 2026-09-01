#ifndef CQ_C_API_H
#define CQ_C_API_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32) || defined(__CYGWIN__)
  #ifdef CQ_EXPORTS
    #define CQ_API __declspec(dllexport)
  #else
    #define CQ_API
  #endif
#else
  #define CQ_API __attribute__((visibility("default")))
#endif

typedef void* CQSimulatorHandle;

CQ_API CQSimulatorHandle cq_create_simulator(uint32_t num_qubits, uint32_t max_bond_dim);
CQ_API void cq_destroy_simulator(CQSimulatorHandle handle);
CQ_API void cq_reset(CQSimulatorHandle handle);

CQ_API void cq_apply_h(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_s(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_sdg(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_t(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_tdg(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_x(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_y(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_z(CQSimulatorHandle handle, uint32_t q);
CQ_API void cq_apply_cx(CQSimulatorHandle handle, uint32_t ctrl, uint32_t tgt);
CQ_API void cq_apply_swap(CQSimulatorHandle handle, uint32_t q1, uint32_t q2);
CQ_API void cq_apply_rz(CQSimulatorHandle handle, uint32_t q, double angle_rad);

CQ_API uint8_t cq_measure_qubit(CQSimulatorHandle handle, uint32_t q);
CQ_API int cq_sample_counts_json(CQSimulatorHandle handle, uint32_t shots, char* out_json, size_t max_len);
CQ_API int cq_execute_qasm(CQSimulatorHandle handle, const char* qasm_str, uint32_t shots, char* out_json, size_t max_len);

#ifdef __cplusplus
}
#endif

#endif // CQ_C_API_H
