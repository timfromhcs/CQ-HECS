#pragma once
#include <vulkan/vulkan.h>
#include <cstdint>
#include <cstddef>
#include "cq_hecs/vulkan/vulkan_memory.hpp"

namespace cq_hecs {

/// @brief RAII wrapper for Vulkan storage buffer (SSBO) with VRAM tracking
class VulkanBuffer {
public:
    VulkanBuffer() = default;
    ~VulkanBuffer();

    // Move-only
    VulkanBuffer(const VulkanBuffer&) = delete;
    VulkanBuffer& operator=(const VulkanBuffer&) = delete;
    VulkanBuffer(VulkanBuffer&& other) noexcept;
    VulkanBuffer& operator=(VulkanBuffer&& other) noexcept;

    bool allocate(VkDevice device,
                  VkPhysicalDevice physical_device,
                  VkDeviceSize size,
                  VkBufferUsageFlags usage,
                  VkMemoryPropertyFlags properties,
                  VulkanMemoryManager& memory_manager);

    void release();

    void* map();
    void unmap();

    void copy_to_buffer(const void* data, VkDeviceSize size);
    void copy_from_buffer(void* data, VkDeviceSize size);

    VkBuffer get_buffer() const { return m_buffer; }
    VkDeviceMemory get_memory() const { return m_memory; }
    VkDeviceSize get_size() const { return m_size; }
    void* get_mapped() const { return m_mapped; }
    bool is_valid() const { return m_buffer != VK_NULL_HANDLE; }

private:
    uint32_t find_memory_type(VkPhysicalDevice physical_device, uint32_t type_filter, VkMemoryPropertyFlags properties);

    VkDevice m_device = VK_NULL_HANDLE;
    VkBuffer m_buffer = VK_NULL_HANDLE;
    VkDeviceMemory m_memory = VK_NULL_HANDLE;
    VkDeviceSize m_size = 0;
    void* m_mapped = nullptr;
    VulkanMemoryManager* m_memory_manager = nullptr;
};

} // namespace cq_hecs
