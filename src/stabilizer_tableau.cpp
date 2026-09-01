#include "cq/stabilizer_tableau.hpp"
#include <bit>
#include <cassert>
#include <cstring>
#include <iostream>

namespace cq {

StabilizerTableau::StabilizerTableau(uint32_t n)
    : num_qubits(n), num_words((n + 63) / 64) {
    x_table.resize(2 * num_qubits * num_words, 0);
    z_table.resize(2 * num_qubits * num_words, 0);
    r_phase.resize(2 * num_qubits, 0);
    reset();
}

void StabilizerTableau::reset() {
    std::fill(x_table.begin(), x_table.end(), 0ULL);
    std::fill(z_table.begin(), z_table.end(), 0ULL);
    std::fill(r_phase.begin(), r_phase.end(), uint8_t(0));

    for (uint32_t i = 0; i < num_qubits; ++i) {
        uint32_t w = i / 64;
        uint64_t mask = 1ULL << (i % 64);
        // Destabilizer i = X_i
        x_table[i * num_words + w] = mask;
        // Stabilizer i = Z_i
        z_table[(num_qubits + i) * num_words + w] = mask;
    }
}

int StabilizerTableau::g_phase(bool x1, bool z1, bool x2, bool z2) noexcept {
    if (!x1 && !z1) return 0;
    if (x1 && z1) { // Y
        if (x2 && !z2) return -1; // Y * X = -i Z
        if (!x2 && z2) return 1;  // Y * Z = i X
        return 0;
    }
    if (x1 && !z1) { // X
        if (!x2 && z2) return -1; // X * Z = -i Y
        if (x2 && z2) return 1;   // X * Y = i Z
        return 0;
    }
    // Z
    if (x2 && !z2) return 1;  // Z * X = i Y
    if (x2 && z2) return -1;  // Z * Y = -i X
    return 0;
}

void StabilizerTableau::row_sum(uint32_t source_row, uint32_t target_row) {
    size_t src_base = source_row * num_words;
    size_t tgt_base = target_row * num_words;

    int sum_g = 2 * r_phase[target_row] + 2 * r_phase[source_row];

    for (uint32_t w = 0; w < num_words; ++w) {
        uint64_t x1 = x_table[tgt_base + w];
        uint64_t z1 = z_table[tgt_base + w];
        uint64_t x2 = x_table[src_base + w];
        uint64_t z2 = z_table[src_base + w];

        uint64_t any = x1 | z1 | x2 | z2;
        while (any != 0) {
            int b = std::countr_zero(any);
            uint64_t m = 1ULL << b;
            sum_g += g_phase((x1 & m) != 0, (z1 & m) != 0, (x2 & m) != 0, (z2 & m) != 0);
            any &= ~m;
        }

        x_table[tgt_base + w] ^= x2;
        z_table[tgt_base + w] ^= z2;
    }

    sum_g = ((sum_g % 4) + 4) % 4;
    r_phase[target_row] = (sum_g == 2) ? 1 : 0;
}

void StabilizerTableau::apply_h(uint32_t q) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);
    size_t total_rows = 2 * num_qubits;

    for (size_t i = 0; i < total_rows; ++i) {
        size_t idx = i * num_words + w;
        bool bx = (x_table[idx] & m) != 0;
        bool bz = (z_table[idx] & m) != 0;
        r_phase[i] ^= (bx && bz);
        if (bx != bz) {
            x_table[idx] ^= m;
            z_table[idx] ^= m;
        }
    }
}

void StabilizerTableau::apply_s(uint32_t q) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);
    size_t total_rows = 2 * num_qubits;

    for (size_t i = 0; i < total_rows; ++i) {
        size_t idx = i * num_words + w;
        bool bx = (x_table[idx] & m) != 0;
        bool bz = (z_table[idx] & m) != 0;
        r_phase[i] ^= (bx && bz);
        if (bx) {
            z_table[idx] ^= m;
        }
    }
}

void StabilizerTableau::apply_sdg(uint32_t q) {
    apply_s(q);
    apply_s(q);
    apply_s(q);
}

void StabilizerTableau::apply_cx(uint32_t ctrl, uint32_t tgt) {
    uint32_t wc = ctrl / 64;
    uint64_t mc = 1ULL << (ctrl % 64);
    uint32_t wt = tgt / 64;
    uint64_t mt = 1ULL << (tgt % 64);
    size_t total_rows = 2 * num_qubits;

    for (size_t i = 0; i < total_rows; ++i) {
        size_t base = i * num_words;
        bool xc = (x_table[base + wc] & mc) != 0;
        bool zc = (z_table[base + wc] & mc) != 0;
        bool xt = (x_table[base + wt] & mt) != 0;
        bool zt = (z_table[base + wt] & mt) != 0;

        r_phase[i] ^= (xc && zt && (xt ^ zc ^ 1));
        if (xc) x_table[base + wt] ^= mt;
        if (zt) z_table[base + wc] ^= mc;
    }
}

void StabilizerTableau::apply_x(uint32_t q) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);
    size_t total_rows = 2 * num_qubits;
    for (size_t i = 0; i < total_rows; ++i) {
        if ((z_table[i * num_words + w] & m) != 0) {
            r_phase[i] ^= 1;
        }
    }
}

void StabilizerTableau::apply_z(uint32_t q) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);
    size_t total_rows = 2 * num_qubits;
    for (size_t i = 0; i < total_rows; ++i) {
        if ((x_table[i * num_words + w] & m) != 0) {
            r_phase[i] ^= 1;
        }
    }
}

void StabilizerTableau::apply_y(uint32_t q) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);
    size_t total_rows = 2 * num_qubits;
    for (size_t i = 0; i < total_rows; ++i) {
        size_t idx = i * num_words + w;
        bool bx = (x_table[idx] & m) != 0;
        bool bz = (z_table[idx] & m) != 0;
        r_phase[i] ^= (bx ^ bz);
    }
}

void StabilizerTableau::apply_swap(uint32_t q1, uint32_t q2) {
    if (q1 == q2) return;
    apply_cx(q1, q2);
    apply_cx(q2, q1);
    apply_cx(q1, q2);
}

uint8_t StabilizerTableau::measure(uint32_t q, std::mt19937_64* rng) {
    uint32_t w = q / 64;
    uint64_t m = 1ULL << (q % 64);

    // Check if any stabilizer row has X_q == 1
    int p = -1;
    for (uint32_t i = num_qubits; i < 2 * num_qubits; ++i) {
        if ((x_table[i * num_words + w] & m) != 0) {
            p = static_cast<int>(i);
            break;
        }
    }

    if (p != -1) {
        // Case 1: Non-deterministic outcome
        for (size_t i = 0; i < 2 * num_qubits; ++i) {
            if (i != static_cast<size_t>(p) && ((x_table[i * num_words + w] & m) != 0)) {
                row_sum(static_cast<uint32_t>(p), static_cast<uint32_t>(i));
            }
        }

        // Copy row p to corresponding destabilizer row p - N
        uint32_t destab_idx = static_cast<uint32_t>(p) - num_qubits;
        for (uint32_t kw = 0; kw < num_words; ++kw) {
            x_table[destab_idx * num_words + kw] = x_table[p * num_words + kw];
            z_table[destab_idx * num_words + kw] = z_table[p * num_words + kw];
        }
        r_phase[destab_idx] = r_phase[p];

        // Clear row p
        for (uint32_t kw = 0; kw < num_words; ++kw) {
            x_table[p * num_words + kw] = 0;
            z_table[p * num_words + kw] = 0;
        }
        z_table[p * num_words + w] = m;

        uint8_t outcome = 0;
        if (rng) {
            outcome = (*rng)() & 1;
        }
        r_phase[p] = outcome;
        return outcome;
    }

    // Case 2: Deterministic outcome
    // Accumulate destabilizers where x_{i, q} == 1 into temporary scratch row
    std::vector<uint64_t> scratch_x(num_words, 0);
    std::vector<uint64_t> scratch_z(num_words, 0);
    int sum_g = 0;

    for (uint32_t i = 0; i < num_qubits; ++i) {
        if ((x_table[i * num_words + w] & m) != 0) {
            uint32_t stab_row = num_qubits + i;
            size_t stab_base = stab_row * num_words;
            sum_g += 2 * r_phase[stab_row];

            for (uint32_t kw = 0; kw < num_words; ++kw) {
                uint64_t x1 = scratch_x[kw];
                uint64_t z1 = scratch_z[kw];
                uint64_t x2 = x_table[stab_base + kw];
                uint64_t z2 = z_table[stab_base + kw];

                uint64_t any = x1 | z1 | x2 | z2;
                while (any != 0) {
                    int b = std::countr_zero(any);
                    uint64_t mb = 1ULL << b;
                    sum_g += g_phase((x1 & mb) != 0, (z1 & mb) != 0, (x2 & mb) != 0, (z2 & mb) != 0);
                    any &= ~mb;
                }
                scratch_x[kw] ^= x2;
                scratch_z[kw] ^= z2;
            }
        }
    }

    sum_g = ((sum_g % 4) + 4) % 4;
    return (sum_g == 2) ? 1 : 0;
}

