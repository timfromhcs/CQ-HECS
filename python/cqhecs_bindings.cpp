#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/map.h>
#include <nanobind/stl/tuple.h>

#include "cq/exact_cyclotomic.hpp"
#include "cq/stabilizer_tableau.hpp"
#include "cq/mps_sampler.hpp"
#include "cq/hybrid_engine.hpp"
#include "cq/qasm_parser.hpp"

namespace nb = nanobind;
using namespace cq;

NB_MODULE(_cqhecs_core, m) {
    m.doc() = "CQ-HECS Quantum Engine: Bit-Exact Z[1/sqrt(2), i] Ring, Gottesman-Knill Stabilizer & Hybrid MPS";

    // 1. Cyclotomic8 (Giles-Selinger Ring)
    nb::class_<Cyclotomic8>(m, "Cyclotomic8")
        .def(nb::init<>())
        .def(nb::init<int64_t, int64_t, int64_t, int64_t, uint32_t>(),
             nb::arg("a"), nb::arg("b"), nb::arg("c"), nb::arg("d"), nb::arg("k") = 0)
        .def_rw("a", &Cyclotomic8::a)
        .def_rw("b", &Cyclotomic8::b)
        .def_rw("c", &Cyclotomic8::c)
        .def_rw("d", &Cyclotomic8::d)
        .def_rw("k", &Cyclotomic8::k)
        .def("to_double_re", &Cyclotomic8::to_double_re)
        .def("to_double_im", &Cyclotomic8::to_double_im)
        .def("norm_sq", &Cyclotomic8::norm_sq)
        .def("__add__", &Cyclotomic8::operator+)
        .def("__sub__", &Cyclotomic8::operator-)
        .def("__mul__", &Cyclotomic8::operator*)
        .def("__eq__", &Cyclotomic8::operator==)
        .def("__repr__", &Cyclotomic8::to_string);

    // 2. StabilizerTableau
    nb::class_<StabilizerTableau>(m, "StabilizerTableau")
        .def(nb::init<uint32_t>(), nb::arg("num_qubits"))
        .def("reset", &StabilizerTableau::reset)
        .def("apply_h", &StabilizerTableau::apply_h)
        .def("apply_s", &StabilizerTableau::apply_s)
        .def("apply_sdg", &StabilizerTableau::apply_sdg)
        .def("apply_x", &StabilizerTableau::apply_x)
        .def("apply_y", &StabilizerTableau::apply_y)
        .def("apply_z", &StabilizerTableau::apply_z)
        .def("apply_cx", &StabilizerTableau::apply_cx)
        .def("apply_swap", &StabilizerTableau::apply_swap)
        .def("measure", &StabilizerTableau::measure, nb::arg("q"), nb::arg("rng") = nullptr)
        .def("verify_symplectic_invariants", &StabilizerTableau::verify_symplectic_invariants);

    // 3. HybridEngine
    nb::class_<HybridEngine>(m, "HybridEngine")
        .def(nb::init<uint32_t, uint32_t>(), nb::arg("num_qubits"), nb::arg("max_bond_dim") = 64)
        .def("reset", &HybridEngine::reset)
        .def("apply_h", &HybridEngine::apply_h)
        .def("apply_s", &HybridEngine::apply_s)
        .def("apply_sdg", &HybridEngine::apply_sdg)
        .def("apply_t", &HybridEngine::apply_t)
        .def("apply_tdg", &HybridEngine::apply_tdg)
        .def("apply_x", &HybridEngine::apply_x)
        .def("apply_y", &HybridEngine::apply_y)
        .def("apply_z", &HybridEngine::apply_z)
        .def("apply_cx", &HybridEngine::apply_cx)
        .def("apply_swap", &HybridEngine::apply_swap)
        .def("apply_rz", &HybridEngine::apply_rz)
        .def("measure_qubit", &HybridEngine::measure_qubit)
        .def("sample_counts", &HybridEngine::sample_counts, nb::arg("shots") = 1024, nb::arg("seed") = 42)
        .def("get_probability", &HybridEngine::get_probability);
}
