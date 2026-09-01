#pragma once
#include <cstdint>
#include <vector>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

namespace cq_hecs {

/// @brief 3D coordinate on the 6 x 5 x 10 orthogonal lattice
struct LatticeCoord {
    uint32_t x = 0; // [0, 5]
    uint32_t y = 0; // [0, 4]
    uint32_t z = 0; // [0, 9]

    constexpr bool operator==(const LatticeCoord& other) const = default;
};

/// @brief Represents an undirected bond between two adjacent qubits in the 3D lattice
struct LatticeBond {
    uint32_t u;
    uint32_t v;
    uint32_t direction; // 0:+x, 1:-x, 2:+y, 3:-y, 4:+z, 5:-z
};

/// @brief 3D Volumetric Grid Topology Manager for VRTS-300
/// Encapsulates the 6 x 5 x 10 orthogonal 3D grid with 6-neighbor spatial bonds
/// and topological Manhattan distance routing with path length <= 18 hops.
class Lattice3D {
public:
    static constexpr uint32_t DIM_X = 6;
    static constexpr uint32_t DIM_Y = 5;
    static constexpr uint32_t DIM_Z = 10;
    static constexpr uint32_t TOTAL_QUBITS = DIM_X * DIM_Y * DIM_Z; // 300
    static constexpr uint32_t MAX_MANHATTAN_HOPS = (DIM_X - 1) + (DIM_Y - 1) + (DIM_Z - 1); // 5 + 4 + 9 = 18

    Lattice3D() = default;

    /// @brief Convert 3D coordinate (x, y, z) to linear qubit index in [0, 299]
    static constexpr uint32_t to_index(uint32_t x, uint32_t y, uint32_t z) {
        if (x >= DIM_X || y >= DIM_Y || z >= DIM_Z) {
            throw std::out_of_range("Lattice coordinate out of bounds");
        }
        return x + DIM_X * (y + DIM_Y * z);
    }

    /// @brief Convert linear qubit index in [0, 299] to 3D coordinate
    static constexpr LatticeCoord to_coord(uint32_t index) {
        if (index >= TOTAL_QUBITS) {
            throw std::out_of_range("Lattice index out of bounds");
        }
        uint32_t z = index / (DIM_X * DIM_Y);
        uint32_t rem = index % (DIM_X * DIM_Y);
        uint32_t y = rem / DIM_X;
        uint32_t x = rem % DIM_X;
        return LatticeCoord{x, y, z};
    }

    /// @brief Get all valid 6-neighbor spatial bond indices for a site (+x, -x, +y, -y, +z, -z)
    std::vector<uint32_t> get_neighbors(uint32_t index) const;

    /// @brief Check if two qubit indices are direct 1-hop spatial neighbors
    bool are_neighbors(uint32_t u, uint32_t v) const;

    /// @brief Compute exact topological Manhattan distance between two qubits
    /// Strictly guaranteed to be in range [0, 18]
    static uint32_t manhattan_distance(uint32_t u, uint32_t v);

    /// @brief Route between two qubits along Manhattan shortest path
    /// Returns vector of node indices from `from_idx` to `to_idx` inclusive.
    /// Number of hops is strictly <= 18 hops.
    std::vector<uint32_t> route_manhattan(uint32_t from_idx, uint32_t to_idx) const;

    /// @brief Retrieve all physical bonds on the 3D lattice (total 760 bonds)
    std::vector<LatticeBond> get_all_bonds() const;

    /// @brief Retrieve canonical spanning tree edges covering all 300 qubits
    std::vector<std::pair<uint32_t, uint32_t>> get_canonical_spanning_tree() const;
};

} // namespace cq_hecs
