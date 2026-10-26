#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cmath>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>

#include "cq_hecs/core/statevector_simulator.hpp"

using cq_hecs::core::ComplexQ31;
using cq_hecs::core::StateVectorSimulator;

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "FAIL: " << message << std::endl;
        std::abort();
    }
}

void require_throws_invalid_width(uint32_t n) {
    bool thrown = false;
    try {
        StateVectorSimulator sim(n);
        (void)sim;
    } catch (const std::exception&) {
        thrown = true;
    }
    require(thrown, "unsupported width must be rejected before allocation");
}

void check_shots_sum(const std::map<std::string, uint32_t>& counts, uint32_t shots) {
    uint64_t sum = 0;
    for (const auto& kv : counts) sum += kv.second;
    require(sum == shots, "counts must sum exactly to the requested shots");
}

void test_basis_states() {
    StateVectorSimulator zero(1);
    auto zeros = zero.sample_counts(2000, 7);
    require(zeros.size() == 1 && zeros.at("0") == 2000, "|0> must always sample 0");

    StateVectorSimulator one(1);
    one.apply_x(0);
    auto ones = one.sample_counts(2000, 7);
    require(ones.size() == 1 && ones.at("1") == 2000, "|1> must always sample 1");
}

void test_superposition_distribution() {
    StateVectorSimulator plus(1);
    plus.apply_h(0);
    const uint32_t shots = 40000;
    auto counts = plus.sample_counts(shots, 12345);
    check_shots_sum(counts, shots);
    require(counts.count("0") == 1 && counts.count("1") == 1,
            "|+> must produce both outcomes, not only the most likely one");

    double observed = static_cast<double>(counts.at("0")) / shots;
    double sigma = std::sqrt(0.25 / shots);
    require(std::abs(observed - 0.5) < 5.0 * sigma,
            "|+> zero-frequency must be statistically consistent with 0.5");
}

void test_asymmetric_state() {
    const uint32_t shots = 60000;
    StateVectorSimulator sim(1);
    sim.state[0] = ComplexQ31{static_cast<int32_t>(std::llround(std::sqrt(0.8) * 2147483647.0)), 0};
    sim.state[1] = ComplexQ31{static_cast<int32_t>(std::llround(std::sqrt(0.2) * 2147483647.0)), 0};
    auto counts = sim.sample_counts(shots, 2024);
    check_shots_sum(counts, shots);

    double observed1 = static_cast<double>(counts.at("1")) / shots;
    double sigma = std::sqrt(0.8 * 0.2 / shots);
    require(std::abs(observed1 - 0.2) < 5.0 * sigma,
            "asymmetric 0.8/0.2 state must sample the 0.2 outcome at the correct rate");
    require(counts.at("1") > 0, "the less likely outcome must still occur");
}

void test_bell_state() {
    StateVectorSimulator bell(2);
    bell.apply_h(0);
    bell.apply_cnot(0, 1);
    auto counts = bell.sample_counts(20000, 9);
    check_shots_sum(counts, 20000);
    require(counts.size() == 2, "Bell state must have exactly two support outcomes");
    require(counts.count("00") == 1 && counts.count("11") == 1,
            "Bell state must only sample 00 and 11");
}

void test_measurement_collapses_and_renormalises() {
    bool saw_zero = false;
    bool saw_one = false;
    for (uint64_t seed = 0; seed < 64; ++seed) {
        StateVectorSimulator sim(1);
        sim.apply_h(0);
        std::mt19937_64 rng(seed);
        uint8_t outcome = sim.measure(0, rng);
        if (outcome == 0) saw_zero = true; else saw_one = true;

        double total = sim.total_probability();
        require(std::abs(total - 1.0) < 1e-9, "post-measurement state must be normalised");
        double p1 = sim.probability_of_one(0);
        require(std::abs(p1 - static_cast<double>(outcome)) < 1e-9,
                "post-measurement state must be the measured eigenstate");
    }
    require(saw_zero && saw_one, "repeated measurements of |+> must produce both outcomes");
}

void test_endianness_and_shots() {
    StateVectorSimulator sim(3);
    sim.apply_x(1); // qubit 0 is the least significant bit and printed rightmost
    auto counts = sim.sample_counts(16, 1);
    require(counts.size() == 1 && counts.count("010") == 1,
            "bitstring convention must map qubit 0 to the rightmost character");
}

void test_seed_reproducibility() {
    StateVectorSimulator sim(2);
    sim.apply_h(0);
    sim.apply_h(1);
    auto a = sim.sample_counts(1000, 777);
    auto b = sim.sample_counts(1000, 777);
    require(a == b, "same seed and state must reproduce the same counts");
}

void test_width_and_index_validation() {
    require_throws_invalid_width(29);
    require_throws_invalid_width(63);
    require_throws_invalid_width(64);

    StateVectorSimulator zero_width(0);
    require(zero_width.dim == 1, "width 0 must represent the single |0> amplitude");
    auto counts = zero_width.sample_counts(5, 1);
    check_shots_sum(counts, 5);
    require(counts.size() == 1 && counts.begin()->first.empty(),
            "width 0 has the empty bitstring as its only outcome");

    bool thrown = false;
    try { zero_width.apply_h(0); } catch (const std::out_of_range&) { thrown = true; }
    require(thrown, "gate on an out-of-range qubit must throw");

    StateVectorSimulator two(2);
    thrown = false;
    try { two.apply_cnot(0, 2); } catch (const std::out_of_range&) { thrown = true; }
    require(thrown, "CNOT with an out-of-range target must throw");
}

void test_zero_shot_sampling() {
    StateVectorSimulator sim(1);
    auto counts = sim.sample_counts(0);
    require(counts.empty(), "zero shots must return an empty count map");
}

} // namespace

int main() {
    std::cout << "[TEST] StateVectorSimulator Born-rule sampling & width contract\n";
    test_basis_states();
    test_superposition_distribution();
    test_asymmetric_state();
    test_bell_state();
    test_measurement_collapses_and_renormalises();
    test_endianness_and_shots();
    test_seed_reproducibility();
    test_width_and_index_validation();
    test_zero_shot_sampling();
    std::cout << ">>> PASS: StateVectorSimulator sampling contract verified\n";
    return 0;
}
