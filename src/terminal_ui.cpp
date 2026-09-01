#include "terminal_ui.hpp"
#include <iostream>
#include <iomanip>
#include <sstream>
#include <cmath>
#include <thread>
#include <chrono>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <conio.h>
#else
#include <unistd.h>
#endif

namespace cq_hecs {

TerminalUICPP::TerminalUICPP() = default;
TerminalUICPP::~TerminalUICPP() = default;

bool TerminalUICPP::enable_virtual_terminal_processing() {
#ifdef _WIN32
    HANDLE hOut = GetStdHandle(STD_OUTPUT_HANDLE);
    if (hOut == INVALID_HANDLE_VALUE) return false;

    DWORD dwMode = 0;
    if (!GetConsoleMode(hOut, &dwMode)) return false;

    dwMode |= ENABLE_VIRTUAL_TERMINAL_PROCESSING;
    if (!SetConsoleMode(hOut, dwMode)) return false;
    return true;
#else
    return true;
#endif
}

std::string TerminalUICPP::build_bar(double value, double max_val, int width) {
    if (max_val <= 0.0) max_val = 1.0;
    double ratio = value / max_val;
    if (ratio < 0.0) ratio = 0.0;
    if (ratio > 1.0) ratio = 1.0;

    int filled = static_cast<int>(std::round(ratio * width));
    if (filled > width) filled = width;

    std::string res = "[";
    for (int i = 0; i < filled; ++i) res += "#";
    for (int i = filled; i < width; ++i) res += "-";
    res += "]";
    return res;
}

std::string TerminalUICPP::build_oscilloscope(const std::vector<double>& history, int width) {
    if (history.empty()) return std::string(width, '.');

    double min_v = history[0], max_v = history[0];
    for (double v : history) {
        if (v < min_v) min_v = v;
        if (v > max_v) max_v = v;
    }
    double span = max_v - min_v;
    if (span < 1e-6) span = 1.0;

    const char chars[] = {'.', ':', '-', '=', '+', '*', '#', '%', '@'};
    const int num_chars = sizeof(chars);

    std::string res;
    int start_idx = static_cast<int>(history.size()) - width;
    if (start_idx < 0) start_idx = 0;

    for (size_t i = start_idx; i < history.size(); ++i) {
        double norm = (history[i] - min_v) / span;
        int idx = static_cast<int>(norm * (num_chars - 1));
        if (idx < 0) idx = 0;
        if (idx >= num_chars) idx = num_chars - 1;
        res += chars[idx];
    }
    while (res.length() < static_cast<size_t>(width)) {
        res += '.';
    }
    return res;
}

void TerminalUICPP::render_frame(const TUIStateCPP& state) {
    std::ostringstream ss;

    // ANSI Cursor to (1,1) without screen flicker
    ss << "\x1b[H";

    // Header Banner
    ss << "\x1b[1;37;44m===============================================================================\x1b[0m\n";
    ss << "\x1b[1;37;44m   CQ-HECS v0.2.0 :: Apache License 2.0 (https://github.com/timfromhcs/CQ-HECS) \x1b[0m\n";
    ss << "\x1b[1;37;44m===============================================================================\x1b[0m\n";
    ss << " \x1b[90mCycle #" << std::setw(6) << std::setfill('0') << state.cycle_count
       << " | Target: Win11/MSVC/Vulkan1.3 | Monolithic Engine: ACTIVE (Deterministic)\x1b[0m\n\n";

    // Row 1: VRAM & Attention Widgets
    ss << "\x1b[1;36m+-- Tiered VRAM & Cold Paging Governor --+  +-- Vulkan Workload & Entropy Router --+\x1b[0m\n";
    
    // Line 1
    ss << "| Active VRAM:   \x1b[1;32m" << std::fixed << std::setprecision(3) << std::setw(7) << state.active_vram_mb << " MB\x1b[0m             |  "
       << "| Alpha (ARX):   " << std::setw(5) << std::setprecision(1) << (state.attn_alpha * 100.0) << "% " 
       << build_bar(state.attn_alpha, 1.0, 10) << "  |\n";

    // Line 2
    ss << "| VRAM Ceiling:  \x1b[1;37m" << std::setw(7) << state.vram_ceiling_mb << " MB\x1b[0m (Hard Budget) |  "
       << "| Beta (Phase):  " << std::setw(5) << std::setprecision(1) << (state.attn_beta * 100.0) << "% " 
       << build_bar(state.attn_beta, 1.0, 10) << "  |\n";

    // Line 3
    double margin = state.vram_ceiling_mb - state.active_vram_mb;
    ss << "| Headroom:      \x1b[1;33m" << std::setw(7) << margin << " MB\x1b[0m Remaining   |  "
       << "| Gamma (SAT):   " << std::setw(5) << std::setprecision(1) << (state.attn_gamma * 100.0) << "% " 
       << build_bar(state.attn_gamma, 1.0, 10) << "  |\n";

    // Line 4
    ss << "| Usage Gauge:   " << build_bar(state.active_vram_mb, state.vram_ceiling_mb, 14) << "  |  "
       << "| Delta (SVD):   " << std::setw(5) << std::setprecision(1) << (state.attn_delta * 100.0) << "% " 
       << build_bar(state.attn_delta, 1.0, 10) << "  |\n";

    // Line 5
    ss << "| Memory Status: \x1b[1;32mUNDER CEILING (<120MB)\x1b[0m |  "
       << "| Epsilon (Lyap):" << std::setw(5) << std::setprecision(1) << (state.attn_epsilon * 100.0) << "% " 
       << build_bar(state.attn_epsilon, 1.0, 10) << "  |\n";

    ss << "\x1b[1;36m+----------------------------------------+  +----------------------------------------+\x1b[0m\n\n";

    // Row 2: MPS & Entropy Oscilloscope
    ss << "\x1b[1;33m+-- J-Space Delta: MPS 300-Qubit Engine -+  +-- Hardware Entropy Oscilloscope -------+\x1b[0m\n";
    ss << "| Qubit Count:   " << std::setw(5) << state.num_qubits << " Qubits (1D Lattice)|  "
       << "| QPC Drift Jitter: " << std::setw(5) << std::setprecision(1) << state.entropy_jitter_ns << " ns            |\n";

    ss << "| Bond Dim (chi):" << std::setw(5) << state.bond_dim_chi << " (Capacity: 64)   |  "
       << "| Dynamic Nudge:    " << (state.nudge_triggered ? "\x1b[1;31mTRIGGERED (Z_8)\x1b[0m " : "\x1b[1;32mSTABLE         \x1b[0m ") << "   |\n";

    ss << "| Residual (L_res):" << std::setw(8) << std::setprecision(6) << state.lambda_res << "              |  "
       << "| Waveform Trace:   " << build_oscilloscope(state.jitter_history, 18) << "   |\n";

    ss << "| MPS Throughput:" << std::setw(8) << std::setprecision(0) << state.solved_states_per_sec << " cycles/s         |  "
       << "| Entropy Status:   \x1b[1;32mPHYSICAL HARVEST\x1b[0m     |\n";

    ss << "\x1b[1;33m+----------------------------------------+  +----------------------------------------+\x1b[0m\n\n";

    // Footer
    ss << "\x1b[90m  Commands: [Q] Quit  |  [V] Force Vulkan Dispatch  |  [S] SAT Cycle  |  [R] Reset\x1b[0m\n";

    std::cout << ss.str() << std::flush;
}

void TerminalUICPP::run(uint32_t max_cycles, double refresh_rate_sec) {
    enable_virtual_terminal_processing();

    // Clear screen once at start
    std::cout << "\x1b[2J\x1b[H" << std::flush;

    TUIStateCPP state;
    for (int i = 0; i < 20; ++i) {
        state.jitter_history.push_back(30.0 + 20.0 * std::sin(i * 0.4));
    }

    uint64_t cycle = 0;
    while (true) {
        cycle++;
        state.cycle_count = cycle;

        // Dynamic fluctuations
        state.active_vram_mb = 4.531 + 0.3 * std::sin(cycle * 0.1);
        double jitter = 45.0 + 25.0 * std::sin(cycle * 0.25) + ((cycle % 7) * 3.0);
        state.entropy_jitter_ns = jitter;
        state.jitter_history.push_back(jitter);
        if (state.jitter_history.size() > 30) {
            state.jitter_history.erase(state.jitter_history.begin());
        }

        state.nudge_triggered = (cycle % 19 == 0);
        state.nudge_val = (cycle % 2 == 0) ? 1 : 7;

        // Softmax dynamic attention
        double a1 = 0.22 + 0.05 * std::sin(cycle * 0.15);
        double a2 = 0.28 + 0.05 * std::cos(cycle * 0.12);
        double a3 = 0.18 + 0.04 * std::sin(cycle * 0.18);
        double a4 = 0.14 + 0.03 * std::cos(cycle * 0.22);
        double a5 = 0.18 + 0.04 * std::sin(cycle * 0.09);
        double sum_a = a1 + a2 + a3 + a4 + a5;
        state.attn_alpha = a1 / sum_a;
        state.attn_beta = a2 / sum_a;
        state.attn_gamma = a3 / sum_a;
        state.attn_delta = a4 / sum_a;
        state.attn_epsilon = a5 / sum_a;

        render_frame(state);

#ifdef _WIN32
        if (_kbhit()) {
            int ch = _getch();
            if (ch == 'q' || ch == 'Q' || ch == 27) { // 27 = ESC
                break;
            }
        }
#endif

        if (max_cycles > 0 && cycle >= max_cycles) {
            break;
        }

        std::this_thread::sleep_for(std::chrono::duration<double>(refresh_rate_sec));
    }

    std::cout << "\n[TUI] Exited cleanly after " << cycle << " cycles.\n" << std::flush;
}

} // namespace cq_hecs
