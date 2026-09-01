#include "cqhecs/stabilizer/tableau.hpp"
#include <bit>
#include <cassert>
#include <iostream>

namespace cqhecs {
namespace stabilizer {

StabilizerTableau::StabilizerTableau(uint32_t n_qubits)
    : num_qubits(n_qubits), num_words((n_qubits + 63) / 64) {
    reset();
}

void StabilizerTableau::reset() {
    size_t num_rows = 2 * num_qubits;
    x_bits.assign(num_rows, std::vector<uint64_t>(num_words, 0ULL));
    z_bits.assign(num_rows, std::vector<uint64_t>(num_words, 0ULL));
    phases.assign(num_rows, 0);

    for (uint32_t i = 0; i < num_qubits; ++i) {
        // Destabilizer: X_i
        set_x(i, i, true);
        // Stabilizer: Z_i
        set_z(num_qubits + i, i, true);
    }
}

void StabilizerTableau::apply_h(uint32_t q) {
    size_t word_idx = q / 64;
    uint64_t mask = 1ULL << (q % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        bool x = (x_bits[i][word_idx] & mask) != 0;
        bool z = (z_bits[i][word_idx] & mask) != 0;

        phases[i] ^= (x && z) ? 1 : 0;

        if (x != z) {
            x_bits[i][word_idx] ^= mask;
            z_bits[i][word_idx] ^= mask;
        }
    }
}

void StabilizerTableau::apply_s(uint32_t q) {
    size_t word_idx = q / 64;
    uint64_t mask = 1ULL << (q % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        bool x = (x_bits[i][word_idx] & mask) != 0;
        bool z = (z_bits[i][word_idx] & mask) != 0;

        phases[i] ^= (x && z) ? 1 : 0;
        if (x) {
            z_bits[i][word_idx] ^= mask;
        }
    }
}

void StabilizerTableau::apply_sdg(uint32_t q) {
    // Sdg = S * S * S
    apply_s(q);
    apply_s(q);
    apply_s(q);
}

void StabilizerTableau::apply_x(uint32_t q) {
    size_t word_idx = q / 64;
    uint64_t mask = 1ULL << (q % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        if (z_bits[i][word_idx] & mask) {
            phases[i] ^= 1;
        }
    }
}

void StabilizerTableau::apply_y(uint32_t q) {
    size_t word_idx = q / 64;
    uint64_t mask = 1ULL << (q % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        bool x = (x_bits[i][word_idx] & mask) != 0;
        bool z = (z_bits[i][word_idx] & mask) != 0;
        if (x ^ z) {
            phases[i] ^= 1;
        }
    }
}

void StabilizerTableau::apply_z(uint32_t q) {
    size_t word_idx = q / 64;
    uint64_t mask = 1ULL << (q % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        if (x_bits[i][word_idx] & mask) {
            phases[i] ^= 1;
        }
    }
}

void StabilizerTableau::apply_cx(uint32_t ctrl, uint32_t tgt) {
    size_t c_word = ctrl / 64;
    uint64_t c_mask = 1ULL << (ctrl % 64);
    size_t t_word = tgt / 64;
    uint64_t t_mask = 1ULL << (tgt % 64);
    size_t num_rows = 2 * num_qubits;

    for (size_t i = 0; i < num_rows; ++i) {
        bool xc = (x_bits[i][c_word] & c_mask) != 0;
        bool zc = (z_bits[i][c_word] & c_mask) != 0;
        bool xt = (x_bits[i][t_word] & t_mask) != 0;
        bool zt = (z_bits[i][t_word] & t_mask) != 0;

        phases[i] ^= (xc && zt && (xt == zc)) ? 1 : 0;

        if (xc) {
            x_bits[i][t_word] ^= t_mask;
        }
        if (zt) {
            z_bits[i][c_word] ^= c_mask;
        }
    }
}

void StabilizerTableau::apply_cz(uint32_t q1, uint32_t q2) {
    apply_h(q2);
    apply_cx(q1, q2);
    apply_h(q2);
}

void StabilizerTableau::apply_swap(uint32_t q1, uint32_t q2) {
    if (q1 == q2) return;
    apply_cx(q1, q2);
    apply_cx(q2, q1);
    apply_cx(q1, q2);
}

static inline int g_func(bool x1, bool z1, bool x2, bool z2) {
    if (!x1 && !z1) return 0;
    if (x1 && z1) return (z2 ? 1 : 0) - (x2 ? 1 : 0);
    if (x1 && !z1) return (z2 ? 1 : 0) * (x2 ? 1 : -1);
    // !x1 && z1
    return (x2 ? 1 : 0) * (z2 ? -1 : 1);
}

void StabilizerTableau::row_sum(size_t h, size_t i) {
    int sum_g = 2 * phases[h] + 2 * phases[i];

    for (size_t w = 0; w < num_words; ++w) {
        uint64_t x1 = x_bits[i][w];
        uint64_t z1 = z_bits[i][w];
        uint64_t x2 = x_bits[h][w];
        uint64_t z2 = z_bits[h][w];

        uint64_t active = x1 | z1;
        while (active) {
            int bit = std::countr_zero(active);
            uint64_t bmask = 1ULL << bit;
            sum_g += g_func((x1 & bmask) != 0, (z1 & bmask) != 0,
                            (x2 & bmask) != 0, (z2 & bmask) != 0);
            active &= (active - 1);
        }

        x_bits[h][w] ^= x1;
        z_bits[h][w] ^= z1;
    }

    sum_g = (sum_g % 4 + 4) % 4;
    phases[h] = (sum_g == 2) ? 1 : 0;
}

uint8_t StabilizerTableau::measure(uint32_t q, std::mt19937_64* rng) {
    size_t p = 2 * num_qubits;
    for (size_t i = num_qubits; i < 2 * num_qubits; ++i) {
        if (get_x(i, q)) {
            p = i;
            break;
        }
    }

    if (p < 2 * num_qubits) {
        // Random outcome
        for (size_t i = 0; i < 2 * num_qubits; ++i) {
            if (i != p && get_x(i, q)) {
                row_sum(i, p);
            }
        }

        size_t p_destab = p - num_qubits;
        x_bits[p_destab] = x_bits[p];
        z_bits[p_destab] = z_bits[p];
        phases[p_destab] = phases[p];

        for (size_t w = 0; w < num_words; ++w) {
            x_bits[p][w] = 0ULL;
            z_bits[p][w] = 0ULL;
        }
        set_z(p, q, true);

        uint8_t outcome = (rng) ? ((*rng)() & 1) : 0;
        phases[p] = outcome;
        return outcome;
    } else {
        // Deterministic outcome
        std::vector<uint64_t> scratch_x(num_words, 0ULL);
        std::vector<uint64_t> scratch_z(num_words, 0ULL);
        uint8_t scratch_phase = 0;

        for (size_t i = 0; i < num_qubits; ++i) {
            if (get_x(i, q)) {
                // row_sum scratch += i + num_qubits
                size_t src = i + num_qubits;
                int sum_g = 2 * scratch_phase + 2 * phases[src];
                for (size_t w = 0; w < num_words; ++w) {
                    uint64_t x1 = x_bits[src][w];
                    uint64_t z1 = z_bits[src][w];
                    uint64_t x2 = scratch_x[w];
                    uint64_t z2 = scratch_z[w];

                    uint64_t active = x1 | z1;
                    while (active) {
                        int bit = std::countr_zero(active);
                        uint64_t bmask = 1ULL << bit;
                        sum_g += g_func((x1 & bmask) != 0, (z1 & bmask) != 0,
                                        (x2 & bmask) != 0, (z2 & bmask) != 0);
                        active &= (active - 1);
                    }
                    scratch_x[w] ^= x1;
                    scratch_z[w] ^= z1;
                }
                sum_g = (sum_g % 4 + 4) % 4;
                scratch_phase = (sum_g == 2) ? 1 : 0;
            }
        }
        return scratch_phase;
    }
}

std::map<std::string, uint32_t> StabilizerTableau::sample_counts(uint32_t shots, uint64_t seed) {
    std::map<std::string, uint32_t> counts;
    std::mt19937_64 rng(seed);

    for (uint32_t s = 0; s < shots; ++s) {
        StabilizerTableau copy_tab = *this;
        std::string bitstr(num_qubits, '0');
        for (uint32_t q = 0; q < num_qubits; ++q) {
            uint8_t val = copy_tab.measure(q, &rng);
            bitstr[num_qubits - 1 - q] = val ? '1' : '0';
        }
        counts[bitstr]++;
    }
    return counts;
}

bool StabilizerTableau::verify_symplectic_invariants() const {
    auto symplectic_inner_product = [&](size_t row1, size_t row2) -> int {
        int inner = 0;
        for (size_t w = 0; w < num_words; ++w) {
            uint64_t term = (x_bits[row1][w] & z_bits[row2][w]) ^ (z_bits[row1][w] & x_bits[row2][w]);
            inner ^= (std::popcount(term) & 1);
        }
        return inner;
    };

    // 1. Stabilizers must commute with all stabilizers
    for (size_t i = num_qubits; i < 2 * num_qubits; ++i) {
        for (size_t j = i + 1; j < 2 * num_qubits; ++j) {
            if (symplectic_inner_product(i, j) != 0) return false;
        }
    }

    // 2. Destabilizers must commute with all other destabilizers
    for (size_t i = 0; i < num_qubits; ++i) {
        for (size_t j = i + 1; j < num_qubits; ++j) {
            if (symplectic_inner_product(i, j) != 0) return false;
        }
    }

    // 3. D_i and S_j commute iff i != j, and anticommute if i == j
    for (size_t i = 0; i < num_qubits; ++i) {
        for (size_t j = 0; j < num_qubits; ++j) {
            int expected = (i == j) ? 1 : 0;
            if (symplectic_inner_product(i, num_qubits + j) != expected) {
                return false;
            }
        }
    }

    return true;
}

bool StabilizerTableau::is_stabilizer_satisfied(
    const std::vector<uint32_t>& x_qubits,
    const std::vector<uint32_t>& z_qubits,
    uint8_t expected_phase) const {
    (void)expected_phase;
    
    // Check if the target Pauli commutes with all current stabilizers
    auto symplectic_with_pauli = [&](size_t row) -> int {
        int inner = 0;
        for (uint32_t q : x_qubits) {
            if (get_z(row, q)) inner ^= 1;
        }
        for (uint32_t q : z_qubits) {
            if (get_x(row, q)) inner ^= 1;
        }
        return inner;
    };

    for (size_t i = num_qubits; i < 2 * num_qubits; ++i) {
        if (symplectic_with_pauli(i) != 0) {
            return false;
        }
    }

    return true;
}

} // namespace stabilizer
} // namespace cqhecs
