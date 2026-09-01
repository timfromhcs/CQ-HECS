#pragma once

#include <cstdint>
#include <vector>
#include <random>
#include <string>
#include <map>

namespace cqhecs {
namespace stabilizer {

/**
 * @brief Bit-parallel Gottesman-Knill Stabilizer Tableau.
 * 
 * Supports up to 10,000+ qubits with O(N^2) Gaussian elimination.
 * Stored as a 2N x (2N + 1) binary matrix packed into 64-bit unsigned integers.
 * 
 * Rows 0 to N-1: Destabilizer generators
 * Rows N to 2N-1: Stabilizer generators
 * Column layout:
 * - [0, N-1]: X bits
 * - [N, 2N-1]: Z bits
 * - 2N: Phase bit r in {0, 1} where (-1)^r is the eigenvalue
 */
class StabilizerTableau {
public:
    uint32_t num_qubits;
    size_t num_words; // ceil(N / 64)

    // Each row has:
    // x_words: num_words
    // z_words: num_words
    // phase: uint8_t (0 or 1)
    std::vector<std::vector<uint64_t>> x_bits; // 2N rows x num_words
    std::vector<std::vector<uint64_t>> z_bits; // 2N rows x num_words
    std::vector<uint8_t> phases;               // 2N rows

    explicit StabilizerTableau(uint32_t n_qubits);

    void reset();

    // Single-qubit Clifford gates
    void apply_h(uint32_t q);
    void apply_s(uint32_t q);
    void apply_sdg(uint32_t q);
    void apply_x(uint32_t q);
    void apply_y(uint32_t q);
    void apply_z(uint32_t q);

    // Two-qubit Clifford gates
    void apply_cx(uint32_t ctrl, uint32_t tgt);
    void apply_cz(uint32_t q1, uint32_t q2);
    void apply_swap(uint32_t q1, uint32_t q2);

    // Row sum: row[h] <- row[h] * row[i]
    void row_sum(size_t h, size_t i);

    // Single qubit measurement with collapse (Gaussian elimination)
    uint8_t measure(uint32_t q, std::mt19937_64* rng = nullptr);

    // Fast sampling of all qubits
    std::map<std::string, uint32_t> sample_counts(uint32_t shots, uint64_t seed = 42);

    // Invariant verifications
    bool verify_symplectic_invariants() const;
    bool is_stabilizer_satisfied(const std::vector<uint32_t>& x_qubits,
                                 const std::vector<uint32_t>& z_qubits,
                                 uint8_t expected_phase = 0) const;

    // Direct bit getters
    bool get_x(size_t row, uint32_t col) const {
        return (x_bits[row][col / 64] >> (col % 64)) & 1ULL;
    }
    bool get_z(size_t row, uint32_t col) const {
        return (z_bits[row][col / 64] >> (col % 64)) & 1ULL;
    }
    void set_x(size_t row, uint32_t col, bool val) {
        if (val) x_bits[row][col / 64] |= (1ULL << (col % 64));
        else x_bits[row][col / 64] &= ~(1ULL << (col % 64));
    }
    void set_z(size_t row, uint32_t col, bool val) {
        if (val) z_bits[row][col / 64] |= (1ULL << (col % 64));
        else z_bits[row][col / 64] &= ~(1ULL << (col % 64));
    }
};

} // namespace stabilizer
} // namespace cqhecs
