// C-ABI hardening contract for the CPU core library (AGENTS_V7 W4-18).
//
// Every refusal below must (a) not crash, (b) report through the documented
// code / cq_core_last_error(), and (c) leave the simulator state untouched.
// The test links the shared library, so it exercises exactly what a foreign
// caller gets. It needs no GPU and runs in the CPU-only and sanitizer builds.
#include "cq/cq_c_api.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>

namespace {

int g_failures = 0;

void check(bool ok, const char* what, int line) {
    if (!ok) {
        std::fprintf(stderr, "FAIL line %d: %s\n", line, what);
        ++g_failures;
    }
}
#define CHECK(cond) check((cond), #cond, __LINE__)

std::string sample(CQSimulatorHandle h, uint32_t shots) {
    char buf[4096];
    int rc = cq_sample_counts_json(h, shots, buf, sizeof(buf));
    return rc == 0 ? std::string(buf) : std::string("<rc=") + std::to_string(rc) + ">";
}

const char* kBell =
    "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[2];\nh q[0];\ncx q[0], q[1];\n";

void test_abi_version() {
    CHECK(cq_core_abi_version() == ((1u << 16) | 1u));
    CHECK(cq_core_check_abi(1, 0) == 0);
    CHECK(cq_core_check_abi(1, 1) == 0);
    CHECK(cq_core_check_abi(1, 2) == -1);  // caller newer than library
    CHECK(cq_core_check_abi(2, 0) == -1);  // different major
    CHECK(cq_core_check_abi(0, 0) == -1);
    const std::string caps = cq_core_build_capabilities();
    CHECK(caps.find("\"cpu_core\":true") != std::string::npos);
}

void test_create_limits() {
    cq_core_clear_error();
    CHECK(cq_create_simulator(0, 64) == nullptr);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_INVALID_ARG);
    CHECK(cq_create_simulator(4097, 64) == nullptr);
    CHECK(cq_create_simulator(4, 0) == nullptr);
    CHECK(cq_create_simulator(4, 65537) == nullptr);
    CQSimulatorHandle h = cq_create_simulator(4, 64);
    CHECK(h != nullptr);
    CHECK(cq_core_last_error() == CQ_CORE_OK);
    cq_destroy_simulator(h);
    cq_destroy_simulator(nullptr);  // must be a no-op
}

void test_null_handle() {
    cq_core_clear_error();
    cq_apply_h(nullptr, 0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_NULL_HANDLE);
    cq_core_clear_error();
    cq_apply_cx(nullptr, 0, 1);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_NULL_HANDLE);
    cq_core_clear_error();
    cq_apply_rz(nullptr, 0, 1.0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_NULL_HANDLE);
    cq_core_clear_error();
    CHECK(cq_measure_qubit(nullptr, 0) == 0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_NULL_HANDLE);
    cq_reset(nullptr);
    char buf[64];
    CHECK(cq_sample_counts_json(nullptr, 1, buf, sizeof(buf)) == -1);
    CHECK(cq_execute_qasm(nullptr, kBell, 1, buf, sizeof(buf)) == -1);
}

void test_qubit_range_and_state_unchanged() {
    CQSimulatorHandle h = cq_create_simulator(2, 64);
    CHECK(h != nullptr);
    cq_apply_x(h, 1);  // state |10> in the engine's bit order
    const std::string before = sample(h, 8);

    cq_core_clear_error();
    cq_apply_x(h, 2);  // out of range
    CHECK(cq_core_last_error() == CQ_CORE_ERR_QUBIT_RANGE);
    cq_apply_h(h, 0xFFFFFFFFu);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_QUBIT_RANGE);
    cq_apply_cx(h, 0, 5);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_QUBIT_RANGE);
    cq_apply_swap(h, 7, 0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_QUBIT_RANGE);
    cq_apply_cx(h, 1, 1);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_DUPLICATE_QUBIT);
    cq_apply_swap(h, 0, 0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_DUPLICATE_QUBIT);
    CHECK(cq_measure_qubit(h, 9) == 0);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_QUBIT_RANGE);

    CHECK(sample(h, 8) == before);  // no refused call changed the state
    cq_destroy_simulator(h);
}

void test_rz_angles() {
    CQSimulatorHandle h = cq_create_simulator(2, 64);
    cq_core_clear_error();
    cq_apply_rz(h, 0, std::numeric_limits<double>::quiet_NaN());
    CHECK(cq_core_last_error() == CQ_CORE_ERR_INVALID_ARG);
    cq_apply_rz(h, 0, std::numeric_limits<double>::infinity());
    CHECK(cq_core_last_error() == CQ_CORE_ERR_INVALID_ARG);
    // Negative and huge finite angles are legal (the conversion reduces modulo 2*pi);
    // the old unchecked double->uint32 cast was undefined behaviour for them.
    cq_core_clear_error();
    cq_apply_rz(h, 0, -1.0);
    CHECK(cq_core_last_error() == CQ_CORE_OK);
    cq_apply_rz(h, 1, 1.0e300);
    CHECK(cq_core_last_error() == CQ_CORE_OK);
    cq_apply_rz(h, 1, -1.0e300);
    CHECK(cq_core_last_error() == CQ_CORE_OK);
    cq_destroy_simulator(h);
}

