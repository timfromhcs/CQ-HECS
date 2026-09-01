#include "tiered_storage.hpp"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <iostream>
#include <cstring>
#include <stdexcept>

namespace cq_hecs {

TieredStorageGovernor::TieredStorageGovernor(size_t max_active_bytes, const std::wstring& swap_file_path)
    : m_max_active_bytes(max_active_bytes)
    , m_active_bytes(0)
    , m_cold_bytes(0)
    , m_page_fault_count(0)
    , m_swap_path(swap_file_path)
    , m_file_handle(INVALID_HANDLE_VALUE)
    , m_mapping_handle(NULL)
    , m_mapped_view(nullptr)
    , m_mmf_capacity(256ULL * 1024ULL * 1024ULL) // 256 MB cold swap pool
    , m_next_swap_offset(0)
    , m_next_page_id(1)
{
    init_win32_mmf();
}

TieredStorageGovernor::~TieredStorageGovernor() {
    // Free all active memory pages
    for (auto& pair : m_pages) {
        if (pair.second.is_in_memory && pair.second.host_ptr) {
            std::free(pair.second.host_ptr);
            pair.second.host_ptr = nullptr;
        }
    }
    m_pages.clear();
    close_win32_mmf();

    // Clean up disk swap file
    DeleteFileW(m_swap_path.c_str());
}

void TieredStorageGovernor::init_win32_mmf() {
    m_file_handle = CreateFileW(
        m_swap_path.c_str(),
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        NULL,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE,
        NULL
    );

    if (m_file_handle == INVALID_HANDLE_VALUE) {
        throw std::runtime_error("Failed to create Win32 swap file for cold storage pool");
    }

    ULARGE_INTEGER li_cap;
    li_cap.QuadPart = m_mmf_capacity;

    m_mapping_handle = CreateFileMappingW(
        m_file_handle,
        NULL,
        PAGE_READWRITE,
        li_cap.HighPart,
        li_cap.LowPart,
        NULL
    );

    if (m_mapping_handle == NULL) {
        CloseHandle(m_file_handle);
        m_file_handle = INVALID_HANDLE_VALUE;
        throw std::runtime_error("Failed to create file mapping object");
    }

    m_mapped_view = static_cast<uint8_t*>(MapViewOfFile(
        m_mapping_handle,
        FILE_MAP_ALL_ACCESS,
        0,
        0,
        m_mmf_capacity
    ));

    if (!m_mapped_view) {
        CloseHandle(m_mapping_handle);
        CloseHandle(m_file_handle);
        m_mapping_handle = NULL;
        m_file_handle = INVALID_HANDLE_VALUE;
        throw std::runtime_error("Failed to map view of file for cold storage pool");
    }
}

void TieredStorageGovernor::close_win32_mmf() {
    if (m_mapped_view) {
        FlushViewOfFile(m_mapped_view, 0);
        UnmapViewOfFile(m_mapped_view);
        m_mapped_view = nullptr;
    }
    if (m_mapping_handle) {
        CloseHandle(m_mapping_handle);
        m_mapping_handle = NULL;
    }
    if (m_file_handle != INVALID_HANDLE_VALUE) {
        CloseHandle(m_file_handle);
        m_file_handle = INVALID_HANDLE_VALUE;
    }
}

uint32_t TieredStorageGovernor::allocate_page(size_t size_bytes, const void* initial_data) {
    std::lock_guard<std::mutex> lock(m_mutex);

    // Check if new allocation would violate active budget
    if (m_active_bytes + size_bytes > m_max_active_bytes) {
        // Evict pages until budget is satisfied
        for (auto& pair : m_pages) {
            if (m_active_bytes + size_bytes <= m_max_active_bytes) break;
            if (pair.second.is_in_memory) {
                // Inline eviction
                StoragePage& p = pair.second;
                if (m_next_swap_offset + p.size_bytes <= m_mmf_capacity && m_mapped_view && p.host_ptr) {
                    p.file_offset = m_next_swap_offset;
                    std::memcpy(m_mapped_view + p.file_offset, p.host_ptr, p.size_bytes);
                    m_next_swap_offset += (p.size_bytes + 63) & ~63; // 64-byte alignment
                    std::free(p.host_ptr);
                    p.host_ptr = nullptr;
                    p.is_in_memory = false;
                    m_active_bytes -= p.size_bytes;
                    m_cold_bytes += p.size_bytes;
                }
            }
        }
    }

    void* ptr = std::malloc(size_bytes);
    if (!ptr) {
        throw std::bad_alloc();
    }
    if (initial_data) {
        std::memcpy(ptr, initial_data, size_bytes);
    } else {
        std::memset(ptr, 0, size_bytes);
    }

    uint32_t pid = m_next_page_id++;
    StoragePage page;
    page.page_id = pid;
    page.size_bytes = size_bytes;
    page.file_offset = 0;
    page.is_in_memory = true;
    page.host_ptr = ptr;

    m_pages[pid] = page;
    m_active_bytes += size_bytes;
    return pid;
}

bool TieredStorageGovernor::evict_page_to_cold_storage(uint32_t page_id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto it = m_pages.find(page_id);
    if (it == m_pages.end() || !it->second.is_in_memory) {
        return false;
    }

    StoragePage& page = it->second;
    if (m_next_swap_offset + page.size_bytes > m_mmf_capacity) {
        return false; // Cold storage full
    }

    page.file_offset = m_next_swap_offset;
    std::memcpy(m_mapped_view + page.file_offset, page.host_ptr, page.size_bytes);
    m_next_swap_offset += (page.size_bytes + 63) & ~63; // Align to 64 bytes

    std::free(page.host_ptr);
    page.host_ptr = nullptr;
    page.is_in_memory = false;

    m_active_bytes -= page.size_bytes;
    m_cold_bytes += page.size_bytes;
    return true;
}

void* TieredStorageGovernor::fetch_page_to_memory(uint32_t page_id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto it = m_pages.find(page_id);
    if (it == m_pages.end()) {
        return nullptr;
    }

    StoragePage& page = it->second;
    if (page.is_in_memory) {
        return page.host_ptr;
    }

    // Page fault: fetch back from MMF cold pool
    m_page_fault_count++;

    // Ensure budget by evicting another page if necessary
    if (m_active_bytes + page.size_bytes > m_max_active_bytes) {
        for (auto& other : m_pages) {
            if (other.first != page_id && other.second.is_in_memory) {
                // Evict other page
                StoragePage& p = other.second;
                if (m_next_swap_offset + p.size_bytes <= m_mmf_capacity) {
                    p.file_offset = m_next_swap_offset;
                    std::memcpy(m_mapped_view + p.file_offset, p.host_ptr, p.size_bytes);
                    m_next_swap_offset += (p.size_bytes + 63) & ~63;
                    std::free(p.host_ptr);
                    p.host_ptr = nullptr;
                    p.is_in_memory = false;
                    m_active_bytes -= p.size_bytes;
                    m_cold_bytes += p.size_bytes;
                    if (m_active_bytes + page.size_bytes <= m_max_active_bytes) break;
                }
            }
        }
    }

    void* ptr = std::malloc(page.size_bytes);
    if (!ptr) {
        throw std::bad_alloc();
    }
    std::memcpy(ptr, m_mapped_view + page.file_offset, page.size_bytes);

    page.host_ptr = ptr;
    page.is_in_memory = true;
    m_active_bytes += page.size_bytes;
    m_cold_bytes -= page.size_bytes;

    return page.host_ptr;
}

void TieredStorageGovernor::free_page(uint32_t page_id) {
    std::lock_guard<std::mutex> lock(m_mutex);
    auto it = m_pages.find(page_id);
    if (it == m_pages.end()) return;

    if (it->second.is_in_memory && it->second.host_ptr) {
        std::free(it->second.host_ptr);
        m_active_bytes -= it->second.size_bytes;
    } else if (!it->second.is_in_memory) {
        m_cold_bytes -= it->second.size_bytes;
    }
    m_pages.erase(it);
}

} // namespace cq_hecs
