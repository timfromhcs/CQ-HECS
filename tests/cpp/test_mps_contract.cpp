#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cmath>
#include <complex>
#include <iostream>
#include <map>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "cq_hecs/core/mps_simulator.hpp"
#include "cq_hecs/core/statevector_simulator.hpp"

using cq_hecs::core::MPSSimulator;
using cq_hecs::core::MPSSiteTensor;
using cq_hecs::core::StateVectorSimulator;

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::abort();
    }
}

double dense_overlap(const std::vector<std::complex<double>>& a,
                     const StateVectorSimulator& ref) {
    require(a.size() == ref.dim, "dense state dimensions must agree");
    std::complex<double> acc(0.0, 0.0);
    double na = 0.0;
    double nb = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        std::complex<double> b(ref.state[i].to_double(),
                               static_cast<double>(ref.state[i].im) / 2147483647.0);
        acc += std::conj(a[i]) * b;
        na += std::norm(a[i]);
        nb += std::norm(b);
    }
    if (na <= 0.0 || nb <= 0.0) return 0.0;
    return std::norm(acc) / (na * nb);
}

void require_close_to_dense(const MPSSimulator& mps, const StateVectorSimulator& ref,
                            double tolerance, const char* message) {
    double fidelity = dense_overlap(mps.to_statevector(), ref);
    if (fidelity < tolerance) {
        std::cerr << "  overlap fidelity = " << fidelity << " (required " << tolerance << ")\n";
    }
    require(fidelity >= tolerance, message);
}

double vector_overlap(const std::vector<std::complex<double>>& a,
                      const std::vector<std::complex<double>>& b) {
    require(a.size() == b.size(), "dense vectors must have equal length");
    std::complex<double> acc(0.0, 0.0);
    double na = 0.0;
    double nb = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        acc += std::conj(a[i]) * b[i];
        na += std::norm(a[i]);
        nb += std::norm(b[i]);
    }
    if (na <= 0.0 || nb <= 0.0) return 0.0;
    return std::norm(acc) / (na * nb);
}

void check_shots_sum(const std::map<std::string, uint32_t>& counts, uint32_t shots) {
    uint64_t sum = 0;
    for (const auto& kv : counts) sum += kv.second;
    require(sum == shots, "counts must sum exactly to the requested shots");
}

void test_single_qubit_gates_against_dense() {
    struct Gate { int type; };
    const Gate gates[] = {{1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}};
    for (const auto& gate : gates) {
        MPSSimulator mps(2, 16);
        StateVectorSimulator ref(2);
        mps.apply_1q_gate(0, gate.type);
        switch (gate.type) {
            case 1: ref.apply_h(0); break;
            case 2: ref.apply_x(0); break;
            case 3: ref.apply_y(0); break;
            case 4: ref.apply_z(0); break;
            case 5: ref.apply_s(0); break;
            case 6: ref.apply_sdg(0); break;
            case 7: ref.apply_t(0); break;
            case 8: ref.apply_tdg(0); break;
            default: break;
        }
        require_close_to_dense(mps, ref, 0.999999, "single-qubit MPS gate must match dense state");
    }
}

void test_bell_state_and_sampling() {
    MPSSimulator mps(2, 16);
    StateVectorSimulator ref(2);
    mps.apply_h(0); ref.apply_h(0);
    mps.apply_cx(0, 1); ref.apply_cnot(0, 1);
    require_close_to_dense(mps, ref, 0.999999, "Bell state MPS update must match dense state");

    auto counts = mps.sample_counts(20000, 5);
    check_shots_sum(counts, 20000);
    require(counts.size() == 2 && counts.count("00") == 1 && counts.count("11") == 1,
            "Bell sampling must only produce 00 and 11");
}

void test_non_adjacent_cnot() {
    MPSSimulator mps(3, 16);
    StateVectorSimulator ref(3);
    mps.apply_h(0); ref.apply_h(0);
    mps.apply_cx(0, 2); ref.apply_cnot(0, 2);
    mps.apply_h(2); ref.apply_h(2);
    require_close_to_dense(mps, ref, 0.999999,
                           "non-adjacent CNOT via SWAP routing must match dense state");
}

void test_truncation_is_reported() {
    MPSSimulator mps(2, 1); // cap below the Bell rank
    mps.apply_h(0);
    mps.apply_cx(0, 1);
    require(mps.last_truncation_discarded_weight > 0.4,
            "rank truncation must be reported as discarded weight");
    auto counts = mps.sample_counts(1000, 1);
    check_shots_sum(counts, 1000);
}

