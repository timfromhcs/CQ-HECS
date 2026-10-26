#ifndef CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP
#define CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP

#include "types.hpp"
#include "cordic.hpp"
#include <vector>
#include <map>
#include <string>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cassert>
#include <cstddef>
#include <limits>
#include <random>
#include <stdexcept>

namespace cq_hecs {
namespace core {

/**
 * @brief Bit-exact Q1.31 Statevector Simulator for high-precision validation.
 *
 * State evolution is performed in Q1.31 fixed point. Born-rule sampling and
 * post-measurement renormalisation necessarily evaluate probabilities in
 * double precision and convert the surviving amplitudes back to Q1.31; that
 * conversion is the only floating-point step and is documented here instead
 * of being hidden behind a "zero float" claim.
 *
 * The supported width is bounded so that the dense state allocation is
 * checked before any shift or multiplication can overflow.
 */
class StateVectorSimulator {
public:
    /// 2^28 amplitudes * 8 bytes = 2 GiB. Larger widths are rejected up front.
    static constexpr uint32_t MAX_SUPPORTED_QUBITS = 28;

    uint32_t num_qubits;
    size_t dim{1};
    std::vector<ComplexQ31> state;

    explicit StateVectorSimulator(uint32_t n) : num_qubits(n) {
        if (n >= static_cast<uint32_t>(sizeof(size_t) * 8) || n > MAX_SUPPORTED_QUBITS) {
            throw std::invalid_argument(
                "StateVectorSimulator: qubit count " + std::to_string(n) +
                " exceeds the supported width of " + std::to_string(MAX_SUPPORTED_QUBITS) +
                " (dense state allocation rejected before shift/allocation)");
        }
        dim = size_t(1) << n;
        reset();
    }

    void reset() {
        state.assign(dim, ComplexQ31::zero());
        state[0] = ComplexQ31::one(); // |0...0>
    }

    /// Throws std::out_of_range for a qubit index that cannot index this state.
    void check_qubit(uint32_t q) const {
        if (q >= num_qubits) {
            throw std::out_of_range(
                "StateVectorSimulator: qubit index " + std::to_string(q) +
                " is out of range for " + std::to_string(num_qubits) + " qubits");
        }
    }

    /// Total probability represented by the stored amplitudes (diagnostic).
    double total_probability() const {
        double total = 0.0;
        for (const auto& amp : state) {
            total += amplitude_probability(amp);
        }
        return total;
    }

    /// Probability of measuring |1> on @p target, normalised by the state norm.
    double probability_of_one(uint32_t target) const {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        double p1 = 0.0;
        double total = 0.0;
        for (size_t i = 0; i < dim; ++i) {
            double p = amplitude_probability(state[i]);
            total += p;
            if (i & bit) p1 += p;
        }
        if (!(total > 0.0) || !std::isfinite(total)) {
            throw std::runtime_error("StateVectorSimulator: state has no finite probability mass");
        }
        return std::clamp(p1 / total, 0.0, 1.0);
    }

    /// Probability |amplitude|^2 with the Q1.31 scale used by to_double().
    static double amplitude_probability(const ComplexQ31& amp) {
        double re = amp.to_double();
        double im = static_cast<double>(amp.im) / 2147483647.0;
        return re * re + im * im;
    }