void test_wide_non_clifford_refused() {
    CQSimulatorHandle h = cq_create_simulator(20, 64);  // wider than the 16-qubit shadow statevector
    CHECK(h != nullptr);
    const std::string zeros(20, '0');
    cq_core_clear_error();
    cq_apply_t(h, 3);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_UNSUPPORTED);
    cq_apply_tdg(h, 3);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_UNSUPPORTED);
    cq_apply_rz(h, 3, 0.5);
    CHECK(cq_core_last_error() == CQ_CORE_ERR_UNSUPPORTED);
    // Still a faithful stabilizer simulator: the refused gates changed nothing.
    CHECK(sample(h, 5) == "{\"" + zeros + "\": 5}");
    cq_destroy_simulator(h);

    CQSimulatorHandle small = cq_create_simulator(4, 64);  // narrow: non-Clifford is fine
    cq_core_clear_error();
    cq_apply_t(small, 0);
    CHECK(cq_core_last_error() == CQ_CORE_OK);
    cq_destroy_simulator(small);
}

void test_sample_buffers() {
    CQSimulatorHandle h = cq_create_simulator(2, 64);
    char tiny[4];
    CHECK(cq_sample_counts_json(h, 4, tiny, sizeof(tiny)) == -2);
    char buf[64];
    CHECK(cq_sample_counts_json(h, 4, nullptr, 64) == -1);
    CHECK(cq_sample_counts_json(h, 4, buf, 0) == -1);
    CHECK(cq_sample_counts_json(h, (1u << 24) + 1u, buf, sizeof(buf)) == -4);
    CHECK(cq_sample_counts_json(h, 4, buf, sizeof(buf)) == 0);
    CHECK(std::strcmp(buf, "{\"00\": 4}") == 0);
    cq_destroy_simulator(h);
}

void test_execute_qasm() {
    char out[4096];
    CQSimulatorHandle h = cq_create_simulator(2, 64);

    CHECK(cq_execute_qasm(h, kBell, 100, out, sizeof(out)) == 0);
    const std::string bell = out;
    CHECK(bell.find("\"00\"") != std::string::npos && bell.find("\"11\"") != std::string::npos);
    CHECK(bell.find("\"01\"") == std::string::npos && bell.find("\"10\"") == std::string::npos);

    CHECK(cq_execute_qasm(h, nullptr, 1, out, sizeof(out)) == -1);
    CHECK(cq_execute_qasm(h, kBell, 1, nullptr, 16) == -1);
    CHECK(cq_execute_qasm(h, kBell, 1, out, 0) == -1);
    CHECK(cq_execute_qasm(h, kBell, 1u << 25, out, sizeof(out)) == -4);

    // Invalid syntax / unknown gate: refused, never skipped.
    CHECK(cq_execute_qasm(h, "OPENQASM 2.0;\nqreg q[2];\nteleport q[0];\n", 1, out, sizeof(out)) == -3);
    CHECK(out[0] == '\0');
    // A circuit wider than the simulator.
    CHECK(cq_execute_qasm(h, "OPENQASM 2.0;\nqreg q[5];\nh q[4];\n", 1, out, sizeof(out)) == -6);
    // RX/RY are parsed but not implemented by this engine: they must be refused,
    // not silently skipped (the old default: branch skipped them).
    // (the parser refuses them as -3, the executor as -4; never skipped)
    int rc_rx = cq_execute_qasm(h, "OPENQASM 2.0;\nqreg q[2];\nrx(0.5) q[0];\n", 1, out, sizeof(out));
    CHECK(rc_rx == -3 || rc_rx == -4);
    int rc_ry = cq_execute_qasm(h, "OPENQASM 2.0;\nqreg q[2];\nry(0.5) q[0];\n", 1, out, sizeof(out));
    CHECK(rc_ry == -3 || rc_ry == -4);
    // Output buffer too small for the result.
    char tiny[3];
    CHECK(cq_execute_qasm(h, kBell, 10, tiny, sizeof(tiny)) == -2);
    // A refused circuit leaves the simulator reusable.
    CHECK(cq_execute_qasm(h, kBell, 10, out, sizeof(out)) == 0);
    cq_destroy_simulator(h);

    // Gate after a measurement = mid-circuit measurement: refused.
    CQSimulatorHandle m = cq_create_simulator(2, 64);
    CHECK(cq_execute_qasm(m, "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\nh q[0];\nmeasure q[0] -> c[0];\nh q[0];\n",
                          1, out, sizeof(out)) == -4);
    // Terminal measurement is fine.
    CHECK(cq_execute_qasm(m, "OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\nh q[0];\nmeasure q[0] -> c[0];\n",
                          10, out, sizeof(out)) == 0);
    cq_destroy_simulator(m);

    // Non-Clifford on a wide simulator is refused as a whole circuit (validated up front).
    CQSimulatorHandle wide = cq_create_simulator(20, 64);
    CHECK(cq_execute_qasm(wide, "OPENQASM 2.0;\nqreg q[20];\nh q[0];\nt q[0];\n", 1, out, sizeof(out)) == -4);
    cq_destroy_simulator(wide);
}

void test_oversized_input() {
    CQSimulatorHandle h = cq_create_simulator(2, 64);
    std::string big(16u * 1024u * 1024u + 2u, 'a');
    char out[64];
    CHECK(cq_execute_qasm(h, big.c_str(), 1, out, sizeof(out)) == -5);
    cq_destroy_simulator(h);
}

}  // namespace

int main() {
    test_abi_version();
    test_create_limits();
    test_null_handle();
    test_qubit_range_and_state_unchanged();
    test_rz_angles();
    test_wide_non_clifford_refused();
    test_sample_buffers();
    test_execute_qasm();
    test_oversized_input();
    if (g_failures) {
        std::fprintf(stderr, "test_c_abi_core: %d failure(s)\n", g_failures);
        return 1;
    }
    std::printf("PASS: C-ABI core hardening contract\n");
    return 0;
}
