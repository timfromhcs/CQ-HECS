#include "cq_hecs/vulkan/vulkan_context.hpp"
#include "vulkan/shaders_vrts_embedded.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
#include <cstring>
#include <algorithm>

namespace cq_hecs {

struct PushConstantsCordic {
    uint32_t gate_type;
    uint32_t phase_angle;
    uint32_t is_inverse;
    uint32_t total_pairs;
};

struct PushConstantsReset {
    uint32_t total_elements;
    uint32_t target_basis;
};

struct PushConstantsContract {
    uint32_t dim_m;
    uint32_t dim_k;
    uint32_t dim_n;
};

struct PushConstantsBcp {
    uint32_t num_clauses;
    uint32_t num_fronts;
    uint32_t words;
};

VulkanContext::VulkanContext() = default;

VulkanContext::~VulkanContext() {
    cleanup();
}

bool VulkanContext::initialize() {
    if (m_initialized) return true;

    if (!create_instance()) {
        cleanup();
        return false;
    }
    if (!select_physical_device()) {
        cleanup();
        return false;
    }
    if (!create_logical_device()) {
        cleanup();
        return false;
    }
    if (!create_command_pool()) {
        cleanup();
        return false;
    }
    if (!create_descriptor_pool()) {
        cleanup();
        return false;
    }
    if (!init_pipelines()) {
        cleanup();
        return false;
    }

    m_initialized = true;
    return true;
}

void VulkanContext::cleanup() {
    if (m_device != VK_NULL_HANDLE) {
        vkDeviceWaitIdle(m_device);

        m_pipeline_cordic.destroy();
        m_pipeline_contract.destroy();
        m_pipeline_omniwave_bcp.destroy();
        m_pipeline_bond_svd.destroy();
        m_pipeline_state_reset.destroy();

        if (m_descriptor_pool != VK_NULL_HANDLE) {
            vkDestroyDescriptorPool(m_device, m_descriptor_pool, nullptr);
            m_descriptor_pool = VK_NULL_HANDLE;
        }
        if (m_command_pool != VK_NULL_HANDLE) {
            vkDestroyCommandPool(m_device, m_command_pool, nullptr);
            m_command_pool = VK_NULL_HANDLE;
        }
        vkDestroyDevice(m_device, nullptr);
        m_device = VK_NULL_HANDLE;
    }

    if (m_instance != VK_NULL_HANDLE) {
        vkDestroyInstance(m_instance, nullptr);
        m_instance = VK_NULL_HANDLE;
    }

    m_initialized = false;
    m_memory_manager.reset_counters();
}

bool VulkanContext::create_instance() {
    VkApplicationInfo app_info{};
    app_info.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
    app_info.pApplicationName = "CQ-HECS VRTS-300";
    app_info.applicationVersion = VK_MAKE_VERSION(2, 0, 0);
    app_info.pEngineName = "VRTS-Vulkan";
    app_info.engineVersion = VK_MAKE_VERSION(2, 0, 0);
    app_info.apiVersion = VK_API_VERSION_1_2;

    VkInstanceCreateInfo create_info{};
    create_info.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
    create_info.pApplicationInfo = &app_info;

    VkResult res = vkCreateInstance(&create_info, nullptr, &m_instance);
    return res == VK_SUCCESS;
}

bool VulkanContext::select_physical_device() {
    uint32_t device_count = 0;
    vkEnumeratePhysicalDevices(m_instance, &device_count, nullptr);
    std::vector<VkPhysicalDevice> devices(device_count);
    if (device_count > 0) {
        vkEnumeratePhysicalDevices(m_instance, &device_count, devices.data());
    }

    std::vector<DeviceDescription> described;
    described.reserve(devices.size());
    for (const auto& dev : devices) {
        VkPhysicalDeviceProperties props;
        vkGetPhysicalDeviceProperties(dev, &props);
        DeviceDescription d;
        d.name = props.deviceName;
        switch (props.deviceType) {
            case VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU: d.kind = DeviceKind::Discrete; break;
            case VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU: d.kind = DeviceKind::Integrated; break;
            case VK_PHYSICAL_DEVICE_TYPE_CPU: d.kind = DeviceKind::Software; break;
            default: d.kind = DeviceKind::Other; break;
        }
        d.vendor_id = props.vendorID;
        d.device_id = props.deviceID;
        d.driver_version = props.driverVersion;
        d.api_version = props.apiVersion;
        described.push_back(d);
    }

    const char* request = std::getenv("CQ_HECS_VULKAN_DEVICE");
    const DeviceChoice choice = choose_device(described, request ? std::string(request) : std::string());
    m_selection_reason = choice.reason;
    if (choice.index < 0) {
        std::cerr << "[VulkanContext] " << choice.reason << "\n";
        return false;
    }

    m_physical_device = devices[static_cast<size_t>(choice.index)];
    m_device_identity = described[static_cast<size_t>(choice.index)];
    m_device_name = m_device_identity.name;
    m_is_lavapipe = m_device_identity.kind == DeviceKind::Software || is_software_name(m_device_name);
    return true;
}

bool VulkanContext::create_logical_device() {
    uint32_t queue_family_count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(m_physical_device, &queue_family_count, nullptr);
    std::vector<VkQueueFamilyProperties> queue_families(queue_family_count);
    vkGetPhysicalDeviceQueueFamilyProperties(m_physical_device, &queue_family_count, queue_families.data());

    bool found = false;
    for (uint32_t i = 0; i < queue_family_count; ++i) {
        if (queue_families[i].queueFlags & VK_QUEUE_COMPUTE_BIT) {
            m_queue_family_index = i;
            found = true;
            break;
        }
    }

    if (!found) return false;

    float queue_priority = 1.0f;
    VkDeviceQueueCreateInfo queue_create_info{};
    queue_create_info.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
    queue_create_info.queueFamilyIndex = m_queue_family_index;
    queue_create_info.queueCount = 1;
    queue_create_info.pQueuePriorities = &queue_priority;

    VkPhysicalDeviceFeatures supported_features{};
    vkGetPhysicalDeviceFeatures(m_physical_device, &supported_features);
    if (!supported_features.shaderInt64) {
        std::cerr << "[VulkanContext] Device does not support shaderInt64, which "
                     "the embedded compute shaders require.\n";
        return false;
    }

    VkPhysicalDeviceFeatures device_features{};
    device_features.shaderInt64 = VK_TRUE;

    VkDeviceCreateInfo create_info{};
    create_info.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
    create_info.queueCreateInfoCount = 1;
    create_info.pQueueCreateInfos = &queue_create_info;
    create_info.pEnabledFeatures = &device_features;

    if (vkCreateDevice(m_physical_device, &create_info, nullptr, &m_device) != VK_SUCCESS) {
        return false;
    }

    vkGetDeviceQueue(m_device, m_queue_family_index, 0, &m_compute_queue);
    return true;
}

bool VulkanContext::create_command_pool() {
    VkCommandPoolCreateInfo pool_info{};
    pool_info.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
    pool_info.queueFamilyIndex = m_queue_family_index;
    pool_info.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;

    return vkCreateCommandPool(m_device, &pool_info, nullptr, &m_command_pool) == VK_SUCCESS;
}

bool VulkanContext::create_descriptor_pool() {
    VkDescriptorPoolSize pool_sizes[1];
    pool_sizes[0].type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    pool_sizes[0].descriptorCount = 128;

    VkDescriptorPoolCreateInfo pool_info{};
    pool_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
    pool_info.poolSizeCount = 1;
    pool_info.pPoolSizes = pool_sizes;
    pool_info.maxSets = 64;
    pool_info.flags = VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT;

    return vkCreateDescriptorPool(m_device, &pool_info, nullptr, &m_descriptor_pool) == VK_SUCCESS;
}

bool VulkanContext::init_pipelines() {
    // 1. CORDIC Pipeline (1 SSBO, sizeof(PushConstantsCordic))
    if (!m_pipeline_cordic.create_from_spirv(m_device,
                                             embedded_vrts_shaders::spv_cordic,
                                             embedded_vrts_shaders::spv_cordic_size,
                                             1,
                                             sizeof(PushConstantsCordic))) {
        return false;
    }

    // 2. State Reset Pipeline (1 SSBO, sizeof(PushConstantsReset))
    if (!m_pipeline_state_reset.create_from_spirv(m_device,
                                                  embedded_vrts_shaders::spv_state_reset,
                                                  embedded_vrts_shaders::spv_state_reset_size,
                                                  1,
                                                  sizeof(PushConstantsReset))) {
        return false;
    }

    // 3. Tensor Dot Contract Pipeline (3 SSBOs, sizeof(PushConstantsContract))
    if (!m_pipeline_contract.create_from_spirv(m_device,
                                               embedded_vrts_shaders::spv_tensor_contract,
                                               embedded_vrts_shaders::spv_tensor_contract_size,
                                               3,
                                               sizeof(PushConstantsContract))) {
        return false;
    }

    // 4. Bond SVD Pipeline (3 SSBOs, 24 bytes push constants)
    if (!m_pipeline_bond_svd.create_from_spirv(m_device,
                                               embedded_vrts_shaders::spv_bond_svd,
                                               embedded_vrts_shaders::spv_bond_svd_size,
                                               3,
                                               24)) {
        return false;
    }

    // 5. OMNIWAVE batched BCP (5 SSBOs, sizeof(PushConstantsBcp))
    if (!m_pipeline_omniwave_bcp.create_from_spirv(m_device,
                                                   embedded_vrts_shaders::spv_omniwave_bcp,
                                                   embedded_vrts_shaders::spv_omniwave_bcp_size,
                                                   5,
                                                   sizeof(PushConstantsBcp))) {
        return false;
    }

    return true;
}

bool VulkanContext::dispatch_cordic(VulkanBuffer& buffer, uint32_t gate_type, uint32_t phase_angle, uint32_t is_inverse, uint32_t total_pairs) {
    if (!m_initialized || !buffer.is_valid()) return false;
    std::lock_guard<std::mutex> lock(m_dispatch_mutex);

    // Allocate Descriptor Set
    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = m_descriptor_pool;
    alloc_info.descriptorSetCount = 1;
    VkDescriptorSetLayout layout = m_pipeline_cordic.get_descriptor_set_layout();
    alloc_info.pSetLayouts = &layout;

    VkDescriptorSet desc_set = VK_NULL_HANDLE;
    if (vkAllocateDescriptorSets(m_device, &alloc_info, &desc_set) != VK_SUCCESS) return false;

    // Update descriptor set
    VkDescriptorBufferInfo buf_info{};
    buf_info.buffer = buffer.get_buffer();
    buf_info.offset = 0;
    buf_info.range = buffer.get_size();

    VkWriteDescriptorSet write{};
    write.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    write.dstSet = desc_set;
    write.dstBinding = 0;
    write.descriptorCount = 1;
    write.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    write.pBufferInfo = &buf_info;

    vkUpdateDescriptorSets(m_device, 1, &write, 0, nullptr);

    // Command buffer allocation
    VkCommandBufferAllocateInfo cmd_alloc{};
    cmd_alloc.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc.commandPool = m_command_pool;
    cmd_alloc.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc.commandBufferCount = 1;

    VkCommandBuffer cmd = VK_NULL_HANDLE;
    if (vkAllocateCommandBuffers(m_device, &cmd_alloc, &cmd) != VK_SUCCESS ||
        cmd == VK_NULL_HANDLE) {
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (vkBeginCommandBuffer(cmd, &begin_info) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_cordic.get_pipeline());
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_cordic.get_layout(), 0, 1, &desc_set, 0, nullptr);

    PushConstantsCordic pc{gate_type, phase_angle, is_inverse, total_pairs};
    vkCmdPushConstants(cmd, m_pipeline_cordic.get_layout(), VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);

    uint32_t groups = (total_pairs + 63) / 64;
    vkCmdDispatch(cmd, groups > 0 ? groups : 1, 1, 1);

    if (vkEndCommandBuffer(cmd) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkSubmitInfo submit_info{};
    submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit_info.commandBufferCount = 1;
    submit_info.pCommandBuffers = &cmd;

    VkResult submit_result = vkQueueSubmit(m_compute_queue, 1, &submit_info, VK_NULL_HANDLE);
    VkResult wait_result = submit_result == VK_SUCCESS
                               ? vkQueueWaitIdle(m_compute_queue)
                               : submit_result;

    vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
    vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);

    return submit_result == VK_SUCCESS && wait_result == VK_SUCCESS;
}

bool VulkanContext::dispatch_state_reset(VulkanBuffer& buffer, uint32_t total_elements, uint32_t target_basis) {
    if (!m_initialized || !buffer.is_valid()) return false;
    std::lock_guard<std::mutex> lock(m_dispatch_mutex);

    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = m_descriptor_pool;
    alloc_info.descriptorSetCount = 1;
    VkDescriptorSetLayout layout = m_pipeline_state_reset.get_descriptor_set_layout();
    alloc_info.pSetLayouts = &layout;

    VkDescriptorSet desc_set = VK_NULL_HANDLE;
    if (vkAllocateDescriptorSets(m_device, &alloc_info, &desc_set) != VK_SUCCESS) return false;

    VkDescriptorBufferInfo buf_info{};
    buf_info.buffer = buffer.get_buffer();
    buf_info.offset = 0;
    buf_info.range = buffer.get_size();

    VkWriteDescriptorSet write{};
    write.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
    write.dstSet = desc_set;
    write.dstBinding = 0;
    write.descriptorCount = 1;
    write.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
    write.pBufferInfo = &buf_info;

    vkUpdateDescriptorSets(m_device, 1, &write, 0, nullptr);

    VkCommandBufferAllocateInfo cmd_alloc{};
    cmd_alloc.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc.commandPool = m_command_pool;
    cmd_alloc.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc.commandBufferCount = 1;

    VkCommandBuffer cmd = VK_NULL_HANDLE;
    if (vkAllocateCommandBuffers(m_device, &cmd_alloc, &cmd) != VK_SUCCESS ||
        cmd == VK_NULL_HANDLE) {
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (vkBeginCommandBuffer(cmd, &begin_info) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_state_reset.get_pipeline());
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_state_reset.get_layout(), 0, 1, &desc_set, 0, nullptr);

    PushConstantsReset pc{total_elements, target_basis};
    vkCmdPushConstants(cmd, m_pipeline_state_reset.get_layout(), VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);

    uint32_t groups = (total_elements + 63) / 64;
    vkCmdDispatch(cmd, groups > 0 ? groups : 1, 1, 1);

    if (vkEndCommandBuffer(cmd) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkSubmitInfo submit_info{};
    submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit_info.commandBufferCount = 1;
    submit_info.pCommandBuffers = &cmd;

    VkResult submit_result = vkQueueSubmit(m_compute_queue, 1, &submit_info, VK_NULL_HANDLE);
    VkResult wait_result = submit_result == VK_SUCCESS
                               ? vkQueueWaitIdle(m_compute_queue)
                               : submit_result;

    vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
    vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);

    return submit_result == VK_SUCCESS && wait_result == VK_SUCCESS;
}

bool VulkanContext::dispatch_tensor_contract(VulkanBuffer& buf_a, VulkanBuffer& buf_b, VulkanBuffer& buf_c, uint32_t m, uint32_t k, uint32_t n) {
    if (!m_initialized || !buf_a.is_valid() || !buf_b.is_valid() || !buf_c.is_valid()) return false;
    std::lock_guard<std::mutex> lock(m_dispatch_mutex);

    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = m_descriptor_pool;
    alloc_info.descriptorSetCount = 1;
    VkDescriptorSetLayout layout = m_pipeline_contract.get_descriptor_set_layout();
    alloc_info.pSetLayouts = &layout;

    VkDescriptorSet desc_set = VK_NULL_HANDLE;
    if (vkAllocateDescriptorSets(m_device, &alloc_info, &desc_set) != VK_SUCCESS) return false;

    VkDescriptorBufferInfo buf_infos[3];
    buf_infos[0] = {buf_a.get_buffer(), 0, buf_a.get_size()};
    buf_infos[1] = {buf_b.get_buffer(), 0, buf_b.get_size()};
    buf_infos[2] = {buf_c.get_buffer(), 0, buf_c.get_size()};

    VkWriteDescriptorSet writes[3]{};
    for (int i = 0; i < 3; ++i) {
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet = desc_set;
        writes[i].dstBinding = i;
        writes[i].descriptorCount = 1;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        writes[i].pBufferInfo = &buf_infos[i];
    }

    vkUpdateDescriptorSets(m_device, 3, writes, 0, nullptr);

    VkCommandBufferAllocateInfo cmd_alloc{};
    cmd_alloc.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc.commandPool = m_command_pool;
    cmd_alloc.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc.commandBufferCount = 1;

    VkCommandBuffer cmd = VK_NULL_HANDLE;
    if (vkAllocateCommandBuffers(m_device, &cmd_alloc, &cmd) != VK_SUCCESS ||
        cmd == VK_NULL_HANDLE) {
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (vkBeginCommandBuffer(cmd, &begin_info) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_contract.get_pipeline());
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_contract.get_layout(), 0, 1, &desc_set, 0, nullptr);

    PushConstantsContract pc{m, k, n};
    vkCmdPushConstants(cmd, m_pipeline_contract.get_layout(), VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);

    uint32_t gx = (n + 15) / 16;
    uint32_t gy = (m + 15) / 16;
    vkCmdDispatch(cmd, gx > 0 ? gx : 1, gy > 0 ? gy : 1, 1);

    if (vkEndCommandBuffer(cmd) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }

    VkSubmitInfo submit_info{};
    submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
    submit_info.commandBufferCount = 1;
    submit_info.pCommandBuffers = &cmd;

    VkResult submit_result = vkQueueSubmit(m_compute_queue, 1, &submit_info, VK_NULL_HANDLE);
    VkResult wait_result = submit_result == VK_SUCCESS
                               ? vkQueueWaitIdle(m_compute_queue)
                               : submit_result;

    vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
    vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);

