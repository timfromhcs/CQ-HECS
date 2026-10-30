// Vulkan device-selection policy (GEMINI.md 3.7), testable without a driver.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <iostream>

#include "cq_hecs/vulkan/device_policy.hpp"

using namespace cq_hecs;

int main() {
    const DeviceDescription lavapipe{"llvmpipe (LLVM 17.0.6, 256 bits)", DeviceKind::Software, 0x10005, 0, 1, 1};
    const DeviceDescription igpu{"AMD Radeon(TM) Graphics", DeviceKind::Integrated, 0x1002, 0x1636, 2, 2};
    const DeviceDescription dgpu{"NVIDIA GeForce RTX 4090", DeviceKind::Discrete, 0x10de, 0x2684, 3, 3};
    const DeviceDescription named_cpu{"SwiftShader Device", DeviceKind::Other, 0x1ae0, 0, 4, 4};

    // No device at all.
    assert(choose_device({}, "").index == -1);
    // Automatic ranking: discrete > integrated > software > other.
    assert(choose_device({lavapipe, igpu, dgpu}, "").index == 2);
    assert(choose_device({lavapipe, igpu}, "").index == 1);
    assert(choose_device({lavapipe}, "").index == 0);
    // A software rasteriser reported as "other" is still ranked as software.
    const DeviceDescription unknown{"Mystery", DeviceKind::Other, 0, 0, 0, 0};
    assert(choose_device({unknown, named_cpu}, "").index == 1);
    // Explicit requests: index or case-insensitive name, never a fallback.
    assert(choose_device({lavapipe, igpu, dgpu}, "0").index == 0);
    assert(choose_device({lavapipe, igpu, dgpu}, "radeon").index == 1);
    const DeviceChoice missing = choose_device({lavapipe}, "nvidia");
    assert(missing.index == -1 && missing.reason.find("no fallback") != std::string::npos);
    const DeviceChoice out_of_range = choose_device({lavapipe}, "3");
    assert(out_of_range.index == -1 && out_of_range.reason.find("no fallback") != std::string::npos);
    std::cout << ">>> [PASS] Vulkan device policy: ranking, explicit selection, no fallback.\n";
    return 0;
}
