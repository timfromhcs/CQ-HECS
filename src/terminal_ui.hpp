#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace cq_hecs {

struct TUIStateCPP {
    double active_vram_mb = 4.531;
    double vram_ceiling_mb = 120.0;
    uint32_t num_qubits = 300;
    uint32_t bond_dim_chi = 64;
    double lambda_res = 0.000000;
    double entropy_jitter_ns = 54.2;
    bool nudge_triggered = false;
    uint32_t nudge_val = 0;
    double attn_alpha = 0.22;
    double attn_beta = 0.28;
    double attn_gamma = 0.18;
    double attn_delta = 0.14;
    double attn_epsilon = 0.18;
    double solved_states_per_sec = 39880.0;
    double cuckoo_pruning_per_sec = 89450.0;
    std::vector<double> jitter_history;
    uint64_t cycle_count = 0;
};

class TerminalUICPP {
public:
    TerminalUICPP();
    ~TerminalUICPP();

    static bool enable_virtual_terminal_processing();
    void run(uint32_t max_cycles = 0, double refresh_rate_sec = 0.1);

private:
    void render_frame(const TUIStateCPP& state);
    std::string build_bar(double value, double max_val, int width);
    std::string build_oscilloscope(const std::vector<double>& history, int width);
};

} // namespace cq_hecs
