#include "cqhecs/vulkan/vulkan_engine.hpp"
#include <iostream>
#include <random>
#include <cstring>

namespace cqhecs {
namespace vulkan {

VulkanEngine::VulkanEngine(uint32_t n_qubits, uint32_t max_chi)
    : num_qubits(n_qubits), max_bond_dim(max_chi) {
    initialize();
}

VulkanEngine::~VulkanEngine() {
    // Release all tracked memory
    governor.reset();
}

bool VulkanEngine::initialize() {
    if (initialized_) return true;
    allocate_mps_sites(num_qubits, max_bond_dim);
    initialized_ = true;
    return true;
}

void VulkanEngine::allocate_mps_sites(uint32_t n_qubits, uint32_t chi) {
    // Free any previously allocated site memory
    for (const auto& s : sites_) {
        governor.deallocate(s.byte_size);
    }
    sites_.clear();
    sites_.resize(n_qubits);

    num_qubits = n_qubits;
    max_bond_dim = chi; // Exact or explicitly governed (no silent truncation)

    for (uint32_t i = 0; i < n_qubits; ++i) {
        uint32_t c_left = (i == 0) ? 1 : max_bond_dim;
        uint32_t c_right = (i == n_qubits - 1) ? 1 : max_bond_dim;

        // Size: 2 * chi_L * chi_R * 8 bytes (ComplexQ31 is 8 bytes)
        size_t tensor_bytes = 2ULL * c_left * c_right * 8ULL;
        governor.allocate(tensor_bytes);

        sites_[i].chi_left = c_left;
        sites_[i].chi_right = c_right;
        sites_[i].byte_size = tensor_bytes;
    }
}

void VulkanEngine::apply_h(uint32_t q) {
    if (q >= num_qubits) throw std::out_of_range("VulkanEngine: qubit index out of range");
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::apply_x(uint32_t q) {
    if (q >= num_qubits) throw std::out_of_range("VulkanEngine: qubit index out of range");
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::apply_z(uint32_t q) {
    if (q >= num_qubits) throw std::out_of_range("VulkanEngine: qubit index out of range");
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::apply_s(uint32_t q) {
    if (q >= num_qubits) throw std::out_of_range("VulkanEngine: qubit index out of range");
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::apply_t(uint32_t q) {
    if (q >= num_qubits) throw std::out_of_range("VulkanEngine: qubit index out of range");
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::apply_cx(uint32_t ctrl, uint32_t tgt) {
    if (ctrl >= num_qubits || tgt >= num_qubits) {
        throw std::out_of_range("VulkanEngine: qubit index out of range");
    }
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine is a memory-planning allocator and does not "
        "evolve a quantum state; use cq_hecs::core::MPSSimulator or "
        "cq_hecs::core::StateVectorSimulator for gate execution");
}

void VulkanEngine::truncate_bond(uint32_t site_idx) {
    if (site_idx + 1 >= num_qubits || max_bond_dim == 0) return;
    // Metadata-only planning adjustment; no amplitudes are stored here.
    if (sites_[site_idx].chi_right > max_bond_dim) {
        size_t old_bytes_l = sites_[site_idx].byte_size;
        size_t old_bytes_r = sites_[site_idx + 1].byte_size;

        sites_[site_idx].chi_right = max_bond_dim;
        sites_[site_idx + 1].chi_left = max_bond_dim;

        size_t new_bytes_l = 2ULL * sites_[site_idx].chi_left * max_bond_dim * 8ULL;
        size_t new_bytes_r = 2ULL * max_bond_dim * sites_[site_idx + 1].chi_right * 8ULL;

        governor.deallocate(old_bytes_l + old_bytes_r);
        governor.allocate(new_bytes_l + new_bytes_r);

        sites_[site_idx].byte_size = new_bytes_l;
        sites_[site_idx + 1].byte_size = new_bytes_r;
    }
}

std::vector<uint8_t> VulkanEngine::sample_fast_shots(uint32_t shots, uint64_t seed) {
    (void)shots;
    (void)seed;
    throw std::logic_error(
        "cqhecs::vulkan::VulkanEngine stores no amplitudes and cannot sample; "
        "use cq_hecs::core::MPSSimulator::sample_counts or "
        "cq_hecs::core::StateVectorSimulator::sample_counts");
}

} // namespace vulkan
} // namespace cqhecs
