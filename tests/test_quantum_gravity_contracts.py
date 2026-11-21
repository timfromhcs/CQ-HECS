"""Contracts: observables, experiment envelope schema, circuit manifests, catalog."""

from __future__ import annotations

import json

import numpy as np
import pytest

from cqhecs.quantum_gravity.catalog import MethodCard, catalog
from cqhecs.quantum_gravity.circuits import (
    bmv_null_qasm,
    bmv_qasm,
    build_bmv_manifest,
    default_theta_values,
    sha256_text,
    write_manifest,
)
from cqhecs.quantum_gravity.errors import QGBlocker, QGUnsupported
from cqhecs.quantum_gravity.observables import (
    chsh_from_correlators,
    concurrence_2qubit,
    concurrence_pure_2qubit,
    entanglement_entropy,
    negativity_2qubit,
    partial_trace,
    partial_transpose,
)
from cqhecs.quantum_gravity.results import (
    SCHEMA,
    SchemaVersionError,
    build_experiment_result,
    from_dict,
)

BELL = np.array([1, 0, 0, 1]) / np.sqrt(2)
PRODUCT = np.array([1, 0, 0, 0], dtype=complex)


def test_bell_entanglement_values():
    rho = np.outer(BELL, BELL.conj())
    assert abs(concurrence_2qubit(rho) - 1.0) < 1e-12
    assert abs(negativity_2qubit(rho) - 0.5) < 1e-12
    assert abs(entanglement_entropy(rho, (2, 2), (0,)) - 1.0) < 1e-12
    assert abs(concurrence_pure_2qubit(BELL) - 1.0) < 1e-12


def test_partial_transpose_negative_eigenvalue_for_bell():
    rho = np.outer(BELL, BELL.conj())
    pt = partial_transpose(rho, (2, 2), 0)
    assert abs(np.min(np.linalg.eigvalsh(pt)) + 0.5) < 1e-12


def test_product_state_separable():
    rho = np.outer(PRODUCT, PRODUCT.conj())
    assert concurrence_2qubit(rho) < 1e-12
    assert negativity_2qubit(rho) < 1e-12
    assert entanglement_entropy(rho, (2, 2), (0,)) < 1e-12


def test_partial_trace_of_bell_is_maximally_mixed():
    rho = np.outer(BELL, BELL.conj())
    reduced = partial_trace(rho, (2, 2), (0,))
    assert np.allclose(reduced, np.eye(2) / 2, atol=1e-12)


def test_concurrence_pure_and_density_agree():
    rng = np.random.default_rng(0)
    for _ in range(10):
        psi = rng.normal(size=4) + 1j * rng.normal(size=4)
        psi /= np.linalg.norm(psi)
        rho = np.outer(psi, psi.conj())
        assert abs(concurrence_pure_2qubit(psi) - concurrence_2qubit(rho)) < 1e-10


def test_chsh_helper_rejects_bad_shape():
    with pytest.raises(ValueError):
        chsh_from_correlators(np.zeros((3, 3)))


def test_catalog_surfaces_and_schema():
    data = catalog()
    assert data["schema"] == "cqhecs.qg.catalog.v1"
    assert "OPENQUANTUM_QPU" in data["execution_surfaces"]
    assert data["physical_surfaces"] == ["OPENQUANTUM_QPU"]
    assert any(m["method_id"] == "qg.bmv.zz.v1" for m in data["methods"])


def test_method_card_rejects_bad_surface():
    with pytest.raises(ValueError):
        MethodCard(
            method_id="x",
            title="x",
            track="A",
            surface="NOT_A_SURFACE",
            assumptions=(),
            observables=(),
            established="",
            cannot_establish=(),
        )


def test_error_types_carry_codes():
    err = QGUnsupported("nope", code="X")
    assert err.code == "X"
    blocker = QGBlocker("blocked", code="B", next_action="do this")
    assert blocker.next_action == "do this"


def test_bmv_qasm_is_deterministic_and_null_is_zero():
    assert bmv_qasm(0.5) == bmv_qasm(0.5)
    assert bmv_qasm(0.5) != bmv_qasm(0.6)
    assert "rz(0) q[1];" in bmv_null_qasm()


def test_circuit_manifest_digests_and_roundtrip(tmp_path):
    manifest = build_bmv_manifest(default_theta_values())
    for circuit in manifest["circuits"]:
        assert circuit["qasm_sha256"] == sha256_text(circuit["qasm"])
    target = write_manifest(manifest, tmp_path)
    stored = json.loads(target.read_text("utf-8"))
    assert stored["schema"] == "cqhecs.qg.circuit_manifest.v1"
    for circuit in stored["circuits"]:
        qasm_file = tmp_path / circuit["qasm_file"]
        assert qasm_file.is_file()
        assert sha256_text(qasm_file.read_text("utf-8")) == circuit["qasm_sha256"]


def test_experiment_result_valid_and_roundtrip(tmp_path):
    result = build_experiment_result(
        campaign_id="qg-2026-01",
        experiment_id="qg-bmv-scan-01",
        hypothesis_id="QG-BMV-01",
        model_id="qg.bmv.zz.v1",
        model_version="1.0.0",
        execution_surface="CLASSICAL_REFERENCE",
        status="COMPLETED",
        limitations=["model-only; not a gravitational measurement"],
        observable_estimates={"concurrence": 0.7071},
        numerical_error=1e-12,
    )
    assert result.schema == SCHEMA
    target = result.write(tmp_path / "exp.json")
    reloaded = from_dict(json.loads(target.read_text("utf-8")))
    assert reloaded.experiment_id == "qg-bmv-scan-01"
    assert reloaded.numerical_error == 1e-12


def test_completed_requires_limitation():
    with pytest.raises(SchemaVersionError):
        build_experiment_result(
            campaign_id="c",
            experiment_id="e",
            hypothesis_id="h",
            model_id="m",
            model_version="1",
            execution_surface="CLASSICAL_REFERENCE",
            status="COMPLETED",
        )


def test_refused_requires_reason():
    with pytest.raises(SchemaVersionError):
        build_experiment_result(
            campaign_id="c",
            experiment_id="e",
            hypothesis_id="h",
            model_id="m",
            model_version="1",
            execution_surface="CLASSICAL_REFERENCE",
            status="REFUSED",
            limitations=["x"],
        )


def test_counts_must_total_shots():
    with pytest.raises(SchemaVersionError):
        build_experiment_result(
            campaign_id="c",
            experiment_id="e",
            hypothesis_id="h",
            model_id="m",
            model_version="1",
            execution_surface="OPENQUANTUM_QPU",
            status="COMPLETED",
            limitations=["x"],
            counts={"00": 3, "11": 4},
            shots_returned=10,
        )


def test_unknown_major_schema_is_refused():
    document = {
        "schema": "cqhecs.qg.experiment.v99",
        "campaign_id": "c",
        "experiment_id": "e",
        "hypothesis_id": "h",
        "model_id": "m",
        "model_version": "1",
    }
    with pytest.raises(SchemaVersionError):
        from_dict(document)
