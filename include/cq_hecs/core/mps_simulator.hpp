#ifndef CQ_HECS_CORE_MPS_SIMULATOR_HPP
#define CQ_HECS_CORE_MPS_SIMULATOR_HPP

#include "types.hpp"
#include "cordic.hpp"
#include <vector>
#include <tuple>
#include <map>
#include <cmath>
#include <algorithm>
#include <stdexcept>
#include <cassert>
#include <random>
#include <complex>
#include <cstddef>
#include <limits>
#include <string>

namespace cq_hecs {
namespace core {

/**
 * @brief Represents a single site tensor in an MPS chain: A[s, alpha, beta]
 * s: physical index {0, 1}
 * alpha: left bond index [0, chi_left - 1]
 * beta: right bond index [0, chi_right - 1]
 */
struct MPSSiteTensor {
    uint32_t chi_left{1};
    uint32_t chi_right{1};
    // Size = 2 * chi_left * chi_right
    std::vector<ComplexQ31> data;

    MPSSiteTensor() : chi_left(1), chi_right(1), data(2, ComplexQ31::zero()) {
        data[0] = ComplexQ31::one(); // |0> state
    }

    MPSSiteTensor(uint32_t cl, uint32_t cr) : chi_left(cl), chi_right(cr) {
        const size_t count = checked_size(cl, cr);
        data.assign(count, ComplexQ31::zero());
    }

    static size_t checked_size(uint32_t cl, uint32_t cr) {
        size_t count = static_cast<size_t>(cl) * static_cast<size_t>(cr) * 2u;
        if (count > std::numeric_limits<size_t>::max() / sizeof(ComplexQ31)) {
            throw std::length_error("MPSSiteTensor: tensor dimensions overflow the address space");
        }
        return count;
    }

    ComplexQ31& at(uint32_t s, uint32_t a, uint32_t b) {
        return data[(s * chi_left + a) * chi_right + b];
    }

    const ComplexQ31& at(uint32_t s, uint32_t a, uint32_t b) const {
        return data[(s * chi_left + a) * chi_right + b];
    }

    size_t byte_size() const noexcept {
        return data.size() * sizeof(ComplexQ31);
    }
};

/**
 * @brief Matrix Product State (MPS) Quantum Simulator.
 *
 * Supports hundreds of qubits with a bounded bond dimension D. Amplitudes are
 * stored in Q1.31 fixed point. Two-site gates are applied by contracting the
 * pair, applying the gate and factorising the result with a complex SVD. When
 * the SVD rank exceeds the configured bond cap, the smallest singular values
 * are discarded and the discarded weight is recorded as a diagnostic. That
 * diagnostic is not a certified global state/observable error bound. Truncation
 * also rescales the retained local tensors to keep the fixed-point spectrum
 * from underflowing; sampling normalises the represented state.
 */
class MPSSimulator {
public:
    uint32_t num_qubits;
    uint32_t max_bond_dim; // 0 = no configured cap
    std::vector<MPSSiteTensor> sites;

    /// Squared weight discarded by the most recent two-site factorisation.
    double last_truncation_discarded_weight{0.0};
    /// Sum of squared discarded weights over the lifetime of the state (diagnostic).
    double cumulative_discarded_weight{0.0};

    MPSSimulator(uint32_t n_qubits, uint32_t max_d = 64)
        : num_qubits(n_qubits), max_bond_dim(max_d), sites(n_qubits) {
        if (n_qubits == 0) {
            throw std::invalid_argument("MPSSimulator: at least one qubit is required");
        }
        reset();
    }

    void reset() {
        sites.clear();
        sites.resize(num_qubits);
        for (uint32_t i = 0; i < num_qubits; ++i) {
            sites[i] = MPSSiteTensor(1, 1);
            sites[i].at(0, 0, 0) = ComplexQ31::one();
            sites[i].at(1, 0, 0) = ComplexQ31::zero();
        }
        last_truncation_discarded_weight = 0.0;
        cumulative_discarded_weight = 0.0;
    }

    void check_qubit(uint32_t q) const {
        if (q >= num_qubits) {
            throw std::out_of_range(
                "MPSSimulator: qubit index " + std::to_string(q) +
                " is out of range for " + std::to_string(num_qubits) + " qubits");
        }
    }

    size_t get_total_memory_bytes() const noexcept {
        size_t total = sizeof(MPSSimulator);
        for (const auto& s : sites) {
            total += s.byte_size() + sizeof(MPSSiteTensor);
        }
        return total;
    }

