#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/map.h>

#include "cqhecs/algebra/ring.hpp"
#include "cqhecs/stabilizer/tableau.hpp"
#include "cqhecs/vulkan/vulkan_engine.hpp"

namespace nb = nanobind;
using namespace cqhecs::algebra;
using namespace cqhecs::stabilizer;
using namespace cqhecs::vulkan;

NB_MODULE(_cqhecs_pybind, m) {
    m.doc() = "CQ-HECS Quantum Engine Python Bindings";

    // 1. ExactRingElement
    nb::class_<ExactRingElement>(m, "ExactRingElement")
        .def(nb::init<>())
        .def(nb::init<int64_t, int64_t, int64_t, int64_t, uint32_t>(),
             nb::arg("a"), nb::arg("b"), nb::arg("c"), nb::arg("d"), nb::arg("k") = 0)
        .def_rw("a", &ExactRingElement::a)
        .def_rw("b", &ExactRingElement::b)
        .def_rw("c", &ExactRingElement::c)
        .def_rw("d", &ExactRingElement::d)
        .def_rw("k", &ExactRingElement::k)
        .def("to_double_re", &ExactRingElement::to_double_re)
        .def("to_double_im", &ExactRingElement::to_double_im)
        .def("to_probability", &ExactRingElement::to_probability)
        .def("reduce", &ExactRingElement::reduce)
        .def("conj", &ExactRingElement::conj)
        .def("norm_sq", &ExactRingElement::norm_sq)
        .def("__add__", &ExactRingElement::operator+)
        .def("__sub__", &ExactRingElement::operator-)
        .def("__mul__", nb::overload_cast<const ExactRingElement&>(&ExactRingElement::operator*, nb::const_))
        .def("__eq__", &ExactRingElement::operator==)
        .def("__repr__", &ExactRingElement::to_string);

    // 2. StabilizerTableau
    nb::class_<StabilizerTableau>(m, "StabilizerTableau")
        .def(nb::init<uint32_t>(), nb::arg("n_qubits"))
        .def("reset", &StabilizerTableau::reset)
        .def("apply_h", &StabilizerTableau::apply_h)
        .def("apply_s", &StabilizerTableau::apply_s)
        .def("apply_sdg", &StabilizerTableau::apply_sdg)
        .def("apply_x", &StabilizerTableau::apply_x)
        .def("apply_y", &StabilizerTableau::apply_y)
        .def("apply_z", &StabilizerTableau::apply_z)
        .def("apply_cx", &StabilizerTableau::apply_cx)
        .def("apply_cz", &StabilizerTableau::apply_cz)
        .def("apply_swap", &StabilizerTableau::apply_swap)
        .def("measure", &StabilizerTableau::measure, nb::arg("q"), nb::arg("rng") = nullptr)
        .def("sample_counts", &StabilizerTableau::sample_counts, nb::arg("shots"), nb::arg("seed") = 42)
        .def("verify_symplectic_invariants", &StabilizerTableau::verify_symplectic_invariants);

    // 3. VulkanEngine
    nb::class_<VulkanEngine>(m, "VulkanEngine")
        .def(nb::init<uint32_t, uint32_t>(), nb::arg("n_qubits") = 300, nb::arg("max_chi") = 48)
        .def("initialize", &VulkanEngine::initialize)
        .def("apply_h", &VulkanEngine::apply_h)
        .def("apply_x", &VulkanEngine::apply_x)
        .def("apply_z", &VulkanEngine::apply_z)
        .def("apply_cx", &VulkanEngine::apply_cx)
        .def("get_active_vram_mb", &VulkanEngine::get_active_vram_mb)
        .def("sample_fast_shots", &VulkanEngine::sample_fast_shots, nb::arg("shots"), nb::arg("seed") = 42);
}
