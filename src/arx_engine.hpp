#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace cq_hecs {

struct ARXBenchmarkResultCPP {
    std::string primitive_name;
    uint32_t num_rounds = 0;
    bool forward_verified = false;
    bool inverse_verified = false;
    bool carry_shadow_exact = false;
    double path_pruning_ratio = 0.0;
    double elapsed_ms = 0.0;
    double throughput_ops_per_sec = 0.0;
};

class ARXEngineCPP {
public:
    ARXEngineCPP();
    ~ARXEngineCPP();

    // 1. BLAKE2b G-function
    void blake2b_g_forward(uint64_t& a, uint64_t& b, uint64_t& c, uint64_t& d, uint64_t m0, uint64_t m1);
    void blake2b_g_backward(uint64_t& a, uint64_t& b, uint64_t& c, uint64_t& d, uint64_t m0, uint64_t m1);
    ARXBenchmarkResultCPP benchmark_blake2b(uint32_t rounds = 1000);

    // 2. ChaCha20 Quarter-Round
    void chacha20_qr_forward(uint32_t& a, uint32_t& b, uint32_t& c, uint32_t& d);
    void chacha20_qr_backward(uint32_t& a, uint32_t& b, uint32_t& c, uint32_t& d);
    ARXBenchmarkResultCPP benchmark_chacha20(uint32_t rounds = 1000);

    // 3. SHA-256 Schedule Expansion
    uint32_t sha256_expand_step(uint32_t w_t2, uint32_t w_t7, uint32_t w_t15, uint32_t w_t16);
    uint32_t sha256_invert_step(uint32_t w_t, uint32_t w_t2, uint32_t w_t7, uint32_t w_t15);
    ARXBenchmarkResultCPP benchmark_sha256(uint32_t steps = 1000);

    // Carry shadow linearization
    static void linearize_add_64(uint64_t a, uint64_t b, uint64_t& out_sum, uint64_t& out_carry) {
        out_sum = a ^ b;
        out_carry = (a & b) << 1;
    }

    static void linearize_add_32(uint32_t a, uint32_t b, uint32_t& out_sum, uint32_t& out_carry) {
        out_sum = a ^ b;
        out_carry = (a & b) << 1;
    }

private:
    static inline uint64_t rotr64(uint64_t x, int n) {
        return (x >> n) | (x << (64 - n));
    }
    static inline uint64_t rotl64(uint64_t x, int n) {
        return (x << n) | (x >> (64 - n));
    }
    static inline uint32_t rotr32(uint32_t x, int n) {
        return (x >> n) | (x << (32 - n));
    }
    static inline uint32_t rotl32(uint32_t x, int n) {
        return (x << n) | (x >> (32 - n));
    }
};

} // namespace cq_hecs
