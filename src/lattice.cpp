#include "cq_hecs/lattice.hpp"
#include <queue>
#include <unordered_set>
#include <algorithm>
#include <cmath>

namespace cq_hecs {

std::vector<uint32_t> Lattice3D::get_neighbors(uint32_t index) const {
    LatticeCoord c = to_coord(index);
    std::vector<uint32_t> neighbors;
    neighbors.reserve(6);

    // +x
    if (c.x + 1 < DIM_X) neighbors.push_back(to_index(c.x + 1, c.y, c.z));
    // -x
    if (c.x > 0)         neighbors.push_back(to_index(c.x - 1, c.y, c.z));
    // +y
    if (c.y + 1 < DIM_Y) neighbors.push_back(to_index(c.x, c.y + 1, c.z));
    // -y
    if (c.y > 0)         neighbors.push_back(to_index(c.x, c.y - 1, c.z));
    // +z
    if (c.z + 1 < DIM_Z) neighbors.push_back(to_index(c.x, c.y, c.z + 1));
    // -z
    if (c.z > 0)         neighbors.push_back(to_index(c.x, c.y, c.z - 1));

    return neighbors;
}

bool Lattice3D::are_neighbors(uint32_t u, uint32_t v) const {
    if (u == v) return false;
    return manhattan_distance(u, v) == 1;
}

uint32_t Lattice3D::manhattan_distance(uint32_t u, uint32_t v) {
    LatticeCoord c1 = to_coord(u);
    LatticeCoord c2 = to_coord(v);
    uint32_t dx = (c1.x > c2.x) ? (c1.x - c2.x) : (c2.x - c1.x);
    uint32_t dy = (c1.y > c2.y) ? (c1.y - c2.y) : (c2.y - c1.y);
    uint32_t dz = (c1.z > c2.z) ? (c1.z - c2.z) : (c2.z - c1.z);
    return dx + dy + dz;
}

std::vector<uint32_t> Lattice3D::route_manhattan(uint32_t from_idx, uint32_t to_idx) const {
    std::vector<uint32_t> path;
    if (from_idx >= TOTAL_QUBITS || to_idx >= TOTAL_QUBITS) {
        throw std::out_of_range("Indices out of bounds for routing");
    }

    LatticeCoord cur = to_coord(from_idx);
    const LatticeCoord dest = to_coord(to_idx);

    path.push_back(to_index(cur.x, cur.y, cur.z));

    // Dimension-order routing: X -> Y -> Z
    while (cur.x != dest.x) {
        if (cur.x < dest.x) cur.x++;
        else cur.x--;
        path.push_back(to_index(cur.x, cur.y, cur.z));
    }

    while (cur.y != dest.y) {
        if (cur.y < dest.y) cur.y++;
        else cur.y--;
        path.push_back(to_index(cur.x, cur.y, cur.z));
    }

    while (cur.z != dest.z) {
        if (cur.z < dest.z) cur.z++;
        else cur.z--;
        path.push_back(to_index(cur.x, cur.y, cur.z));
    }

    return path;
}

std::vector<LatticeBond> Lattice3D::get_all_bonds() const {
    std::vector<LatticeBond> bonds;
    bonds.reserve(760);

    for (uint32_t z = 0; z < DIM_Z; ++z) {
        for (uint32_t y = 0; y < DIM_Y; ++y) {
            for (uint32_t x = 0; x < DIM_X; ++x) {
                uint32_t u = to_index(x, y, z);
                if (x + 1 < DIM_X) {
                    bonds.push_back(LatticeBond{u, to_index(x + 1, y, z), 0});
                }
                if (y + 1 < DIM_Y) {
                    bonds.push_back(LatticeBond{u, to_index(x, y + 1, z), 2});
                }
                if (z + 1 < DIM_Z) {
                    bonds.push_back(LatticeBond{u, to_index(x, y, z + 1), 4});
                }
            }
        }
    }

    return bonds;
}

std::vector<std::pair<uint32_t, uint32_t>> Lattice3D::get_canonical_spanning_tree() const {
    std::vector<std::pair<uint32_t, uint32_t>> tree;
    tree.reserve(TOTAL_QUBITS - 1);

    std::vector<bool> visited(TOTAL_QUBITS, false);
    std::queue<uint32_t> q;

    visited[0] = true;
    q.push(0);

    while (!q.empty()) {
        uint32_t u = q.front();
        q.pop();

        for (uint32_t v : get_neighbors(u)) {
            if (!visited[v]) {
                visited[v] = true;
                tree.push_back({u, v});
                q.push(v);
            }
        }
    }

    return tree;
}

} // namespace cq_hecs