    void apply_h(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                size_t idx0 = i + j;
                size_t idx1 = idx0 + bit;
                ComplexQ31 a0 = state[idx0];
                ComplexQ31 a1 = state[idx1];

                int64_t sum_re = (static_cast<int64_t>(a0.re) + a1.re) * ComplexQ31::INV_SQRT2_VAL >> 31;
                int64_t sum_im = (static_cast<int64_t>(a0.im) + a1.im) * ComplexQ31::INV_SQRT2_VAL >> 31;
                int64_t diff_re = (static_cast<int64_t>(a0.re) - a1.re) * ComplexQ31::INV_SQRT2_VAL >> 31;
                int64_t diff_im = (static_cast<int64_t>(a0.im) - a1.im) * ComplexQ31::INV_SQRT2_VAL >> 31;

                if (sum_re > 0x7FFFFFFFLL) sum_re = 0x7FFFFFFFLL;
                if (sum_re < -0x80000000LL) sum_re = -0x80000000LL;
                if (sum_im > 0x7FFFFFFFLL) sum_im = 0x7FFFFFFFLL;
                if (sum_im < -0x80000000LL) sum_im = -0x80000000LL;
                if (diff_re > 0x7FFFFFFFLL) diff_re = 0x7FFFFFFFLL;
                if (diff_re < -0x80000000LL) diff_re = -0x80000000LL;
                if (diff_im > 0x7FFFFFFFLL) diff_im = 0x7FFFFFFFLL;
                if (diff_im < -0x80000000LL) diff_im = -0x80000000LL;

                state[idx0] = ComplexQ31{static_cast<int32_t>(sum_re), static_cast<int32_t>(sum_im)};
                state[idx1] = ComplexQ31{static_cast<int32_t>(diff_re), static_cast<int32_t>(diff_im)};
            }
        }
    }

