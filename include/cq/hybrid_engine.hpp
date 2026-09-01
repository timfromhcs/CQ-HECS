#ifndef CQ_HYBRID_ENGINE_HPP
#define CQ_HYBRID_ENGINE_HPP

#include <cstdint>
#include <vector>
#include <string>
#include <map>
#include <memory>
#include "cq/stabilizer_tableau.hpp"
#include "cq/exact_cyclotomic.hpp"
#include "cq_hecs/core/mps_simulator.hpp"
#include "cq_hecs/core/statevector_simulator.hpp"

namespace cq {

enum class SimulationBackend {
    STABILIZER_TABLEAU,
    MPS_TENSOR_NETWORK,
    EXACT_STATEVECTOR
};

/**
 * @brief Hybrid Quantum Engine: Seamlessly switches between Stabilizer Tableau and MPS/Statevector.
 * 
 * - Circuits with only Clifford gates (H, S, CX, X, Y, Z, SWAP) execute 100% in StabilizerTableau.
 * - Non-Clifford gates (T, Tdag, RZ) trigger automatic conversion to exact tensor network / statevector.
 * - Slicing / Branching preserves exact representation.
 */
class HybridEngine {
public:
    uint32_t num_qubits{0};
    uint32_t max_bond_dim{64};
    SimulationBackend active_backend{SimulationBackend::STABILIZER_TABLEAU};

    StabilizerTableau tableau;
    cq_hecs::core::MPSSimulator mps;
    cq_hecs::core::StatevectorSimulator statevector;

    HybridEngine(uint32_t n, uint32_t bond_dim = 64);

    void reset();

    // Universal gate interface
    void apply_h(uint32_t q);
    void apply_s(uint32_t q);
    void apply_sdg(uint32_t q);
    void apply_x(uint32_t q);
    void apply_y(uint32_t q);
    void apply_z(uint32_t q);
    void apply_cx(uint32_t ctrl, uint32_t tgt);
    void apply_swap(uint32_t q1, uint32_t q2);

    // Non-Clifford gates (triggers hybrid promotion)
    void apply_t(uint32_t q);
    void apply_tdg(uint32_t q);
    void apply_rz(uint32_t q, uint32_t phase_q32);
    void apply_cz(uint32_t ctrl, uint32_t tgt);
    void apply_mcz(const std::vector<uint32_t>& ctrls, uint32_t tgt);

    // Sampling and measurement
    uint8_t measure_qubit(uint32_t q, std::mt19937_64* rng = nullptr);
    std::map<std::string, uint32_t> sample_counts(uint32_t shots, uint64_t seed = 42);

    // State analysis
    double get_probability(uint32_t basis_state) const;
    double get_fidelity_with_ground() const;

private:
    void promote_to_statevector();
};

} // namespace cq

#endif // CQ_HYBRID_ENGINE_HPP
