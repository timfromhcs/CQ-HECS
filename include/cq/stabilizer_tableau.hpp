#ifndef CQ_STABILIZER_TABLEAU_HPP
#define CQ_STABILIZER_TABLEAU_HPP

#include <cstdint>
#include <vector>
#include <string>
#include <random>

namespace cq {

/**
 * @brief Bit-Parallel Gottesman-Knill Stabilizer Tableau.
 * 
 * Supports up to 10,000+ qubits in O(N^2) time with 64-bit word bit-parallelism.
 * Exactly simulates Clifford group operations: H, S, Sdg, CX, X, Y, Z, and measurement.
 */
class StabilizerTableau {
public:
    uint32_t num_qubits{0};
    uint32_t num_words{0};

    // 2N rows: rows 0..N-1 are destabilizers, rows N..2N-1 are stabilizers.
    // Each row contains num_words 64-bit unsigned integers.
    std::vector<uint64_t> x_table;
    std::vector<uint64_t> z_table;
    std::vector<uint8_t> r_phase; // 0 for +1, 1 for -1

    StabilizerTableau() = default;
    explicit StabilizerTableau(uint32_t n);

    void reset();

    // Clifford Gate Operations
    void apply_h(uint32_t q);
    void apply_s(uint32_t q);
    void apply_sdg(uint32_t q);
    void apply_cx(uint32_t ctrl, uint32_t tgt);
    void apply_x(uint32_t q);
    void apply_y(uint32_t q);
    void apply_z(uint32_t q);
    void apply_swap(uint32_t q1, uint32_t q2);

    // Measurement
    uint8_t measure(uint32_t q, std::mt19937_64* rng = nullptr);

    // Symplectic and stabilizer analysis
    int eval_pauli_expectation(const std::vector<uint64_t>& px, const std::vector<uint64_t>& pz) const;
    bool verify_symplectic_invariants() const;
    bool is_stabilizer_satisfied(const std::vector<uint64_t>& px, const std::vector<uint64_t>& pz, uint8_t expected_phase = 0) const;

    // Row operations
    void row_sum(uint32_t source_row, uint32_t target_row);

private:
    static int g_phase(bool x1, bool z1, bool x2, bool z2) noexcept;
};

} // namespace cq

#endif // CQ_STABILIZER_TABLEAU_HPP