    double get_memory_mb() const noexcept {
        return static_cast<double>(get_total_memory_bytes()) / (1024.0 * 1024.0);
    }

    size_t total_memory_bytes() const noexcept {
        return get_total_memory_bytes();
    }

    void apply_h(uint32_t q) {
        apply_1q_gate(q, 1);
    }

    /// Generic CNOT: adjacent pairs use the two-site update, non-adjacent pairs
    /// are routed through exact adjacent SWAPs and restored afterwards.
    void apply_cx(uint32_t c, uint32_t t) {
        check_qubit(c);
        check_qubit(t);
        if (c == t) {
            throw std::invalid_argument("MPSSimulator: CNOT control and target must differ");
        }
        if (c + 1 == t || t + 1 == c) {
            apply_cnot_adjacent(c, t);
            return;
        }
        // Move the target next to the control, apply, then restore the ordering.
        uint32_t target = t;
        if (target < c) {
            while (target + 1 < c) {
                swap_adjacent(target);
                ++target;
            }
            // target is now c-1: control is the right site, target the left.
            apply_cnot_adjacent(c, target);
            while (target > t) {
                swap_adjacent(target - 1);
                --target;
            }
        } else {
            while (target > c + 1) {
                swap_adjacent(target - 1);
                --target;
            }
            // target is now c+1: control is the left site.
            apply_cnot_adjacent(c, target);
            while (target < t) {
                swap_adjacent(target);
                ++target;
            }
        }
    }

    void prepare_ghz_state() {
        create_ghz();
    }

    /**
     * @brief Apply single-qubit gate on site q (1=H, 2=X, 3=Y, 4=Z, 5=S,
     * 6=Sdg, 7=T, 8=Tdg, 9=RZ with phase).
     */
    void apply_1q_gate(uint32_t q, int gate_type, uint32_t phase = 0) {
        check_qubit(q);
        auto& site = sites[q];

        for (uint32_t a = 0; a < site.chi_left; ++a) {
            for (uint32_t b = 0; b < site.chi_right; ++b) {
                ComplexQ31 c0 = site.at(0, a, b);
                ComplexQ31 c1 = site.at(1, a, b);

                if (gate_type == 1) { // Hadamard
                    // c0' = (c0 + c1) / sqrt(2), c1' = (c0 - c1) / sqrt(2)
                    ComplexQ31 sum = complex_add(c0, c1);
                    ComplexQ31 diff = complex_sub(c0, c1);
                    site.at(0, a, b) = ComplexQ31{q31_mul(sum.re, ComplexQ31::INV_SQRT2_VAL), q31_mul(sum.im, ComplexQ31::INV_SQRT2_VAL)};
                    site.at(1, a, b) = ComplexQ31{q31_mul(diff.re, ComplexQ31::INV_SQRT2_VAL), q31_mul(diff.im, ComplexQ31::INV_SQRT2_VAL)};
                } else if (gate_type == 2) { // Pauli X
                    site.at(0, a, b) = c1;
                    site.at(1, a, b) = c0;
                } else if (gate_type == 3) { // Pauli Y
                    site.at(0, a, b) = ComplexQ31{c1.im, -c1.re};
                    site.at(1, a, b) = ComplexQ31{-c0.im, c0.re};
                } else if (gate_type == 4) { // Pauli Z
                    site.at(1, a, b) = ComplexQ31{-c1.re, -c1.im};
                } else if (gate_type == 5) { // S gate (pi/2)
                    site.at(1, a, b) = ComplexQ31{-c1.im, c1.re};
                } else if (gate_type == 6) { // Sdg (-pi/2)
                    site.at(1, a, b) = ComplexQ31{c1.im, -c1.re};
                } else if (gate_type == 7) { // T gate (pi/4)
                    site.at(1, a, b) = cordic_rotate(c1, 0x20000000u);
                } else if (gate_type == 8) { // Tdg (-pi/4)
                    site.at(1, a, b) = cordic_rotate(c1, 0xE0000000u);
                } else if (gate_type == 9) { // RZ
                    uint32_t half = phase >> 1;
                    site.at(0, a, b) = cordic_rotate(c0, 0u - half);
                    site.at(1, a, b) = cordic_rotate(c1, half);
                } else {
                    throw std::invalid_argument(
                        "MPSSimulator: unsupported single-qubit gate type " + std::to_string(gate_type));
                }
            }
        }
    }

