#pragma once
#include <vulkan/vulkan.h>
#include <vector>
#include <string>
#include <cstdint>

namespace cq_hecs {

/// @brief Encapsulates a Vulkan compute pipeline, descriptor layout, and pipeline layout
class VulkanPipeline {
public:
    VulkanPipeline() = default;
    ~VulkanPipeline();

    // Move-only
    VulkanPipeline(const VulkanPipeline&) = delete;
    VulkanPipeline& operator=(const VulkanPipeline&) = delete;
    VulkanPipeline(VulkanPipeline&& other) noexcept;
    VulkanPipeline& operator=(VulkanPipeline&& other) noexcept;

    bool create_from_spirv(VkDevice device,
                           const uint32_t* code_words,
                           size_t code_size_bytes,
                           uint32_t num_ssbos,
                           uint32_t push_constant_size);

    bool create_from_file(VkDevice device,
                          const std::string& spv_path,
                          uint32_t num_ssbos,
                          uint32_t push_constant_size);

    void destroy();

    VkPipeline get_pipeline() const { return m_pipeline; }
    VkPipelineLayout get_layout() const { return m_pipeline_layout; }
    VkDescriptorSetLayout get_descriptor_set_layout() const { return m_desc_layout; }
    bool is_valid() const { return m_pipeline != VK_NULL_HANDLE; }

private:
    VkDevice m_device = VK_NULL_HANDLE;
    VkPipeline m_pipeline = VK_NULL_HANDLE;
    VkPipelineLayout m_pipeline_layout = VK_NULL_HANDLE;
    VkDescriptorSetLayout m_desc_layout = VK_NULL_HANDLE;
    VkShaderModule m_shader_module = VK_NULL_HANDLE;
};

} // namespace cq_hecs
