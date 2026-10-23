// Native regression + robustness tests for the fail-closed QASM parser.
//
// These tests target the historical fail-open defects directly:
//   * unknown gates silently accepted as identity
//   * malformed numeric parameters silently coerced to 0.0
//   * out-of-range indices silently expanding the register
//   * missing semicolons silently tolerated
//   * empty input silently defaulting to a 300-qubit circuit
//
// A failure prints a diagnostic and exits non-zero so CTest fails the build.

#include "qasm_parser.hpp"
#include "vulkan_engine.hpp"

#include <cstdio>
#include <cstdlib>
#include <random>
#include <string>
#include <vector>

using cq_hecs::QASMCircuitData;
using cq_hecs::QASMParserCPP;

namespace {

int g_failures = 0;

void check(bool condition, const char* what) {
    if (!condition) {
        std::fprintf(stderr, "FAIL: %s\n", what);
        ++g_failures;
    }
}

bool rejects(QASMParserCPP& parser, const std::string& source, const char* category) {
    QASMCircuitData circuit;
    const bool ok = parser.parse_string(source, circuit);
    if (ok || circuit.ok()) return false;
    for (const auto& error : circuit.errors) {
        if (error.category == category) return true;
    }
    std::fprintf(stderr, "  expected category '%s', got:", category);
    for (const auto& error : circuit.errors) {
        std::fprintf(stderr, " [%s] %s", error.category.c_str(), error.message.c_str());
    }
    std::fprintf(stderr, "\n");
    return false;
}

bool accepts(QASMParserCPP& parser, const std::string& source) {
    QASMCircuitData circuit;
    const bool ok = parser.parse_string(source, circuit);
    if (!ok || !circuit.ok()) {
        for (const auto& error : circuit.errors) {
            std::fprintf(stderr, "  unexpected error [%s] line %d: %s\n",
                         error.category.c_str(), error.line, error.message.c_str());
        }
        return false;
    }
    return true;
}

}  // namespace

int main() {
    QASMParserCPP parser;

    // Empty input is a documented no-op with zero qubits (no fabricated default).
    {
        QASMCircuitData circuit;
        check(parser.parse_string("", circuit), "empty input parses");
        check(circuit.num_qubits == 0, "empty input must not fabricate qubits");
        check(circuit.commands.empty(), "empty input must not fabricate gates");
    }

    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\nteleport q[0];\n",
                  "unsupported_gate"),
          "unknown gate is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\ncp(nope) q[0], q[1];\n",
                  "invalid_parameter"),
          "malformed parameter is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\ncp(3.14.15) q[0], q[1];\n",
                  "invalid_parameter"),
          "partially numeric parameter is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\nrx(nan) q[0];\n",
                  "invalid_parameter"),
          "NaN parameter is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\nh q[9];\n",
                  "index_out_of_range"),
          "out-of-range index is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4]\nh q[0];\n",
                  "missing_semicolon"),
          "missing semicolon is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[4];\nqreg q[4];\n",
                  "duplicate_register"),
          "duplicate register is rejected");
    check(rejects(parser, "OPENQASM 2.0;\nqreg q[0];\n",
                  "invalid_register_size"),
          "zero-sized register is rejected");

    // Valid circuit: exact, documented counts.
    {
        QASMCircuitData circuit;
        const std::string valid =
            "OPENQASM 2.0;\ninclude \"qelib1.inc\";\n"
            "qreg q[4];\ncreg c[1];\n"
            "h q[0];\ncx q[0], q[1];\nmeasure q[0] -> c[0];\n";
        check(parser.parse_string(valid, circuit), "valid circuit parses");
        check(circuit.num_qubits == 4, "valid circuit qubit count");
        check(circuit.commands.size() == 3, "valid circuit command count");
        check(circuit.commands[0].name == "h", "first command is h");
        check(circuit.commands[2].clbits.size() == 1, "measure maps one clbit");

        // Whole-register operand expands deterministically.
        QASMCircuitData expanded;
        check(parser.parse_string("OPENQASM 2.0;\nqreg q[4];\nh q;\n", expanded),
              "whole-register operand parses");
        check(expanded.commands.size() == 4, "whole-register operand expands to 4 gates");
    }

    // Bounded randomized robustness: arbitrary bytes must never crash and must
    // either parse cleanly or report at least one structured error.
    {
        std::mt19937_64 rng(0xC0FFEEu);
        const std::string alphabet =
            "OPENQASM 2.0;qreg creg hxysztcxrzcp()[],; \n\r\t0123456789.-+/pi";
        constexpr int iterations = 5000;
        for (int i = 0; i < iterations; ++i) {
            const size_t length = static_cast<size_t>(rng() % 256);
            std::string input;
            input.reserve(length);
            for (size_t k = 0; k < length; ++k) {
                input.push_back(alphabet[rng() % alphabet.size()]);
            }
            QASMCircuitData circuit;
            const bool ok = parser.parse_string(input, circuit);
            if (ok && !circuit.ok()) {
                std::fprintf(stderr, "FAIL: parse_string returned true with errors\n");
                ++g_failures;
                break;
            }
            if (!ok && circuit.errors.empty()) {
                std::fprintf(stderr, "FAIL: rejected input without a diagnostic\n");
                ++g_failures;
                break;
            }
        }
        check(g_failures == 0, "randomized malformed input is handled fail-closed");
    }

    // The executor must refuse invalid circuits before touching the device.
    {
        QASMCircuitData invalid;
        invalid.errors.push_back({1, "unsupported_gate", "synthetic"});
        cq_hecs::VulkanEngine engine;
        const auto result = parser.execute_on_vulkan(invalid, engine);
        check(!result.success, "executor refuses a circuit with parse errors");
        check(result.gate_count == 0, "executor applies no gates to an invalid circuit");
    }

    if (g_failures != 0) {
        std::fprintf(stderr, "%d check(s) failed\n", g_failures);
        return 1;
    }
    std::printf("QASM fail-closed contract: all checks passed\n");
    return 0;
}