    /**
     * @brief Apply CNOT between adjacent sites (|ctrl - tgt| == 1).
     */
    void apply_cnot_adjacent(uint32_t ctrl, uint32_t tgt) {
        check_qubit(ctrl);
        check_qubit(tgt);
        if (ctrl + 1 != tgt && tgt + 1 != ctrl) {
            throw std::invalid_argument(
                "MPSSimulator: apply_cnot_adjacent requires adjacent qubits");
        }
        uint32_t q_left = std::min(ctrl, tgt);
        uint32_t q_right = std::max(ctrl, tgt);

        auto& sL = sites[q_left];
        auto& sR = sites[q_right];

        uint32_t chi_L = sL.chi_left;
        uint32_t chi_M = sL.chi_right;
        uint32_t chi_R = sR.chi_right;
        if (sR.chi_left != chi_M) {
            throw std::runtime_error("MPSSimulator: inconsistent shared bond dimension");
        }

        // Two-site contracted tensor: Theta[sL, sR, a, b]
        std::vector<ComplexQ31> theta(static_cast<size_t>(4) * chi_L * chi_R, ComplexQ31::zero());
        auto theta_idx = [&](uint32_t sl, uint32_t sr, uint32_t a, uint32_t b) {
            return ((static_cast<size_t>(sl) * 2 + sr) * chi_L + a) * chi_R + b;
        };

        for (uint32_t sl = 0; sl < 2; ++sl) {
            for (uint32_t sr = 0; sr < 2; ++sr) {
                for (uint32_t a = 0; a < chi_L; ++a) {
                    for (uint32_t b = 0; b < chi_R; ++b) {
                        ComplexQ31 sum = ComplexQ31::zero();
                        for (uint32_t m = 0; m < chi_M; ++m) {
                            sum = complex_add(sum, complex_mul(sL.at(sl, a, m), sR.at(sr, m, b)));
                        }
                        theta[theta_idx(sl, sr, a, b)] = sum;
                    }
                }
            }
        }

        // Apply CNOT: if the control qubit is 1, flip the target qubit.
        for (uint32_t a = 0; a < chi_L; ++a) {
            for (uint32_t b = 0; b < chi_R; ++b) {
                if (ctrl == q_left) {
                    std::swap(theta[theta_idx(1, 0, a, b)], theta[theta_idx(1, 1, a, b)]);
                } else {
                    std::swap(theta[theta_idx(0, 1, a, b)], theta[theta_idx(1, 1, a, b)]);
                }
            }
        }

        factorise_theta(theta, chi_L, chi_R, sites[q_left], sites[q_right]);
    }

    /**
     * @brief Swap two adjacent physical sites, keeping the MPS representation.
     */
    void swap_adjacent(uint32_t q) {
        check_qubit(q);
        if (q + 1 >= num_qubits) {
            throw std::out_of_range("MPSSimulator: swap_adjacent requires q + 1 to be in range");
        }
        auto& sL = sites[q];
        auto& sR = sites[q + 1];
        uint32_t chi_L = sL.chi_left;
        uint32_t chi_M = sL.chi_right;
        uint32_t chi_R = sR.chi_right;
        if (sR.chi_left != chi_M) {
            throw std::runtime_error("MPSSimulator: inconsistent shared bond dimension");
        }

        std::vector<ComplexQ31> theta(static_cast<size_t>(4) * chi_L * chi_R, ComplexQ31::zero());
        auto idx = [&](uint32_t sl, uint32_t sr, uint32_t a, uint32_t b) {
            return ((static_cast<size_t>(sl) * 2 + sr) * chi_L + a) * chi_R + b;
        };
        for (uint32_t sl = 0; sl < 2; ++sl) {
            for (uint32_t sr = 0; sr < 2; ++sr) {
                for (uint32_t a = 0; a < chi_L; ++a) {
                    for (uint32_t b = 0; b < chi_R; ++b) {
                        ComplexQ31 sum = ComplexQ31::zero();
                        for (uint32_t m = 0; m < chi_M; ++m) {
                            sum = complex_add(sum, complex_mul(sL.at(sl, a, m), sR.at(sr, m, b)));
                        }
                        // SWAP exchanges the two physical indices.
                        theta[idx(sr, sl, a, b)] = sum;
                    }
                }
            }
        }

        // A SWAP preserves the Schmidt rank; do not truncate below its actual rank.
        factorise_theta(theta, chi_L, chi_R, sites[q], sites[q + 1], true);
    }

