#pragma once
#include <cstdint>
#include <vector>
#include <memory>
#include <string>
#include "cq_hecs/lattice.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

namespace cq_hecs {

struct GraphEdge {
    uint32_t u;
    uint32_t v;
    int32_t weight = 1;
};

struct ConstraintResult {
    bool solved = false;
    int64_t minimum_energy = 0;
    int64_t ground_truth_energy = 0;
    uint64_t max_cut_edges = 0;
    size_t peak_vram_bytes = 0;
    bool vram_limit_respected = true;
    std::vector<int8_t> spin_assignment; // +1 or -1 for each of the 300 nodes
};

/// @brief 300-Node Combinatorial Constraint & MaxCut Solver
/// Solves 300-variable combinatorial optimization problems using 3D tensor network contractions
/// on the 6 x 5 x 10 lattice with continuous VRAM monitoring against the 3.0 GB ceiling.
class ConstraintSolver {
public:
    ConstraintSolver(std::shared_ptr<VulkanContext> vulkan = nullptr);

    /// @brief Create canonical 300-node 3D lattice MaxCut problem
    /// Contains 760 edges with known bipartite ground truth: MaxCut = 760, MinEnergy = -760
    void setup_canonical_300_problem();

    /// @brief Load problem from DIMACS CNF / graph format
    bool load_from_dimacs(const std::string& filepath);

    /// @brief Add a weighted constraint edge between two nodes
    void add_edge(uint32_t u, uint32_t v, int32_t weight = 1);

    /// @brief Execute tensor network contraction to find ground state energy
    /// Polls VRAM counters at each stage and asserts VRAM <= 3.0 GB
    ConstraintResult solve();

    size_t get_node_count() const { return m_num_nodes; }
    size_t get_edge_count() const { return m_edges.size(); }
    int64_t get_ground_truth_energy() const { return m_ground_truth_energy; }

private:
    std::shared_ptr<VulkanContext> m_vulkan;
    Lattice3D m_lattice;
    uint32_t m_num_nodes = 300;
    std::vector<GraphEdge> m_edges;
    int64_t m_ground_truth_energy = -760;
};

} // namespace cq_hecs
