"""
Real-reference dataset harness (v3 W4).

This module is deliberately narrow: it evaluates a CQ-HECS noise model against
*real* measured bitstrings whose circuits are also available. It does not claim
that a noisy emulation is equivalent to a physical device.

The first supported record is ``r-io-5`` (Quantum Noise Transfer, MIT). The
upstream record publishes real counts from ``ibm_fez`` and ``ibm_marrakesh``,
run-time calibration snapshots, and circuit *metadata* (family, width, depth,
gate counts) but not the circuits themselves. Bell, GHZ and QFT circuits are
reconstructed from their standard definitions; the 40 random circuits are
excluded because their gate sequence is not published.

A second record, ``r-io-6`` (BlueQubit ``rcs-nighthawk``, Apache-2.0), is
registered with a pinned Git revision and small checksummed files. It is not
evaluated here: its circuits act on 20-61 qubits, above the exact
density-matrix ceiling of the current noisy backend.

Every number produced here is tagged with the dataset digest, the calibration
digest and the noise-model parameters. A result that does not beat the ideal
distribution is reported as such; the hypothesis is allowed to be rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from cqhecs.hardware_bridge import (
    NoiseModel,
    TwoQubitDepolarizingChannel,
    depolarizing_parameter_from_infidelity,
)

#: Bumped when the on-disk result contract changes.
REFERENCE_SCHEMA_VERSION = "1.0"

_TWO_QUBIT_GATES = frozenset({"cx", "cnot", "cz", "swap", "cp", "cu1", "crx", "cry", "crz"})


class ReferenceDataError(Exception):
    """Base class for reference-dataset failures."""


class DatasetNotAvailableError(ReferenceDataError):
    """The dataset is known but not present locally (and not fetchable here)."""


class IntegrityError(ReferenceDataError):
    """A file is missing, has the wrong size, or fails its pinned SHA-256."""


@dataclass(frozen=True)
class DatasetFile:
    """One pinned file inside a reference dataset."""

    path: str
    sha256: str
    size: int


@dataclass(frozen=True)
class DatasetRecord:
    """Metadata for a real-input/output dataset."""

    dataset_id: str
    title: str
    licence: str
    licence_url: str
    source: str
    raw_base: str
    files: Tuple[DatasetFile, ...]
    pinned_revision: Optional[str] = None
    complete_circuits: bool = False
    redistributable: bool = False
    notes: Tuple[str, ...] = ()

    @property
    def digests(self) -> Dict[str, str]:
        return {f.path: f.sha256 for f in self.files}


#: Registered records. Sizes and digests were measured on 2026-10-30.
DATASETS: Dict[str, DatasetRecord] = {
    "r-io-5": DatasetRecord(
        dataset_id="r-io-5",
        title="Quantum Noise Transfer (real ibm_fez / ibm_marrakesh counts)",
        licence="MIT",
        licence_url="https://huggingface.co/datasets/sahilfarib/quantum-noise-transfer",
        source="https://huggingface.co/datasets/sahilfarib/quantum-noise-transfer",
        raw_base=(
            "https://huggingface.co/datasets/sahilfarib/"
            "quantum-noise-transfer/resolve/main/"
        ),
        files=(
            DatasetFile(
                "data/raw/circuit_meta.json",
                "ef6f02de39f5de79a53d9b62427a65bf084fc9eb60379774396930fd95da8728",
                20993,
            ),
            DatasetFile(
                "data/raw/calibration_A.json",
                "de37663378731563266315635399d8e44b485338164a3f019a0f0e042695a653",
                25442,
            ),
            DatasetFile(
                "data/raw/calibration_B.json",
                "c76a17f94abe37390bdd1babe5df92ee9290ba9c2a917722aa5c9d0ae00cb378",
                25264,
            ),
            DatasetFile(
                "data/raw/noisy_A.json",
                "64a83c7d4b1a152cadd19b5b57f253a0a3548f53233cc15d6c3337d3d8edb749",
                55613,
            ),
            DatasetFile(
                "data/raw/noisy_B.json",
                "916fae86d2028cafcbde11e87b0a0b90515a46f5915c22025962c688980edd26",
                52611,
            ),
        ),
        complete_circuits=False,
        redistributable=True,
        notes=(
            "Bell, GHZ and QFT circuits are reconstructible; random circuits are not.",
            "Physical layout is not published; the harness uses a device-mean model.",
            "Upstream README says 8192 shots, but every raw_counts block sums to 1024.",
        ),
    ),
    "r-io-6": DatasetRecord(
        dataset_id="r-io-6",
        title="BlueQubit rcs-nighthawk (real ibm_phoenix circuits and bitstrings)",
        licence="Apache-2.0",
        licence_url="https://github.com/BlueQubitDev/rcs-nighthawk/blob/main/LICENSE",
        source="https://github.com/BlueQubitDev/rcs-nighthawk",
        raw_base="https://raw.githubusercontent.com/BlueQubitDev/rcs-nighthawk/main/",
        pinned_revision="b9dd86b016743465ebc97fb9f6677f4a251a3baa",
        files=(
            DatasetFile(
                "data/layout.json",
                "7d8192b7175c437a76d4c9f8616a0561cc70a1285b849d9ef0aa433c7705f33b",
                18298,
            ),
            DatasetFile(
                "data/circuits/manifest.json",
                "18353d10816dbb3de16558eba35e88c04f9296cfdc636ff39cf2a0c657596869",
                57997,
            ),
            DatasetFile(
                "data/counts/mirror_survival.json",
                "c9dc298a0c69a4f9dbb4d34b2e1eb329c8dc48512578f40a449b4ca4bba608de",
                10733,
            ),
            DatasetFile(
                "data/results/patch_xeb.json",
                "e30254ae1cdfea37e1d809fdaa7309279ff9c8ff1cafbe2511cb214b9c8a7237",
                84100,
            ),
        ),
        complete_circuits=True,
        redistributable=False,
        notes=(
            "233 QASM/QPY circuits plus raw bitstrings; 20-61 qubits.",
            "Above the exact density-matrix ceiling; registered, not evaluated by W4.",
            "Pinned to the public Git revision; 61 logical qubits map to ibm_phoenix.",
        ),
    ),
}


def dataset(dataset_id: str) -> DatasetRecord:
    """Return a registered dataset record or raise a typed error."""
    try:
        return DATASETS[dataset_id]
    except KeyError as exc:
        raise DatasetNotAvailableError(
            f"unknown reference dataset {dataset_id!r}; known: {sorted(DATASETS)}"
        ) from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_dataset(
    record: DatasetRecord,
    root: Path,
    *,
    allow_missing: bool = False,
) -> Dict[str, str]:
    """
    Verify every pinned file under ``root``.

    ``root`` is either the directory that contains the record's ``path``
    entries, or a directory that contains the final path components (for
    vendored ``data/raw/*.json`` the harness passes the vendored directory and
    maps the basename, see :func:`resolve_file`).
    """
    verified: Dict[str, str] = {}
    missing: List[str] = []
    for entry in record.files:
        candidate = resolve_file(record, root, entry.path)
        if not candidate.is_file():
            missing.append(str(candidate))
            continue
        size = candidate.stat().st_size
        if size != entry.size:
            raise IntegrityError(
                f"{candidate} has {size} bytes, expected {entry.size}"
            )
        actual = _sha256(candidate)
        if actual != entry.sha256:
            raise IntegrityError(
                f"{candidate} has SHA-256 {actual}, expected {entry.sha256}"
            )
        verified[entry.path] = actual
    if missing and not allow_missing:
        raise IntegrityError("missing reference files: " + ", ".join(missing))
    return verified


def resolve_file(record: DatasetRecord, root: Path, logical_path: str) -> Path:
    """
    Map a record-relative path to a local file.

    Vendored datasets keep the upstream basenames in one flat directory. If the
    literal relative path does not exist, the basename in ``root`` is used.
    """
    direct = Path(root) / Path(logical_path)
    if direct.is_file():
        return direct
    return Path(root) / Path(logical_path).name


def fetch_dataset(
    dataset_id: str,
    root: Path,
    *,
    timeout: float = 60.0,
) -> Dict[str, str]:
    """
    Download every pinned file of ``dataset_id`` into ``root`` and verify it.

    Downloads are atomic (``.part`` then replace). A digest mismatch removes the
    partial file and raises :class:`IntegrityError`; no unverified file is left
    behind under its final name.
    """
    record = dataset(dataset_id)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for entry in record.files:
        target = resolve_file(record, root, entry.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and target.stat().st_size == entry.size and _sha256(target) == entry.sha256:
            continue
        url = record.raw_base + entry.path
        request = urllib.request.Request(url, headers={"User-Agent": "CQ-HECS-reference/1.0"})
        temporary = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                with temporary.open("wb") as handle:
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        handle.write(block)
        except (urllib.error.URLError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise DatasetNotAvailableError(f"cannot fetch {url}: {exc}") from exc
        size = temporary.stat().st_size
        if size != entry.size:
            temporary.unlink(missing_ok=True)
            raise IntegrityError(f"{url} returned {size} bytes, expected {entry.size}")
        actual = _sha256(temporary)
        if actual != entry.sha256:
            temporary.unlink(missing_ok=True)
            raise IntegrityError(f"{url} has SHA-256 {actual}, expected {entry.sha256}")
        temporary.replace(target)
    return verify_dataset(record, root)


# ---------------------------------------------------------------------------
# Circuit reconstruction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReferenceCircuit:
    """A circuit reconstructed from a published family definition."""

    circuit_id: str
    backend: str
    family: str
    num_qubits: int
    instructions: Tuple[Tuple[str, Tuple[int, ...], Tuple[float, ...]], ...]
    real_counts: Mapping[str, int]
    exact_gate_sequence: bool
    reconstruction_note: str
    executions: int = 1

    @property
    def shots(self) -> int:
        return sum(self.real_counts.values())


def _bell() -> List[Tuple[str, List[int], List[float]]]:
    return [("h", [0], []), ("cx", [0, 1], []), ("measure", [0], []), ("measure", [1], [])]


def _ghz(n: int) -> List[Tuple[str, List[int], List[float]]]:
    circuit: List[Tuple[str, List[int], List[float]]] = [("h", [0], [])]
    circuit.extend(("cx", [q, q + 1], []) for q in range(n - 1))
    circuit.extend(("measure", [q], []) for q in range(n))
    return circuit


def _qft(n: int) -> List[Tuple[str, List[int], List[float]]]:
    """Canonical QFT (H, controlled phase, final swaps) followed by measurement."""
    circuit: List[Tuple[str, List[int], List[float]]] = []
    for j in range(n):
        circuit.append(("h", [j], []))
        for k in range(j + 1, n):
            angle = math.pi / (2.0 ** (k - j))
            circuit.append(("cp", [k, j], [angle]))
    for i in range(n // 2):
        circuit.append(("swap", [i, n - 1 - i], []))
    circuit.extend(("measure", [q], []) for q in range(n))
    return circuit


def _reconstruct(family: str, n: int) -> Tuple[List[Tuple[str, List[int], List[float]]], bool, str]:
    if family == "bell" and n == 2:
        return _bell(), True, "standard Bell pair H(0); CX(0,1)"
    if family == "ghz" and n >= 2:
        return _ghz(n), True, "standard GHZ H(0); CX chain"
    if family == "qft" and n >= 2:
        return _qft(n), False, (
            "canonical QFT decomposition; the published gate is a single opaque "
            "'QFT' operation, so the exact decomposition is not verified"
        )
    raise ReferenceDataError(f"no reconstruction rule for family={family!r}, n={n}")


@dataclass
class QuantumNoiseTransfer:
    """The parsed, verified ``r-io-5`` record."""

    root: Path
    metadata: Mapping[str, Mapping[str, Any]]
    calibrations: Mapping[str, Mapping[str, Any]]
    counts: Mapping[str, Mapping[str, Mapping[str, int]]]
    digests: Mapping[str, str]

    @property
    def dataset_sha256(self) -> str:
        joined = "".join(f"{name}:{self.digests[name]}\n" for name in sorted(self.digests))
        return hashlib.sha256(joined.encode("ascii")).hexdigest()

    def circuits(
        self,
        backend: str = "A",
        families: Iterable[str] = ("bell", "ghz", "qft"),
        *,
        unique: bool = True,
    ) -> List[ReferenceCircuit]:
        """
        Reconstruct the supported circuits.

        With ``unique=True`` (the default) repeated executions of the same
        circuit definition are pooled into one entry and ``executions`` records
        how many upstream runs were merged. This avoids treating 15 runs of one
        Bell circuit as 15 independent circuits in the bootstrap.
        """
        if backend not in self.calibrations:
            raise ReferenceDataError(f"unknown backend {backend!r}; choose A or B")
        wanted = set(families)
        grouped: Dict[Tuple[Any, ...], ReferenceCircuit] = {}
        order: List[Tuple[Any, ...]] = []
        for circuit_id, meta in self.metadata.items():
            family = str(meta.get("type", ""))
            if family not in wanted:
                continue
            n = int(meta["n_qubits"])
            instructions, exact, note = _reconstruct(family, n)
            entry = self.counts[backend].get(circuit_id)
            if entry is None:
                raise IntegrityError(f"counts for {circuit_id} are missing from backend {backend}")
            raw = entry.get("raw_counts") if isinstance(entry, dict) else None
            if not isinstance(raw, dict):
                raise IntegrityError(f"counts for {circuit_id} have no raw_counts block")
            normalized = {str(k): int(v) for k, v in raw.items()}
            key = (
                family,
                n,
                tuple(sorted((str(k), int(v)) for k, v in (meta.get("gate_counts") or {}).items())),
            )
            if unique and key in grouped:
                previous = grouped[key]
                merged = dict(previous.real_counts)
                for bitstring, count in normalized.items():
                    merged[bitstring] = merged.get(bitstring, 0) + count
                grouped[key] = ReferenceCircuit(
                    circuit_id=previous.circuit_id,
                    backend=previous.backend,
                    family=previous.family,
                    num_qubits=previous.num_qubits,
                    instructions=previous.instructions,
                    real_counts=merged,
                    exact_gate_sequence=previous.exact_gate_sequence,
                    reconstruction_note=previous.reconstruction_note,
                    executions=previous.executions + 1,
                )
                continue
            circuit = ReferenceCircuit(
                circuit_id=circuit_id,
                backend=backend,
                family=family,
                num_qubits=n,
                instructions=tuple(
                    (name, tuple(qubits), tuple(float(p) for p in params))
                    for name, qubits, params in instructions
                ),
                real_counts=normalized,
                exact_gate_sequence=exact,
                reconstruction_note=note,
            )
            grouped[key] = circuit
            order.append(key)
        return [grouped[key] for key in order]


def load_quantum_noise_transfer(root: Path) -> QuantumNoiseTransfer:
    """Load and verify the vendored ``r-io-5`` files."""
    record = dataset("r-io-5")
    root = Path(root)
    digests = verify_dataset(record, root)
    metadata = json.loads(resolve_file(record, root, "data/raw/circuit_meta.json").read_text("utf-8"))
    if not isinstance(metadata, list):
        raise IntegrityError("circuit_meta.json must be a list")
    calibrations = {}
    for backend in ("A", "B"):
        calibrations[backend] = json.loads(
            resolve_file(record, root, f"data/raw/calibration_{backend}.json").read_text("utf-8")
        )
    counts = {}
    for backend in ("A", "B"):
        counts[backend] = json.loads(
            resolve_file(record, root, f"data/raw/noisy_{backend}.json").read_text("utf-8")
        )
    return QuantumNoiseTransfer(
        root=root,
        metadata={str(item["circuit_id"]): item for item in metadata},
        calibrations=calibrations,
        counts=counts,
        digests=digests,
    )


# ---------------------------------------------------------------------------
# Device-mean noise model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeviceMeans:
    """Robust device-wide summaries of a run-time calibration snapshot."""

    backend: str
    captured_at: Optional[str]
    num_qubits: int
    num_operational_edges: int
    cx_error_median: float
    cx_error_mean: float
    readout_error_median: float
    readout_error_mean: float
    two_qubit_depolarizing_parameter: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "captured_at": self.captured_at,
            "num_qubits": self.num_qubits,
            "num_operational_edges": self.num_operational_edges,
            "cx_error_median": self.cx_error_median,
            "cx_error_mean": self.cx_error_mean,
            "readout_error_median": self.readout_error_median,
            "readout_error_mean": self.readout_error_mean,
            "two_qubit_depolarizing_parameter": self.two_qubit_depolarizing_parameter,
        }


def _finite(values: Iterable[Any]) -> List[float]:
    result: List[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        number = float(value)
        if math.isfinite(number):
            result.append(number)
    return result


def device_means(calibration: Mapping[str, Any]) -> DeviceMeans:
    """
    Summarise a calibration snapshot without inventing missing data.

    ``gate_errors`` holds CX error per directed edge. IBM marks a
    non-operational edge with ``1.0``; those entries are excluded from the
    median and reported through ``num_operational_edges``. One-qubit gate
    errors are not present in this record and are therefore not modelled.
    """
    errors: List[float] = []
    operational_pairs: set[Tuple[int, int]] = set()
    for key, value in (calibration.get("gate_errors") or {}).items():
        try:
            pair = json.loads(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        numbers = _finite([value])
        if not numbers:
            continue
        error = numbers[0]
        if 0.0 <= error < 0.75:
            errors.append(error)
            operational_pairs.add((int(pair[0]), int(pair[1])))
    readout = [p for p in _finite(calibration.get("readout_error") or []) if 0.0 <= p <= 0.5]
    if not errors:
        raise ReferenceDataError("calibration has no operational two-qubit gate errors")
    if not readout:
        raise ReferenceDataError("calibration has no readout errors")
    cx_median = float(statistics.median(errors))
    return DeviceMeans(
        backend=str(calibration.get("backend", "unknown")),
        captured_at=calibration.get("retrieved_at"),
        num_qubits=int(calibration.get("n_qubits", 0)),
        num_operational_edges=len({tuple(sorted(pair)) for pair in operational_pairs}),
        cx_error_median=cx_median,
        cx_error_mean=float(statistics.fmean(errors)),
        readout_error_median=float(statistics.median(readout)),
        readout_error_mean=float(statistics.fmean(readout)),
        two_qubit_depolarizing_parameter=depolarizing_parameter_from_infidelity(cx_median, 2),
    )


def build_device_mean_noise_model(
    circuit: ReferenceCircuit,
    means: DeviceMeans,
) -> NoiseModel:
    """
    Build a homogeneous model: median CX depolarizing on every two-qubit gate,
    median symmetric readout on every qubit, no one-qubit gate error.

    The name encodes the parameters so a result cannot be separated from the
    model that produced it.
    """
    model = NoiseModel(
        name=(
            f"device_mean[{means.backend};cx={means.cx_error_median:.8g};"
            f"readout={means.readout_error_median:.8g}]"
        )
    )
    model.metadata = {
        "source": "r-io-5 calibration (device-mean, no layout)",
        "cx_error_median": means.cx_error_median,
        "readout_error_median": means.readout_error_median,
        "one_qubit_gate_error": "not published in this record; modelled as 0",
        "relaxation": False,
    }
    seen: set[Tuple[str, Tuple[int, ...]]] = set()
    for name, qubits, _params in circuit.instructions:
        if name not in _TWO_QUBIT_GATES or len(qubits) != 2:
            continue
        key = (name, tuple(qubits))
        if key in seen:
            continue
        seen.add(key)
        model.add_2q_channel(
            name,
            (int(qubits[0]), int(qubits[1])),
            TwoQubitDepolarizingChannel(means.two_qubit_depolarizing_parameter),
        )
    low, high = means.readout_error_median, means.readout_error_median
    for qubit in range(circuit.num_qubits):
        model.set_readout_error(qubit, low, high)
    model.validate()
    return model


# ---------------------------------------------------------------------------
# Metrics and evaluation
# ---------------------------------------------------------------------------


def counts_vector(counts: Mapping[str, int], num_qubits: int) -> np.ndarray:
    """Normalise counts into a length-``2**n`` probability vector."""
    vector = np.zeros(1 << num_qubits, dtype=float)
    total = 0
    for bitstring, count in counts.items():
        key = str(bitstring).replace(" ", "")
        if len(key) != num_qubits:
            raise ValueError(
                f"bitstring {bitstring!r} has {len(key)} bits, expected {num_qubits}"
            )
        if count < 0:
            raise ValueError(f"negative count for {bitstring!r}")
        vector[int(key, 2)] += float(count)
        total += int(count)
    if total <= 0:
        raise ValueError("counts are empty")
    return vector / total


def probabilities_vector(probabilities: Mapping[str, float], num_qubits: int) -> np.ndarray:
    """Convert a backend probability dictionary into a dense vector."""
    vector = np.zeros(1 << num_qubits, dtype=float)
    for bitstring, probability in probabilities.items():
        key = str(bitstring)
        if len(key) != num_qubits:
            raise ValueError(
                f"bitstring {bitstring!r} has {len(key)} bits, expected {num_qubits}"
            )
        value = float(probability)
        if value < 0.0 or not math.isfinite(value):
            raise ValueError(f"invalid probability {probability!r} for {bitstring!r}")
        vector[int(key, 2)] = value
    return vector


def total_variation(p: np.ndarray, q: np.ndarray) -> float:
    """Total variation distance between two probability vectors."""
    if p.shape != q.shape:
        raise ValueError("distributions have different shapes")
    return 0.5 * float(np.abs(p - q).sum())


def _simulate(circuit: ReferenceCircuit, noise_model: Optional[NoiseModel]) -> np.ndarray:
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
        [list(instruction) for instruction in circuit.instructions],
        noise_model=noise_model,
        shots=1,
        seed=0,
    )
    if not result.probabilities:
        raise ReferenceDataError(
            f"simulation of {circuit.circuit_id} returned no probabilities: {result.state}"
        )
    return probabilities_vector(result.probabilities, circuit.num_qubits)


@dataclass
class CircuitEvaluation:
    circuit_id: str
    backend: str
    family: str
    num_qubits: int
    shots: int
    executions: int
    tv_ideal: float
    tv_noisy: float
    delta: float
    exact_gate_sequence: bool
    reconstruction_note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "circuit_id": self.circuit_id,
            "backend": self.backend,
            "family": self.family,
            "num_qubits": self.num_qubits,
            "shots": self.shots,
            "executions": self.executions,
            "tv_ideal": self.tv_ideal,
            "tv_noisy": self.tv_noisy,
            "delta_tv": self.delta,
            "exact_gate_sequence": self.exact_gate_sequence,
            "reconstruction_note": self.reconstruction_note,
        }


@dataclass
class ReferenceEvaluation:
    dataset_id: str
    dataset_sha256: str
    circuit_digest: str
    model: Mapping[str, Any]
    circuits: List[CircuitEvaluation]
    aggregate: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": REFERENCE_SCHEMA_VERSION,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "circuit_digest": self.circuit_digest,
            "model": dict(self.model),
            "hypothesis": {
                "id": "H-V3-1",
                "statement": (
                    "On reconstructible circuits, the device-mean noisy prediction has a "
                    "smaller total-variation distance to the real counts than the ideal "
                    "distribution, with a median paired difference below 0 and a 95% "
                    "bootstrap interval excluding 0."
                ),
            },
            "aggregate": self.aggregate,
            "circuits": [item.to_dict() for item in self.circuits],
        }


def _bootstrap_median_delta(
    deltas: Sequence[float],
    *,
    samples: int,
    rng: np.random.Generator,
) -> Tuple[float, float, float]:
    if not deltas:
        raise ValueError("no deltas to bootstrap")
    data = np.asarray(deltas, dtype=float)
    if len(data) == 1:
        value = float(data[0])
        return value, value, value
    draws = np.empty(samples, dtype=float)
    for index in range(samples):
        draws[index] = float(np.median(rng.choice(data, size=len(data), replace=True)))
    return float(np.median(data)), float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def evaluate(
    dataset_root: Path,
    *,
    backends: Sequence[str] = ("A", "B"),
    bootstrap_samples: int = 1000,
    seed: int = 20261030,
) -> ReferenceEvaluation:
    """
    Run the preregistered H-V3-1 evaluation on all reconstructible circuits.

    The bootstrap resamples circuits (the unit of the hypothesis) and, inside
    each circuit, the measured shots. It never resamples the model, which is
    fixed by calibration before the run.
    """
    data = load_quantum_noise_transfer(dataset_root)
    evaluations: List[CircuitEvaluation] = []
    model_info: Dict[str, Any] = {}
    rng = np.random.default_rng(seed)

    for backend in backends:
        means = device_means(data.calibrations[backend])
        model_info[backend] = means.to_dict()
        for circuit in data.circuits(backend):
            ideal = _simulate(circuit, None)
            noisy = _simulate(circuit, build_device_mean_noise_model(circuit, means))
            real = counts_vector(circuit.real_counts, circuit.num_qubits)
            tv_ideal = total_variation(real, ideal)
            tv_noisy = total_variation(real, noisy)
            evaluations.append(
                CircuitEvaluation(
                    circuit_id=circuit.circuit_id,
                    backend=backend,
                    family=circuit.family,
                    num_qubits=circuit.num_qubits,
                    shots=circuit.shots,
                    executions=circuit.executions,
                    tv_ideal=tv_ideal,
                    tv_noisy=tv_noisy,
                    delta=tv_noisy - tv_ideal,
                    exact_gate_sequence=circuit.exact_gate_sequence,
                    reconstruction_note=circuit.reconstruction_note,
                )
            )

    deltas = [item.delta for item in evaluations]
    median, low, high = _bootstrap_median_delta(deltas, samples=bootstrap_samples, rng=rng)

    def summary(items: Sequence[CircuitEvaluation]) -> Dict[str, Any]:
        values = [item.delta for item in items]
        if not values:
            return {"n": 0}
        med, lo, hi = _bootstrap_median_delta(values, samples=bootstrap_samples, rng=rng)
        return {
            "n": len(values),
            "median_delta_tv": med,
            "mean_delta_tv": float(np.mean(values)),
            "ci95_low": lo,
            "ci95_high": hi,
            "n_noisy_better": sum(1 for value in values if value < 0),
            "median_tv_ideal": float(np.median([item.tv_ideal for item in items])),
            "median_tv_noisy": float(np.median([item.tv_noisy for item in items])),
        }

    families = sorted({item.family for item in evaluations})
    aggregate = {
        "n_circuits": len(evaluations),
        "median_delta_tv": median,
        "ci95_low": low,
        "ci95_high": high,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed,
        "verdict": "SUPPORTED" if high < 0.0 else ("REJECTED" if low > 0.0 else "INCONCLUSIVE"),
        "by_backend": {backend: summary([x for x in evaluations if x.backend == backend]) for backend in backends},
        "by_family": {family: summary([x for x in evaluations if x.family == family]) for family in families},
    }
    # Exploratory, not preregistered: QFT-on-|0...0> is maximally mixed, and a
    # unital noise model cannot move it. Excluding it shows whether the model
    # is identifiable at all, but the formal verdict stays the pooled one.
    identifiable = [x for x in evaluations if x.family in ("bell", "ghz")]
    if identifiable:
        med, lo, hi = _bootstrap_median_delta(
            [x.delta for x in identifiable], samples=bootstrap_samples, rng=rng
        )
        aggregate["exploratory_identifiable"] = {
            "families": ["bell", "ghz"],
            "n": len(identifiable),
            "median_delta_tv": med,
            "ci95_low": lo,
            "ci95_high": hi,
            "n_noisy_better": sum(1 for x in identifiable if x.delta < 0),
            "verdict": "SUPPORTED" if hi < 0.0 else ("REJECTED" if lo > 0.0 else "INCONCLUSIVE"),
            "note": (
                "not preregistered; QFT on the zero state is invariant under unital "
                "noise, so the pooled test includes six structurally uninformative circuits"
            ),
        }

    circuit_digest = hashlib.sha256(
        "".join(f"{item.circuit_id}:{item.backend}\n" for item in sorted(evaluations, key=lambda x: (x.backend, x.circuit_id))).encode("ascii")
    ).hexdigest()

    return ReferenceEvaluation(
        dataset_id="r-io-5",
        dataset_sha256=data.dataset_sha256,
        circuit_digest=circuit_digest,
        model={
            "kind": "device-mean calibration, no physical layout",
            "backends": model_info,
            "one_qubit_gate_error": "not published in this record; modelled as 0",
            "shots_are_not_resampled_for_the_model": True,
        },
        circuits=evaluations,
        aggregate=aggregate,
    )