bool StabilizerTableau::verify_symplectic_invariants() const {
    // Check [S_i, S_j] == 0 and [D_i, S_j] == delta_{ij}
    for (uint32_t i = 0; i < num_qubits; ++i) {
        size_t s_row = (num_qubits + i) * num_words;
        size_t d_row = i * num_words;

        // Check S_i with S_j
        for (uint32_t j = i + 1; j < num_qubits; ++j) {
            size_t s2_row = (num_qubits + j) * num_words;
            uint32_t inner = 0;
            for (uint32_t w = 0; w < num_words; ++w) {
                uint64_t cross = (x_table[s_row + w] & z_table[s2_row + w]) ^
                                 (z_table[s_row + w] & x_table[s2_row + w]);
                inner ^= (std::popcount(cross) & 1);
            }
            if (inner != 0) return false;
        }

        // Check D_i with S_j
        for (uint32_t j = 0; j < num_qubits; ++j) {
            size_t s2_row = (num_qubits + j) * num_words;
            uint32_t inner = 0;
            for (uint32_t w = 0; w < num_words; ++w) {
                uint64_t cross = (x_table[d_row + w] & z_table[s2_row + w]) ^
                                 (z_table[d_row + w] & x_table[s2_row + w]);
                inner ^= (std::popcount(cross) & 1);
            }
            uint32_t expected = (i == j) ? 1 : 0;
            if (inner != expected) return false;
        }
    }
    return true;
}

bool StabilizerTableau::is_stabilizer_satisfied(const std::vector<uint64_t>& px,
                                               const std::vector<uint64_t>& pz,
                                               uint8_t expected_phase) const {
    // P stabilizes |psi> if P commutes with all stabilizers S_i and has the correct phase
    for (uint32_t i = 0; i < num_qubits; ++i) {
        size_t s_row = (num_qubits + i) * num_words;
        uint32_t inner = 0;
        for (uint32_t w = 0; w < num_words; ++w) {
            uint64_t cross = (px[w] & z_table[s_row + w]) ^ (pz[w] & x_table[s_row + w]);
            inner ^= (std::popcount(cross) & 1);
        }
        if (inner != 0) return false; // Non-commuting
    }

    // Now verify phase by Gaussian row reduction in destabilizer basis
    std::vector<uint64_t> acc_x = px;
    std::vector<uint64_t> acc_z = pz;
    int sum_g = 2 * expected_phase;

    for (uint32_t i = 0; i < num_qubits; ++i) {
        uint32_t w = i / 64;
        uint64_t m = 1ULL << (i % 64);
        if ((acc_x[w] & m) != 0) {
            size_t stab_row = (num_qubits + i) * num_words;
            sum_g += 2 * r_phase[num_qubits + i];
            for (uint32_t kw = 0; kw < num_words; ++kw) {
                uint64_t x1 = acc_x[kw];
                uint64_t z1 = acc_z[kw];
                uint64_t x2 = x_table[stab_row + kw];
                uint64_t z2 = z_table[stab_row + kw];

                uint64_t any = x1 | z1 | x2 | z2;
                while (any != 0) {
                    int b = std::countr_zero(any);
                    uint64_t mb = 1ULL << b;
                    sum_g += g_phase((x1 & mb) != 0, (z1 & mb) != 0, (x2 & mb) != 0, (z2 & mb) != 0);
                    any &= ~mb;
                }
                acc_x[kw] ^= x2;
                acc_z[kw] ^= z2;
            }
        }
    }

    sum_g = ((sum_g % 4) + 4) % 4;
    return (sum_g == 0);
}

} // namespace cq
