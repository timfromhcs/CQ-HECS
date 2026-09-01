#include <iostream>
#include "cq_hecs/tensor_network.hpp"
#include "cq_hecs/vulkan/vulkan_context.hpp"

using namespace cq_hecs;

int main() {
    std::cout << "CQ-HECS v2.0.0-VRTS-Vulkan: 300-Qubit GHZ Example\n";
    auto vulkan = std::make_shared<VulkanContext>();
    if (vulkan->initialize()) {
        std::cout << "Vulkan Initialized on Device: " << vulkan->get_device_name() << "\n";
    }

    VRTS300Engine engine(vulkan);
    std::cout << "Constructing GHZ state across 6 x 5 x 10 lattice...\n";
    engine.construct_ghz300();

    auto [non_parity, zero_shots] = engine.measure_parity_shots(10000);
    std::cout << "Measured 10,000 shots:\n";
    std::cout << "  |0>^{\\otimes 300}: " << zero_shots << "\n";
    std::cout << "  |1>^{\\otimes 300}: " << (10000 - zero_shots - non_parity) << "\n";
    std::cout << "  Non-parity errors: " << non_parity << "\n";

    return 0;
}