    void apply_x(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                std::swap(state[i + j], state[i + j + bit]);
            }
        }
    }

    void apply_z(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                size_t idx1 = i + j + bit;
                state[idx1] = ComplexQ31{-state[idx1].re, -state[idx1].im};
            }
        }
    }

    void apply_y(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                size_t idx0 = i + j;
                size_t idx1 = idx0 + bit;
                ComplexQ31 a0 = state[idx0];
                ComplexQ31 a1 = state[idx1];
                // Y = [[0, -i], [i, 0]]
                state[idx0] = ComplexQ31{a1.im, -a1.re};
                state[idx1] = ComplexQ31{-a0.im, a0.re};
            }
        }
    }

    void apply_rz(uint32_t target, uint32_t phase) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        uint32_t half = phase >> 1;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                size_t idx0 = i + j;
                size_t idx1 = idx0 + bit;
                state[idx0] = cordic_rotate(state[idx0], 0u - half);
                state[idx1] = cordic_rotate(state[idx1], half);
            }
        }
    }

    void apply_cnot(uint32_t ctrl, uint32_t tgt) {
        check_qubit(ctrl);
        check_qubit(tgt);
        size_t ctrl_bit = size_t(1) << ctrl;
        size_t tgt_bit = size_t(1) << tgt;

        for (size_t i = 0; i < dim; ++i) {
            if ((i & ctrl_bit) != 0 && (i & tgt_bit) == 0) {
                size_t partner = i | tgt_bit;
                std::swap(state[i], state[partner]);
            }
        }
    }

    void apply_cphase(uint32_t ctrl, uint32_t tgt, uint32_t phase) {
        check_qubit(ctrl);
        check_qubit(tgt);
        size_t ctrl_bit = size_t(1) << ctrl;
        size_t tgt_bit = size_t(1) << tgt;

        for (size_t i = 0; i < dim; ++i) {
            if ((i & ctrl_bit) != 0 && (i & tgt_bit) != 0) {
                state[i] = cordic_rotate(state[i], phase);
            }
        }
    }

    void apply_crz(uint32_t ctrl, uint32_t tgt, uint32_t phase) {
        check_qubit(ctrl);
        check_qubit(tgt);
        size_t ctrl_bit = size_t(1) << ctrl;
        size_t tgt_bit = size_t(1) << tgt;
        uint32_t half = phase >> 1;

        for (size_t i = 0; i < dim; ++i) {
            if ((i & ctrl_bit) != 0) {
                if ((i & tgt_bit) == 0) {
                    state[i] = cordic_rotate(state[i], 0u - half);
                } else {
                    state[i] = cordic_rotate(state[i], half);
                }
            }
        }
    }

    void apply_swap(uint32_t q1, uint32_t q2) {
        check_qubit(q1);
        check_qubit(q2);
        if (q1 == q2) return;
        size_t b1 = size_t(1) << q1;
        size_t b2 = size_t(1) << q2;

        for (size_t i = 0; i < dim; ++i) {
            bool bit1 = (i & b1) != 0;
            bool bit2 = (i & b2) != 0;
            if (bit1 && !bit2) {
                size_t partner = (i & ~b1) | b2;
                std::swap(state[i], state[partner]);
            }
        }
    }

    void apply_cx(uint32_t ctrl, uint32_t tgt) {
        apply_cnot(ctrl, tgt);
    }

    void apply_s(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; ++i) {
            if (i & bit) {
                int32_t r = state[i].re;
                int32_t m = state[i].im;
                state[i] = ComplexQ31{-m, r};
            }
        }
    }

    void apply_sdg(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; ++i) {
            if (i & bit) {
                int32_t r = state[i].re;
                int32_t m = state[i].im;
                state[i] = ComplexQ31{m, -r};
            }
        }
    }

    void apply_t(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; ++i) {
            if (i & bit) {
                state[i] = cordic_rotate(state[i], 0x20000000u);
            }
        }
    }

    void apply_tdg(uint32_t target) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; ++i) {
            if (i & bit) {
                state[i] = cordic_rotate(state[i], 0xE0000000u);
            }
        }
    }

    /**
     * @brief Born-rule measurement of @p target in the requested RNG stream.
     *
     * Draws an outcome from the normalised state distribution, projects the
     * state onto that outcome and renormalises the surviving amplitudes.
     * The seed/stream is caller-controlled so repeated runs are reproducible.
     */
    uint8_t measure(uint32_t target, std::mt19937_64& rng) {
        double p1 = probability_of_one(target);
        std::uniform_real_distribution<double> draw(0.0, 1.0);
        uint8_t outcome = (draw(rng) < p1) ? uint8_t{1} : uint8_t{0};
        double keep = outcome ? p1 : (1.0 - p1);
        if (!(keep > 0.0)) {
            throw std::runtime_error(
                "StateVectorSimulator: sampled a zero-probability measurement outcome");
        }
        project_and_renormalise(target, outcome, keep);
        return outcome;
    }

    /// Convenience overload using a process-local non-deterministic stream.
    uint8_t measure(uint32_t target) {
        static thread_local std::mt19937_64 rng{std::random_device{}()};
        return measure(target, rng);
    }

    /**
     * @brief Sample @p shots basis states from the Born-rule distribution.
     *
     * The returned bitstrings use the same convention as the rest of the
     * native API: qubit 0 is the least significant bit and is printed last
     * (leftmost character = highest-numbered qubit).
     */
    std::map<std::string, uint32_t> sample_counts(
        uint32_t shots, uint64_t seed = 1337) const {
        std::map<std::string, uint32_t> counts;
        if (shots == 0) return counts;
        if (num_qubits == 0) {
            counts[std::string()] = shots;
            return counts;
        }

        std::vector<double> cumulative(dim, 0.0);
        double total = 0.0;
        for (size_t i = 0; i < dim; ++i) {
            double p = amplitude_probability(state[i]);
            if (!std::isfinite(p) || p < 0.0) {
                throw std::runtime_error(
                    "StateVectorSimulator: non-finite or negative probability during sampling");
            }
            total += p;
            cumulative[i] = total;
        }
        if (!(total > 0.0) || !std::isfinite(total)) {
            throw std::runtime_error("StateVectorSimulator: cannot sample a zero-norm state");
        }

        std::mt19937_64 rng(seed);
        std::uniform_real_distribution<double> draw(0.0, total);
        for (uint32_t s = 0; s < shots; ++s) {
            double u = draw(rng);
            auto it = std::upper_bound(cumulative.begin(), cumulative.end(), u);
            size_t outcome = static_cast<size_t>(it - cumulative.begin());
            if (outcome >= dim) outcome = dim - 1;

            std::string bits(num_qubits, '0');
            for (uint32_t q = 0; q < num_qubits; ++q) {
                if ((outcome >> q) & 1) bits[num_qubits - 1 - q] = '1';
            }
            counts[bits]++;
        }
        return counts;
    }

    double fidelity_with_ground() const {
        double re = state[0].to_double();
        double im = static_cast<double>(state[0].im) / 2147483647.0;
        return re * re + im * im;
    }

    /**
     * @brief Project onto @p outcome of @p target and renormalise the survivors.
     * @param probability Probability of the kept outcome before projection.
     */
    void project_and_renormalise(uint32_t target, uint8_t outcome, double probability) {
        check_qubit(target);
        size_t bit = size_t(1) << target;
        double scale = 1.0 / std::sqrt(probability);
        for (size_t i = 0; i < dim; ++i) {
            bool is_one = (i & bit) != 0;
            if ((is_one ? 1 : 0) != static_cast<int>(outcome)) {
                state[i] = ComplexQ31::zero();
            } else {
                double re = static_cast<double>(state[i].re) * scale;
                double im = static_cast<double>(state[i].im) * scale;
                re = std::clamp(re, -2147483648.0, 2147483647.0);
                im = std::clamp(im, -2147483648.0, 2147483647.0);
                state[i] = ComplexQ31{
                    static_cast<int32_t>(std::llround(re)),
                    static_cast<int32_t>(std::llround(im))};
            }
        }
    }

    /**
     * @brief Quantum Fourier Transform (QFT) on n qubits.
     */
    void apply_qft(uint32_t n) {
        if (n > num_qubits) {
            throw std::out_of_range("StateVectorSimulator: QFT width exceeds the number of qubits");
        }
        for (uint32_t i = 0; i < n; ++i) {
            apply_h(i);
            for (uint32_t j = i + 1; j < n; ++j) {
                // Angle = 2*pi / 2^(j - i + 1)
                // In Z_{2^32}: 2^32 / 2^(j - i + 1) = 1 << (32 - (j - i + 1))
                uint32_t k = j - i + 1;
                uint32_t angle = (k < 32) ? (1u << (32 - k)) : 0u;
                apply_cphase(j, i, angle);
            }
        }
        // Bit-reversal SWAPs
        for (uint32_t i = 0; i < n / 2; ++i) {
            apply_swap(i, n - 1 - i);
        }
    }

    /**
     * @brief Inverse Quantum Fourier Transform (IQFT) on n qubits.
     */
    void apply_iqft(uint32_t n) {
        if (n > num_qubits) {
            throw std::out_of_range("StateVectorSimulator: IQFT width exceeds the number of qubits");
        }
        // Reverse bit-reversal SWAPs
        for (int i = int(n / 2) - 1; i >= 0; --i) {
            apply_swap(i, n - 1 - i);
        }
        // Inverse gate sequence in reverse order
        for (int i = int(n) - 1; i >= 0; --i) {
            for (int j = int(n) - 1; j > i; --j) {
                uint32_t k = j - i + 1;
                uint32_t angle = (k < 32) ? (1u << (32 - k)) : 0u;
                apply_cphase(j, i, 0u - angle);
            }
            apply_h(i);
        }
    }

    /**
     * @brief Computes overlap fidelity |<this|other>|^2 against reference state.
     */
    double compute_fidelity(const StateVectorSimulator& other) const {
        if (dim != other.dim) {
            throw std::invalid_argument("StateVectorSimulator: fidelity requires equal dimensions");
        }
        int64_t sum_re = 0;
        int64_t sum_im = 0;

        for (size_t i = 0; i < dim; ++i) {
            ComplexQ31 a = state[i];
            ComplexQ31 b = other.state[i];
            // conj(a) * b = (a.re - i a.im)(b.re + i b.im) = (a.re*b.re + a.im*b.im) + i(a.re*b.im - a.im*b.re)
            int64_t re_term = (int64_t(a.re) * b.re + int64_t(a.im) * b.im) >> 31;
            int64_t im_term = (int64_t(a.re) * b.im - int64_t(a.im) * b.re) >> 31;
            sum_re += re_term;
            sum_im += im_term;
        }

        double re = double(sum_re) / double(ComplexQ31::ONE_VAL);
        double im = double(sum_im) / double(ComplexQ31::ONE_VAL);
        double fid = re * re + im * im;
        return (fid > 1.0) ? 1.0 : fid;
    }
};

using StatevectorSimulator = StateVectorSimulator;

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP
