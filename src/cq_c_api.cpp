#define CQ_EXPORTS
#include "cq/cq_c_api.h"
#include "cq/hybrid_engine.hpp"
#include "cq/qasm_parser.hpp"
#include <cmath>
#include <cstring>
#include <exception>
#include <new>
#include <sstream>
#include <vector>

#ifndef CQ_NATIVE_VULKAN
#define CQ_NATIVE_VULKAN 0
#endif

// C ABI hardening contract (AGENTS_V7 W4-18):
//   * No C++ exception ever crosses the boundary: every entry point is wrapped.
//   * Every pointer argument is checked; every qubit index is range-checked
//     against the simulator it is used on; sizes are bounded before allocation.
//   * Unsupported work is REFUSED (and reported through the thread-local last
//     error), never skipped or approximated. In particular the hybrid engine
//     keeps a shadow statevector only up to 16 qubits, so a non-Clifford gate on
//     a wider simulator would silently return a wrong state; it is refused here.
//   * void entry points cannot return a status, so they set cq_core_last_error().
namespace {

constexpr uint32_t kMaxQubits = 4096;
constexpr uint32_t kMaxBondDim = 65536;
constexpr uint32_t kMaxShots = 1u << 24;
constexpr size_t kMaxQasmBytes = 16u * 1024u * 1024u;
constexpr uint32_t kMaxStatevectorQubits = 16;  // HybridEngine shadow statevector width

thread_local int g_last_error = CQ_CORE_OK;

inline void set_error(int code) { g_last_error = code; }

inline cq::HybridEngine* engine_of(CQSimulatorHandle h) {
    if (!h) {
        set_error(CQ_CORE_ERR_NULL_HANDLE);
        return nullptr;
    }
    set_error(CQ_CORE_OK);
    return static_cast<cq::HybridEngine*>(h);
}

inline bool qubit_ok(const cq::HybridEngine* e, uint32_t q) {
    if (q >= e->num_qubits) {
        set_error(CQ_CORE_ERR_QUBIT_RANGE);
        return false;
    }
    return true;
}

inline bool pair_ok(const cq::HybridEngine* e, uint32_t a, uint32_t b) {
    if (!qubit_ok(e, a) || !qubit_ok(e, b)) return false;
    if (a == b) {
        set_error(CQ_CORE_ERR_DUPLICATE_QUBIT);
        return false;
    }
    return true;
}

inline bool non_clifford_ok(const cq::HybridEngine* e) {
    if (e->num_qubits > kMaxStatevectorQubits) {
        set_error(CQ_CORE_ERR_UNSUPPORTED);
        return false;
    }
    return true;
}

template <class F>
inline void guarded(F&& fn) noexcept {
    try {
        fn();
    } catch (...) {
        set_error(CQ_CORE_ERR_INTERNAL);
    }
}

}  // namespace

extern "C" {

// Reports the build configuration so callers never infer a GPU path from the
// presence of the library. cq_hecs_core itself is CPU-only in both configurations.
CQ_API const char* cq_core_build_capabilities(void) {
#if CQ_NATIVE_VULKAN
    return "{\"cpu_core\":true,\"vulkan_linked\":true}";
#else
    return "{\"cpu_core\":true,\"vulkan_linked\":false}";
#endif
}

CQ_API uint32_t cq_core_abi_version(void) {
    return (static_cast<uint32_t>(CQ_CORE_ABI_MAJOR) << 16) | static_cast<uint32_t>(CQ_CORE_ABI_MINOR);
}

CQ_API int cq_core_check_abi(uint32_t expected_major, uint32_t expected_minor) {
    // Same major: compatible provided the library is at least as new as the caller expects.
    if (expected_major != static_cast<uint32_t>(CQ_CORE_ABI_MAJOR)) return -1;
    if (expected_minor > static_cast<uint32_t>(CQ_CORE_ABI_MINOR)) return -1;
    return 0;
}

CQ_API int cq_core_last_error(void) { return g_last_error; }

CQ_API void cq_core_clear_error(void) { g_last_error = CQ_CORE_OK; }

CQ_API CQSimulatorHandle cq_create_simulator(uint32_t num_qubits, uint32_t max_bond_dim) {
    set_error(CQ_CORE_OK);
    if (num_qubits == 0 || num_qubits > kMaxQubits || max_bond_dim == 0 || max_bond_dim > kMaxBondDim) {
        set_error(CQ_CORE_ERR_INVALID_ARG);
        return nullptr;
    }
    try {
        return static_cast<CQSimulatorHandle>(new cq::HybridEngine(num_qubits, max_bond_dim));
    } catch (const std::bad_alloc&) {
        set_error(CQ_CORE_ERR_NO_MEMORY);
    } catch (...) {
        set_error(CQ_CORE_ERR_INTERNAL);
    }
    return nullptr;
}

CQ_API void cq_destroy_simulator(CQSimulatorHandle handle) {
    if (handle) {
        guarded([&] { delete static_cast<cq::HybridEngine*>(handle); });
    }
}

CQ_API void cq_reset(CQSimulatorHandle handle) {
    if (auto* e = engine_of(handle)) guarded([&] { e->reset(); });
}

#define CQ_CLIFFORD_1Q(NAME, CALL)                                          \
    CQ_API void NAME(CQSimulatorHandle handle, uint32_t q) {                \
        auto* e = engine_of(handle);                                        \
        if (!e || !qubit_ok(e, q)) return;                                  \
        guarded([&] { e->CALL(q); });                                       \
    }

CQ_CLIFFORD_1Q(cq_apply_h, apply_h)
CQ_CLIFFORD_1Q(cq_apply_s, apply_s)
CQ_CLIFFORD_1Q(cq_apply_sdg, apply_sdg)
CQ_CLIFFORD_1Q(cq_apply_x, apply_x)
CQ_CLIFFORD_1Q(cq_apply_y, apply_y)
CQ_CLIFFORD_1Q(cq_apply_z, apply_z)
#undef CQ_CLIFFORD_1Q

CQ_API void cq_apply_t(CQSimulatorHandle handle, uint32_t q) {
    auto* e = engine_of(handle);
    if (!e || !qubit_ok(e, q) || !non_clifford_ok(e)) return;
    guarded([&] { e->apply_t(q); });
}

CQ_API void cq_apply_tdg(CQSimulatorHandle handle, uint32_t q) {
    auto* e = engine_of(handle);
    if (!e || !qubit_ok(e, q) || !non_clifford_ok(e)) return;
    guarded([&] { e->apply_tdg(q); });
}

CQ_API void cq_apply_cx(CQSimulatorHandle handle, uint32_t ctrl, uint32_t tgt) {
    auto* e = engine_of(handle);
    if (!e || !pair_ok(e, ctrl, tgt)) return;
    guarded([&] { e->apply_cx(ctrl, tgt); });
}

CQ_API void cq_apply_swap(CQSimulatorHandle handle, uint32_t q1, uint32_t q2) {
    auto* e = engine_of(handle);
    if (!e || !pair_ok(e, q1, q2)) return;
    guarded([&] { e->apply_swap(q1, q2); });
}

CQ_API void cq_apply_rz(CQSimulatorHandle handle, uint32_t q, double angle_rad) {
    auto* e = engine_of(handle);
    if (!e || !qubit_ok(e, q)) return;
    if (!std::isfinite(angle_rad)) {
        set_error(CQ_CORE_ERR_INVALID_ARG);
        return;
    }
    if (!non_clifford_ok(e)) return;
    // Reduce to [0, 1) turns before the integer conversion: casting a negative or
    // out-of-range double to uint32_t is undefined behaviour.
    double turns = angle_rad / (2.0 * 3.141592653589793);
    turns -= std::floor(turns);
    double scaled = turns * 4294967296.0;
    uint32_t phase_q32 = scaled >= 4294967296.0 ? 0u : static_cast<uint32_t>(scaled);
    guarded([&] { e->apply_rz(q, phase_q32); });
}

CQ_API uint8_t cq_measure_qubit(CQSimulatorHandle handle, uint32_t q) {
    auto* e = engine_of(handle);
    if (!e || !qubit_ok(e, q)) return 0;
    uint8_t out = 0;
    guarded([&] { out = e->measure_qubit(q); });
    return out;
}

CQ_API int cq_sample_counts_json(CQSimulatorHandle handle, uint32_t shots, char* out_json, size_t max_len) {
    if (!handle || !out_json || max_len == 0) return -1;
    if (shots > kMaxShots) return -4;
    try {
        auto counts = static_cast<cq::HybridEngine*>(handle)->sample_counts(shots);

        std::ostringstream ss;
        ss << "{";
        bool first = true;
        for (const auto& [bitstring, count] : counts) {
            if (!first) ss << ", ";
            first = false;
            ss << "\"" << bitstring << "\": " << count;
        }
        ss << "}";

        std::string res = ss.str();
        if (res.size() >= max_len) return -2;
        std::memcpy(out_json, res.c_str(), res.size() + 1);
        return 0;
    } catch (...) {
        set_error(CQ_CORE_ERR_INTERNAL);
        return -7;
    }
}

CQ_API int cq_execute_qasm(CQSimulatorHandle handle, const char* qasm_str, uint32_t shots, char* out_json, size_t max_len) {
    if (!handle || !qasm_str || !out_json || max_len == 0) return -1;
    if (shots > kMaxShots) return -4;
    // Bounded length check without trusting the terminator beyond the cap.
    size_t len = 0;
    while (len <= kMaxQasmBytes && qasm_str[len] != '\0') ++len;
    if (len > kMaxQasmBytes) return -5;
    out_json[0] = '\0';

    try {
        auto* engine = static_cast<cq::HybridEngine*>(handle);
        engine->reset();

        auto circuit = cq::Qasm3Parser::parse_string(std::string(qasm_str, len));
        if (!circuit.ok()) {
            // Fail closed: never execute a circuit that failed validation.
            return -3;
        }
        if (circuit.num_qubits > engine->num_qubits) return -6;

        // Validate the WHOLE circuit before executing any instruction, so a
        // refusal never leaves a half-applied state behind.
        std::vector<bool> measured(engine->num_qubits, false);
        for (const auto& inst : circuit.instructions) {
            const size_t arity =
                (inst.type == cq::GateType::CX || inst.type == cq::GateType::SWAP) ? 2u : 1u;
            switch (inst.type) {
                case cq::GateType::BARRIER:
                    continue;
                case cq::GateType::MEASURE:
                    for (uint32_t q : inst.qubits) {
                        if (q >= engine->num_qubits) return -6;
                        measured[q] = true;
                    }
                    continue;
                case cq::GateType::RX:
                case cq::GateType::RY:
                    return -4;  // not implemented by this engine: refuse, do not skip
                case cq::GateType::T:
                case cq::GateType::TDG:
                case cq::GateType::RZ:
                    if (engine->num_qubits > kMaxStatevectorQubits) return -4;
                    break;
                default:
                    break;
            }
            if (inst.qubits.size() != arity) return -3;
            for (uint32_t q : inst.qubits) {
                if (q >= engine->num_qubits) return -6;
                // Sampling is terminal; a gate after a measurement is mid-circuit
                // measurement, which this path does not implement.
                if (measured[q]) return -4;
            }
            if (arity == 2 && inst.qubits[0] == inst.qubits[1]) return -3;
        }

        for (const auto& inst : circuit.instructions) {
            switch (inst.type) {
                case cq::GateType::H: engine->apply_h(inst.qubits[0]); break;
                case cq::GateType::S: engine->apply_s(inst.qubits[0]); break;
                case cq::GateType::SDG: engine->apply_sdg(inst.qubits[0]); break;
                case cq::GateType::T: engine->apply_t(inst.qubits[0]); break;
                case cq::GateType::TDG: engine->apply_tdg(inst.qubits[0]); break;
                case cq::GateType::X: engine->apply_x(inst.qubits[0]); break;
                case cq::GateType::Y: engine->apply_y(inst.qubits[0]); break;
                case cq::GateType::Z: engine->apply_z(inst.qubits[0]); break;
                case cq::GateType::CX: engine->apply_cx(inst.qubits[0], inst.qubits[1]); break;
                case cq::GateType::SWAP: engine->apply_swap(inst.qubits[0], inst.qubits[1]); break;
                case cq::GateType::RZ: engine->apply_rz(inst.qubits[0], inst.angle_q32); break;
                default: break;  // BARRIER / MEASURE: validated above, no state change
            }
        }
    } catch (...) {
        set_error(CQ_CORE_ERR_INTERNAL);
        return -7;
    }

    return cq_sample_counts_json(handle, shots, out_json, max_len);
}

} // extern "C"
