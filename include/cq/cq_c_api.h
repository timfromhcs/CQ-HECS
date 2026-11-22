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

/* ABI version. MAJOR changes on any incompatible change; MINOR on additions.
   1.1 added: cq_core_abi_version, cq_core_check_abi, cq_core_last_error,
   cq_core_clear_error, argument validation on every entry point. */
#define CQ_CORE_ABI_MAJOR 1
#define CQ_CORE_ABI_MINOR 1

/* Thread-local error codes reported by cq_core_last_error(). Entry points that
   return void (gates, reset) set it; it is reset to CQ_CORE_OK by each call
   that validates its handle. A refused operation changes no state. */
#define CQ_CORE_OK 0
#define CQ_CORE_ERR_NULL_HANDLE 1
#define CQ_CORE_ERR_QUBIT_RANGE 2
#define CQ_CORE_ERR_DUPLICATE_QUBIT 3
#define CQ_CORE_ERR_INVALID_ARG 4
#define CQ_CORE_ERR_UNSUPPORTED 6  /* e.g. a non-Clifford gate on a simulator wider than 16 qubits */
#define CQ_CORE_ERR_INTERNAL 7
#define CQ_CORE_ERR_NO_MEMORY 9

/* (major << 16) | minor of the loaded library. */
CQ_API uint32_t cq_core_abi_version(void);
/* 0 when the library is ABI-compatible with a caller built against
   (expected_major, expected_minor); -1 otherwise. Call before any other entry point. */
CQ_API int cq_core_check_abi(uint32_t expected_major, uint32_t expected_minor);
CQ_API int cq_core_last_error(void);
CQ_API void cq_core_clear_error(void);

/* JSON describing how this library was built, e.g.
   {"cpu_core":true,"vulkan_linked":false}. Static string; do not free. */
CQ_API const char* cq_core_build_capabilities(void);

/* Returns NULL (and sets the last error) when num_qubits is 0 or > 4096,
   max_bond_dim is 0 or > 65536, or allocation fails. */
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

/* Qubit indices are checked against the simulator; an out-of-range index, a
   repeated two-qubit operand or a non-finite angle is refused (no state change)
   and reported via cq_core_last_error(). */
CQ_API uint8_t cq_measure_qubit(CQSimulatorHandle handle, uint32_t q);
/* Return codes (sample/execute): 0 ok; -1 NULL argument or zero-size buffer;
   -2 buffer too small; -3 invalid circuit (parse/validation error); -4 refused
   (shots > 16777216, RX/RY, non-Clifford gate on a simulator wider than 16
   qubits, or a gate after a measurement); -5 QASM text longer than 16 MiB;
   -6 circuit uses more qubits than the simulator; -7 internal error.
   On any non-zero return out_json holds an empty string (execute) and the
   circuit was validated in full before any gate ran. */
CQ_API int cq_sample_counts_json(CQSimulatorHandle handle, uint32_t shots, char* out_json, size_t max_len);
CQ_API int cq_execute_qasm(CQSimulatorHandle handle, const char* qasm_str, uint32_t shots, char* out_json, size_t max_len);

#ifdef __cplusplus
}
#endif

#endif // CQ_C_API_H
