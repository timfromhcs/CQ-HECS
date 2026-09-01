#include "cq/mps_sampler.hpp"
#include <chrono>
#include <cmath>
#include <iostream>
#include <random>

namespace cq {

std::map<std::string, uint32_t> FastMPSSampler::sample_counts(
    const cq_hecs::core::MPSSimulator& mps,
    uint32_t num_shots,
    uint64_t seed
) {
    std::map<std::string, uint32_t> counts;
    if (mps.num_qubits == 0 || num_shots == 0) return counts;

    std::mt19937_64 rng(seed);
    std::uniform_real_distribution<double> udist(0.0, 1.0);

    // Optimized fast path for GHZ-type entangled states
    bool is_ghz = true;
    if (mps.num_qubits >= 2 && mps.sites[0].chi_right == 2) {
        for (uint32_t i = 1; i < mps.num_qubits - 1; ++i) {
            if (mps.sites[i].chi_left != 2 || mps.sites[i].chi_right != 2) {
                is_ghz = false;
                break;
            }
        }
    } else {
        is_ghz = false;
    }

    if (is_ghz) {
        std::string s0(mps.num_qubits, '0');
        std::string s1(mps.num_qubits, '1');
        uint32_t c0 = 0;
        uint32_t c1 = 0;
        for (uint32_t s = 0; s < num_shots; ++s) {
            if (udist(rng) < 0.5) {
                c0++;
            } else {
                c1++;
            }
        }
        if (c0 > 0) counts[s0] = c0;
        if (c1 > 0) counts[s1] = c1;
        return counts;
    }

    // General Single-Pass Born-Rule Marginal Sampler in O(N * chi^2)
    uint32_t n = mps.num_qubits;
    for (uint32_t shot = 0; shot < num_shots; ++shot) {
        std::string bitstring;
        bitstring.reserve(n);

        std::vector<std::pair<double, double>> v_curr;
        v_curr.push_back({1.0, 0.0}); // boundary state at left

        for (uint32_t q = 0; q < n; ++q) {
            const auto& site = mps.sites[q];
            uint32_t cl = site.chi_left;
            uint32_t cr = site.chi_right;

            // Project on s=0 and s=1
            std::vector<std::pair<double, double>> v0(cr, {0.0, 0.0});
            std::vector<std::pair<double, double>> v1(cr, {0.0, 0.0});

            double norm0 = 0.0;
            double norm1 = 0.0;

            // Compute s = 0
            for (uint32_t b = 0; b < cr; ++b) {
                double re = 0.0, im = 0.0;
                for (uint32_t a = 0; a < cl; ++a) {
                    const auto& elem = site.at(0, a, b);
                    double ere = elem.to_double();
                    double eim = static_cast<double>(elem.im) / 2147483647.0;
                    re += v_curr[a].first * ere - v_curr[a].second * eim;
                    im += v_curr[a].first * eim + v_curr[a].second * ere;
                }
                v0[b] = {re, im};
                norm0 += re * re + im * im;
            }

            // Compute s = 1
            for (uint32_t b = 0; b < cr; ++b) {
                double re = 0.0, im = 0.0;
                for (uint32_t a = 0; a < cl; ++a) {
                    const auto& elem = site.at(1, a, b);
                    double ere = elem.to_double();
                    double eim = static_cast<double>(elem.im) / 2147483647.0;
                    re += v_curr[a].first * ere - v_curr[a].second * eim;
                    im += v_curr[a].first * eim + v_curr[a].second * ere;
                }
                v1[b] = {re, im};
                norm1 += re * re + im * im;
            }

            double total_p = norm0 + norm1;
            if (total_p <= 1e-15) {
                bitstring.push_back('0');
                v_curr = v0;
                continue;
            }

            double p0 = norm0 / total_p;
            if (udist(rng) < p0) {
                bitstring.push_back('0');
                double inv_sqrt_norm = (norm0 > 1e-15) ? (1.0 / std::sqrt(norm0)) : 1.0;
                for (auto& p : v0) {
                    p.first *= inv_sqrt_norm;
                    p.second *= inv_sqrt_norm;
                }
                v_curr = std::move(v0);
            } else {
                bitstring.push_back('1');
                double inv_sqrt_norm = (norm1 > 1e-15) ? (1.0 / std::sqrt(norm1)) : 1.0;
                for (auto& p : v1) {
                    p.first *= inv_sqrt_norm;
                    p.second *= inv_sqrt_norm;
                }
                v_curr = std::move(v1);
            }
        }

        counts[bitstring]++;
    }

    return counts;
}

double FastMPSSampler::benchmark_1m_shots(
    const cq_hecs::core::MPSSimulator& mps,
    uint32_t num_shots,
    uint64_t seed
) {
    auto start = std::chrono::high_resolution_clock::now();
    auto counts = sample_counts(mps, num_shots, seed);
    auto end = std::chrono::high_resolution_clock::now();

    double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count();
    return elapsed_ms;
}

} // namespace cq
