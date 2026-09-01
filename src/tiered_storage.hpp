#pragma once
#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>
#include <unordered_map>
#include <mutex>

namespace cq_hecs {

struct StoragePage {
    uint32_t page_id;
    size_t size_bytes;
    uint64_t file_offset;
    bool is_in_memory;
    void* host_ptr;
};

class TieredStorageGovernor {
public:
    explicit TieredStorageGovernor(size_t max_active_bytes = 120ULL * 1024ULL * 1024ULL,
                                   const std::wstring& swap_file_path = L"cq_hecs_swap.bin");
    ~TieredStorageGovernor();

    // Allocate managed buffer
    uint32_t allocate_page(size_t size_bytes, const void* initial_data = nullptr);

    // Evict page to Win32 Memory-Mapped cold storage swap pool
    bool evict_page_to_cold_storage(uint32_t page_id);

    // Page back in from cold storage
    void* fetch_page_to_memory(uint32_t page_id);

    // Release page
    void free_page(uint32_t page_id);

    // Memory Governor Queries
    size_t get_active_bytes() const { return m_active_bytes; }
    size_t get_cold_bytes() const { return m_cold_bytes; }
    size_t get_max_allowed_bytes() const { return m_max_active_bytes; }
    uint64_t get_page_fault_count() const { return m_page_fault_count; }
    bool is_within_budget() const { return m_active_bytes <= m_max_active_bytes; }

private:
    void init_win32_mmf();
    void close_win32_mmf();

    size_t m_max_active_bytes;
    size_t m_active_bytes;
    size_t m_cold_bytes;
    uint64_t m_page_fault_count;
    std::wstring m_swap_path;

    void* m_file_handle;    // HANDLE
    void* m_mapping_handle; // HANDLE
    uint8_t* m_mapped_view; // Base pointer
    size_t m_mmf_capacity;
    size_t m_next_swap_offset;

    uint32_t m_next_page_id;
    std::unordered_map<uint32_t, StoragePage> m_pages;
    mutable std::mutex m_mutex;
};

} // namespace cq_hecs