void test_truncation_matches_optimal_svd() {
    // A 2-qubit state whose two-site tensor is
    //   A = [[1/sqrt(2), i/sqrt(2)], [0, 1/sqrt(2)]]
    // after a CNOT. Its squared singular values are (3 +/- sqrt(5))/4, so a
    // bond cap of one must discard exactly (3 - sqrt(5))/4 and retain the
    // dominant rank-1 factor. A fake "SVD" that merely reconstructs the tensor
    // reports a different discarded weight and a worse approximation.
    MPSSimulator mps(2, 1);
    mps.sites[0] = MPSSiteTensor(1, 2);
    mps.sites[1] = MPSSiteTensor(2, 1);
    const auto h = cq_hecs::core::ComplexQ31::inv_sqrt2();
    const cq_hecs::core::ComplexQ31 zero = cq_hecs::core::ComplexQ31::zero();
    const cq_hecs::core::ComplexQ31 ih{0, h.re};
    mps.sites[0].at(0, 0, 0) = h;   // C00
    mps.sites[0].at(0, 0, 1) = ih;  // C01
    mps.sites[0].at(1, 0, 0) = h;   // C10
    mps.sites[0].at(1, 0, 1) = zero; // C11
    mps.sites[1].at(0, 0, 0) = cq_hecs::core::ComplexQ31::one();
    mps.sites[1].at(1, 1, 0) = cq_hecs::core::ComplexQ31::one();

    mps.apply_cnot_adjacent(0, 1);

    const double root5 = std::sqrt(5.0);
    const double expected_discarded = (3.0 - root5) / 4.0;
    const double expected_fidelity = (3.0 + root5) / 6.0;
    require(std::abs(mps.last_truncation_discarded_weight - expected_discarded) < 1e-6,
            "truncation must report the true discarded singular-value weight");
    require(mps.sites[0].chi_right == 1 && mps.sites[1].chi_left == 1,
            "bond cap one must produce a rank-one MPS");

    // Basis order is {|00>, |10>, |01>, |11>} with qubit 0 as the LSB.
    const std::vector<std::complex<double>> original{
        std::complex<double>(h.to_double(), 0.0),
        std::complex<double>(0.0, 0.0),
        std::complex<double>(0.0, h.to_double()),
        std::complex<double>(h.to_double(), 0.0)};
    const double fidelity = vector_overlap(mps.to_statevector(), original);
    if (std::abs(fidelity - expected_fidelity) >= 1e-6) {
        std::cerr << "  rank-one fidelity = " << fidelity
                  << " (expected " << expected_fidelity << ")\n";
    }
    require(std::abs(fidelity - expected_fidelity) < 1e-6,
            "rank-one truncation must retain the dominant singular subspace");
}

void test_repeated_truncation_keeps_rank_and_sampling_valid() {
    // Heavy truncation at every step must not drive the fixed-point singular
    // spectrum below resolution and collapse the state to rank one.
    const uint32_t n = 6;
    MPSSimulator mps(n, 2); // cap far below the entangling workload's rank
    for (int layer = 0; layer < 12; ++layer) {
        for (uint32_t q = 0; q < n; ++q) {
            mps.apply_1q_gate(q, ((q + static_cast<uint32_t>(layer)) % 2 == 0) ? 1 : 7);
        }
        for (uint32_t q = 0; q + 1 < n; ++q) {
            mps.apply_cx(q, q + 1);
        }
    }
    require(mps.cumulative_discarded_weight > 0.0,
            "the workload must exercise rank truncation");
    uint32_t max_bond = 1;
    for (const auto& site : mps.sites) {
        max_bond = std::max(max_bond, std::max(site.chi_left, site.chi_right));
    }
    require(max_bond >= 2,
            "repeated truncation must not collapse the MPS bond rank to one");
    auto counts = mps.sample_counts(2000, 9);
    check_shots_sum(counts, 2000);
}

void test_sampling_non_ghz_bond_two() {
    // GHZ on qubits 0/1 tensored with |+> on qubit 2. The MPS has bond
    // dimension two but is not the canonical GHZ state, so the sampler must
    // use the generic environment path.
    MPSSimulator mps(3, 16);
    mps.apply_h(0);
    mps.apply_cx(0, 1);
    mps.apply_h(2);
    require(!mps.is_ghz_state(), "state must not be classified as GHZ");

    auto counts = mps.sample_counts(40000, 77);
    check_shots_sum(counts, 40000);
    require(counts.size() == 4, "GHZ tensor |+> must have four support outcomes");
    for (const char* expected : {"000", "100", "011", "111"}) {
        require(counts.count(expected) == 1, "support outcome is missing");
        double observed = static_cast<double>(counts.at(expected)) / 40000.0;
        require(std::abs(observed - 0.25) < 0.02,
                "each support outcome must occur with probability 0.25");
    }
}

void test_asymmetric_sampling() {
    MPSSimulator mps(1, 16);
    mps.sites[0].at(0, 0, 0) = cq_hecs::core::ComplexQ31{
        static_cast<int32_t>(std::llround(std::sqrt(0.8) * 2147483647.0)), 0};
    mps.sites[0].at(1, 0, 0) = cq_hecs::core::ComplexQ31{
        static_cast<int32_t>(std::llround(std::sqrt(0.2) * 2147483647.0)), 0};

    auto counts = mps.sample_counts(50000, 11);
    check_shots_sum(counts, 50000);
    double observed = static_cast<double>(counts.at("1")) / 50000.0;
    double sigma = std::sqrt(0.8 * 0.2 / 50000.0);
    require(std::abs(observed - 0.2) < 5.0 * sigma,
            "MPS sampler must respect the represented 0.8/0.2 distribution");
}

