#pragma once
// Vulkan physical-device selection policy (GEMINI.md 3.7).
//
// Pure function over device descriptions so the policy is testable without a
// Vulkan driver. Rules:
//   * without a request: discrete GPU > integrated GPU > software rasteriser
//     (lavapipe/llvmpipe/SwiftShader by name, or VK_PHYSICAL_DEVICE_TYPE_CPU)
//     > other; ties keep enumeration order;
//   * with a request (CQ_HECS_VULKAN_DEVICE=<index>|<name substring>): exactly
//     that device or nothing. A request never falls back to another device.
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <string>
#include <vector>

namespace cq_hecs {

enum class DeviceKind { Discrete, Integrated, Software, Other };

struct DeviceDescription {
    std::string name;
    DeviceKind kind = DeviceKind::Other;
    uint32_t vendor_id = 0;
    uint32_t device_id = 0;
    uint32_t driver_version = 0;
    uint32_t api_version = 0;
};

struct DeviceChoice {
    int index = -1;          // -1: no device selected
    std::string reason;      // why this device, or why none
};

inline std::string lower_copy(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return text;
}

inline bool is_software_name(const std::string& name) {
    const std::string lower = lower_copy(name);
    return lower.find("lavapipe") != std::string::npos ||
           lower.find("llvmpipe") != std::string::npos ||
           lower.find("swiftshader") != std::string::npos;
}

inline const char* kind_name(DeviceKind kind) {
    switch (kind) {
        case DeviceKind::Discrete: return "discrete-gpu";
        case DeviceKind::Integrated: return "integrated-gpu";
        case DeviceKind::Software: return "software";
        default: return "other";
    }
}

inline int automatic_rank(const DeviceDescription& d) {
    if (d.kind == DeviceKind::Software || is_software_name(d.name)) return 1;
    switch (d.kind) {
        case DeviceKind::Discrete: return 3;
        case DeviceKind::Integrated: return 2;
        default: return 0;
    }
}

inline DeviceChoice choose_device(const std::vector<DeviceDescription>& devices, const std::string& request) {
    DeviceChoice choice;
    if (devices.empty()) {
        choice.reason = "no Vulkan physical device was enumerated";
        return choice;
    }
    if (!request.empty()) {
        const bool numeric = std::all_of(request.begin(), request.end(),
                                         [](unsigned char c) { return std::isdigit(c) != 0; });
        if (numeric && request.size() < 10) {
            const unsigned long wanted = std::stoul(request);
            if (wanted < devices.size()) {
                choice.index = static_cast<int>(wanted);
                choice.reason = "requested by index " + request;
            } else {
                choice.reason = "requested index " + request + " but only " +
                                std::to_string(devices.size()) + " device(s) exist; no fallback";
            }
            return choice;
        }
        const std::string needle = lower_copy(request);
        for (size_t i = 0; i < devices.size(); ++i) {
            if (lower_copy(devices[i].name).find(needle) != std::string::npos) {
                choice.index = static_cast<int>(i);
                choice.reason = "requested by name '" + request + "'";
                return choice;
            }
        }
        choice.reason = "no device name contains '" + request + "'; no fallback";
        return choice;
    }
    int best_rank = -1;
    for (size_t i = 0; i < devices.size(); ++i) {
        const int rank = automatic_rank(devices[i]);
        if (rank > best_rank) {
            best_rank = rank;
            choice.index = static_cast<int>(i);
        }
    }
    choice.reason = std::string("automatic: highest-ranked ") +
                    (automatic_rank(devices[choice.index]) == 1 ? "software" : kind_name(devices[choice.index].kind)) +
                    " device";
    return choice;
}

}  // namespace cq_hecs
