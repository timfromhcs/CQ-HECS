#include <iostream>
#include "cq_hecs/constraint_solver.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

using namespace cq_hecs;

int main() {
    std::cout << "CQ-HECS v2.0.0-VRTS-Vulkan: 300-Node MaxCut Example\n";
    auto vulkan = std::make_shared<VulkanContext>();
    vulkan->initialize();

    ConstraintSolver solver(vulkan);
    std::cout << "Solving 300-node 3D lattice graph with " << solver.get_edge_count() << " edges...\n";

    ConstraintResult res = solver.solve();
    std::cout << "Optimal Max Cut: " << res.max_cut_edges << " / " << solver.get_edge_count() << "\n";
    std::cout << "Minimum Energy:  " << res.minimum_energy << "\n";
    std::cout << "Peak VRAM:       " << (res.peak_vram_bytes / (1024 * 1024)) << " MB\n";

    return 0;
}
