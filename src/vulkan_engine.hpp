#pragma once
#include <vulkan/vulkan.h>
#include <cstdint>
#include <vector>
#include <string>
#include <memory>

namespace cq_hecs {

struct VulkanBuffer {
    VkBuffer buffer = VK_NULL_HANDLE;
    VkDeviceMemory memory = VK_NULL_HANDLE;
    VkDeviceSize size = 0;
    void* mapped = nullptr;
};

struct MPSNode {
    uint32_t site_index;
    uint32_t chi_left;
    uint32_t chi_right;
    uint32_t physical_dim; // 2 for qubit
    size_t byte_size;
    VulkanBuffer buffer;
};

class VulkanEngine {
public:
    VulkanEngine();
    ~VulkanEngine();

    bool initialize();
    void cleanup();

    // Buffer Operations
    bool create_buffer(VkDeviceSize size, VkBufferUsageFlags usage, 
                       VkMemoryPropertyFlags properties, VulkanBuffer& out_buffer);
    void destroy_buffer(VulkanBuffer& buffer);

    // Compute Shader Pipeline Setup
    bool load_compute_pipeline(const std::string& spv_path, 
                               uint32_t push_constant_size, 
                               uint32_t buffer_binding_count,
                               VkPipeline& out_pipeline, 
                               VkPipelineLayout& out_layout,
                               VkDescriptorSetLayout& out_desc_layout);

    bool load_compute_pipeline_from_memory(const uint32_t* spv_words,
                                          size_t size_bytes,
                                          uint32_t push_constant_size,
                                          uint32_t buffer_binding_count,
                                          VkPipeline& out_pipeline,
                                          VkPipelineLayout& out_layout,
                                          VkDescriptorSetLayout& out_desc_layout);

    // High-Level Dispatches for CQ-HECS Kernels
    bool run_cq_hecs_core_phase(uint32_t* state_data, uint32_t count, uint32_t phase_shift);
    bool run_destructive_interference(uint32_t* state_data, uint32_t pair_count);
    bool run_arx_carry_split(uint64_t* a_data, uint64_t* b_carry_data, uint32_t count);
    bool run_explosion_shield_compress(const int64_t* input_state, int64_t* out_delta, 
                                       uint32_t count, uint64_t header_seed, int32_t scaling_exp);
    bool run_explosion_shield_decompress(const int64_t* delta_data, int64_t* out_state, 
                                         uint32_t count, uint64_t header_seed, int32_t scaling_exp);
    bool run_cuckoo_prune(const uint64_t* candidates, uint32_t candidate_count, 
                          uint32_t* out_prune_flags, uint32_t table_capacity);

    // MPS 300 Qubit Simulation & Memory Governor
    bool allocate_300q_mps(uint32_t chi = 64);
    void free_mps();
    size_t get_active_vram_bytes() const { return m_active_vram_bytes; }
    size_t get_mps_node_count() const { return m_mps_nodes.size(); }
    bool is_vram_under_limit(size_t limit_bytes = 120ULL * 1024ULL * 1024ULL) const {
        return m_active_vram_bytes <= limit_bytes;
    }

    bool is_initialized() const { return m_initialized; }

private:
    uint32_t find_memory_type(uint32_t type_filter, VkMemoryPropertyFlags properties);
    VkShaderModule create_shader_module(const std::vector<char>& code);

    VkInstance m_instance = VK_NULL_HANDLE;
    VkPhysicalDevice m_physical_device = VK_NULL_HANDLE;
    VkDevice m_device = VK_NULL_HANDLE;
    VkQueue m_compute_queue = VK_NULL_HANDLE;
    uint32_t m_compute_queue_family_index = 0;
    VkCommandPool m_command_pool = VK_NULL_HANDLE;
    VkDescriptorPool m_descriptor_pool = VK_NULL_HANDLE;

    // Precompiled Compute Pipelines
    VkPipeline m_pipeline_core = VK_NULL_HANDLE;
    VkPipelineLayout m_layout_core = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_desc_layout_core = VK_NULL_HANDLE;

    VkPipeline m_pipeline_explosion = VK_NULL_HANDLE;
    VkPipelineLayout m_layout_explosion = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_desc_layout_explosion = VK_NULL_HANDLE;

    VkPipeline m_pipeline_cuckoo = VK_NULL_HANDLE;
    VkPipelineLayout m_layout_cuckoo = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_desc_layout_cuckoo = VK_NULL_HANDLE;

    // MPS 300 Qubit Chain
    std::vector<MPSNode> m_mps_nodes;
    size_t m_active_vram_bytes = 0;
    bool m_initialized = false;
};

} // namespace cq_hecs