    /**
     * @brief Creates a bit-exact GHZ state across all num_qubits sites in 1D MPS.
     * State: (|00...0> + |11...1>) / sqrt(2).
     */
    void create_ghz() {
        sites.clear();
        sites.resize(num_qubits);

        if (num_qubits == 1) {
            sites[0] = MPSSiteTensor(1, 1);
            sites[0].at(0, 0, 0) = ComplexQ31::inv_sqrt2();
            sites[0].at(1, 0, 0) = ComplexQ31::inv_sqrt2();
            return;
        }

        sites[0] = MPSSiteTensor(1, 2);
        sites[0].at(0, 0, 0) = ComplexQ31::inv_sqrt2();
        sites[0].at(1, 0, 1) = ComplexQ31::inv_sqrt2();

        for (uint32_t i = 1; i < num_qubits - 1; ++i) {
            sites[i] = MPSSiteTensor(2, 2);
            sites[i].at(0, 0, 0) = ComplexQ31::one();
            sites[i].at(1, 1, 1) = ComplexQ31::one();
        }

        uint32_t last = num_qubits - 1;
        sites[last] = MPSSiteTensor(2, 1);
        sites[last].at(0, 0, 0) = ComplexQ31::one();
        sites[last].at(1, 1, 0) = ComplexQ31::one();
    }

    /**
     * @brief Exact check for the canonical GHZ MPS produced by create_ghz().
     * Used only to select the O(shots) fast path; any other state is sampled
     * with the generic environment-based sampler.
     */
    bool is_ghz_state() const {
        auto eq = [](const ComplexQ31& a, const ComplexQ31& b) {
            return a.re == b.re && a.im == b.im;
        };
        if (num_qubits == 0) return false;
        if (num_qubits == 1) {
            return sites[0].chi_left == 1 && sites[0].chi_right == 1 &&
                   eq(sites[0].at(0, 0, 0), ComplexQ31::inv_sqrt2()) &&
                   eq(sites[0].at(1, 0, 0), ComplexQ31::inv_sqrt2());
        }
        if (sites[0].chi_left != 1 || sites[0].chi_right != 2) return false;
        if (!eq(sites[0].at(0, 0, 0), ComplexQ31::inv_sqrt2()) ||
            !eq(sites[0].at(1, 0, 1), ComplexQ31::inv_sqrt2())) {
            return false;
        }
        for (uint32_t i = 1; i + 1 < num_qubits; ++i) {
            const auto& s = sites[i];
            if (s.chi_left != 2 || s.chi_right != 2) return false;
            if (!eq(s.at(0, 0, 0), ComplexQ31::one()) ||
                !eq(s.at(1, 1, 1), ComplexQ31::one())) {
                return false;
            }
        }
        const auto& last = sites[num_qubits - 1];
        return last.chi_left == 2 && last.chi_right == 1 &&
               eq(last.at(0, 0, 0), ComplexQ31::one()) &&
               eq(last.at(1, 1, 0), ComplexQ31::one());
    }

    /**
     * @brief Sample the GHZ parity distribution.
     *
     * Only valid for a state that is exactly the canonical GHZ MPS. The
     * uniform 50/50 draw is correct because the GHZ state has two equally
     * likely outcomes; this method throws for any other state instead of
     * pretending that uniform sampling is Born-rule sampling.
     */
    std::tuple<uint32_t, uint32_t, uint32_t> sample_ghz_parity(
        uint32_t shots, uint64_t seed = 42) const {
        if (!is_ghz_state()) {
            throw std::logic_error(
                "MPSSimulator: sample_ghz_parity requires a canonical GHZ state; "
                "use sample_counts() for a generic state");
        }
        std::mt19937_64 rng(seed);
        uint32_t zero_shots = 0;
        uint32_t one_shots = 0;
        for (uint32_t s = 0; s < shots; ++s) {
            if ((rng() & 1ULL) == 0) zero_shots++; else one_shots++;
        }
        return {zero_shots, one_shots, 0};
    }

    /// Backwards-compatible name; semantics are those of sample_ghz_parity().
    std::tuple<uint32_t, uint32_t, uint32_t> measure_ghz_parity(uint32_t shots) const {
        return sample_ghz_parity(shots);
    }