void test_random_circuit_differential() {
    const uint32_t n = 4;
    MPSSimulator mps(n, 16);
    StateVectorSimulator ref(n);
    std::mt19937 rng(20261026);
    const int gates[] = {1, 2, 4, 5, 7, 8};

    for (int step = 0; step < 24; ++step) {
        uint32_t q = rng() % n;
        int gate = gates[rng() % 6];
        mps.apply_1q_gate(q, gate);
        switch (gate) {
            case 1: ref.apply_h(q); break;
            case 2: ref.apply_x(q); break;
            case 4: ref.apply_z(q); break;
            case 5: ref.apply_s(q); break;
            case 7: ref.apply_t(q); break;
            case 8: ref.apply_tdg(q); break;
            default: break;
        }
        if (step % 4 == 3) {
            uint32_t c = rng() % n;
            uint32_t t = (c + 1 + (rng() % (n - 1))) % n;
            if (c == t) continue;
            mps.apply_cx(c, t);
            ref.apply_cnot(c, t);
        }
    }
    require_close_to_dense(mps, ref, 0.999,
                           "random small circuit MPS evolution must match dense state");
}

void test_error_paths() {
    MPSSimulator mps(2, 16);
    bool thrown = false;
    try { mps.apply_1q_gate(2, 1); } catch (const std::out_of_range&) { thrown = true; }
    require(thrown, "out-of-range qubit must throw");

    thrown = false;
    try { mps.apply_1q_gate(0, 99); } catch (const std::invalid_argument&) { thrown = true; }
    require(thrown, "unknown gate type must throw");

    thrown = false;
    try { mps.apply_cnot_adjacent(0, 1); mps.apply_cnot_adjacent(0, 2); }
    catch (const std::exception&) { thrown = true; }
    require(thrown, "non-adjacent apply_cnot_adjacent must throw");

    thrown = false;
    try { mps.apply_cx(1, 1); } catch (const std::invalid_argument&) { thrown = true; }
    require(thrown, "CNOT with equal control/target must throw");

    thrown = false;
    try { mps.measure_ghz_parity(10); } catch (const std::logic_error&) { thrown = true; }
    require(thrown, "GHZ-only sampler must reject a non-GHZ state");
}

void test_ghz_300_parity() {
    MPSSimulator mps(300, 16);
    mps.create_ghz();
    require(mps.is_ghz_state(), "create_ghz must produce the canonical GHZ state");
    auto [zeros, ones, errors] = mps.sample_ghz_parity(50000, 42);
    require(errors == 0, "GHZ parity must have no non-parity outcomes");
    require(zeros + ones == 50000, "GHZ parity shots must sum to the requested count");

    auto counts = mps.sample_counts(2000, 3);
    check_shots_sum(counts, 2000);
    require(counts.size() == 2, "300-qubit GHZ sampling must only produce all-0/all-1");
}

} // namespace

void test_bond_growth() {
    MPSSimulator mps(4, 16);
    mps.apply_1q_gate(0, 1);
    mps.apply_cx(0, 1);
    mps.apply_1q_gate(1, 7);
    mps.apply_1q_gate(2, 1);
    mps.apply_cx(2, 3);
    mps.apply_1q_gate(3, 7);
    mps.apply_cx(1, 2);
    require(mps.sites[1].chi_right >= 2, "bond dimension must grow under entangling gates");
    require(mps.sites[2].chi_left >= 2, "shared bond must grow under entangling gates");
}

void test_bond_saturation_pattern() {
    const uint32_t n = 8;
    MPSSimulator mps(n, 16);
    for (int layer = 0; layer < 5; ++layer) {
        for (uint32_t q = 0; q + 1 < n; q += 2) {
            mps.apply_1q_gate(q, 1);
            mps.apply_cx(q, q + 1);
            mps.apply_1q_gate(q + 1, 7);
        }
        for (uint32_t q = 1; q + 1 < n; q += 2) {
            mps.apply_cx(q, q + 1);
            mps.apply_1q_gate(q, 9, 0x12345678u);
        }
    }
    require(mps.get_memory_mb() > 0.001, "entangled state must retain tensor memory");
    require(mps.sites[3].chi_right >= 4, "entangling layers must grow the bond dimension");
}

int main() {
    std::cout << "[TEST] MPS two-site update, sampling and failure contract\n";
    test_single_qubit_gates_against_dense();
    test_bell_state_and_sampling();
    test_bond_growth();
    test_bond_saturation_pattern();
    test_non_adjacent_cnot();
    test_truncation_is_reported();
    test_truncation_matches_optimal_svd();
    test_repeated_truncation_keeps_rank_and_sampling_valid();
    test_sampling_non_ghz_bond_two();
    test_asymmetric_sampling();
    test_random_circuit_differential();
    test_error_paths();
    test_ghz_300_parity();
    std::cout << ">>> PASS: MPS correctness contract verified\n";
    return 0;
}
