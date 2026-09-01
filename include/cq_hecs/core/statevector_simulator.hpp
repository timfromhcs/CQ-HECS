#ifndef CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP
#define CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP

#include "types.hpp"
#include "cordic.hpp"
#include <vector>
#include <cmath>
#include <algorithm>
#include <cstdint>
#include <cassert>

namespace cq_hecs {
namespace core {

/**
 * @brief Bit-exact Q1.31 Statevector Simulator for high-precision validation.
 * Guaranteed zero floating-point arithmetic throughout state evolution.
 */
class StateVectorSimulator {
public:
    uint32_t num_qubits;
    size_t dim;
    std::vector<ComplexQ31> state;

    explicit StateVectorSimulator(uint32_t n) : num_qubits(n), dim(size_t(1) << n) {
        reset();
    }

    void reset() {
        state.assign(dim, ComplexQ31::zero());
        state[0] = ComplexQ31::one(); // |0...0>
    }

    void apply_h(uint32_t target) {
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
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                std::swap(state[i + j], state[i + j + bit]);
            }
        }
    }

    void apply_z(uint32_t target) {
        size_t bit = size_t(1) << target;
        for (size_t i = 0; i < dim; i += (bit << 1)) {
            for (size_t j = 0; j < bit; ++j) {
                size_t idx1 = i + j + bit;
                state[idx1] = ComplexQ31{-state[idx1].re, -state[idx1].im};
            }
        }
    }

    void apply_rz(uint32_t target, uint32_t phase) {
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
        size_t ctrl_bit = size_t(1) << ctrl;
        size_t tgt_bit = size_t(1) << tgt;

        for (size_t i = 0; i < dim; ++i) {
            if ((i & ctrl_bit) != 0 && (i & tgt_bit) != 0) {
                state[i] = cordic_rotate(state[i], phase);
            }
        }
    }

    void apply_crz(uint32_t ctrl, uint32_t tgt, uint32_t phase) {
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

    /**
     * @brief Quantum Fourier Transform (QFT) on n qubits.
     */
    void apply_qft(uint32_t n) {
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
        assert(dim == other.dim);
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

} // namespace core
} // namespace cq_hecs

#endif // CQ_HECS_CORE_STATEVECTOR_SIMULATOR_HPP