    /**
     * @brief Born-rule sampling from the represented MPS for any state.
     *
     * Uses right-environment transfer matrices so conditional probabilities
     * account for the whole suffix, not only the prefix amplitude.
     */
    std::map<std::string, uint32_t> sample_counts(uint32_t shots, uint64_t seed = 42) const {
        std::map<std::string, uint32_t> counts;
        if (shots == 0) return counts;

        if (is_ghz_state()) {
            std::mt19937_64 rng(seed);
            std::string zeros(num_qubits, '0');
            std::string ones(num_qubits, '1');
            uint32_t c0 = 0, c1 = 0;
            for (uint32_t s = 0; s < shots; ++s) {
                if ((rng() & 1ULL) == 0) c0++; else c1++;
            }
            if (c0) counts[zeros] = c0;
            if (c1) counts[ones] = c1;
            return counts;
        }

        // Right environments R_q for every bond q = 0..num_qubits.
        std::vector<std::vector<double>> env_re;
        std::vector<std::vector<double>> env_im;
        std::vector<uint32_t> bond_dims(num_qubits + 1, 1);
        for (uint32_t q = 1; q < num_qubits; ++q) {
            if (sites[q].chi_left != sites[q - 1].chi_right) {
                throw std::runtime_error("MPSSimulator: inconsistent bond dimensions");
            }
            bond_dims[q] = sites[q].chi_left;
        }

        env_re.resize(num_qubits + 1);
        env_im.resize(num_qubits + 1);
        env_re[num_qubits] = {1.0};
        env_im[num_qubits] = {0.0};

        auto amp = [](const ComplexQ31& z) {
            return std::complex<double>(z.to_double(),
                                        static_cast<double>(z.im) / 2147483647.0);
        };

        for (int q = static_cast<int>(num_qubits) - 1; q >= 0; --q) {
            const auto& site = sites[static_cast<size_t>(q)];
            uint32_t dl = site.chi_left;
            uint32_t dr = site.chi_right;
            uint32_t next_dim = bond_dims[static_cast<size_t>(q) + 1];
            if (dr != next_dim) {
                throw std::runtime_error("MPSSimulator: inconsistent right bond dimension");
            }
            const auto& rre = env_re[static_cast<size_t>(q) + 1];
            const auto& rim = env_im[static_cast<size_t>(q) + 1];
            std::vector<double> re(static_cast<size_t>(dl) * dl, 0.0);
            std::vector<double> im(static_cast<size_t>(dl) * dl, 0.0);
            for (uint32_t a = 0; a < dl; ++a) {
                for (uint32_t a2 = 0; a2 < dl; ++a2) {
                    double acc_re = 0.0, acc_im = 0.0;
                    for (uint32_t s = 0; s < 2; ++s) {
                        for (uint32_t b = 0; b < dr; ++b) {
                            std::complex<double> left = std::conj(amp(site.at(s, a, b)));
                            for (uint32_t b2 = 0; b2 < dr; ++b2) {
                                std::complex<double> right = amp(site.at(s, a2, b2));
                                double rr = rre[static_cast<size_t>(b) * dr + b2];
                                double ri = rim[static_cast<size_t>(b) * dr + b2];
                                std::complex<double> t = left * std::complex<double>(rr, ri) * right;
                                acc_re += t.real();
                                acc_im += t.imag();
                            }
                        }
                    }
                    re[static_cast<size_t>(a) * dl + a2] = acc_re;
                    im[static_cast<size_t>(a) * dl + a2] = acc_im;
                }
            }
            env_re[static_cast<size_t>(q)] = std::move(re);
            env_im[static_cast<size_t>(q)] = std::move(im);
        }

        std::mt19937_64 rng(seed);
        std::uniform_real_distribution<double> draw(0.0, 1.0);

        for (uint32_t shot = 0; shot < shots; ++shot) {
            std::string bits;
            bits.reserve(num_qubits);
            std::vector<std::complex<double>> v{std::complex<double>(1.0, 0.0)};

            for (uint32_t q = 0; q < num_qubits; ++q) {
                const auto& site = sites[q];
                uint32_t dl = site.chi_left;
                uint32_t dr = site.chi_right;
                const auto& rre = env_re[static_cast<size_t>(q) + 1];
                const auto& rim = env_im[static_cast<size_t>(q) + 1];

                std::vector<std::complex<double>> w0(dr, 0.0);
                std::vector<std::complex<double>> w1(dr, 0.0);
                for (uint32_t b = 0; b < dr; ++b) {
                    std::complex<double> s0 = 0.0, s1 = 0.0;
                    for (uint32_t a = 0; a < dl; ++a) {
                        s0 += v[a] * amp(site.at(0, a, b));
                        s1 += v[a] * amp(site.at(1, a, b));
                    }
                    w0[b] = s0;
                    w1[b] = s1;
                }

                auto weight = [&](const std::vector<std::complex<double>>& w) {
                    double acc = 0.0;
                    for (uint32_t b = 0; b < dr; ++b) {
                        for (uint32_t b2 = 0; b2 < dr; ++b2) {
                            std::complex<double> r(rre[static_cast<size_t>(b) * dr + b2],
                                                   rim[static_cast<size_t>(b) * dr + b2]);
                            acc += (std::conj(w[b]) * r * w[b2]).real();
                        }
                    }
                    return acc;
                };

                double p0 = std::max(0.0, weight(w0));
                double p1 = std::max(0.0, weight(w1));
                double total = p0 + p1;
                if (!(total > 0.0) || !std::isfinite(total)) {
                    throw std::runtime_error("MPSSimulator: zero or non-finite sampling weight");
                }

                bool choose_one = draw(rng) * total >= p0;
                double chosen = choose_one ? p1 : p0;
                if (!(chosen > 0.0)) {
                    throw std::runtime_error("MPSSimulator: sampled a zero-probability branch");
                }
                double scale = 1.0 / std::sqrt(chosen);
                v = choose_one ? w1 : w0;
                for (auto& z : v) z *= scale;
                bits.push_back(choose_one ? '1' : '0');
            }

            std::string out(num_qubits, '0');
            for (uint32_t q = 0; q < num_qubits; ++q) {
                out[num_qubits - 1 - q] = bits[q];
            }
            counts[out]++;
        }

        return counts;
    }

    /**
     * @brief Dense expansion of the represented state (test/reference only).
     * Bounded to keep the explicit allocation small.
     */
    std::vector<std::complex<double>> to_statevector(uint32_t max_qubits = 22) const {
        if (num_qubits > max_qubits) {
            throw std::invalid_argument(
                "MPSSimulator::to_statevector refuses an unguarded dense expansion");
        }
        std::vector<std::complex<double>> psi{std::complex<double>(1.0, 0.0)};
        auto amp = [](const ComplexQ31& z) {
            return std::complex<double>(z.to_double(),
                                        static_cast<double>(z.im) / 2147483647.0);
        };
        for (uint32_t q = 0; q < num_qubits; ++q) {
            const auto& site = sites[q];
            uint32_t dl = site.chi_left;
            uint32_t dr = site.chi_right;
            size_t prefixes = size_t(1) << q;
            std::vector<std::complex<double>> next(prefixes * 2 * dr, 0.0);
            for (size_t p = 0; p < prefixes; ++p) {
                for (uint32_t a = 0; a < dl; ++a) {
                    std::complex<double> v = psi[p * dl + a];
                    if (v == 0.0) continue;
                    for (uint32_t b = 0; b < dr; ++b) {
                        for (uint32_t s = 0; s < 2; ++s) {
                            size_t index = p + (static_cast<size_t>(s) << q);
                            next[index * dr + b] += v * amp(site.at(s, a, b));
                        }
                    }
                }
            }
            psi = std::move(next);
        }
        std::vector<std::complex<double>> result(size_t(1) << num_qubits, 0.0);
        for (size_t i = 0; i < result.size(); ++i) result[i] = psi[i];
        return result;
    }

private:
    static ComplexQ31 quantise(double re, double im) {
        constexpr double ONE = 2147483647.0;
        re = std::clamp(re, -1.0, 1.0);
        im = std::clamp(im, -1.0, 1.0);
        int32_t r = static_cast<int32_t>(std::llround(re * ONE));
        int32_t i = static_cast<int32_t>(std::llround(im * ONE));
        return ComplexQ31{r, i};
    }

