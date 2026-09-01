#pragma once
#include <cstdint>
#include <vector>
#include <memory>
#include <string>
#include "cq_hecs/lattice.hpp"
#include "cq_hecs/cordic_engine.hpp"
#include "cq_hecs/residual_engine.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

namespace cq_hecs {

enum class GateType : uint32_t {
    HADAMARD = 0,
    PAULI_X,
    PAULI_Y,
    PAULI_Z,
    S,
    S_DAGGER,
    T,
    T_DAGGER,
    RX,
    RY,
    RZ,
    CNOT,
    SWAP
};

struct GateRecord {
    GateType type;
    uint32_t qubit0;
    uint32_t qubit1; // used for 2-qubit gates
    uint32_t phase_angle; // in Z_{2^32}
};

/// @brief Site tensor node on the 3D lattice
struct TensorNode3D {
    uint32_t site_id = 0;
    ComplexFixed state[2]; // Local 1-qubit basis |0>, |1> in fixed point
    uint32_t entangled_with = 0xFFFFFFFFu; // Pair entanglement partner if entangled
    bool is_entangled = false;
};

/// @brief Volumetric Reversible Tensor Space Engine (VRTS-300)
/// Manages a 300-qubit 3D PEPS/TTN state on a 6 x 5 x 10 orthogonal grid
/// with pure Vulkan 1.2+ compute, strict 3.0 GB VRAM ceiling,
/// dual-layer residual folding, and bit-exact Z_{2^32} CORDIC reversibility.
class VRTS300Engine {
public:
    VRTS300Engine(std::shared_ptr<VulkanContext> vulkan = nullptr);
    ~VRTS300Engine() = default;

    /// @brief Reset lattice to product ground state |0>^{\otimes 300}
    void reset_ground_state();

    // Single Qubit Gates
    void apply_hadamard(uint32_t qubit);
    void apply_pauli_x(uint32_t qubit);
    void apply_pauli_y(uint32_t qubit);
    void apply_pauli_z(uint32_t qubit);
    void apply_s(uint32_t qubit);
    void apply_s_dagger(uint32_t qubit);
    void apply_t(uint32_t qubit);
    void apply_t_dagger(uint32_t qubit);
    void apply_rx(uint32_t qubit, uint32_t phase_angle);
    void apply_ry(uint32_t qubit, uint32_t phase_angle);
    void apply_rz(uint32_t qubit, uint32_t phase_angle);

    // Two Qubit Gates
    void apply_cnot(uint32_t control, uint32_t target);
    void apply_swap(uint32_t q0, uint32_t q1);

    // Inverse execution for Loschmidt echo audit
    void apply_gate_inverse(const GateRecord& record);
    void apply_full_inverse();

    /// @brief Construct canonical 300-qubit GHZ state across the 6x5x10 lattice
    void construct_ghz300();

    /// @brief Execute full tensor contraction and measure state parity over N shots
    /// Returns pair: <non_parity_count, count_zeros>
    /// For GHZ state: non_parity_count == 0, count_zeros == num_shots / 2
    std::pair<uint64_t, uint64_t> measure_parity_shots(uint32_t num_shots);

    /// @brief Compute bit-exact state overlap / fidelity with another state (e.g. ground state)
    /// Returns 1.0 if bit-exact match across all 300 state tensors
    double compute_fidelity(const VRTS300Engine& other) const;

    /// @brief Check if all 300 site tensors bit-for-bit match ground state |0>^{\otimes 300}
    bool is_bit_exact_ground_state() const;

    // Inspection
    const Lattice3D& get_lattice() const { return m_lattice; }
    const CordicEngine& get_cordic() const { return m_cordic; }
    const ResidualEngine& get_residual_engine() const { return m_residual; }
    const std::vector<GateRecord>& get_gate_history() const { return m_history; }
    size_t get_gate_count() const { return m_history.size(); }

    const TensorNode3D& get_node(uint32_t site) const { return m_nodes[site]; }
    size_t get_active_vram_bytes() const;
    size_t get_peak_vram_bytes() const;

private:
    Lattice3D m_lattice;
    CordicEngine m_cordic;
    ResidualEngine m_residual;
    std::shared_ptr<VulkanContext> m_vulkan;

    std::vector<TensorNode3D> m_nodes;
    std::vector<GateRecord> m_history;

    // GPU mirror buffer for active site tensors
    VulkanBuffer m_gpu_state_buffer;
    bool m_gpu_state_active = false;

    void sync_to_gpu();
    void sync_from_gpu();
};

} // namespace cq_hecs
