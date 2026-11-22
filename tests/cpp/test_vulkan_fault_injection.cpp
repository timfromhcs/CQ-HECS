// VkResult fault-injection tests (AGENTS_V7 W4-17).
//
// Modes (argv[1]):
//   init    needs no GPU: injected failures during instance creation/enumeration.
//   device  needs a Vulkan device (hardware or a software ICD): injected failures
//           at every checked call of the dispatch and buffer paths, device-loss
//           latching, no resource leak after failures, recovery after teardown.
//           Exits 77 (CTest SKIPPED) when no device exists, never 0.
//
// Faults are injected through cq_hecs::vkfault, which fails the NEXT call at a
// site with a chosen VkResult WITHOUT executing the real call. This makes OOM and
// DEVICE_LOST deterministic on any machine. Nothing here is a GPU-speed claim.
#include "cq_hecs/vulkan/vk_fault.hpp"
#include "cq_hecs/vulkan/vulkan_buffer.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

using namespace cq_hecs;
using vkfault::Site;

namespace {

int g_failures = 0;

void check(bool ok, const char* what, int line) {
    if (!ok) {
        std::fprintf(stderr, "FAIL line %d: %s\n", line, what);
        ++g_failures;
    }
}
#define CHECK(cond) check((cond), #cond, __LINE__)

struct Amp {
    int32_t re;
    int32_t im;
};

bool env_flag(const char* name) {
#ifdef _MSC_VER
    char* value = nullptr;
    size_t length = 0;
    if (_dupenv_s(&value, &length, name) != 0 || value == nullptr) return false;
    const bool enabled = value[0] != '\0';
    std::free(value);
    return enabled;
#else
    const char* value = std::getenv(name);
    return value != nullptr && value[0] != '\0';
#endif
}

bool alloc(VulkanContext& ctx, VulkanBuffer& b, size_t bytes) {
    return b.allocate(ctx.get_device(), ctx.get_physical_device(), static_cast<VkDeviceSize>(bytes),
                      VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                      VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                      ctx.get_memory_manager());
}

constexpr uint32_t kElements = 4;

// One state-reset dispatch on a freshly filled buffer; returns the dispatch status
// and the buffer content read back (sentinel-initialised, so "not run" is visible).
bool reset_dispatch(VulkanContext& ctx, std::vector<Amp>& out) {
    VulkanBuffer buf;
    if (!alloc(ctx, buf, kElements * sizeof(Amp))) return false;
    std::vector<Amp> init(kElements, Amp{123, 456});
    if (!buf.copy_to_buffer(init.data(), init.size() * sizeof(Amp))) return false;
    const bool ok = ctx.dispatch_state_reset(buf, kElements, 1);
    out.assign(kElements, Amp{-1, -1});
    if (!buf.copy_from_buffer(out.data(), out.size() * sizeof(Amp))) return false;
    return ok;
}

int run_init() {
    // 1. Instance creation failure: initialize() must fail cleanly and say why.
    {
        VulkanContext ctx;
        vkfault::disarm_all();
        vkfault::arm(Site::CreateInstance, VK_ERROR_INCOMPATIBLE_DRIVER);
        CHECK(!ctx.initialize());
        CHECK(vkfault::hits(Site::CreateInstance) == 1);
        CHECK(!ctx.is_initialized());
        CHECK(ctx.last_result() == VK_ERROR_INCOMPATIBLE_DRIVER);
        CHECK(ctx.get_device() == VK_NULL_HANDLE);
        vkfault::disarm_all();
    }
    // 2. Physical-device enumeration failure. Needs a real instance; if the loader
    //    has no driver at all the instance step fails first and this case is NOT_RUN.
    {
        VulkanContext ctx;
        vkfault::disarm_all();
        vkfault::arm(Site::EnumeratePhysicalDevices, VK_ERROR_INITIALIZATION_FAILED);
        const bool ok = ctx.initialize();
        if (vkfault::hits(Site::EnumeratePhysicalDevices) == 0) {
            std::printf("NOT_RUN: enumeration fault (no Vulkan instance could be created here)\n");
        } else {
            CHECK(!ok);
            CHECK(!ctx.is_initialized());
            CHECK(ctx.last_result() == VK_ERROR_INITIALIZATION_FAILED);
        }
        vkfault::disarm_all();
    }
    // 3. The fault table is inert when nothing is armed.
    {
        VkResult r = VK_SUCCESS;
        CHECK(!vkfault::consume(Site::QueueSubmit, r));
        vkfault::arm(Site::QueueSubmit, VK_ERROR_DEVICE_LOST, 2, 1);  // pass 1, fail 2
        CHECK(!vkfault::consume(Site::QueueSubmit, r));
        CHECK(vkfault::consume(Site::QueueSubmit, r) && r == VK_ERROR_DEVICE_LOST);
        CHECK(vkfault::consume(Site::QueueSubmit, r));
        CHECK(!vkfault::consume(Site::QueueSubmit, r));
        vkfault::disarm_all();
    }
    // 4. A buffer cannot be allocated on a null device, nor with size 0.
    {
        VulkanMemoryManager mm;
        VulkanBuffer b;
        CHECK(!b.allocate(VK_NULL_HANDLE, VK_NULL_HANDLE, 64, VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                          VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT, mm));
        CHECK(mm.get_allocated_bytes() == 0);
        CHECK(!b.copy_to_buffer(nullptr, 4));
        char tmp[4] = {0};
        CHECK(!b.copy_from_buffer(tmp, 4));  // invalid buffer: false, no crash
    }
    if (g_failures) return 1;
    std::printf("PASS: Vulkan fault injection (init)\n");
    return 0;
}

// Every checked dispatch-path site, failed with an ordinary error. After each
// failure the context must remain fully usable (no leaked descriptor set or
// command buffer: the pool holds 64 sets, so 100 failures would exhaust it).
void dispatch_site_sweep(VulkanContext& ctx, const std::vector<Amp>& baseline) {
    const Site sites[] = {Site::AllocateDescriptorSets, Site::AllocateCommandBuffers, Site::BeginCommandBuffer,
                          Site::EndCommandBuffer, Site::QueueSubmit, Site::QueueWaitIdle};
    for (Site site : sites) {
        for (int i = 0; i < 100; ++i) {
            vkfault::arm(site, VK_ERROR_OUT_OF_DEVICE_MEMORY);
            std::vector<Amp> got;
            const bool ok = reset_dispatch(ctx, got);
            if (ok || vkfault::hits(site) != 1 || ctx.last_result() != VK_ERROR_OUT_OF_DEVICE_MEMORY ||
                ctx.is_device_lost()) {
                CHECK(!ok);
                CHECK(vkfault::hits(site) == 1);
                CHECK(ctx.last_result() == VK_ERROR_OUT_OF_DEVICE_MEMORY);
                CHECK(!ctx.is_device_lost());  // OOM is recoverable, not device loss
                std::fprintf(stderr, "  (site %d iteration %d)\n", static_cast<int>(site), i);
                break;
            }
        }
        vkfault::disarm_all();
        std::vector<Amp> got;
        const bool recovered = reset_dispatch(ctx, got);
        CHECK(recovered);
        CHECK(ctx.last_result() == VK_SUCCESS);
        CHECK(std::memcmp(got.data(), baseline.data(), got.size() * sizeof(Amp)) == 0);
    }
}

void device_lost_latch(VulkanContext& ctx, const std::vector<Amp>& baseline) {
    vkfault::disarm_all();
    vkfault::arm(Site::QueueWaitIdle, VK_ERROR_DEVICE_LOST);
    std::vector<Amp> got;
    CHECK(!reset_dispatch(ctx, got));
    CHECK(ctx.is_device_lost());
    CHECK(ctx.last_result() == VK_ERROR_DEVICE_LOST);

    // Latched: the next dispatch must fail fast WITHOUT calling into Vulkan. Arm a
    // submit fault and verify it is never consumed.
    vkfault::arm(Site::QueueSubmit, VK_ERROR_OUT_OF_DEVICE_MEMORY);
    CHECK(!reset_dispatch(ctx, got));
    CHECK(vkfault::hits(Site::QueueSubmit) == 0);
    CHECK(ctx.is_device_lost());
    vkfault::disarm_all();

    // Teardown and re-creation recovers: the latch is cleared and results are
    // identical to the pre-loss baseline.
    ctx.cleanup();
    CHECK(!ctx.is_device_lost());
    CHECK(ctx.initialize());
    CHECK(reset_dispatch(ctx, got));
    CHECK(std::memcmp(got.data(), baseline.data(), got.size() * sizeof(Amp)) == 0);

    // Device loss injected at submit (rather than at wait) latches the same way.
    vkfault::arm(Site::QueueSubmit, VK_ERROR_DEVICE_LOST);
    CHECK(!reset_dispatch(ctx, got));
    CHECK(ctx.is_device_lost());
    vkfault::disarm_all();
    ctx.cleanup();  // must not hang or crash on a context that saw device loss
    CHECK(ctx.initialize());
    CHECK(reset_dispatch(ctx, got));
}

void buffer_failures(VulkanContext& ctx) {
    VulkanMemoryManager& mm = ctx.get_memory_manager();
    VulkanBuffer keep;
    CHECK(alloc(ctx, keep, 256));
    const size_t base = mm.get_allocated_bytes();
    CHECK(base >= 256);

    const Site sites[] = {Site::CreateBuffer, Site::AllocateMemory, Site::BindBufferMemory};
    for (Site site : sites) {
        vkfault::arm(site, VK_ERROR_OUT_OF_DEVICE_MEMORY);
        {
            VulkanBuffer b;
            CHECK(!alloc(ctx, b, 128));
            CHECK(vkfault::hits(site) == 1);
            CHECK(!b.is_valid());
            // The failed allocation must have returned exactly what it tracked: a
            // double release here would wrongly shrink the accounted total.
            CHECK(mm.get_allocated_bytes() == base);
        }
        CHECK(mm.get_allocated_bytes() == base);
        vkfault::disarm_all();
    }

    // Map failure: the transfer is reported as failed, never as success.
    {
        VulkanBuffer b;
        CHECK(alloc(ctx, b, 64));
        std::vector<uint32_t> data(16, 0xABCDu);
        vkfault::arm(Site::MapMemory, VK_ERROR_MEMORY_MAP_FAILED);
        CHECK(!b.copy_to_buffer(data.data(), 64));
        CHECK(vkfault::hits(Site::MapMemory) == 1);
        vkfault::disarm_all();
        CHECK(b.copy_to_buffer(data.data(), 64));
        std::vector<uint32_t> back(16, 0);
        CHECK(b.copy_from_buffer(back.data(), 64));
        CHECK(back == data);
        CHECK(!b.copy_to_buffer(data.data(), 65));   // larger than the buffer
        CHECK(!b.copy_from_buffer(back.data(), 65));
        CHECK(!b.copy_to_buffer(nullptr, 4));
    }

    // The 3 GB governor reports a failed allocation (no exception across the
    // C ABI) and leaves the accounting untouched.
    {
        VulkanBuffer huge;
        bool threw = false;
        bool ok = true;
        try {
            ok = alloc(ctx, huge, VulkanMemoryManager::VRAM_HARD_CEILING_BYTES + 1);
        } catch (...) {
            threw = true;
        }
        CHECK(!threw);
        CHECK(!ok);
        CHECK(mm.get_allocated_bytes() == base);
        VulkanBuffer zero;
        CHECK(!alloc(ctx, zero, 0));
    }
    keep.release();
    CHECK(mm.get_allocated_bytes() == base - 256);
}

int run_device() {
    VulkanContext ctx;
    vkfault::disarm_all();
    if (!ctx.initialize()) {
        if (env_flag("CQ_REQUIRE_VULKAN") || env_flag("CQ_REQUIRE_HARDWARE_GPU")) {
            std::fprintf(stderr, "FAIL: CQ_REQUIRE_VULKAN set but no Vulkan device initialised\n");
            return 1;
        }
        std::printf("SKIP (NOT_RUN): no usable Vulkan device; device fault-injection cases did not run\n");
        return 77;
    }
    std::printf("Vulkan device: %s%s\n", ctx.get_device_name().c_str(),
                ctx.is_lavapipe_emulation() ? " (software ICD)" : " (hardware)");

    std::vector<Amp> baseline;
    CHECK(reset_dispatch(ctx, baseline));
    CHECK(baseline[0].re != 123);  // the kernel really ran and rewrote the buffer

    dispatch_site_sweep(ctx, baseline);
    buffer_failures(ctx);
    device_lost_latch(ctx, baseline);

    vkfault::disarm_all();
    if (g_failures) {
        std::fprintf(stderr, "test_vulkan_fault_injection(device): %d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("PASS: Vulkan fault injection (device)\n");
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string mode = argc > 1 ? argv[1] : "init";
    if (mode == "init") return run_init();
    if (mode == "device") return run_device();
    std::fprintf(stderr, "usage: test_vulkan_fault_injection [init|device]\n");
    return 2;
}
