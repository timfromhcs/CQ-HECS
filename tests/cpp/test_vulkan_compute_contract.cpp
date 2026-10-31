// GPU compute contract: prove that Vulkan dispatches actually execute and that
// fixed-point results read back from device memory match the documented math.
//
// This test uses the real VulkanContext pipelines (no CPU fallback). If no
// Vulkan physical device exists, it exits 77 so CTest can mark it SKIPPED;
// set CQ_REQUIRE_VULKAN=1 to require any Vulkan device (including a software
// ICD such as Lavapipe), or CQ_REQUIRE_HARDWARE_GPU=1 to additionally reject
// software ICDs (used for the local physical-GPU verification run).

#include "cq_hecs/vulkan/vulkan_buffer.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

using namespace cq_hecs;

namespace {

constexpr int kSkip = 77;
constexpr int kFixedOne = 1 << 30;

struct ComplexAmp {
    int32_t real_val;
    int32_t imag_val;
};

bool is_software_device(const std::string& name) {
    std::string lower;
    lower.reserve(name.size());
    for (char c : name) {
        lower.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    return lower.find("lavapipe") != std::string::npos ||
           lower.find("llvmpipe") != std::string::npos ||
           lower.find("swiftshader") != std::string::npos;
}

bool allocate_host_visible(VulkanContext& ctx, VulkanBuffer& buffer, size_t bytes) {
    return buffer.allocate(ctx.get_device(),
                           ctx.get_physical_device(),
                           static_cast<VkDeviceSize>(bytes),
                           VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
                           VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT |
                               VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
                           ctx.get_memory_manager());
}

bool expect_int(const char* what, int32_t actual, int32_t expected, int line) {
    if (actual == expected) return true;
    std::cerr << "FAIL line " << line << ": " << what << " expected " << expected
              << ", got " << actual << "\n";
    return false;
}

bool test_state_reset(VulkanContext& ctx) {
    constexpr uint32_t kElements = 4; // two sites, |0> and |1> per site
    VulkanBuffer buffer;
    if (!allocate_host_visible(ctx, buffer, kElements * sizeof(ComplexAmp))) {
        std::cerr << "FAIL: state_reset buffer allocation\n";
        return false;
    }

    std::vector<ComplexAmp> initial(kElements, ComplexAmp{123, 456});
    buffer.copy_to_buffer(initial.data(), initial.size() * sizeof(ComplexAmp));

    if (!ctx.dispatch_state_reset(buffer, kElements, /*target_basis=*/1)) {
        std::cerr << "FAIL: dispatch_state_reset returned false\n";
        return false;
    }

    std::vector<ComplexAmp> got(kElements);
    buffer.copy_from_buffer(got.data(), got.size() * sizeof(ComplexAmp));

    bool ok = true;
    // Even indices are |0>, odd indices are |1> per site.
    ok &= expect_int("reset site0 |0> real", got[0].real_val, 0, __LINE__);
    ok &= expect_int("reset site0 |0> imag", got[0].imag_val, 0, __LINE__);
    ok &= expect_int("reset site0 |1> real", got[1].real_val, kFixedOne, __LINE__);
    ok &= expect_int("reset site0 |1> imag", got[1].imag_val, 0, __LINE__);
    ok &= expect_int("reset site1 |0> real", got[2].real_val, 0, __LINE__);
    ok &= expect_int("reset site1 |1> real", got[3].real_val, kFixedOne, __LINE__);
    std::cout << (ok ? "PASS" : "FAIL") << " state_reset on GPU\n";
    return ok;
}

bool test_cordic_phase_and_pauli_x(VulkanContext& ctx) {
    constexpr uint32_t kAngle = 0x40000000u; // pi/2 in Z_{2^32}
    VulkanBuffer buffer;
    if (!allocate_host_visible(ctx, buffer, 2 * sizeof(ComplexAmp))) {
        std::cerr << "FAIL: cordic buffer allocation\n";
        return false;
    }

    std::vector<ComplexAmp> initial = {
        {kFixedOne, 0}, // |0> = 1
        {0, 0},         // |1> = 0
    };
    buffer.copy_to_buffer(initial.data(), initial.size() * sizeof(ComplexAmp));

    // Phase-shift one amplitude by pi/2. The CORDIC shader also implements an
    // inverse mode; run it after the forward pass to check readback coherence.
    if (!ctx.dispatch_cordic(buffer, /*gate_type=*/0, kAngle, /*is_inverse=*/0,
                             /*total_pairs=*/1)) {
        std::cerr << "FAIL: dispatch_cordic phase shift returned false\n";
        return false;
    }

    std::vector<ComplexAmp> rotated(2);
    buffer.copy_from_buffer(rotated.data(), rotated.size() * sizeof(ComplexAmp));
    bool ok = true;
    ok &= expect_int("cordic pi/2 real", rotated[0].real_val, 0, __LINE__);
    ok &= expect_int("cordic pi/2 imag", rotated[0].imag_val, kFixedOne, __LINE__);

    if (!ctx.dispatch_cordic(buffer, 0, kAngle, /*is_inverse=*/1, 1)) {
        std::cerr << "FAIL: dispatch_cordic inverse returned false\n";
        return false;
    }
    std::vector<ComplexAmp> restored(2);
    buffer.copy_from_buffer(restored.data(), restored.size() * sizeof(ComplexAmp));
    ok &= expect_int("cordic inverse real", restored[0].real_val, kFixedOne, __LINE__);
    ok &= expect_int("cordic inverse imag", restored[0].imag_val, 0, __LINE__);

    // Pauli X swaps the two amplitudes. The shader consumes one pair per
    // invocation, so total_pairs=1 covers both entries.
    std::vector<ComplexAmp> basis = {{kFixedOne, 0}, {0, 0}};
    buffer.copy_to_buffer(basis.data(), basis.size() * sizeof(ComplexAmp));
    if (!ctx.dispatch_cordic(buffer, /*gate_type=*/1, 0, 0, /*total_pairs=*/1)) {
        std::cerr << "FAIL: dispatch_cordic Pauli X returned false\n";
        return false;
    }
    std::vector<ComplexAmp> flipped(2);
    buffer.copy_from_buffer(flipped.data(), flipped.size() * sizeof(ComplexAmp));
    ok &= expect_int("pauli_x |0> real", flipped[0].real_val, 0, __LINE__);
    ok &= expect_int("pauli_x |1> real", flipped[1].real_val, kFixedOne, __LINE__);

    std::cout << (ok ? "PASS" : "FAIL") << " cordic phase/Pauli-X on GPU\n";
    return ok;
}

bool test_tensor_contract(VulkanContext& ctx) {
    constexpr uint32_t M = 2;
    constexpr uint32_t K = 3;
    constexpr uint32_t N = 2;

    // Exact binary fractions keep every Q30 product representable.
    const std::vector<ComplexAmp> a = {
        {kFixedOne, 0},          {kFixedOne / 2, 0}, {kFixedOne / 4, 0},
        {kFixedOne / 4, 0},      {kFixedOne, 0},     {kFixedOne / 2, 0},
    };
    const std::vector<ComplexAmp> b = {
        {kFixedOne / 2, 0}, {kFixedOne / 4, 0},
        {kFixedOne, 0},     {kFixedOne / 2, 0},
        {kFixedOne / 2, 0}, {0, 0},
    };
    const std::vector<ComplexAmp> expected = {
        // C = A * B in Q30
        {kFixedOne + kFixedOne / 8, 0},       // 1.125
        {kFixedOne / 2, 0},                   // 0.5
        {kFixedOne + kFixedOne / 4 + kFixedOne / 8, 0}, // 1.375
        {kFixedOne / 2 + kFixedOne / 16, 0},  // 0.5625
    };

    VulkanBuffer buf_a, buf_b, buf_c;
    if (!allocate_host_visible(ctx, buf_a, a.size() * sizeof(ComplexAmp)) ||
        !allocate_host_visible(ctx, buf_b, b.size() * sizeof(ComplexAmp)) ||
        !allocate_host_visible(ctx, buf_c, expected.size() * sizeof(ComplexAmp))) {
        std::cerr << "FAIL: tensor contract buffer allocation\n";
        return false;
    }
    buf_a.copy_to_buffer(a.data(), a.size() * sizeof(ComplexAmp));
    buf_b.copy_to_buffer(b.data(), b.size() * sizeof(ComplexAmp));
    std::vector<ComplexAmp> zero(expected.size(), ComplexAmp{0, 0});
    buf_c.copy_to_buffer(zero.data(), zero.size() * sizeof(ComplexAmp));

    if (!ctx.dispatch_tensor_contract(buf_a, buf_b, buf_c, M, K, N)) {
        std::cerr << "FAIL: dispatch_tensor_contract returned false\n";
        return false;
    }

    std::vector<ComplexAmp> got(expected.size());
    buf_c.copy_from_buffer(got.data(), got.size() * sizeof(ComplexAmp));
    bool ok = true;
    for (size_t i = 0; i < expected.size(); ++i) {
        ok &= expect_int("contract real", got[i].real_val, expected[i].real_val, __LINE__);
        ok &= expect_int("contract imag", got[i].imag_val, expected[i].imag_val, __LINE__);
    }
    std::cout << (ok ? "PASS" : "FAIL") << " tensor contract on GPU\n";
    return ok;
}

// CPU reference for the OMNIWAVE BCP pass (same contract as
// cqhecs.omniwave.bcp.evaluate_batch): 0 SAT, 1 CONFLICT, 2|(code<<2) UNIT, 3 OPEN.
uint32_t bcp_reference(const std::vector<uint32_t>& offsets, const std::vector<uint32_t>& codes,
                       const std::vector<uint32_t>& assigned, const std::vector<uint32_t>& values,
                       uint32_t words, uint32_t front, uint32_t clause) {
    uint32_t open = 0, unit = 0;
    for (uint32_t i = offsets[clause]; i < offsets[clause + 1]; ++i) {
        uint32_t code = codes[i], v = code >> 1, w = front * words + (v >> 5), bit = 1u << (v & 31u);
        if ((assigned[w] & bit) == 0) { ++open; unit = code; continue; }
        bool val = (values[w] & bit) != 0;
        if (val != ((code & 1u) == 1u)) return 0u;
    }
    if (open == 0) return 1u;
    if (open == 1) return 2u | (unit << 2);
    return 3u;
}

bool test_omniwave_bcp(VulkanContext& ctx) {
    // 40 variables (two words), 300 clauses, 97 fronts from a fixed LCG.
    const uint32_t vars = 40, num_clauses = 300, fronts = 97, words = 2;
    uint32_t state = 12345u;
    auto next = [&]() { state = state * 1103515245u + 12345u; return (state >> 8) & 0xFFFFFFu; };
    std::vector<uint32_t> offsets{0}, codes;
    for (uint32_t c = 0; c < num_clauses; ++c) {
        uint32_t len = 1 + next() % 4;
        for (uint32_t k = 0; k < len; ++k) codes.push_back(2 * (next() % vars) + (next() & 1u));
        offsets.push_back(static_cast<uint32_t>(codes.size()));
    }
    std::vector<uint32_t> assigned(fronts * words), values(fronts * words);
    for (uint32_t f = 0; f < fronts; ++f) {
        for (uint32_t w = 0; w < words; ++w) {
            uint32_t mask = w == 1 ? 0xFFu : 0xFFFFFFFFu;  // only 40 variables exist
            assigned[f * words + w] = (next() | (next() << 16)) & mask;
            values[f * words + w] = (next() | (next() << 16)) & mask;
        }
    }
    VulkanBuffer b_off, b_codes, b_assigned, b_values, b_status;
    if (!allocate_host_visible(ctx, b_off, offsets.size() * 4) ||
        !allocate_host_visible(ctx, b_codes, codes.size() * 4) ||
        !allocate_host_visible(ctx, b_assigned, assigned.size() * 4) ||
        !allocate_host_visible(ctx, b_values, values.size() * 4) ||
        !allocate_host_visible(ctx, b_status, fronts * num_clauses * 4)) {
        std::cerr << "FAIL: omniwave buffer allocation\n";
        return false;
    }
    b_off.copy_to_buffer(offsets.data(), offsets.size() * 4);
    b_codes.copy_to_buffer(codes.data(), codes.size() * 4);
    b_assigned.copy_to_buffer(assigned.data(), assigned.size() * 4);
    b_values.copy_to_buffer(values.data(), values.size() * 4);
    if (!ctx.dispatch_omniwave_bcp(b_off, b_codes, b_assigned, b_values, b_status, num_clauses, fronts, words)) {
        std::cerr << "FAIL: dispatch_omniwave_bcp returned false\n";
        return false;
    }
    std::vector<uint32_t> got(fronts * num_clauses);
    b_status.copy_from_buffer(got.data(), got.size() * 4);
    uint32_t mismatches = 0, kinds[4] = {0, 0, 0, 0};
    for (uint32_t f = 0; f < fronts; ++f) {
        for (uint32_t c = 0; c < num_clauses; ++c) {
            uint32_t want = bcp_reference(offsets, codes, assigned, values, words, f, c);
            ++kinds[want & 3u];
            if (got[f * num_clauses + c] != want) ++mismatches;
        }
    }
    bool every_kind = kinds[0] && kinds[1] && kinds[2] && kinds[3];
    bool ok = mismatches == 0 && every_kind;
    std::cout << (ok ? "PASS" : "FAIL") << " omniwave BCP on GPU (" << fronts * num_clauses
              << " cells, " << mismatches << " mismatches, SAT/CONFLICT/UNIT/OPEN = " << kinds[0] << "/"
              << kinds[1] << "/" << kinds[2] << "/" << kinds[3] << ")\n";
    return ok;
}

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

} // namespace

int main() {
    const bool require_hardware = env_flag("CQ_REQUIRE_HARDWARE_GPU");
    const bool require_vulkan = require_hardware || env_flag("CQ_REQUIRE_VULKAN");

    VulkanContext ctx;
    if (!ctx.initialize()) {
        if (require_vulkan) {
            std::cerr << "FAIL: CQ_REQUIRE_VULKAN/CQ_REQUIRE_HARDWARE_GPU is set "
                         "but VulkanContext initialization failed\n";
            return 1;
        }
        std::cout << "SKIP: no usable Vulkan device (set CQ_REQUIRE_VULKAN=1 to "
                     "require a Vulkan device, or CQ_REQUIRE_HARDWARE_GPU=1 to "
                     "require physical hardware)\n";
        return kSkip;
    }

    const std::string device = ctx.get_device_name();
    const bool software = is_software_device(device) || ctx.is_lavapipe_emulation();
    std::cout << "Vulkan device: " << device
              << (software ? " (software ICD)" : " (hardware)")
              << ", lavapipe=" << (ctx.is_lavapipe_emulation() ? "true" : "false")
              << "\n";

    if (software && require_hardware) {
        std::cerr << "FAIL: CQ_REQUIRE_HARDWARE_GPU is set but the selected "
                     "Vulkan device is a software ICD\n";
        return 1;
    }

    bool ok = true;
    ok &= test_state_reset(ctx);
    ok &= test_cordic_phase_and_pauli_x(ctx);
    ok &= test_tensor_contract(ctx);
    ok &= test_omniwave_bcp(ctx);

    if (!ok) {
        std::cerr << "Vulkan GPU compute contract FAILED\n";
        return 1;
    }
    std::cout << "PASS: Vulkan GPU compute contract\n";
    return 0;
}
