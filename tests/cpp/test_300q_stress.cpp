#ifdef NDEBUG
#undef NDEBUG
#endif
#include "cqhecs/vulkan/vulkan_engine.hpp"
#include <iostream>
#include <cassert>
#include <chrono>
#include <stdexcept>
#include <vector>
#include <cmath>

using namespace cqhecs::vulkan;

// This suite verifies the legacy VulkanEngine memory-planning contract only.
// The class stores no amplitudes, so gate execution and sampling must fail
// closed instead of returning success-shaped output.
void test_300q_allocation_governor() {
    std::cout << "[PLANNER] Verifying 300-qubit MPS layout against the 5.0 GB governor...\n";
    const uint32_t N = 300;

    VulkanEngine engine(N, 64);
    double active_mb = engine.get_active_vram_mb();
    std::cout << "  Planned site metadata: " << active_mb << " MB (Ceiling: <= 5120.0 MB)\n";
    assert(active_mb > 0.0 && active_mb <= 5120.0);

    bool threw_h = false;
    bool threw_cx = false;
    try { engine.apply_h(0); } catch (const std::logic_error&) { threw_h = true; }
    try { engine.apply_cx(0, 1); } catch (const std::logic_error&) { threw_cx = true; }
    assert(threw_h && "H must fail closed without a state representation");
    assert(threw_cx && "CX must fail closed without a state representation");

    bool threw_sample = false;
    try { engine.sample_fast_shots(1000); } catch (const std::logic_error&) { threw_sample = true; }
    assert(threw_sample && "sampling must fail closed without a state representation");

    std::cout << "  >>> PASS: planner allocates metadata and gate/sample calls fail closed.\n\n";
}

void test_vram_hard_exception() {
    std::cout << "[PLANNER] Testing VRAM Governor hard exception on > 5120 MB...\n";
    MemoryGovernor gov;
    bool caught = false;
    try {
        size_t excessive = 5ULL * 1024ULL * 1024ULL * 1024ULL + 100ULL * 1024ULL * 1024ULL;
        gov.allocate(excessive);
    } catch (const std::runtime_error& e) {
        caught = true;
        std::cout << "  Caught expected governor exception: " << e.what() << "\n";
    }
    assert(caught && "Memory governor MUST throw on > 5120 MB");
    std::cout << "  >>> PASS: hard VRAM governor exception verified.\n\n";
}

void test_out_of_range_is_reported() {
    std::cout << "[PLANNER] Verifying invalid qubit indices are reported...\n";
    VulkanEngine engine(8, 4);
    bool caught = false;
    try { engine.apply_z(8); } catch (const std::out_of_range&) { caught = true; }
    assert(caught && "out-of-range qubit must throw out_of_range");
    std::cout << "  >>> PASS: invalid qubit index rejected.\n\n";
}

int main() {
    std::cout << "=================================================================\n";
    std::cout << " CQ-HECS 300-Qubit Planner & VRAM Governor Suite\n";
    std::cout << "=================================================================\n\n";

    test_300q_allocation_governor();
    test_vram_hard_exception();
    test_out_of_range_is_reported();

    std::cout << "=================================================================\n";
    std::cout << " PLANNER-ONLY CONTRACT VERIFIED (no quantum state claimed)\n";
    std::cout << "=================================================================\n";
    return 0;
}
