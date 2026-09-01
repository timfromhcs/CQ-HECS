#pragma once
#include <vulkan/vulkan.h>
#include <cstdint>
#include <cstddef>
#include <mutex>
#include <string>
#include <stdexcept>

namespace cq_hecs {

/// @brief Vulkan Memory Governor enforcing a strict 3.0 GB VRAM hard ceiling
class VulkanMemoryManager {
public:
    // Strict hard limit: 3.0 GB = 3072 MB = 3,221,225,472 bytes
    static constexpr size_t VRAM_HARD_CEILING_BYTES = 3ULL * 1024ULL * 1024ULL * 1024ULL;

    VulkanMemoryManager() = default;

    /// @brief Track an allocation of GPU memory
    /// Throws std::runtime_error if the 3.0 GB ceiling would be exceeded
    void track_allocation(size_t bytes) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_allocated_bytes + bytes > VRAM_HARD_CEILING_BYTES) {
            throw std::runtime_error("Strict VRAM ceiling (3.0 GB) exceeded! Requested: " +
                                     std::to_string(bytes) + " bytes, Active: " +
                                     std::to_string(m_allocated_bytes) + " bytes");
        }
        m_allocated_bytes += bytes;
        if (m_allocated_bytes > m_peak_bytes) {
            m_peak_bytes = m_allocated_bytes;
        }
    }

    /// @brief Track a deallocation of GPU memory
    void track_deallocation(size_t bytes) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (bytes > m_allocated_bytes) {
            m_allocated_bytes = 0;
        } else {
            m_allocated_bytes -= bytes;
        }
    }

    size_t get_allocated_bytes() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_allocated_bytes;
    }

    size_t get_peak_bytes() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_peak_bytes;
    }

    size_t get_ceiling_bytes() const {
        return VRAM_HARD_CEILING_BYTES;
    }

    bool is_within_ceiling() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_allocated_bytes <= VRAM_HARD_CEILING_BYTES;
    }

    void reset_counters() {
        std::lock_guard<std::mutex> lock(m_mutex);
        m_allocated_bytes = 0;
        m_peak_bytes = 0;
    }

private:
    mutable std::mutex m_mutex;
    size_t m_allocated_bytes = 0;
    size_t m_peak_bytes = 0;
};

} // namespace cq_hecs
