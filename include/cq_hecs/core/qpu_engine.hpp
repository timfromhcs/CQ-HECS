#ifndef CQ_HECS_CORE_QPU_ENGINE_HPP
#define CQ_HECS_CORE_QPU_ENGINE_HPP

#include "types.hpp"
#include "cordic.hpp"
#include "mps_simulator.hpp"
#include "statevector_simulator.hpp"
#include "../transpiler/bytecode.hpp"
#include "../transpiler/qasm3_parser.hpp"
#include "../transpiler/optimizer.hpp"
#include <vector>
#include <memory>
#include <string>
#include <map>
#include <chrono>
#include <stdexcept>

namespace cq_hecs {
namespace core {

/**
 * @brief Vulkan Indirect Dispatch Command structure matching VkDispatchIndirectCommand.
 */
struct alignas(16) IndirectDispatchCommand {
    uint32_t x{1};
    uint32_t y{1};
    uint32_t z{1};
    uint32_t padding{0};
};

/**
 * @brief CPU reference facade for the native four-path/native test surface.
 *
 * Despite the historical name this class does not submit Vulkan work. It
 * evolves a CPU MPS or dense statevector and is kept as a reference/planner
 * path. No indirect-dispatch metadata is fabricated: a call either evolves
 * the CPU state or throws for an unsupported opcode.
 */
class VulkanQpuEngine {
public:
    uint32_t num_qubits;
    uint32_t max_bond_dim;
    std::unique_ptr<MPSSimulator> mps;
    std::unique_ptr<StateVectorSimulator> sv;
    bool use_mps{true};

    explicit VulkanQpuEngine(uint32_t n_qubits = 300, uint32_t max_d = 64)
        : num_qubits(n_qubits), max_bond_dim(max_d) {
        if (n_qubits > 20) {
            use_mps = true;
            mps = std::make_unique<MPSSimulator>(n_qubits, max_d);
        } else {
            use_mps = false;
            sv = std::make_unique<StateVectorSimulator>(n_qubits);
        }
    }

    void reset() {
        if (mps) mps->reset();
        if (sv) sv->reset();
    }

    /**
     * @brief Execute a sequence of J_QuantumOpcode instructions on the CPU state.
     *
     * Measurement opcodes are terminal: they do not mutate the state, because
     * sampling is performed by sample_counts() over the full register. A gate
     * after a measurement would require mid-circuit measurement and classical
     * feed-forward, which this reference facade does not model, so that case is
     * rejected instead of silently reordered.
     */
    void execute_bytecode(const std::vector<transpiler::J_QuantumOpcode>& opcodes) {
        bool measured = false;
        for (const auto& op : opcodes) {
            transpiler::OpCode code = op.get_opcode();
            if (code == transpiler::OpCode::NOP || code == transpiler::OpCode::BARRIER) {
                continue;
            }
            if (code == transpiler::OpCode::MEASURE) {
                measured = true;
                continue;
            }
            if (measured) {
                throw std::invalid_argument(
                    "VulkanQpuEngine: mid-circuit measurement with subsequent "
                    "gates is not supported by the CPU reference facade");
            }

            if (mps) {
                if (code == transpiler::OpCode::CX) {
                    mps->apply_cx(op.control_q, op.target_q);
                } else if (code == transpiler::OpCode::H) {
                    mps->apply_1q_gate(op.target_q, 1);
                } else if (code == transpiler::OpCode::X) {
                    mps->apply_1q_gate(op.target_q, 2);
                } else if (code == transpiler::OpCode::Y) {
                    mps->apply_1q_gate(op.target_q, 3);
                } else if (code == transpiler::OpCode::Z) {
                    mps->apply_1q_gate(op.target_q, 4);
                } else if (code == transpiler::OpCode::S) {
                    mps->apply_1q_gate(op.target_q, 5);
                } else if (code == transpiler::OpCode::SDG) {
                    mps->apply_1q_gate(op.target_q, 6);
                } else if (code == transpiler::OpCode::T) {
                    mps->apply_1q_gate(op.target_q, 7);
                } else if (code == transpiler::OpCode::TDG) {
                    mps->apply_1q_gate(op.target_q, 8);
                } else if (code == transpiler::OpCode::RZ) {
                    mps->apply_1q_gate(op.target_q, 9, op.phase1);
                } else {
                    throw std::invalid_argument(
                        "VulkanQpuEngine: unsupported opcode on the MPS reference path");
                }
            } else if (sv) {
                if (code == transpiler::OpCode::H) {
                    sv->apply_h(op.target_q);
                } else if (code == transpiler::OpCode::X) {
                    sv->apply_x(op.target_q);
                } else if (code == transpiler::OpCode::Y) {
                    sv->apply_y(op.target_q);
                } else if (code == transpiler::OpCode::Z) {
                    sv->apply_z(op.target_q);
                } else if (code == transpiler::OpCode::S) {
                    sv->apply_s(op.target_q);
                } else if (code == transpiler::OpCode::SDG) {
                    sv->apply_sdg(op.target_q);
                } else if (code == transpiler::OpCode::T) {
                    sv->apply_t(op.target_q);
                } else if (code == transpiler::OpCode::TDG) {
                    sv->apply_tdg(op.target_q);
                } else if (code == transpiler::OpCode::RZ) {
                    sv->apply_rz(op.target_q, op.phase1);
                } else if (code == transpiler::OpCode::CX) {
                    sv->apply_cnot(op.control_q, op.target_q);
                } else if (code == transpiler::OpCode::SWAP) {
                    sv->apply_swap(op.control_q, op.target_q);
                } else {
                    throw std::invalid_argument(
                        "VulkanQpuEngine: unsupported opcode on the statevector reference path");
                }
            } else {
                throw std::logic_error("VulkanQpuEngine: no backend was initialised");
            }
        }
    }

    /**
     * @brief Parse OpenQASM 3.0 string, optimize, and execute.
     */
    void execute_qasm(const std::string& qasm_source) {
        auto circ = transpiler::Qasm3Parser::parse(qasm_source);
        auto opt_circ = transpiler::CircuitOptimizer::optimize(circ);
        execute_bytecode(opt_circ.opcodes);
    }

    /**
     * @brief Sample measurement bitstrings from the CPU reference state.
     */
    std::map<std::string, uint32_t> sample_counts(
        uint32_t shots = 1024, uint64_t seed = 1337) {
        if (mps) return mps->sample_counts(shots, seed);
        if (sv) return sv->sample_counts(shots, seed);
        throw std::logic_error("VulkanQpuEngine: no backend was initialised");
    }

    double get_memory_mb() const noexcept {
        if (mps) return mps->get_memory_mb();
        if (sv) return static_cast<double>(sv->dim * sizeof(ComplexQ31)) / (1024.0 * 1024.0);
        return 0.0;
    }
};

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_QPU_ENGINE_HPP
