#ifndef CQ_HECS_TRANSPILER_OPTIMIZER_HPP
#define CQ_HECS_TRANSPILER_OPTIMIZER_HPP

#include "bytecode.hpp"
#include "qasm3_parser.hpp"
#include <vector>
#include <cstdlib>
#include <algorithm>

namespace cq_hecs {
namespace transpiler {

class CircuitOptimizer {
public:
    /**
     * @brief 1D-MPS Topology Routing Pass.
     * 
     * Inserts minimal SWAP networks for two-qubit gates between non-adjacent qubits (|control - target| > 1).
     * Guarantees all two-qubit gates in the output circuit act exclusively on nearest-neighbor sites (|c - t| == 1).
     */
    static QuantumCircuit route_1d_mps(const QuantumCircuit& input) {
        QuantumCircuit routed;
        routed.num_qubits = input.num_qubits;
        routed.num_clbits = input.num_clbits;
        routed.qubit_map = input.qubit_map;
        routed.clbit_map = input.clbit_map;

        for (const auto& op : input.opcodes) {
            OpCode code = op.get_opcode();

            if (code == OpCode::CX || code == OpCode::SWAP) {
                int c = op.control_q;
                int t = op.target_q;
                int dist = std::abs(c - t);

                if (dist <= 1) {
                    routed.add_op(op);
                } else {
                    // Minimal SWAP chain to bring control adjacent to target
                    if (c < t) {
                        // Forward SWAPs from c to t-1
                        for (int k = c; k < t - 1; ++k) {
                            routed.add_op(J_QuantumOpcode(OpCode::SWAP, static_cast<uint8_t>(k + 1), static_cast<uint8_t>(k), FLAG_ROUTED));
                        }
                        // Execute original gate on adjacent pair (t-1, t)
                        routed.add_op(J_QuantumOpcode(code, static_cast<uint8_t>(t), static_cast<uint8_t>(t - 1), op.flags | FLAG_ROUTED));
                        // Reverse SWAPs back to restore original logical-to-physical mapping
                        for (int k = t - 2; k >= c; --k) {
                            routed.add_op(J_QuantumOpcode(OpCode::SWAP, static_cast<uint8_t>(k + 1), static_cast<uint8_t>(k), FLAG_ROUTED));
                        }
                    } else { // c > t
                        // Forward SWAPs from c down to t+1
                        for (int k = c; k > t + 1; --k) {
                            routed.add_op(J_QuantumOpcode(OpCode::SWAP, static_cast<uint8_t>(k), static_cast<uint8_t>(k - 1), FLAG_ROUTED));
                        }
                        // Execute gate on adjacent pair (t+1, t)
                        routed.add_op(J_QuantumOpcode(code, static_cast<uint8_t>(t), static_cast<uint8_t>(t + 1), op.flags | FLAG_ROUTED));
                        // Reverse SWAPs back
                        for (int k = t + 1; k < c; ++k) {
                            routed.add_op(J_QuantumOpcode(OpCode::SWAP, static_cast<uint8_t>(k + 1), static_cast<uint8_t>(k), FLAG_ROUTED));
                        }
                    }
                }
            } else {
                routed.add_op(op);
            }
        }

        return routed;
    }

    /**
     * @brief Gate Fusion Pass.
     * 
     * Combines consecutive Rz, Z, S, T phase rotations on the same target qubit via integer addition
     * in the Z_{2^32} phase ring, eliminating identity rotations (phase == 0 mod 2^32).
     * Also cancels redundant adjacent self-inverse gates (H-H, X-X, Y-Y, Z-Z).
     */
    static QuantumCircuit fuse_gates(const QuantumCircuit& input) {
        QuantumCircuit fused;
        fused.num_qubits = input.num_qubits;
        fused.num_clbits = input.num_clbits;
        fused.qubit_map = input.qubit_map;
        fused.clbit_map = input.clbit_map;

        std::vector<J_QuantumOpcode> ops = input.opcodes;
        bool modified = true;

        auto get_rz_phase = [](const J_QuantumOpcode& op, uint32_t& out_phase) -> bool {
            OpCode code = op.get_opcode();
            if (code == OpCode::RZ) {
                out_phase = op.phase1;
                return true;
            } else if (code == OpCode::Z) {
                out_phase = 0x80000000u; // pi
                return true;
            } else if (code == OpCode::S) {
                out_phase = 0x40000000u; // pi/2
                return true;
            } else if (code == OpCode::SDG) {
                out_phase = 0xC0000000u; // 3pi/2 (-pi/2)
                return true;
            } else if (code == OpCode::T) {
                out_phase = 0x20000000u; // pi/4
                return true;
            } else if (code == OpCode::TDG) {
                out_phase = 0xE0000000u; // 7pi/4 (-pi/4)
                return true;
            }
            return false;
        };

        while (modified) {
            modified = false;
            std::vector<J_QuantumOpcode> next_ops;
            next_ops.reserve(ops.size());

            size_t i = 0;
            while (i < ops.size()) {
                if (ops[i].get_opcode() == OpCode::NOP) {
                    ++i;
                    continue;
                }

                if (i + 1 < ops.size() && ops[i].target_q == ops[i + 1].target_q) {
                    OpCode c1 = ops[i].get_opcode();
                    OpCode c2 = ops[i + 1].get_opcode();

                    // Check for adjacent Rz / Phase gate fusion
                    uint32_t p1 = 0, p2 = 0;
                    if (get_rz_phase(ops[i], p1) && get_rz_phase(ops[i + 1], p2)) {
                        uint32_t combined_phase = p1 + p2; // modulo 2^32
                        if (combined_phase != 0) {
                            next_ops.push_back(J_QuantumOpcode(OpCode::RZ, ops[i].target_q, 0, FLAG_FUSED, combined_phase));
                        }
                        // If combined_phase == 0, both cancelled out!
                        i += 2;
                        modified = true;
                        continue;
                    }

                    // Check for self-inverse cancellation (H-H, X-X, Y-Y, Z-Z)
                    if ((c1 == OpCode::H && c2 == OpCode::H) ||
                        (c1 == OpCode::X && c2 == OpCode::X) ||
                        (c1 == OpCode::Y && c2 == OpCode::Y) ||
                        (c1 == OpCode::Z && c2 == OpCode::Z)) {
                        i += 2;
                        modified = true;
                        continue;
                    }
                }

                next_ops.push_back(ops[i]);
                ++i;
            }

            ops = std::move(next_ops);
        }

        fused.opcodes = std::move(ops);
        return fused;
    }

    /**
     * @brief Full Optimization Pipeline: Routing + Fusion.
     */
    static QuantumCircuit optimize(const QuantumCircuit& input) {
        QuantumCircuit routed = route_1d_mps(input);
        return fuse_gates(routed);
    }
};

} // namespace transpiler
} // namespace cq_hecs

#endif // CQ_HECS_TRANSPILER_OPTIMIZER_HPP
