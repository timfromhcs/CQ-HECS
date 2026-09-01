#include "entropy_harvester.hpp"
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#else
#include <time.h>
#if defined(__x86_64__) || defined(_M_X64)
#include <x86intrin.h>
#endif
#endif
#include <chrono>

namespace cq_hecs {

EntropyHarvester::EntropyHarvester()
    : m_last_jitter_ns(0.0)
    , m_sample_count(0)
    , m_entropy_pool(0x1a2b3c4d5e6f7081ULL)
{
#ifdef _WIN32
    LARGE_INTEGER freq;
    if (QueryPerformanceFrequency(&freq)) {
        m_perf_frequency = freq.QuadPart;
    } else {
        m_perf_frequency = 10000000LL;
    }
#else
    m_perf_frequency = 1000000000LL;
#endif
}

EntropyHarvester::~EntropyHarvester() {
}

uint64_t EntropyHarvester::mix64(uint64_t a, uint64_t b) {
    uint64_t z = (a ^ b) + 0x9e3779b97f4a7c15ULL;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

uint64_t EntropyHarvester::sample_qpc_jitter() {
    volatile uint64_t spin = 0;
    for (int i = 0; i < 32; ++i) {
        spin += static_cast<uint64_t>(i) * 0x45d9f3bULL;
    }

#ifdef _WIN32
    LARGE_INTEGER t1, t2;
    QueryPerformanceCounter(&t1);
    QueryPerformanceCounter(&t2);
    int64_t delta_ticks = t2.QuadPart - t1.QuadPart;
    if (m_perf_frequency > 0) {
        m_last_jitter_ns = (static_cast<double>(delta_ticks) * 1e9) / static_cast<double>(m_perf_frequency);
    }
    unsigned int aux = 0;
    uint64_t tsc = __rdtscp(&aux);
    return tsc ^ static_cast<uint64_t>(delta_ticks) ^ spin;
#else
    struct timespec t1, t2;
    clock_gettime(CLOCK_MONOTONIC_RAW, &t1);
    clock_gettime(CLOCK_MONOTONIC_RAW, &t2);
    int64_t delta_ticks = (t2.tv_sec - t1.tv_sec) * 1000000000LL + (t2.tv_nsec - t1.tv_nsec);
    m_last_jitter_ns = static_cast<double>(delta_ticks);
    uint64_t tsc = static_cast<uint64_t>(delta_ticks);
#if defined(__x86_64__) || defined(_M_X64)
    unsigned int aux = 0;
    tsc = __rdtscp(&aux);
#endif
    return tsc ^ static_cast<uint64_t>(delta_ticks) ^ spin;
#endif
}

uint64_t EntropyHarvester::sample_bus_contention() {
    // Measure memory-bus contention across disjoint cache lines
    alignas(64) volatile uint32_t mem_test[256] = {0};
#ifdef _WIN32
    LARGE_INTEGER t1, t2;
    QueryPerformanceCounter(&t1);
    for (int i = 0; i < 64; i += 8) {
        mem_test[i] ^= 0x55aa55aaU;
    }
    QueryPerformanceCounter(&t2);
    int64_t bus_delta = t2.QuadPart - t1.QuadPart;
#else
    struct timespec t1, t2;
    clock_gettime(CLOCK_MONOTONIC, &t1);
    for (int i = 0; i < 64; i += 8) {
        mem_test[i] ^= 0x55aa55aaU;
    }
    clock_gettime(CLOCK_MONOTONIC, &t2);
    int64_t bus_delta = (t2.tv_sec - t1.tv_sec) * 1000000000LL + (t2.tv_nsec - t1.tv_nsec);
#endif
    return static_cast<uint64_t>(bus_delta) * 0x9e3779b97f4a7c15ULL;
}

uint64_t EntropyHarvester::harvest_entropy_64() {
    uint64_t qpc_ent = sample_qpc_jitter();
    uint64_t bus_ent = sample_bus_contention();
    m_sample_count++;

    m_entropy_pool = mix64(m_entropy_pool ^ qpc_ent, bus_ent ^ (m_sample_count * 0x517cc1b727220a95ULL));
    return m_entropy_pool;
}

void EntropyHarvester::harvest_buffer(uint64_t* out_buffer, size_t count) {
    if (!out_buffer) return;
    for (size_t i = 0; i < count; ++i) {
        out_buffer[i] = harvest_entropy_64();
    }
}

} // namespace cq_hecs
