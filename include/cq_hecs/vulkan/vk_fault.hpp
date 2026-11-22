#pragma once
// Vulkan fault-injection seam (AGENTS_V7 W4-17).
//
// Every fallible Vulkan call made by VulkanContext / VulkanBuffer goes through
// vkfault::call(Site, ...). In normal operation this is one relaxed atomic load
// per call (negligible next to a GPU round trip). Tests arm a site to make the
// NEXT call(s) return a chosen VkResult WITHOUT executing the real call, so the
// failure path is exercised deterministically (out of memory, device lost,
// submit failure, ...) on any machine, including ones with a working GPU.
//
// The seam is a C++ test facility. It is deliberately NOT exported through the
// C ABI and nothing arms it unless a test calls vkfault::arm().
#include <vulkan/vulkan.h>
#include <atomic>
#include <cstdint>

namespace cq_hecs {
namespace vkfault {

enum class Site : int {
    CreateInstance = 0,
    EnumeratePhysicalDevices,
    CreateDevice,
    CreateCommandPool,
    CreateDescriptorPool,
    CreateBuffer,
    AllocateMemory,
    BindBufferMemory,
    MapMemory,
    AllocateDescriptorSets,
    AllocateCommandBuffers,
    BeginCommandBuffer,
    EndCommandBuffer,
    QueueSubmit,
    QueueWaitIdle,
    Count
};

struct Slot {
    std::atomic<int> remaining{0};  // number of calls still to fail
    std::atomic<int> skip{0};       // number of calls to let through first
    std::atomic<int> result{VK_SUCCESS};
    std::atomic<int> hits{0};       // calls that were failed by injection
};

inline Slot* slots() {
    static Slot table[static_cast<int>(Site::Count)];
    return table;
}

/// Make `count` calls at `site` fail with `result`, after letting `skip` calls through.
inline void arm(Site site, VkResult result, int count = 1, int skip = 0) {
    Slot& s = slots()[static_cast<int>(site)];
    s.result.store(static_cast<int>(result));
    s.skip.store(skip);
    s.hits.store(0);
    s.remaining.store(count);
}

inline void disarm_all() {
    for (int i = 0; i < static_cast<int>(Site::Count); ++i) {
        slots()[i].remaining.store(0);
        slots()[i].skip.store(0);
    }
}

inline int hits(Site site) { return slots()[static_cast<int>(site)].hits.load(); }

/// True when this call must be failed; `out` receives the injected result.
inline bool consume(Site site, VkResult& out) {
    Slot& s = slots()[static_cast<int>(site)];
    if (s.remaining.load(std::memory_order_relaxed) <= 0) return false;
    if (s.skip.load() > 0) {
        s.skip.fetch_sub(1);
        return false;
    }
    if (s.remaining.fetch_sub(1) <= 0) return false;
    s.hits.fetch_add(1);
    out = static_cast<VkResult>(s.result.load());
    return true;
}

/// Run `fn` (returning VkResult) unless an injected fault claims the call.
template <class F>
inline VkResult call(Site site, F&& fn) {
    VkResult injected = VK_SUCCESS;
    if (consume(site, injected)) return injected;
    return fn();
}

}  // namespace vkfault
}  // namespace cq_hecs
