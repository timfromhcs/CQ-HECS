#include <iostream>
#include <vector>
#include <random>
#include <cassert>
#include <chrono>

#include "cq_hecs/tensor_network.hpp"
#include "cq_hecs/lattice.hpp"

using namespace cq_hecs;

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS [Deterministic Audit]: Real Loschmidt Echo Reversibility\n";
    std::cout << " Lattice: 6 x 5 x 10 (300 Qubits) | Target: Bit-Exact U^\\dagger U = I\n";
    std::cout << "=================================================================\n\n";

    // 1. Initialize Vulkan context and VRTS-300 engine in state |0>^{\otimes 300}
    auto vulkan = std::make_shared<VulkanContext>();
    vulkan->initialize();

    VRTS300Engine engine(vulkan);
    VRTS300Engine ground_truth_reference(vulkan);

    std::cout << "[Step 1] Verifying initial state |0>^{\\otimes 300}...\n";
    assert(engine.is_bit_exact_ground_state());
    assert(engine.compute_fidelity(ground_truth_reference) == 1.0);
    std::cout << "         Initial state fidelity: 1.00000000 (Bit-Exact Ground State)\n\n";

    // 2. Apply 5,000 algorithmic gate operations across the 3D lattice
    const uint32_t NUM_GATES = 5000;
    std::cout << "[Step 2] Applying " << NUM_GATES << " algorithmic gate operations across 3D lattice...\n";

    std::mt19937 rng(1337); // Deterministic fixed seed
    std::uniform_int_distribution<uint32_t> qubit_dist(0, Lattice3D::TOTAL_QUBITS - 1);
    std::uniform_int_distribution<uint32_t> gate_dist(0, 6);
    std::uniform_int_distribution<uint32_t> angle_dist(1, 0x3FFFFFFFu);

    auto start_time = std::chrono::high_resolution_clock::now();

    for (uint32_t i = 0; i < NUM_GATES; ++i) {
        uint32_t q = qubit_dist(rng);
        uint32_t gate_type = gate_dist(rng);

        switch (gate_type) {
            case 0: // Hadamard
                engine.apply_hadamard(q);
                break;
            case 1: { // CNOT with adjacent neighbor
                auto neighbors = engine.get_lattice().get_neighbors(q);
                if (!neighbors.empty()) {
                    uint32_t target = neighbors[i % neighbors.size()];
                    engine.apply_cnot(q, target);
                } else {
                    engine.apply_pauli_x(q);
                }
                break;
            }
            case 2: // T gate
                engine.apply_t(q);
                break;
            case 3: // S gate
                engine.apply_s(q);
                break;
            case 4: // CORDIC Rx rotation
                engine.apply_rx(q, angle_dist(rng));
                break;
            case 5: // CORDIC Ry rotation
                engine.apply_ry(q, angle_dist(rng));
                break;
            case 6: // CORDIC Rz rotation
                engine.apply_rz(q, angle_dist(rng));
                break;
        }
    }

    auto apply_time = std::chrono::high_resolution_clock::now();
    std::cout << "         " << engine.get_gate_count() << " gates successfully executed in "
              << std::chrono::duration<double, std::milli>(apply_time - start_time).count() << " ms.\n";

    // Ensure state has perturbed from ground state
    assert(!engine.is_bit_exact_ground_state());
    std::cout << "         State successfully entrained into complex superposition.\n\n";

    // 3. Apply exact inverse sequence U^\dagger in reverse order
    std::cout << "[Step 3] Applying exact inverse sequence U^\\dagger in reverse order...\n";
    engine.apply_full_inverse();

    auto inverse_time = std::chrono::high_resolution_clock::now();
    std::cout << "         Inverse sequence execution completed in "
              << std::chrono::duration<double, std::milli>(inverse_time - apply_time).count() << " ms.\n\n";

    // 4. Compute state overlap: Assert Fidelity == 1.0 (bit-exact match)
    std::cout << "[Step 4] Computing state overlap & verifying bit-exact reversibility...\n";
    bool bit_exact = engine.is_bit_exact_ground_state();
    double fidelity = engine.compute_fidelity(ground_truth_reference);

    std::cout << "         Bit-exact ground state match: " << (bit_exact ? "TRUE" : "FALSE") << "\n";
    std::cout << "         Calculated Fidelity:          " << fidelity << "\n";

    assert(bit_exact);
    assert(fidelity == 1.0);
    if (!bit_exact || fidelity != 1.0) {
        std::cerr << ">>> [FAIL] LOSCHMIDT ECHO AUDIT FAILED: bit_exact=" << bit_exact << " fidelity=" << fidelity << "\n";
        return 1;
    }

    std::cout << "\n>>> [PASS] REAL LOSCHMIDT ECHO AUDIT PASSED WITH 100% BIT-EXACT REVERSIBILITY.\n";
    return 0;
}
