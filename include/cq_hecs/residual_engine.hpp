#pragma once
#include <cstdint>
#include <vector>
#include <unordered_map>
#include <memory>
#include <cstddef>
#include "cq_hecs/cordic_engine.hpp"

namespace cq_hecs {

/// @brief Compressed sparse residual entry stored in Host RAM
#pragma pack(push, 1)
struct SparseResidualEntry {
    uint32_t element_index;
    int64_t real_delta;
    int64_t imag_delta;

    constexpr bool operator==(const SparseResidualEntry& o) const = default;
};
#pragma pack(pop)

/// @brief Lossless residual delta stream for a single site or bond tensor
struct ResidualChunk {
    uint32_t site_id = 0;
    uint32_t original_size = 0;
    std::vector<SparseResidualEntry> entries;

    size_t byte_size() const {
        return sizeof(ResidualChunk) + entries.size() * sizeof(SparseResidualEntry);
    }
};

/// @brief Dual-Layer Residual Folding Engine (T = T_Active + T_Residual)
/// Completely eliminates destructive pruning errors by preserving truncated
/// tensor components as sparse bit-packed delta streams in Host RAM.
class ResidualEngine {
public:
    ResidualEngine() = default;

    /// @brief Fold full tensor into GPU active slice and Host RAM residual stream
    /// @param site_id ID of the site or bond
    /// @param full_tensor Full uncompressed tensor amplitudes
    /// @param max_active_elements Maximum capacity allowed in GPU VRAM
    /// @param out_active Output dominant active tensor for GPU SSBO storage
    /// @param out_residual Output lossless sparse residual for Host RAM storage
    void fold_tensor(uint32_t site_id,
                     const std::vector<ComplexFixed>& full_tensor,
                     size_t max_active_elements,
                     std::vector<ComplexFixed>& out_active,
                     ResidualChunk& out_residual) const;

    /// @brief On-demand bit-exact reconstruction: T = T_Active + T_Residual
    /// Recombines GPU active tensor with Host RAM residual stream upon local gate activation
    void reconstruct_tensor(const std::vector<ComplexFixed>& active_tensor,
                            const ResidualChunk& residual,
                            std::vector<ComplexFixed>& out_full) const;

    /// @brief Store residual chunk into Host RAM repository
    void store_residual(uint32_t site_id, ResidualChunk chunk);

    /// @brief Retrieve residual chunk for site
    const ResidualChunk* get_residual(uint32_t site_id) const;

    /// @brief Check if site has an active residual chunk
    bool has_residual(uint32_t site_id) const;

    /// @brief Evict residual chunk from Host RAM
    void drop_residual(uint32_t site_id);

    /// @brief Total bytes consumed by residual streams in Host RAM
    size_t get_total_host_ram_bytes() const;

    /// @brief Clear all residual streams
    void clear();

private:
    std::unordered_map<uint32_t, ResidualChunk> m_residuals;
};

} // namespace cq_hecs
