#define CQ_EXPORTS
#include "cq/cq_c_api.h"
#include "cq/hybrid_engine.hpp"
#include "cq/qasm_parser.hpp"
#include <cstring>
#include <sstream>

extern "C" {

CQ_API CQSimulatorHandle cq_create_simulator(uint32_t num_qubits, uint32_t max_bond_dim) {
    auto* engine = new cq::HybridEngine(num_qubits, max_bond_dim);
    return static_cast<CQSimulatorHandle>(engine);
}

CQ_API void cq_destroy_simulator(CQSimulatorHandle handle) {
    if (handle) {
        delete static_cast<cq::HybridEngine*>(handle);
    }
}

CQ_API void cq_reset(CQSimulatorHandle handle) {
    if (handle) {
        static_cast<cq::HybridEngine*>(handle)->reset();
    }
}

CQ_API void cq_apply_h(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_h(q);
}

CQ_API void cq_apply_s(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_s(q);
}

CQ_API void cq_apply_sdg(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_sdg(q);
}

CQ_API void cq_apply_t(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_t(q);
}

CQ_API void cq_apply_tdg(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_tdg(q);
}

CQ_API void cq_apply_x(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_x(q);
}

CQ_API void cq_apply_y(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_y(q);
}

CQ_API void cq_apply_z(CQSimulatorHandle handle, uint32_t q) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_z(q);
}

CQ_API void cq_apply_cx(CQSimulatorHandle handle, uint32_t ctrl, uint32_t tgt) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_cx(ctrl, tgt);
}

CQ_API void cq_apply_swap(CQSimulatorHandle handle, uint32_t q1, uint32_t q2) {
    if (handle) static_cast<cq::HybridEngine*>(handle)->apply_swap(q1, q2);
}

CQ_API void cq_apply_rz(CQSimulatorHandle handle, uint32_t q, double angle_rad) {
    if (!handle) return;
    uint32_t phase_q32 = static_cast<uint32_t>((angle_rad / (2.0 * 3.141592653589793)) * 4294967296.0);
    static_cast<cq::HybridEngine*>(handle)->apply_rz(q, phase_q32);
}

CQ_API uint8_t cq_measure_qubit(CQSimulatorHandle handle, uint32_t q) {
    if (!handle) return 0;
    return static_cast<cq::HybridEngine*>(handle)->measure_qubit(q);
}

CQ_API int cq_sample_counts_json(CQSimulatorHandle handle, uint32_t shots, char* out_json, size_t max_len) {
    if (!handle || !out_json || max_len == 0) return -1;
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
    std::strncpy(out_json, res.c_str(), max_len);
    out_json[max_len - 1] = '\0';
    return 0;
}

CQ_API int cq_execute_qasm(CQSimulatorHandle handle, const char* qasm_str, uint32_t shots, char* out_json, size_t max_len) {
    if (!handle || !qasm_str || !out_json) return -1;
    auto* engine = static_cast<cq::HybridEngine*>(handle);
    engine->reset();

    auto circuit = cq::Qasm3Parser::parse_string(qasm_str);
    for (const auto& inst : circuit.instructions) {
        switch (inst.type) {
            case cq::GateType::H:
                engine->apply_h(inst.qubits[0]);
                break;
            case cq::GateType::S:
                engine->apply_s(inst.qubits[0]);
                break;
            case cq::GateType::SDG:
                engine->apply_sdg(inst.qubits[0]);
                break;
            case cq::GateType::T:
                engine->apply_t(inst.qubits[0]);
                break;
            case cq::GateType::TDG:
                engine->apply_tdg(inst.qubits[0]);
                break;
            case cq::GateType::X:
                engine->apply_x(inst.qubits[0]);
                break;
            case cq::GateType::Y:
                engine->apply_y(inst.qubits[0]);
                break;
            case cq::GateType::Z:
                engine->apply_z(inst.qubits[0]);
                break;
            case cq::GateType::CX:
                engine->apply_cx(inst.qubits[0], inst.qubits[1]);
                break;
            case cq::GateType::SWAP:
                engine->apply_swap(inst.qubits[0], inst.qubits[1]);
                break;
            case cq::GateType::RZ:
                engine->apply_rz(inst.qubits[0], inst.angle_q32);
                break;
            default:
                break;
        }
    }

    return cq_sample_counts_json(handle, shots, out_json, max_len);
}

} // extern "C"
