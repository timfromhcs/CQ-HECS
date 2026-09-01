#include "cq_hecs/vulkan/vulkan_pipeline.hpp"
#include <fstream>
#include <vector>

namespace cq_hecs {

VulkanPipeline::~VulkanPipeline() {
    destroy();
}

VulkanPipeline::VulkanPipeline(VulkanPipeline&& other) noexcept
    : m_device(other.m_device),
      m_pipeline(other.m_pipeline),
      m_pipeline_layout(other.m_pipeline_layout),
      m_desc_layout(other.m_desc_layout),
      m_shader_module(other.m_shader_module) {
    other.m_device = VK_NULL_HANDLE;
    other.m_pipeline = VK_NULL_HANDLE;
    other.m_pipeline_layout = VK_NULL_HANDLE;
    other.m_desc_layout = VK_NULL_HANDLE;
    other.m_shader_module = VK_NULL_HANDLE;
}

VulkanPipeline& VulkanPipeline::operator=(VulkanPipeline&& other) noexcept {
    if (this != &other) {
        destroy();
        m_device = other.m_device;
        m_pipeline = other.m_pipeline;
        m_pipeline_layout = other.m_pipeline_layout;
        m_desc_layout = other.m_desc_layout;
        m_shader_module = other.m_shader_module;

        other.m_device = VK_NULL_HANDLE;
        other.m_pipeline = VK_NULL_HANDLE;
        other.m_pipeline_layout = VK_NULL_HANDLE;
        other.m_desc_layout = VK_NULL_HANDLE;
        other.m_shader_module = VK_NULL_HANDLE;
    }
    return *this;
}

void VulkanPipeline::destroy() {
    if (m_device != VK_NULL_HANDLE) {
        if (m_pipeline != VK_NULL_HANDLE) {
            vkDestroyPipeline(m_device, m_pipeline, nullptr);
            m_pipeline = VK_NULL_HANDLE;
        }
        if (m_pipeline_layout != VK_NULL_HANDLE) {
            vkDestroyPipelineLayout(m_device, m_pipeline_layout, nullptr);
            m_pipeline_layout = VK_NULL_HANDLE;
        }
        if (m_desc_layout != VK_NULL_HANDLE) {
            vkDestroyDescriptorSetLayout(m_device, m_desc_layout, nullptr);
            m_desc_layout = VK_NULL_HANDLE;
        }
        if (m_shader_module != VK_NULL_HANDLE) {
            vkDestroyShaderModule(m_device, m_shader_module, nullptr);
            m_shader_module = VK_NULL_HANDLE;
        }
    }
    m_device = VK_NULL_HANDLE;
}

bool VulkanPipeline::create_from_spirv(VkDevice device,
                                       const uint32_t* code_words,
                                       size_t code_size_bytes,
                                       uint32_t num_ssbos,
                                       uint32_t push_constant_size) {
    destroy();
    m_device = device;

    // 1. Create Shader Module
    VkShaderModuleCreateInfo module_info{};
    module_info.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
    module_info.codeSize = code_size_bytes;
    module_info.pCode = code_words;

    if (vkCreateShaderModule(device, &module_info, nullptr, &m_shader_module) != VK_SUCCESS) {
        return false;
    }

    // 2. Create Descriptor Set Layout
    std::vector<VkDescriptorSetLayoutBinding> bindings(num_ssbos);
    for (uint32_t i = 0; i < num_ssbos; ++i) {
        bindings[i].binding = i;
        bindings[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        bindings[i].descriptorCount = 1;
        bindings[i].stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
        bindings[i].pImmutableSamplers = nullptr;
    }

    VkDescriptorSetLayoutCreateInfo desc_info{};
    desc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
    desc_info.bindingCount = static_cast<uint32_t>(bindings.size());
    desc_info.pBindings = bindings.data();

    if (vkCreateDescriptorSetLayout(device, &desc_info, nullptr, &m_desc_layout) != VK_SUCCESS) {
        destroy();
        return false;
    }

    // 3. Create Pipeline Layout
    VkPipelineLayoutCreateInfo layout_info{};
    layout_info.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
    layout_info.setLayoutCount = 1;
    layout_info.pSetLayouts = &m_desc_layout;

    VkPushConstantRange pc_range{};
    if (push_constant_size > 0) {
        pc_range.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
        pc_range.offset = 0;
        pc_range.size = push_constant_size;
        layout_info.pushConstantRangeCount = 1;
        layout_info.pPushConstantRanges = &pc_range;
    }

    if (vkCreatePipelineLayout(device, &layout_info, nullptr, &m_pipeline_layout) != VK_SUCCESS) {
        destroy();
        return false;
    }

    // 4. Create Compute Pipeline
    VkComputePipelineCreateInfo pipeline_info{};
    pipeline_info.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
    pipeline_info.stage.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
    pipeline_info.stage.stage = VK_SHADER_STAGE_COMPUTE_BIT;
    pipeline_info.stage.module = m_shader_module;
    pipeline_info.stage.pName = "main";
    pipeline_info.layout = m_pipeline_layout;

    if (vkCreateComputePipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, nullptr, &m_pipeline) != VK_SUCCESS) {
        destroy();
        return false;
    }

    return true;
}

bool VulkanPipeline::create_from_file(VkDevice device,
                                      const std::string& spv_path,
                                      uint32_t num_ssbos,
                                      uint32_t push_constant_size) {
    std::ifstream file(spv_path, std::ios::ate | std::ios::binary);
    if (!file.is_open()) return false;

    size_t file_size = static_cast<size_t>(file.tellg());
    std::vector<char> buffer(file_size);
    file.seekg(0);
    file.read(buffer.data(), file_size);
    file.close();

    return create_from_spirv(device, reinterpret_cast<const uint32_t*>(buffer.data()), file_size, num_ssbos, push_constant_size);
}

} // namespace cq_hecs
