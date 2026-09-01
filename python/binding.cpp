#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/map.h>
#include <nanobind/stl/tuple.h>

#include "cq_hecs/core/types.hpp"
#include "cq_hecs/core/cordic.hpp"
#include "cq_hecs/core/mps_simulator.hpp"
#include "cq_hecs/core/statevector_simulator.hpp"
#include "cq_hecs/core/qpu_engine.hpp"
#include "cq_hecs/transpiler/bytecode.hpp"
#include "cq_hecs/transpiler/qasm3_parser.hpp"
#include "cq_hecs/transpiler/optimizer.hpp"

namespace nb = nanobind;
using namespace cq_hecs::core;
using namespace cq_hecs::transpiler;

NB_MODULE(_cq_hecs_core, m) {
    m.doc() = "CQ-HECS Quantum Engine C++20 Nanobind Core (Zero-Float Bit-Exact Architecture)";

    nb::class_<ComplexQ31>(m, "ComplexQ31")
        .def(nb::init<>())
        .def(nb::init<int32_t, int32_t>())
        .def_rw("re", &ComplexQ31::re)
        .def_rw("im", &ComplexQ31::im)
        .def("__repr__", [](const ComplexQ31& c) {
            return "ComplexQ31(" + std::to_string(c.re) + ", " + std::to_string(c.im) + ")";
        });

    m.def("cordic_rotate", [](int32_t re, int32_t im, uint32_t phase_q32) {
        ComplexQ31 in{re, im};
        ComplexQ31 out = cordic_rotate(in, phase_q32);
        return std::make_tuple(out.re, out.im);
    }, "Rotate Q1.31 complex amplitude by Z_{2^32} phase angle via CORDIC");

    m.def("radians_to_z32", &radians_to_z32, "Convert radians (float) to uint32 Z_{2^32} phase ring");

    nb::class_<J_QuantumOpcode>(m, "J_QuantumOpcode")
        .def(nb::init<>())
        .def_rw("op_type", &J_QuantumOpcode::op_type)
        .def_rw("target_q", &J_QuantumOpcode::target_q)
        .def_rw("control_q", &J_QuantumOpcode::control_q)
        .def_rw("flags", &J_QuantumOpcode::flags)
        .def_rw("phase1", &J_QuantumOpcode::phase1)
        .def_rw("phase2", &J_QuantumOpcode::phase2)
        .def_rw("phase3", &J_QuantumOpcode::phase3);

    nb::class_<QuantumCircuit>(m, "QuantumCircuit")
        .def(nb::init<>())
        .def_rw("num_qubits", &QuantumCircuit::num_qubits)
        .def_rw("num_clbits", &QuantumCircuit::num_clbits)
        .def_rw("opcodes", &QuantumCircuit::opcodes);

    nb::class_<Qasm3Parser>(m, "Qasm3Parser")
        .def_static("parse", &Qasm3Parser::parse, "Parse OpenQASM 3.0 string into QuantumCircuit");

    nb::class_<CircuitOptimizer>(m, "CircuitOptimizer")
        .def_static("route_1d_mps", &CircuitOptimizer::route_1d_mps)
        .def_static("fuse_gates", &CircuitOptimizer::fuse_gates)
        .def_static("optimize", &CircuitOptimizer::optimize);

    nb::class_<MPSSimulator>(m, "MPSSimulator")
        .def(nb::init<uint32_t, uint32_t>(), nb::arg("num_qubits") = 300, nb::arg("max_bond_dim") = 64)
        .def("create_ghz", &MPSSimulator::create_ghz)
        .def("get_memory_mb", &MPSSimulator::get_memory_mb)
        .def("reset", &MPSSimulator::reset);

    nb::class_<VulkanQpuEngine>(m, "VulkanQpuEngine")
        .def(nb::init<uint32_t, uint32_t>(), nb::arg("n_qubits") = 300, nb::arg("max_d") = 64)
        .def("execute_qasm", &VulkanQpuEngine::execute_qasm)
        .def("sample_counts", &VulkanQpuEngine::sample_counts, nb::arg("shots") = 1024)
        .def("get_memory_mb", &VulkanQpuEngine::get_memory_mb)
        .def("reset", &VulkanQpuEngine::reset);
}
