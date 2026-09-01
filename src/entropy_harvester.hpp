#pragma once
#include <cstdint>
#include <vector>
#include <string>

namespace cq_hecs {

class EntropyHarvester {
public:
    EntropyHarvester();
    ~EntropyHarvester();

    // Collect hardware entropy from Win32 QPC drift, CPU jitter, and bus contention
    uint64_t harvest_entropy_64();
    
    // Harvest multiple entropy samples into buffer
    void harvest_buffer(uint64_t* out_buffer, size_t count);

    // Diagnostics
    double get_last_jitter_ns() const { return m_last_jitter_ns; }
    uint64_t get_sample_count() const { return m_sample_count; }

private:
    uint64_t sample_qpc_jitter();
    uint64_t sample_bus_contention();
    uint64_t mix64(uint64_t a, uint64_t b);

    int64_t m_perf_frequency;
    double m_last_jitter_ns;
    uint64_t m_sample_count;
    uint64_t m_entropy_pool;
};

} // namespace cq_hecs
