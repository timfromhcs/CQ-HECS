#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <memory>
#include <atomic>
#include <stdexcept>

namespace cqhecs {
namespace vulkan {

/**
 * @brief Memory Governor enforcing hard 5.0 GB (5120 MB) VRAM ceiling.
 */
class MemoryGovernor {
public:
    static constexpr size_t MAX_VRAM_BYTES = 5ULL * 1024ULL * 1024ULL * 1024ULL; // 5.0 GB
    static constexpr size_t MAX_VRAM_MB = 5120;

    MemoryGovernor() : allocated_bytes_(0), peak_bytes_(0) {}

    void allocate(size_t bytes) {
        size_t current = allocated_bytes_.fetch_add(bytes) + bytes;
        if (current > MAX_VRAM_BYTES) {
            allocated_bytes_.fetch_sub(bytes);
            throw std::runtime_error(
                "VRAM allocation exceeds hard limit of 5.0 GB (5120 MB). "
                "Current request: " + std::to_string(bytes) + " bytes, "
                "Total active: " + std::to_string(current / (1024 * 1024)) + " MB."
            );
        }
        // Update peak
        size_t prev_peak = peak_bytes_.load();
        while (current > prev_peak && !peak_bytes_.compare_exchange_weak(prev_peak, current));
    }

    void deallocate(size_t bytes) noexcept {
        if (bytes > allocated_bytes_) {
            allocated_bytes_.store(0);
        } else {
            allocated_bytes_.fetch_sub(bytes);
        }
    }

    size_t get_active_bytes() const noexcept {
        return allocated_bytes_.load();
    }

    double get_active_mb() const noexcept {
        return static_cast<double>(allocated_bytes_.load()) / (1024.0 * 1024.0);
    }

    double get_peak_mb() const noexcept {
        return static_cast<double>(peak_bytes_.load()) / (1024.0 * 1024.0);
    }

    void reset() noexcept {
        allocated_bytes_.store(0);
        peak_bytes_.store(0);
    }

private:
    std::atomic<size_t> allocated_bytes_;
    std::atomic<size_t> peak_bytes_;
};

/**
 * @brief Vulkan Compute Engine with active 5.0 GB Memory Governor.
 */
class VulkanEngine {
public:
    uint32_t num_qubits{0};
    uint32_t max_bond_dim{48}; // SVD/Bond-Dimension limit: chi <= 48
    MemoryGovernor governor;

    VulkanEngine(uint32_t n_qubits = 300, uint32_t max_chi = 48);
    ~VulkanEngine();

    bool initialize();

    // 300-Qubit Linear MPS allocation with governor verification
    void allocate_mps_sites(uint32_t n_qubits, uint32_t chi);

    // Gate operations
    void apply_h(uint32_t q);
    void apply_x(uint32_t q);
    void apply_z(uint32_t q);
    void apply_s(uint32_t q);
    void apply_t(uint32_t q);
    void apply_cx(uint32_t ctrl, uint32_t tgt);

    // Fast 1M shots sampling
    std::vector<uint8_t> sample_fast_shots(uint32_t shots, uint64_t seed = 42);

    // Dynamic SVD/QR truncation to keep bond dimension <= max_bond_dim
    void truncate_bond(uint32_t site_idx);

    double get_active_vram_mb() const noexcept {
        return governor.get_active_mb();
    }

private:
    bool initialized_{false};
    struct MPSSiteInfo {
        uint32_t chi_left{1};
        uint32_t chi_right{1};
        size_t byte_size{0};
    };
    std::vector<MPSSiteInfo> sites_;
};

} // namespace vulkan
} // namespace cqhecs
