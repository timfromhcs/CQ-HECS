#include "cq_hecs/residual_engine.hpp"
#include <algorithm>

namespace cq_hecs {

void ResidualEngine::fold_tensor(uint32_t site_id,
                                 const std::vector<ComplexFixed>& full_tensor,
                                 size_t max_active_elements,
                                 std::vector<ComplexFixed>& out_active,
                                 ResidualChunk& out_residual) const {
    out_residual.site_id = site_id;
    out_residual.original_size = static_cast<uint32_t>(full_tensor.size());
    out_residual.entries.clear();

    size_t active_count = std::min(full_tensor.size(), max_active_elements);
    out_active.resize(active_count);

    // Active layer holds dominant components
    for (size_t i = 0; i < active_count; ++i) {
        out_active[i] = full_tensor[i];
    }

    // Residual layer holds all remaining components bit-exactly
    for (size_t i = active_count; i < full_tensor.size(); ++i) {
        const auto& amp = full_tensor[i];
        if (amp.real != 0 || amp.imag != 0) {
            out_residual.entries.push_back(SparseResidualEntry{
                static_cast<uint32_t>(i),
                amp.real,
                amp.imag
            });
        }
    }
}

void ResidualEngine::reconstruct_tensor(const std::vector<ComplexFixed>& active_tensor,
                                       const ResidualChunk& residual,
                                       std::vector<ComplexFixed>& out_full) const {
    size_t target_size = std::max(static_cast<size_t>(residual.original_size), active_tensor.size());
    out_full.assign(target_size, ComplexFixed{0, 0});

    // Copy active components
    for (size_t i = 0; i < active_tensor.size(); ++i) {
        out_full[i] = active_tensor[i];
    }

    // Fold residual components back in: T = T_Active + T_Residual
    for (const auto& entry : residual.entries) {
        if (entry.element_index < target_size) {
            out_full[entry.element_index].real += entry.real_delta;
            out_full[entry.element_index].imag += entry.imag_delta;
        }
    }
}

void ResidualEngine::store_residual(uint32_t site_id, ResidualChunk chunk) {
    m_residuals[site_id] = std::move(chunk);
}

const ResidualChunk* ResidualEngine::get_residual(uint32_t site_id) const {
    auto it = m_residuals.find(site_id);
    if (it != m_residuals.end()) {
        return &it->second;
    }
    return nullptr;
}

bool ResidualEngine::has_residual(uint32_t site_id) const {
    return m_residuals.find(site_id) != m_residuals.end();
}

void ResidualEngine::drop_residual(uint32_t site_id) {
    m_residuals.erase(site_id);
}

size_t ResidualEngine::get_total_host_ram_bytes() const {
    size_t total = 0;
    for (const auto& [_, chunk] : m_residuals) {
        total += chunk.byte_size();
    }
    return total;
}

void ResidualEngine::clear() {
    m_residuals.clear();
}

} // namespace cq_hecs