    /**
     * @brief Factorise the two-site tensor into new site tensors with a complex SVD.
     */
    void factorise_theta(const std::vector<ComplexQ31>& theta,
                         uint32_t chi_L, uint32_t chi_R,
                         MPSSiteTensor& outL, MPSSiteTensor& outR,
                         bool exact_rank = false) {
        const uint32_t rows = 2 * chi_L;
        const uint32_t cols = 2 * chi_R;
        std::vector<std::complex<double>> matrix(static_cast<size_t>(rows) * cols, 0.0);
        for (uint32_t sl = 0; sl < 2; ++sl) {
            for (uint32_t sr = 0; sr < 2; ++sr) {
                for (uint32_t a = 0; a < chi_L; ++a) {
                    for (uint32_t b = 0; b < chi_R; ++b) {
                        size_t r = static_cast<size_t>(sl) * chi_L + a;
                        size_t c = static_cast<size_t>(sr) * chi_R + b;
                        const auto& z = theta[((static_cast<size_t>(sl) * 2 + sr) * chi_L + a) * chi_R + b];
                        matrix[r * cols + c] = std::complex<double>(
                            z.to_double(), static_cast<double>(z.im) / 2147483647.0);
                    }
                }
            }
        }

        SvdResult svd = compute_svd(matrix, rows, cols);

        size_t max_rank = std::min<size_t>(rows, cols);
        if (!exact_rank && max_bond_dim > 0) {
            max_rank = std::min<size_t>(max_rank, max_bond_dim);
        }
        // Keep only numerically non-zero singular values, then apply the rank cap.
        std::vector<size_t> kept;
        kept.reserve(max_rank);
        double discarded = 0.0;
        for (size_t k = 0; k < svd.s.size(); ++k) {
            double w = svd.s[k] * svd.s[k];
            if (kept.size() < max_rank && svd.s[k] > 1e-14) {
                kept.push_back(k);
            } else {
                discarded += w;
            }
        }
        last_truncation_discarded_weight = discarded;
        cumulative_discarded_weight += discarded;

        // Rescale the new local tensors by the retained weight so that repeated
        // truncation cannot drive the fixed-point singular spectrum below the
        // Q1.31 resolution and collapse the bond rank to one. The exponent is
        // -1/4 per factor: their product then has the retained tensor's
        // Frobenius norm (kept_weight^{-1/2} * sqrt(kept_weight) = 1) and every
        // factor is bounded by 1, so quantise() does not need to clamp.
        // This is a local gauge choice, not a claim that the global state norm
        // is one; sampling normalises the represented state. The discarded
        // weight above remains a per-update diagnostic, not a certified global
        // error bound.
        double kept_weight = 0.0;
        for (size_t k : kept) kept_weight += svd.s[k] * svd.s[k];
        double renorm = (kept_weight > 0.0)
                            ? std::pow(kept_weight, -0.25)
                            : 0.0;

        uint32_t rank = static_cast<uint32_t>(std::max<size_t>(1, kept.size()));
        MPSSiteTensor newL(chi_L, rank);
        MPSSiteTensor newR(rank, chi_R);
        for (uint32_t kk = 0; kk < rank; ++kk) {
            // If all singular values were numerically zero, emit a zero tensor.
            size_t k = kept.empty() ? 0 : kept[kk];
            double sigma = kept.empty() ? 0.0 : svd.s[k];
            double scale = std::sqrt(std::max(0.0, sigma)) * renorm;
            for (uint32_t sl = 0; sl < 2; ++sl) {
                for (uint32_t a = 0; a < chi_L; ++a) {
                    size_t r = static_cast<size_t>(sl) * chi_L + a;
                    std::complex<double> u = svd.u[r * svd.n + k];
                    newL.at(sl, a, kk) = quantise(u.real() * scale, u.imag() * scale);
                }
            }
            for (uint32_t sr = 0; sr < 2; ++sr) {
                for (uint32_t b = 0; b < chi_R; ++b) {
                    size_t c = static_cast<size_t>(sr) * chi_R + b;
                    std::complex<double> v = std::conj(svd.v[c * svd.n + k]);
                    newR.at(sr, kk, b) = quantise(v.real() * scale, v.imag() * scale);
                }
            }
        }

        outL = std::move(newL);
        outR = std::move(newR);
    }

    struct SvdResult {
        std::vector<double> s;                       // singular values, descending
        std::vector<std::complex<double>> u;         // m x n (columns are left vectors)
        std::vector<std::complex<double>> v;         // n x n (columns are right vectors)
        size_t m{0};
        size_t n{0};
    };

