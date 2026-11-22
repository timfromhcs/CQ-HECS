// CPU-vs-Vulkan differential test for the shared OMNIWAVE BCP kernel
// (AGENTS_V7 T6-04) plus the C-ABI validation and teardown/device-loss paths of
// cq_omniwave_bcp_eval (W4-17/W4-18).
//
// The CPU reference below mirrors cqhecs.omniwave.bcp.evaluate_batch exactly
// (status word: 0 SAT, 1 CONFLICT, 2|(code<<2) UNIT, 3 OPEN). The GPU result must
// be BIT-IDENTICAL; any mismatch is a hard failure, never a tolerance.
//
// Modes (argv[1]):
//   validate  needs no GPU: malformed input is rejected before any device work.
//   device    needs a Vulkan device (hardware or software ICD). Exits 77
//             (CTest SKIPPED) if none exists; never reports PASS without a device.
//
// This is a correctness test. It makes no performance claim: GPU speed is measured
// end-to-end (with transfers) by scripts/omniwave_benchmark.py, not here.
#include "cq_hecs_api.h"
#include "cq_hecs/vulkan/vk_fault.hpp"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

using cq_hecs::vkfault::Site;

namespace {

int g_failures = 0;

void check(bool ok, const char* what, int line) {
    if (!ok) {
        std::fprintf(stderr, "FAIL line %d: %s\n", line, what);
        ++g_failures;
    }
}
#define CHECK(cond) check((cond), #cond, __LINE__)

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

struct Rng {
    uint64_t s;
    explicit Rng(uint64_t seed) : s(seed * 0x9E3779B97F4A7C15ull + 0x1234567ull) {}
    uint32_t next() {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        return static_cast<uint32_t>(s >> 11);
    }
    uint32_t below(uint32_t n) { return n ? next() % n : 0; }
};

struct Case {
    std::vector<uint32_t> offsets, codes, assigned, values;
    uint32_t num_clauses = 0, num_fronts = 0, words = 0;
};

uint32_t reference_cell(const Case& c, uint32_t front, uint32_t clause) {
    const uint32_t base = front * c.words;
    uint32_t open_count = 0, unit_code = 0;
    for (uint32_t i = c.offsets[clause]; i < c.offsets[clause + 1]; ++i) {
        const uint32_t code = c.codes[i];
        const uint32_t v = code >> 1;
        const bool negative = (code & 1u) != 0;
        const uint32_t word = base + (v >> 5);
        const uint32_t bit = 1u << (v & 31u);
        if ((c.assigned[word] & bit) == 0) {
            ++open_count;
            unit_code = code;
        } else {
            const bool val = (c.values[word] & bit) != 0;
            if (val != negative) return 0;  // SAT
        }
    }
    if (open_count == 0) return 1;                    // CONFLICT
    if (open_count == 1) return 2u | (unit_code << 2);  // UNIT
    return 3;                                         // OPEN
}

Case make_case(uint64_t seed, uint32_t clauses, uint32_t fronts, uint32_t vars, uint32_t extra_words,
               uint32_t max_len) {
    Rng r(seed);
    Case c;
    c.num_clauses = clauses;
    c.num_fronts = fronts;
    c.words = (vars + 31) / 32 + extra_words;
    c.offsets.push_back(0);
    for (uint32_t k = 0; k < clauses; ++k) {
        const uint32_t len = r.below(max_len + 1);  // includes empty clauses
        for (uint32_t j = 0; j < len; ++j) c.codes.push_back(2 * r.below(vars) + (r.next() & 1u));
        c.offsets.push_back(static_cast<uint32_t>(c.codes.size()));
    }
    c.assigned.resize(static_cast<size_t>(fronts) * c.words);
    c.values.resize(static_cast<size_t>(fronts) * c.words);
    for (uint32_t f = 0; f < fronts; ++f) {
        const uint32_t density = r.below(4);  // none / sparse / dense / all assigned
        for (uint32_t w = 0; w < c.words; ++w) {
            uint32_t a;
            switch (density) {
                case 0: a = 0; break;
                case 1: a = r.next() & r.next() & r.next(); break;
                case 2: a = r.next() | r.next() | r.next(); break;
                default: a = 0xFFFFFFFFu; break;
            }
            c.assigned[f * c.words + w] = a;
            c.values[f * c.words + w] = r.next() ^ (r.next() << 16);  // garbage on unassigned bits on purpose
        }
    }
    return c;
}

int run_gpu(const Case& c, std::vector<uint32_t>& out) {
    out.assign(static_cast<size_t>(c.num_fronts) * c.num_clauses, 0xDEADBEEFu);
    return cq_omniwave_bcp_eval(c.offsets.data(), c.codes.empty() ? nullptr : c.codes.data(), c.num_clauses,
                                c.assigned.data(), c.values.data(), c.num_fronts, c.words, out.data());
}

// Compares every cell to the reference; returns the mismatch count. kinds[] counts
// SAT/CONFLICT/UNIT/OPEN so the test can prove it exercised all four outcomes.
uint64_t compare(const Case& c, const std::vector<uint32_t>& got, uint64_t kinds[4]) {
    uint64_t mismatches = 0;
    for (uint32_t f = 0; f < c.num_fronts; ++f) {
        for (uint32_t k = 0; k < c.num_clauses; ++k) {
            const uint32_t want = reference_cell(c, f, k);
            ++kinds[want & 3u];
            if (got[static_cast<size_t>(f) * c.num_clauses + k] != want) ++mismatches;
        }
    }
    return mismatches;
}

int run_validate() {
    uint32_t off[3] = {0, 1, 2};
    uint32_t codes[2] = {0, 2};
    uint32_t asg[4] = {0, 0, 0, 0}, val[4] = {0, 0, 0, 0};
    uint32_t out[8];
    const uint32_t SENT = 0xA5A5A5A5u;
    for (uint32_t& o : out) o = SENT;

    // Null / zero arguments.
    CHECK(cq_omniwave_bcp_eval(nullptr, codes, 2, asg, val, 1, 1, out) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, nullptr, val, 1, 1, out) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, nullptr, 1, 1, out) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, val, 1, 1, nullptr) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 0, asg, val, 1, 1, out) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, val, 0, 1, out) == 1);
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, val, 1, 0, out) == 1);
    // Size limits (rejected before any array is read or any device is touched).
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, val, 65536, 1, out) == 2);
    CHECK(cq_omniwave_bcp_eval(off, codes, 65535u * 64u + 1u, asg, val, 1, 1, out) == 2);
    CHECK(cq_omniwave_bcp_eval(off, codes, 70000, asg, val, 65535, 1, out) == 2);  // cells > 2^32
    CHECK(cq_omniwave_bcp_eval(off, codes, 2, asg, val, 1, (1u << 20) + 1u, out) == 2);
    // Malformed clause database.
    uint32_t bad0[3] = {1, 1, 2};
    CHECK(cq_omniwave_bcp_eval(bad0, codes, 2, asg, val, 1, 1, out) == 4);  // does not start at 0
    uint32_t bad1[3] = {0, 2, 1};
    CHECK(cq_omniwave_bcp_eval(bad1, codes, 2, asg, val, 1, 1, out) == 4);  // not monotone
    uint32_t oob[2] = {0, 64};  // variable index 32 with words = 1 (variables 0..31)
    CHECK(cq_omniwave_bcp_eval(off, oob, 2, asg, val, 1, 1, out) == 4);
    uint32_t huge[2] = {0, 0xFFFFFFFFu};
    CHECK(cq_omniwave_bcp_eval(off, huge, 2, asg, val, 1, 1, out) == 4);
    CHECK(cq_omniwave_bcp_eval(off, nullptr, 2, asg, val, 1, 1, out) == 1);  // literals but no codes
    for (uint32_t o : out) CHECK(o == SENT);  // a rejected call never writes the output

    if (g_failures) {
        std::fprintf(stderr, "test_vulkan_bcp_differential(validate): %d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("PASS: OMNIWAVE BCP input validation (no device needed)\n");
    return 0;
}

int run_device() {
    char name[256];
    const int rc_name = cq_omniwave_device_name(name, sizeof(name));
    if (rc_name != 0) {
        if (env_flag("CQ_REQUIRE_VULKAN") || env_flag("CQ_REQUIRE_HARDWARE_GPU")) {
            std::fprintf(stderr, "FAIL: CQ_REQUIRE_VULKAN set but no Vulkan device (rc %d)\n", rc_name);
            return 1;
        }
        std::printf("SKIP (NOT_RUN): no usable Vulkan device; CPU-vs-GPU differential did not run\n");
        return 77;
    }
    std::printf("Vulkan device: %s\n", name);

    // ---- differential: many shapes, bit-identical to the CPU reference ----
    struct Shape { uint32_t clauses, fronts, vars, extra_words, max_len; };
    std::vector<Shape> shapes = {
        {1, 1, 1, 0, 3},     {63, 5, 8, 0, 4},     {64, 5, 8, 0, 4},    {65, 5, 8, 0, 4},
        {128, 7, 40, 0, 6},  {129, 7, 40, 1, 6},   {300, 97, 40, 0, 4}, {700, 130, 200, 0, 8},
        {257, 33, 63, 0, 5}, {257, 33, 64, 0, 5},  {257, 33, 65, 0, 5}, {1000, 3, 500, 0, 3},
        {1, 65535, 31, 0, 3}, {5, 1000, 100, 2, 6},
    };
    for (uint32_t k = 0; k < 40; ++k) {
        Rng r(1000 + k);
        shapes.push_back({1 + r.below(600), 1 + r.below(120), 1 + r.below(300), r.below(2), 1 + r.below(8)});
    }
    uint64_t kinds[4] = {0, 0, 0, 0};
    uint64_t cells = 0, mismatches = 0;
    uint64_t case_id = 0;
    for (const Shape& sh : shapes) {
        Case c = make_case(case_id++ * 7919ull + 17ull, sh.clauses, sh.fronts, sh.vars, sh.extra_words, sh.max_len);
        std::vector<uint32_t> got;
        const int rc = run_gpu(c, got);
        if (rc != 0) {
            std::fprintf(stderr, "FAIL: GPU returned %d for shape clauses=%u fronts=%u vars=%u\n", rc, sh.clauses,
                         sh.fronts, sh.vars);
            ++g_failures;
            continue;
        }
        cells += static_cast<uint64_t>(c.num_fronts) * c.num_clauses;
        const uint64_t mm = compare(c, got, kinds);
        mismatches += mm;
        if (mm) {
            std::fprintf(stderr, "FAIL: %llu mismatching cells for clauses=%u fronts=%u vars=%u\n",
                         static_cast<unsigned long long>(mm), sh.clauses, sh.fronts, sh.vars);
            ++g_failures;
        }
        // Re-running on the same (reused) context is deterministic.
        std::vector<uint32_t> again;
        CHECK(run_gpu(c, again) == 0);
        CHECK(again == got);
    }
    std::printf("differential: %llu cells, %llu mismatches, SAT/CONFLICT/UNIT/OPEN = %llu/%llu/%llu/%llu\n",
                static_cast<unsigned long long>(cells), static_cast<unsigned long long>(mismatches),
                static_cast<unsigned long long>(kinds[0]), static_cast<unsigned long long>(kinds[1]),
                static_cast<unsigned long long>(kinds[2]), static_cast<unsigned long long>(kinds[3]));
    CHECK(mismatches == 0);
    CHECK(kinds[0] && kinds[1] && kinds[2] && kinds[3]);  // every outcome was actually exercised

    // ---- failure paths: injected faults, distinct codes, out_status untouched, recovery ----
    Case fc = make_case(424242, 200, 20, 60, 0, 5);
    uint64_t scratch[4] = {0, 0, 0, 0};
    std::vector<uint32_t> out;

    // Device loss at submit: rc -5, output untouched, context dropped and re-created.
    cq_hecs::vkfault::disarm_all();
    cq_hecs::vkfault::arm(Site::QueueSubmit, VK_ERROR_DEVICE_LOST);
    CHECK(run_gpu(fc, out) == -5);
    for (uint32_t v : out) CHECK(v == 0xDEADBEEFu);
    cq_hecs::vkfault::disarm_all();
    CHECK(run_gpu(fc, out) == 0);  // recovered on a fresh context
    CHECK(compare(fc, out, scratch) == 0);

    // Device loss at wait-idle takes the same path.
    cq_hecs::vkfault::arm(Site::QueueWaitIdle, VK_ERROR_DEVICE_LOST);
    CHECK(run_gpu(fc, out) == -5);
    cq_hecs::vkfault::disarm_all();
    CHECK(run_gpu(fc, out) == 0);
    CHECK(compare(fc, out, scratch) == 0);

    // A non-fatal dispatch failure: rc -4, the context stays alive and correct.
    cq_hecs::vkfault::arm(Site::QueueSubmit, VK_ERROR_OUT_OF_DEVICE_MEMORY);
    CHECK(run_gpu(fc, out) == -4);
    for (uint32_t v : out) CHECK(v == 0xDEADBEEFu);
    cq_hecs::vkfault::disarm_all();
    CHECK(run_gpu(fc, out) == 0);
    CHECK(compare(fc, out, scratch) == 0);

    // Upload failure (third buffer allocation): rc -3.
    cq_hecs::vkfault::arm(Site::AllocateMemory, VK_ERROR_OUT_OF_DEVICE_MEMORY, 1, 2);
    CHECK(run_gpu(fc, out) == -3);
    cq_hecs::vkfault::disarm_all();
    CHECK(run_gpu(fc, out) == 0);

    // Readback failure: the 5th map is the status readback (4 uploads map first).
    CHECK(!fc.codes.empty());
    cq_hecs::vkfault::arm(Site::MapMemory, VK_ERROR_MEMORY_MAP_FAILED, 1, 4);
    CHECK(run_gpu(fc, out) == -6);
    for (uint32_t v : out) CHECK(v == 0xDEADBEEFu);  // never half-written
    cq_hecs::vkfault::disarm_all();
    CHECK(run_gpu(fc, out) == 0);
    CHECK(compare(fc, out, scratch) == 0);

    // Teardown: repeated shutdown/re-init cycles are safe and results stay identical.
    for (int i = 0; i < 20; ++i) {
        cq_omniwave_shutdown();
        if (i % 3 == 0) cq_omniwave_shutdown();  // double shutdown is a no-op
        CHECK(run_gpu(fc, out) == 0);
        CHECK(compare(fc, out, scratch) == 0);
    }
    cq_omniwave_shutdown();
    cq_hecs::vkfault::disarm_all();

    if (g_failures) {
        std::fprintf(stderr, "test_vulkan_bcp_differential(device): %d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("PASS: CPU-vs-Vulkan BCP differential and failure paths\n");
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    const std::string mode = argc > 1 ? argv[1] : "validate";
    if (mode == "validate") return run_validate();
    if (mode == "device") return run_device();
    std::fprintf(stderr, "usage: test_vulkan_bcp_differential [validate|device]\n");
    return 2;
}