    return submit_result == VK_SUCCESS && wait_result == VK_SUCCESS;
}


bool VulkanContext::dispatch_omniwave_bcp(VulkanBuffer& offsets, VulkanBuffer& codes, VulkanBuffer& assigned,
                                          VulkanBuffer& values, VulkanBuffer& status,
                                          uint32_t num_clauses, uint32_t num_fronts, uint32_t words) {
    if (!m_initialized || num_clauses == 0 || num_fronts == 0 || num_fronts > 65535u) return false;
    VulkanBuffer* buffers[5] = {&offsets, &codes, &assigned, &values, &status};
    for (VulkanBuffer* b : buffers) {
        if (!b->is_valid()) return false;
    }
    std::lock_guard<std::mutex> lock(m_dispatch_mutex);

    VkDescriptorSetAllocateInfo alloc_info{};
    alloc_info.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO;
    alloc_info.descriptorPool = m_descriptor_pool;
    alloc_info.descriptorSetCount = 1;
    VkDescriptorSetLayout layout = m_pipeline_omniwave_bcp.get_descriptor_set_layout();
    alloc_info.pSetLayouts = &layout;
    VkDescriptorSet desc_set = VK_NULL_HANDLE;
    if (vkAllocateDescriptorSets(m_device, &alloc_info, &desc_set) != VK_SUCCESS) return false;

    VkDescriptorBufferInfo infos[5];
    VkWriteDescriptorSet writes[5]{};
    for (int i = 0; i < 5; ++i) {
        infos[i] = {buffers[i]->get_buffer(), 0, buffers[i]->get_size()};
        writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
        writes[i].dstSet = desc_set;
        writes[i].dstBinding = static_cast<uint32_t>(i);
        writes[i].descriptorCount = 1;
        writes[i].descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        writes[i].pBufferInfo = &infos[i];
    }
    vkUpdateDescriptorSets(m_device, 5, writes, 0, nullptr);

    VkCommandBufferAllocateInfo cmd_alloc{};
    cmd_alloc.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
    cmd_alloc.commandPool = m_command_pool;
    cmd_alloc.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
    cmd_alloc.commandBufferCount = 1;
    VkCommandBuffer cmd = VK_NULL_HANDLE;
    if (vkAllocateCommandBuffers(m_device, &cmd_alloc, &cmd) != VK_SUCCESS || cmd == VK_NULL_HANDLE) {
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }
    VkCommandBufferBeginInfo begin_info{};
    begin_info.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
    begin_info.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    if (vkBeginCommandBuffer(cmd, &begin_info) != VK_SUCCESS) {
        vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
        vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
        return false;
    }
    vkCmdBindPipeline(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_omniwave_bcp.get_pipeline());
    vkCmdBindDescriptorSets(cmd, VK_PIPELINE_BIND_POINT_COMPUTE, m_pipeline_omniwave_bcp.get_layout(), 0, 1,
                            &desc_set, 0, nullptr);
    PushConstantsBcp pc{num_clauses, num_fronts, words};
    vkCmdPushConstants(cmd, m_pipeline_omniwave_bcp.get_layout(), VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(pc), &pc);
    vkCmdDispatch(cmd, (num_clauses + 63u) / 64u, num_fronts, 1);

    VkMemoryBarrier barrier{};
    barrier.sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER;
    barrier.srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT;
    barrier.dstAccessMask = VK_ACCESS_HOST_READ_BIT;
    vkCmdPipelineBarrier(cmd, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, 1, &barrier,
                         0, nullptr, 0, nullptr);

    bool ok = vkEndCommandBuffer(cmd) == VK_SUCCESS;
    if (ok) {
        VkSubmitInfo submit_info{};
        submit_info.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submit_info.commandBufferCount = 1;
        submit_info.pCommandBuffers = &cmd;
        ok = vkQueueSubmit(m_compute_queue, 1, &submit_info, VK_NULL_HANDLE) == VK_SUCCESS &&
             vkQueueWaitIdle(m_compute_queue) == VK_SUCCESS;
    }
    vkFreeCommandBuffers(m_device, m_command_pool, 1, &cmd);
    vkFreeDescriptorSets(m_device, m_descriptor_pool, 1, &desc_set);
    return ok;
}

} // namespace cq_hecs