    /**
     * @brief One-sided complex Jacobi SVD: A = U diag(s) V^dagger.
     *
     * Pairs of columns of a working copy of A are rotated until they are
     * mutually orthogonal (to a relative tolerance), accumulating the same
     * rotations in V. The column norms are then the singular values and the
     * normalised columns are the left singular vectors. This yields real
     * singular values and a genuinely orthonormal U/V basis, which the previous
     * diagonalisation of A^dagger A did not; that earlier variant reconstructed
     * A but its "singular values" were not singular values, so truncation was
     * neither optimal nor correctly reported.
     */
    static SvdResult compute_svd(const std::vector<std::complex<double>>& a,
                                 size_t m, size_t n) {
        SvdResult result;
        result.m = m;
        result.n = n;

        std::vector<std::complex<double>> b = a; // m x n working copy
        result.v.assign(n * n, 0.0);
        for (size_t i = 0; i < n; ++i) result.v[i * n + i] = 1.0;

        const double tol = 1e-15;
        const double convergence = 1e-14;
        const int max_sweeps = 100;

        for (int sweep = 0; sweep < max_sweeps; ++sweep) {
            double off = 0.0;
            for (size_t p = 0; p < n; ++p) {
                for (size_t q = p + 1; q < n; ++q) {
                    double alpha = 0.0, beta = 0.0;
                    std::complex<double> gamma = 0.0;
                    for (size_t i = 0; i < m; ++i) {
                        const auto& bp = b[i * n + p];
                        const auto& bq = b[i * n + q];
                        alpha += std::norm(bp);
                        beta += std::norm(bq);
                        gamma += std::conj(bp) * bq;
                    }
                    if (alpha <= tol || beta <= tol) continue;
                    off = std::max(off, std::abs(gamma) / std::sqrt(alpha * beta));
                }
            }
            if (off < convergence) break;

            for (size_t p = 0; p < n; ++p) {
                for (size_t q = p + 1; q < n; ++q) {
                    double alpha = 0.0, beta = 0.0;
                    std::complex<double> gamma = 0.0;
                    for (size_t i = 0; i < m; ++i) {
                        const auto& bp = b[i * n + p];
                        const auto& bq = b[i * n + q];
                        alpha += std::norm(bp);
                        beta += std::norm(bq);
                        gamma += std::conj(bp) * bq;
                    }
                    if (alpha <= tol || beta <= tol) continue;
                    double g = std::abs(gamma);
                    if (g <= tol * std::sqrt(alpha * beta)) continue;

                    double phi = std::arg(gamma);
                    double tau = (beta - alpha) / (2.0 * g);
                    double t = (tau >= 0.0 ? 1.0 : -1.0) /
                               (std::abs(tau) + std::sqrt(1.0 + tau * tau));
                    double c = 1.0 / std::sqrt(1.0 + t * t);
                    double s = t * c;
                    const std::complex<double> ep = std::polar(1.0, -phi);
                    const std::complex<double> eq = std::polar(1.0, phi);

                    for (size_t i = 0; i < m; ++i) {
                        std::complex<double> bp = b[i * n + p];
                        std::complex<double> bq = b[i * n + q];
                        b[i * n + p] = c * bp - s * ep * bq;
                        b[i * n + q] = s * eq * bp + c * bq;
                    }
                    for (size_t i = 0; i < n; ++i) {
                        std::complex<double> vp = result.v[i * n + p];
                        std::complex<double> vq = result.v[i * n + q];
                        result.v[i * n + p] = c * vp - s * ep * vq;
                        result.v[i * n + q] = s * eq * vp + c * vq;
                    }
                }
            }
        }

        std::vector<std::pair<double, size_t>> order;
        order.reserve(n);
        for (size_t j = 0; j < n; ++j) {
            double norm = 0.0;
            for (size_t i = 0; i < m; ++i) norm += std::norm(b[i * n + j]);
            order.emplace_back(std::sqrt(std::max(0.0, norm)), j);
        }
        std::sort(order.begin(), order.end(),
                  [](const auto& x, const auto& y) { return x.first > y.first; });

        result.s.resize(n, 0.0);
        result.u.assign(m * n, 0.0);
        std::vector<std::complex<double>> v_sorted(n * n, 0.0);
        for (size_t k = 0; k < n; ++k) {
            size_t src = order[k].second;
            double sigma = order[k].first;
            result.s[k] = sigma;
            for (size_t i = 0; i < n; ++i) {
                v_sorted[i * n + k] = result.v[i * n + src];
            }
            if (sigma > 1e-14) {
                for (size_t i = 0; i < m; ++i) {
                    result.u[i * n + k] = b[i * n + src] / sigma;
                }
            }
        }
        result.v = std::move(v_sorted);
        return result;
    }
};

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_MPS_SIMULATOR_HPP
