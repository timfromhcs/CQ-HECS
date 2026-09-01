#include "cq_hecs/vulkan/vulkan_buffer.hpp"
#include <cstring>
#include <stdexcept>

namespace cq_hecs {

VulkanBuffer::~VulkanBuffer() {
    release();
}

VulkanBuffer::VulkanBuffer(VulkanBuffer&& other) noexcept
    : m_device(other.m_device),
      m_buffer(other.m_buffer),
      m_memory(other.m_memory),
      m_size(other.m_size),
      m_mapped(other.m_mapped),
      m_memory_manager(other.m_memory_manager) {
    other.m_device = VK_NULL_HANDLE;
    other.m_buffer = VK_NULL_HANDLE;
    other.m_memory = VK_NULL_HANDLE;
    other.m_size = 0;
    other.m_mapped = nullptr;
    other.m_memory_manager = nullptr;
}

VulkanBuffer& VulkanBuffer::operator=(VulkanBuffer&& other) noexcept {
    if (this != &other) {
        release();
        m_device = other.m_device;
        m_buffer = other.m_buffer;
        m_memory = other.m_memory;
        m_size = other.m_size;
        m_mapped = other.m_mapped;
        m_memory_manager = other.m_memory_manager;

        other.m_device = VK_NULL_HANDLE;
        other.m_buffer = VK_NULL_HANDLE;
        other.m_memory = VK_NULL_HANDLE;
        other.m_size = 0;
        other.m_mapped = nullptr;
        other.m_memory_manager = nullptr;
    }
    return *this;
}

uint32_t VulkanBuffer::find_memory_type(VkPhysicalDevice physical_device, uint32_t type_filter, VkMemoryPropertyFlags properties) {
    VkPhysicalDeviceMemoryProperties mem_props;
    vkGetPhysicalDeviceMemoryProperties(physical_device, &mem_props);
    for (uint32_t i = 0; i < mem_props.memoryTypeCount; ++i) {
        if ((type_filter & (1 << i)) && (mem_props.memoryTypes[i].propertyFlags & properties) == properties) {
            return i;
        }
    }
    throw std::runtime_error("Failed to find suitable Vulkan memory type");
}

bool VulkanBuffer::allocate(VkDevice device,
                            VkPhysicalDevice physical_device,
                            VkDeviceSize size,
                            VkBufferUsageFlags usage,
                            VkMemoryPropertyFlags properties,
                            VulkanMemoryManager& memory_manager) {
    release();
    m_device = device;
    m_size = size;
    m_memory_manager = &memory_manager;

    // Track against strict 3.0 GB ceiling
    m_memory_manager->track_allocation(static_cast<size_t>(size));

    VkBufferCreateInfo buffer_info{};
    buffer_info.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
    buffer_info.size = size;
    buffer_info.usage = usage;
    buffer_info.sharingMode = VK_SHARING_MODE_EXCLUSIVE;

    if (vkCreateBuffer(device, &buffer_info, nullptr, &m_buffer) != VK_SUCCESS) {
        m_memory_manager->track_deallocation(static_cast<size_t>(size));
        return false;
    }

    VkMemoryRequirements mem_reqs;
    vkGetBufferMemoryRequirements(device, m_buffer, &mem_reqs);

    VkMemoryAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
    alloc_info.allocationSize = mem_reqs.size;
    alloc_info.memoryTypeIndex = find_memory_type(physical_device, mem_reqs.memoryTypeBits, properties);

    if (vkAllocateMemory(device, &alloc_info, nullptr, &m_memory) != VK_SUCCESS) {
        vkDestroyBuffer(device, m_buffer, nullptr);
        m_buffer = VK_NULL_HANDLE;
        m_memory_manager->track_deallocation(static_cast<size_t>(size));
        return false;
    }

    vkBindBufferMemory(device, m_buffer, m_memory, 0);
    return true;
}

void VulkanBuffer::release() {
    if (m_mapped && m_device != VK_NULL_HANDLE && m_memory != VK_NULL_HANDLE) {
        vkUnmapMemory(m_device, m_memory);
        m_mapped = nullptr;
    }
    if (m_device != VK_NULL_HANDLE) {
        if (m_buffer != VK_NULL_HANDLE) {
            vkDestroyBuffer(m_device, m_buffer, nullptr);
            m_buffer = VK_NULL_HANDLE;
        }
        if (m_memory != VK_NULL_HANDLE) {
            vkFreeMemory(m_device, m_memory, nullptr);
            m_memory = VK_NULL_HANDLE;
        }
    }
    if (m_memory_manager && m_size > 0) {
        m_memory_manager->track_deallocation(static_cast<size_t>(m_size));
    }
    m_size = 0;
    m_device = VK_NULL_HANDLE;
    m_memory_manager = nullptr;
}

void* VulkanBuffer::map() {
    if (!m_mapped && m_device != VK_NULL_HANDLE && m_memory != VK_NULL_HANDLE) {
        if (vkMapMemory(m_device, m_memory, 0, m_size, 0, &m_mapped) != VK_SUCCESS) {
            return nullptr;
        }
    }
    return m_mapped;
}

void VulkanBuffer::unmap() {
    if (m_mapped && m_device != VK_NULL_HANDLE && m_memory != VK_NULL_HANDLE) {
        vkUnmapMemory(m_device, m_memory);
        m_mapped = nullptr;
    }
}

void VulkanBuffer::copy_to_buffer(const void* data, VkDeviceSize size) {
    void* ptr = map();
    if (ptr && data && size <= m_size) {
        std::memcpy(ptr, data, static_cast<size_t>(size));
    }
}

void VulkanBuffer::copy_from_buffer(void* data, VkDeviceSize size) {
    void* ptr = map();
    if (ptr && data && size <= m_size) {
        std::memcpy(data, ptr, static_cast<size_t>(size));
    }
}

} // namespace cq_hecs
