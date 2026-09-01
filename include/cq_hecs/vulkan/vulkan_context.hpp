#pragma once
#include <vulkan/vulkan.h>
#include <string>
#include <vector>
#include <memory>
#include <mutex>
#include "cq_hecs/vulkan/vulkan_memory.hpp"
#include "cq_hecs/vulkan/vulkan_buffer.hpp"
#include "cq_hecs/vulkan/vulkan_pipeline.hpp"
#include "cq_hecs/cordic_engine.hpp"

namespace cq_hecs {

/// @brief Vulkan Compute Context managing instance, device, queue, memory, and pipelines
class VulkanContext {
public:
    VulkanContext();
    ~VulkanContext();

    bool initialize();
    void cleanup();

    bool is_initialized() const { return m_initialized; }
    bool is_lavapipe_emulation() const { return m_is_lavapipe; }
    const std::string& get_device_name() const { return m_device_name; }

    VkDevice get_device() const { return m_device; }
    VkPhysicalDevice get_physical_device() const { return m_physical_device; }
    VkQueue get_compute_queue() const { return m_compute_queue; }
    uint32_t get_queue_family_index() const { return m_queue_family_index; }
    VkCommandPool get_command_pool() const { return m_command_pool; }
    VkDescriptorPool get_descriptor_pool() const { return m_descriptor_pool; }

    VulkanMemoryManager& get_memory_manager() { return m_memory_manager; }
    const VulkanMemoryManager& get_memory_manager() const { return m_memory_manager; }

    // Pipelines
    VulkanPipeline& get_pipeline_cordic() { return m_pipeline_cordic; }
    VulkanPipeline& get_pipeline_contract() { return m_pipeline_contract; }
    VulkanPipeline& get_pipeline_bond_svd() { return m_pipeline_bond_svd; }
    VulkanPipeline& get_pipeline_state_reset() { return m_pipeline_state_reset; }

    // Dispatch methods
    bool dispatch_cordic(VulkanBuffer& buffer, uint32_t gate_type, uint32_t phase_angle, uint32_t is_inverse, uint32_t total_pairs);
    bool dispatch_state_reset(VulkanBuffer& buffer, uint32_t total_elements, uint32_t target_basis);
    bool dispatch_tensor_contract(VulkanBuffer& buf_a, VulkanBuffer& buf_b, VulkanBuffer& buf_c, uint32_t m, uint32_t k, uint32_t n);

private:
    bool create_instance();
    bool select_physical_device();
    bool create_logical_device();
    bool create_command_pool();
    bool create_descriptor_pool();
    bool init_pipelines();

    VkInstance m_instance = VK_NULL_HANDLE;
    VkPhysicalDevice m_physical_device = VK_NULL_HANDLE;
    VkDevice m_device = VK_NULL_HANDLE;
    VkQueue m_compute_queue = VK_NULL_HANDLE;
    uint32_t m_queue_family_index = 0;
    VkCommandPool m_command_pool = VK_NULL_HANDLE;
    VkDescriptorPool m_descriptor_pool = VK_NULL_HANDLE;

    std::string m_device_name;
    bool m_is_lavapipe = false;
    bool m_initialized = false;

    VulkanMemoryManager m_memory_manager;

    VulkanPipeline m_pipeline_cordic;
    VulkanPipeline m_pipeline_contract;
    VulkanPipeline m_pipeline_bond_svd;
    VulkanPipeline m_pipeline_state_reset;

    std::mutex m_dispatch_mutex;
};

} // namespace cq_hecs
