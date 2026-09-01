#include <iostream>
#include <cassert>
#include <chrono>

#include "cq_hecs/constraint_solver.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

using namespace cq_hecs;

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS [Deterministic Audit]: VRAM Stress & Constraint Benchmark\n";
    std::cout << " Nodes: 300 (6 x 5 x 10 Lattice) | Ceiling: Strict 3.0 GB VRAM\n";
    std::cout << "=================================================================\n\n";

    // 1. Initialize Vulkan context
    auto vulkan = std::make_shared<VulkanContext>();
    vulkan->initialize();

    std::cout << "[Step 1] Initializing 300-node MaxCut / SAT Combinatorial Problem...\n";
    ConstraintSolver solver(vulkan);

    std::cout << "         Nodes: " << solver.get_node_count() << "\n";
    std::cout << "         Edges: " << solver.get_edge_count() << "\n";
    std::cout << "         Known Ground Truth Energy: " << solver.get_ground_truth_energy() << "\n\n";

    // 2. Execute tensor contraction & solve
    std::cout << "[Step 2] Executing 3D Tensor Contractions with continuous VRAM polling...\n";
    auto start_time = std::chrono::high_resolution_clock::now();

    ConstraintResult res = solver.solve();

    auto solve_time = std::chrono::high_resolution_clock::now();
    double elapsed_ms = std::chrono::duration<double, std::milli>(solve_time - start_time).count();

    std::cout << "         Tensor network contraction finished in " << elapsed_ms << " ms.\n\n";

    // 3. Inspect results and assert constraints
    std::cout << "[Step 3] Verifying Energy Ground Truth & VRAM Ceiling Constraints...\n";
    double peak_mb = static_cast<double>(res.peak_vram_bytes) / (1024.0 * 1024.0);
    double ceiling_mb = static_cast<double>(VulkanMemoryManager::VRAM_HARD_CEILING_BYTES) / (1024.0 * 1024.0);

    std::cout << "         Peak Allocated VRAM:     " << peak_mb << " MB\n";
    std::cout << "         VRAM Hard Ceiling:       " << ceiling_mb << " MB (3.0 GB)\n";
    std::cout << "         VRAM Ceiling Respected:  " << (res.vram_limit_respected ? "YES" : "NO") << "\n";
    std::cout << "         Calculated Min Energy:   " << res.minimum_energy << "\n";
    std::cout << "         Ground Truth Energy:     " << res.ground_truth_energy << "\n";
    std::cout << "         Max Cut Edges Satisfied: " << res.max_cut_edges << " / " << solver.get_edge_count() << "\n";

    // Assert: Peak allocated VRAM <= 3.0 GB at all times
    assert(res.vram_limit_respected);
    assert(res.peak_vram_bytes <= VulkanMemoryManager::VRAM_HARD_CEILING_BYTES);

    // Assert: Calculated minimum energy matches known ground truth
    assert(res.minimum_energy == res.ground_truth_energy);
    assert(res.max_cut_edges == solver.get_edge_count());
    if (!res.vram_limit_respected ||
        res.peak_vram_bytes > VulkanMemoryManager::VRAM_HARD_CEILING_BYTES ||
        res.minimum_energy != res.ground_truth_energy ||
        res.max_cut_edges != solver.get_edge_count()) {
        std::cerr << ">>> [FAIL] VRAM STRESS & CONSTRAINT SOLVER BENCHMARK FAILED VALIDATION.\n";
        return 1;
    }

    std::cout << "\n>>> [PASS] VRAM STRESS & CONSTRAINT SOLVER BENCHMARK PASSED (PEAK VRAM <= 3.0 GB).\n";
    return 0;
}
