#include "cq/hybrid_engine.hpp"
#include <iostream>
#include <cmath>

namespace cq {

HybridEngine::HybridEngine(uint32_t n, uint32_t bond_dim)
    : num_qubits(n), max_bond_dim(bond_dim),
      active_backend(SimulationBackend::STABILIZER_TABLEAU),
      tableau(n), mps(n, bond_dim), statevector(n <= 16 ? n : 16) {
    reset();
}

void HybridEngine::reset() {
    active_backend = SimulationBackend::STABILIZER_TABLEAU;
    tableau.reset();
    mps.reset();
    if (num_qubits <= 16) {
        statevector.reset();
    }
}

void HybridEngine::promote_to_statevector() {
    if (active_backend == SimulationBackend::EXACT_STATEVECTOR) return;
    active_backend = SimulationBackend::EXACT_STATEVECTOR;
}

void HybridEngine::apply_h(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_h(q);
    }
    if (num_qubits <= 16) {
        statevector.apply_h(q);
    }
}

void HybridEngine::apply_s(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_s(q);
    }
    if (num_qubits <= 16) {
        statevector.apply_s(q);
    }
}

void HybridEngine::apply_sdg(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_sdg(q);
    }
    if (num_qubits <= 16) {
        statevector.apply_sdg(q);
    }
}

void HybridEngine::apply_x(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_x(q);
    }
    if (num_qubits <= 16) {
        statevector.apply_x(q);
    }
}

void HybridEngine::apply_y(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_y(q);
    }
    if (num_qubits <= 16) {
        // Y = i * X * Z
        statevector.apply_x(q);
        statevector.apply_z(q);
    }
}

void HybridEngine::apply_z(uint32_t q) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_z(q);
    }
    if (num_qubits <= 16) {
        statevector.apply_z(q);
    }
}

void HybridEngine::apply_cx(uint32_t ctrl, uint32_t tgt) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_cx(ctrl, tgt);
    }
    if (num_qubits <= 16) {
        statevector.apply_cx(ctrl, tgt);
    }
}

void HybridEngine::apply_swap(uint32_t q1, uint32_t q2) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        tableau.apply_swap(q1, q2);
    }
    if (num_qubits <= 16) {
        apply_cx(q1, q2);
        apply_cx(q2, q1);
        apply_cx(q1, q2);
    }
}

void HybridEngine::apply_t(uint32_t q) {
    promote_to_statevector();
    if (num_qubits <= 16) {
        statevector.apply_t(q);
    }
}

void HybridEngine::apply_tdg(uint32_t q) {
    promote_to_statevector();
    if (num_qubits <= 16) {
        statevector.apply_tdg(q);
    }
}

void HybridEngine::apply_rz(uint32_t q, uint32_t phase_q32) {
    promote_to_statevector();
    if (num_qubits <= 16) {
        statevector.apply_rz(q, phase_q32);
    }
}

void HybridEngine::apply_cz(uint32_t ctrl, uint32_t tgt) {
    apply_h(tgt);
    apply_cx(ctrl, tgt);
    apply_h(tgt);
}

void HybridEngine::apply_mcz(const std::vector<uint32_t>& ctrls, uint32_t tgt) {
    promote_to_statevector();
    if (num_qubits > 16) return;

    // Flip phase of basis states where all ctrls and tgt are 1
    size_t dim = 1ULL << num_qubits;
    uint32_t mask = (1ULL << tgt);
    for (uint32_t c : ctrls) {
        mask |= (1ULL << c);
    }

    for (size_t i = 0; i < dim; ++i) {
        if ((i & mask) == mask) {
            statevector.state[i].re = -statevector.state[i].re;
            statevector.state[i].im = -statevector.state[i].im;
        }
    }
}

uint8_t HybridEngine::measure_qubit(uint32_t q, std::mt19937_64* rng) {
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        return tableau.measure(q, rng);
    }
    // Statevector measurement
    return statevector.measure(q);
}

std::map<std::string, uint32_t> HybridEngine::sample_counts(uint32_t shots, uint64_t seed) {
    std::map<std::string, uint32_t> counts;
    if (active_backend == SimulationBackend::STABILIZER_TABLEAU) {
        // Sample by measuring
        std::mt19937_64 rng(seed);
        for (uint32_t s = 0; s < shots; ++s) {
            StabilizerTableau copy_tab = tableau;
            std::string bs;
            bs.reserve(num_qubits);
            for (uint32_t q = 0; q < num_qubits; ++q) {
                uint8_t b = copy_tab.measure(q, &rng);
                bs.push_back(b ? '1' : '0');
            }
            counts[bs]++;
        }
        return counts;
    }

    // Statevector sampling
    return statevector.sample_counts(shots);
}

double HybridEngine::get_probability(uint32_t basis_state) const {
    if (num_qubits > 16 || basis_state >= (1ULL << num_qubits)) return 0.0;
    const auto& amp = statevector.state[basis_state];
    double re = amp.to_double();
    double im = static_cast<double>(amp.im) / 2147483647.0;
    return re * re + im * im;
}

double HybridEngine::get_fidelity_with_ground() const {
    if (num_qubits > 16) return 1.0;
    return statevector.fidelity_with_ground();
}

} // namespace cq
