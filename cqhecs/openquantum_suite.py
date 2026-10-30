"""
Preregistered 25-job real-QPU suite for Open Quantum (v3 W4, dataset ``r-io-7``).

The public records used so far (``r-io-5``) publish counts but not the exact
circuits or layout. This suite closes that gap with jobs we author ourselves:
every circuit is generated here from a fixed seed, its OpenQASM 2.0 text is
SHA-256-pinned in a manifest *before* any job is submitted, and the measured
counts are matched back to that digest.

Split (fixed before any run):

* ``FIT`` (5 jobs): readout probes and CX-padded GHZ circuits. The noise model
  ``M-FIT`` (mean readout + one two-qubit depolarizing parameter on ``cx``) is
  fitted on these only.
* ``EVAL`` (20 jobs): held out. Hypothesis ``H-V3-8`` is tested on them.

The module never talks to the network. Submission goes through the Open
Quantum CLI (``scripts/run_openquantum_suite.py``); this module only builds the
circuits, ingests result folders and evaluates them. Without real result
folders it raises :class:`~cqhecs.reference.DatasetNotAvailableError`; it never
fills in counts.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from cqhecs.hardware_bridge import NoiseModel, TwoQubitDepolarizingChannel
from cqhecs.reference import (
    DatasetNotAvailableError,
    IntegrityError,
    ReferenceDataError,
    _bootstrap_median_delta,
    counts_vector,
    probabilities_vector,
    total_variation,
)

SUITE_ID = "r-io-7"
SUITE_VERSION = "1.0"
SUITE_SEED = 20261030
DEFAULT_SHOTS = 1000

_ONE_QUBIT_CLIFFORD_T = ("h", "s", "sdg", "t", "tdg", "x", "sx")
_SELF_INVERSE = {"h": "h", "x": "x", "cx": "cx", "s": "sdg", "sdg": "s", "t": "tdg", "tdg": "t"}

Gate = Tuple[str, Tuple[int, ...], Tuple[float, ...]]


@dataclass(frozen=True)
class SuiteCircuit:
    """One preregistered job of the suite."""

    job_id: str
    name: str
    split: str
    family: str
    num_qubits: int
    gates: Tuple[Gate, ...]
    purpose: str
    shots: int = DEFAULT_SHOTS

    @property
    def qasm(self) -> str:
        return to_qasm(self.gates, self.num_qubits)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.qasm.encode("ascii")).hexdigest()

    @property
    def cx_count(self) -> int:
        return sum(1 for name, _q, _p in self.gates if name == "cx")

    def instructions(self) -> List[List[Any]]:
        """CQ-HECS instruction list including terminal measurements."""
        body = [[name, list(qubits), list(params)] for name, qubits, params in self.gates]
        body.extend(["measure", [q], []] for q in range(self.num_qubits))
        return body


def _fmt(value: float) -> str:
    # repr round-trips a float64 exactly, so the QASM text pins the angle.
    return repr(float(value))


def to_qasm(gates: Sequence[Gate], num_qubits: int) -> str:
    """Render a gate list as OpenQASM 2.0 (one ``qreg``, one ``creg``)."""
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{num_qubits}];", f"creg c[{num_qubits}];"]
    for name, qubits, params in gates:
        args = ",".join(f"q[{q}]" for q in qubits)
        if params:
            lines.append(f"{name}({','.join(_fmt(p) for p in params)}) {args};")
        else:
            lines.append(f"{name} {args};")
    lines.extend(f"measure q[{q}] -> c[{q}];" for q in range(num_qubits))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Circuit families
# ---------------------------------------------------------------------------


def _ghz(n: int, pad: int = 0) -> List[Gate]:
    """GHZ chain; ``pad`` extra CX pairs per link leave the state unchanged."""
    gates: List[Gate] = [("h", (0,), ())]
    for q in range(n - 1):
        gates.append(("cx", (q, q + 1), ()))
        for _ in range(pad):
            gates.append(("cx", (q, q + 1), ()))
            gates.append(("cx", (q, q + 1), ()))
    return gates


def _cp(control: int, target: int, angle: float) -> List[Gate]:
    """Controlled phase in the {rz, cx} basis (exact up to global phase)."""
    half = angle / 2.0
    return [
        ("rz", (control,), (half,)),
        ("cx", (control, target), ()),
        ("rz", (target,), (-half,)),
        ("cx", (control, target), ()),
        ("rz", (target,), (half,)),
    ]


def _qft(qubits: Sequence[int], inverse: bool = False) -> List[Gate]:
    """QFT without final swaps on ``qubits`` (most significant first)."""
    forward: List[Gate] = []
    n = len(qubits)
    for j in range(n):
        forward.append(("h", (qubits[j],), ()))
        for k in range(j + 1, n):
            forward.extend(_cp(qubits[k], qubits[j], math.pi / (2.0 ** (k - j))))
    if not inverse:
        return forward
    return _invert(forward)


def _invert(gates: Sequence[Gate]) -> List[Gate]:
    result: List[Gate] = []
    for name, qubits, params in reversed(gates):
        if name in ("rz", "rx", "ry"):
            result.append((name, qubits, (-params[0],)))
        elif name == "sx":
            result.append(("rx", qubits, (-math.pi / 2.0,)))
        elif name in _SELF_INVERSE:
            result.append((_SELF_INVERSE[name], qubits, params))
        else:
            raise ValueError(f"no inverse rule for {name}")
    return result


def _swap(a: int, b: int) -> List[Gate]:
    return [("cx", (a, b), ()), ("cx", (b, a), ()), ("cx", (a, b), ())]


def _qft_little_endian(n: int) -> List[Gate]:
    """Textbook QFT on qubits 0..n-1 (qubit 0 least significant), with swaps."""
    gates: List[Gate] = []
    for top in range(n - 1, -1, -1):
        gates.append(("h", (top,), ()))
        for qubit in range(top):
            gates.extend(_cp(qubit, top, math.pi / (2.0 ** (top - qubit))))
    for qubit in range(n // 2):
        gates.extend(_swap(qubit, n - 1 - qubit))
    return gates


def _qpe(phase_gate: str, counting: int = 3) -> Tuple[List[Gate], int]:
    """
    Phase estimation of a one-qubit phase gate on its |1> eigenstate.

    Counting qubits 0..counting-1 (qubit k controls U^(2^k)), target
    ``counting``. The counting register then holds ``phase * 2^counting``.
    """
    theta = {"t": math.pi / 4.0, "s": math.pi / 2.0}[phase_gate]
    target = counting
    gates: List[Gate] = [("x", (target,), ())]
    gates.extend(("h", (q,), ()) for q in range(counting))
    for k in range(counting):
        gates.extend(_cp(k, target, (2 ** k) * theta))
    gates.extend(_invert(_qft_little_endian(counting)))
    return gates, counting + 1


def _random_clifford_t(n: int, depth: int, rng: np.random.Generator) -> List[Gate]:
    gates: List[Gate] = []
    for _ in range(depth):
        if n > 1 and rng.random() < 0.4:
            a, b = (int(x) for x in rng.choice(n, size=2, replace=False))
            gates.append(("cx", (a, b), ()))
        else:
            gate = str(rng.choice(_ONE_QUBIT_CLIFFORD_T))
            gates.append((gate, (int(rng.integers(n)),), ()))
    return gates


def _mirror(n: int, depth: int, rng: np.random.Generator) -> List[Gate]:
    """U followed by U^-1 (sx excluded so the inverse stays in the gate set)."""
    forward = [g for g in _random_clifford_t(n, depth, rng) if g[0] != "sx"]
    return forward + _invert(forward)


def _brickwork(n: int, layers: int, rng: np.random.Generator) -> List[Gate]:
    gates: List[Gate] = []
    for layer in range(layers):
        for q in range(n):
            a, b, c = (float(x) for x in rng.uniform(0.0, 2.0 * math.pi, size=3))
            gates.extend([("rz", (q,), (a,)), ("ry", (q,), (b,)), ("rz", (q,), (c,))])
        for q in range(layer % 2, n - 1, 2):
            gates.append(("cx", (q, q + 1), ()))
    return gates


def _grover_11() -> List[Gate]:
    return [
        ("h", (0,), ()), ("h", (1,), ()),
        # oracle: CZ = H(1) CX H(1)
        ("h", (1,), ()), ("cx", (0, 1), ()), ("h", (1,), ()),
        # diffusion
        ("h", (0,), ()), ("h", (1,), ()), ("x", (0,), ()), ("x", (1,), ()),
        ("h", (1,), ()), ("cx", (0, 1), ()), ("h", (1,), ()),
        ("x", (0,), ()), ("x", (1,), ()), ("h", (0,), ()), ("h", (1,), ()),
    ]


def _bernstein_vazirani(secret: str) -> Tuple[List[Gate], int]:
    """Secret bit i (from the right) on qubit i; ancilla is the last qubit."""
    n = len(secret)
    anc = n
    gates: List[Gate] = [("x", (anc,), ()), ("h", (anc,), ())]
    gates.extend(("h", (q,), ()) for q in range(n))
    for q, bit in enumerate(reversed(secret)):
        if bit == "1":
            gates.append(("cx", (q, anc), ()))
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.append(("h", (anc,), ()))
    gates.append(("x", (anc,), ()))
    return gates, n + 1


def _deutsch_jozsa_balanced(n: int) -> Tuple[List[Gate], int]:
    """Balanced oracle f(x) = x_0 xor ... xor x_{n-1}; ancilla returned to |0>."""
    anc = n
    gates: List[Gate] = [("x", (anc,), ()), ("h", (anc,), ())]
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.extend(("cx", (q, anc), ()) for q in range(n))
    gates.extend(("h", (q,), ()) for q in range(n))
    gates.append(("h", (anc,), ()))
    gates.append(("x", (anc,), ()))
    return gates, n + 1


def build_suite(seed: int = SUITE_SEED) -> List[SuiteCircuit]:
    """Return the 25 preregistered jobs in submission order."""
    rng = np.random.default_rng(seed)
    jobs: List[SuiteCircuit] = []

    def add(name: str, split: str, family: str, n: int, gates: Sequence[Gate], purpose: str) -> None:
        jobs.append(
            SuiteCircuit(
                job_id=f"OQ-{len(jobs) + 1:02d}",
                name=name,
                split=split,
                family=family,
                num_qubits=n,
                gates=tuple((g, tuple(q), tuple(float(x) for x in p)) for g, q, p in gates),
                purpose=purpose,
            )
        )

    # FIT split -------------------------------------------------------------
    # A bare `measure` circuit has no gates; `id` is not in every backend's
    # basis, so the zero probe is a pair of X gates per qubit.
    add("readout_zero_5", "FIT", "probe", 5,
        [("x", (q,), ()) for q in range(5)] + [("x", (q,), ()) for q in range(5)],
        "P(1|0) per qubit")
    add("readout_one_5", "FIT", "probe", 5, [("x", (q,), ()) for q in range(5)], "P(0|1) per qubit")
    add("bitorder_q0_5", "FIT", "probe", 5, [("x", (0,), ())],
        "bit-order check: ideal outcome 00001 (qubit 0 rightmost)")
    add("ghz5_pad2", "FIT", "ghz_padded", 5, _ghz(5, pad=2), "CX error fit (5 CX per link)")
    add("ghz5_pad4", "FIT", "ghz_padded", 5, _ghz(5, pad=4), "CX error fit (9 CX per link)")

    # EVAL split ------------------------------------------------------------
    add("bell", "EVAL", "ghz", 2, _ghz(2), "two-qubit entanglement")
    add("ghz3", "EVAL", "ghz", 3, _ghz(3), "entanglement")
    add("ghz4", "EVAL", "ghz", 4, _ghz(4), "entanglement")
    add("ghz5", "EVAL", "ghz", 5, _ghz(5), "entanglement")
    qpe_t, n_t = _qpe("t")
    add("qpe3_t", "EVAL", "qpe", n_t, qpe_t, "phase 1/8: ideal outcome 1001 (target 1, counting 001)")
    qpe_s, n_s = _qpe("s")
    add("qpe3_s", "EVAL", "qpe", n_s, qpe_s, "phase 1/4: ideal outcome 1010 (target 1, counting 010)")
    prep = [("x", (1,), ()), ("x", (3,), ())]
    add("qft4_roundtrip", "EVAL", "qft_mirror", 4, prep + _qft([0, 1, 2, 3]) + _qft([0, 1, 2, 3], inverse=True),
        "QFT then inverse QFT on |1010>")
    for depth in (10, 20, 40):
        add(f"mirror4_d{depth}", "EVAL", "mirror", 4, _mirror(4, depth, rng), "U U^-1 returns 0000")
    for n, depth in ((3, 12), (4, 16), (5, 20), (5, 30)):
        add(f"clifford_t{n}_d{depth}", "EVAL", "clifford_t", n, _random_clifford_t(n, depth, rng),
            "random Clifford+T (Path B family)")
    add("brickwork4_l3", "EVAL", "brickwork", 4, _brickwork(4, 3, rng), "random rotations + CX bricks")
    add("brickwork5_l4", "EVAL", "brickwork", 5, _brickwork(5, 4, rng), "random rotations + CX bricks")
    add("grover2_mark11", "EVAL", "algorithm", 2, _grover_11(), "ideal outcome 11")
    bv, n_bv = _bernstein_vazirani("1011")
    add("bv4_1011", "EVAL", "algorithm", n_bv, bv, "ideal outcome 01011")
    dj, n_dj = _deutsch_jozsa_balanced(3)
    add("dj3_balanced", "EVAL", "algorithm", n_dj, dj, "ideal outcome 0111")
    add("ghz5_repeat", "EVAL", "ghz", 5, _ghz(5), "drift check, submitted last")

    if len(jobs) != 25:
        raise AssertionError(f"suite must have 25 jobs, built {len(jobs)}")
    return jobs


def suite_manifest(jobs: Optional[Sequence[SuiteCircuit]] = None, seed: int = SUITE_SEED) -> Dict[str, Any]:
    """JSON-serialisable manifest: digests, splits and ideal distributions."""
    jobs = list(jobs) if jobs is not None else build_suite(seed)
    entries = []
    for job in jobs:
        ideal = simulate(job, None)
        support = {
            format(i, f"0{job.num_qubits}b"): round(float(p), 12)
            for i, p in enumerate(ideal)
            if p > 1e-12
        }
        entries.append(
            {
                "job_id": job.job_id,
                "name": job.name,
                "split": job.split,
                "family": job.family,
                "num_qubits": job.num_qubits,
                "cx_count": job.cx_count,
                "shots": job.shots,
                "purpose": job.purpose,
                "qasm_file": f"{job.job_id}_{job.name}.qasm",
                "qasm_sha256": job.sha256,
                "ideal_support": support if len(support) <= 64 else {"entries": len(support)},
            }
        )
    return {
        "suite_id": SUITE_ID,
        "suite_version": SUITE_VERSION,
        "seed": seed,
        "bit_order": "qubit 0 rightmost (Qiskit little-endian); verified per backend by OQ-03",
        "jobs": entries,
    }


def write_suite(target: Path, seed: int = SUITE_SEED) -> Dict[str, Any]:
    """Write every QASM file plus ``manifest.json`` into ``target``."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    jobs = build_suite(seed)
    manifest = suite_manifest(jobs, seed)
    for job, entry in zip(jobs, manifest["jobs"]):
        (target / entry["qasm_file"]).write_bytes(job.qasm.encode("ascii"))
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Simulation and the M-FIT model
# ---------------------------------------------------------------------------


def simulate(job: SuiteCircuit, noise_model: Optional[NoiseModel]) -> np.ndarray:
    from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend

    result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
        job.instructions(), noise_model=noise_model, shots=1, seed=0
    )
    if not result.probabilities:
        raise ReferenceDataError(f"simulation of {job.job_id} returned no probabilities: {result.state}")
    return probabilities_vector(result.probabilities, job.num_qubits)


@dataclass(frozen=True)
class FittedModel:
    """``M-FIT``: mean readout and one CX depolarizing parameter."""

    p01: float
    p10: float
    cx_depolarizing: float
    per_qubit_p01: Tuple[float, ...]
    per_qubit_p10: Tuple[float, ...]
    fit_tv: float
    fit_jobs: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": "M-FIT",
            "p01_mean": self.p01,
            "p10_mean": self.p10,
            "cx_depolarizing": self.cx_depolarizing,
            "per_qubit_p01": list(self.per_qubit_p01),
            "per_qubit_p10": list(self.per_qubit_p10),
            "fit_mean_tv": self.fit_tv,
            "fit_jobs": list(self.fit_jobs),
            "one_qubit_gate_error": "not modelled (0)",
            "relaxation": False,
        }

    def noise_model(self, job: SuiteCircuit) -> NoiseModel:
        model = NoiseModel(name=f"M-FIT[cx={self.cx_depolarizing:.8g};p01={self.p01:.8g};p10={self.p10:.8g}]")
        model.metadata = self.to_dict()
        if self.cx_depolarizing > 0.0:
            pairs = {tuple(q) for name, q, _ in job.gates if name == "cx"}
            for pair in sorted(pairs):
                model.add_2q_channel("cx", pair, TwoQubitDepolarizingChannel(self.cx_depolarizing))
        for qubit in range(job.num_qubits):
            model.set_readout_error(qubit, self.p01, self.p10)
        model.validate()
        return model


def _marginal_flip_rates(counts: Mapping[str, int], num_qubits: int, expected_bit: str) -> List[float]:
    total = sum(counts.values())
    rates = []
    for qubit in range(num_qubits):
        position = num_qubits - 1 - qubit
        flipped = sum(c for bits, c in counts.items() if bits[position] != expected_bit)
        rates.append(flipped / total)
    return rates


def fit_model(
    jobs: Mapping[str, SuiteCircuit],
    counts: Mapping[str, Mapping[str, int]],
    *,
    coarse_points: int = 61,
    fine_points: int = 41,
    p_max: float = 0.3,
) -> FittedModel:
    """
    Fit ``M-FIT`` on the FIT split only.

    Readout comes from OQ-01/OQ-02 marginals. The CX depolarizing parameter
    minimises the mean TV over the padded GHZ jobs on fixed grids (resolution
    ``p_max / ((coarse_points - 1) * (fine_points - 1) / 2)``).
    """
    by_name = {job.name: job for job in jobs.values()}
    for needed in ("readout_zero_5", "readout_one_5", "ghz5_pad2", "ghz5_pad4"):
        if by_name[needed].job_id not in counts:
            raise DatasetNotAvailableError(f"FIT job {by_name[needed].job_id} ({needed}) has no counts")
    zero = by_name["readout_zero_5"]
    one = by_name["readout_one_5"]
    p01_q = _marginal_flip_rates(counts[zero.job_id], 5, "0")
    p10_q = _marginal_flip_rates(counts[one.job_id], 5, "1")
    p01 = float(np.mean(p01_q))
    p10 = float(np.mean(p10_q))

    padded = [by_name["ghz5_pad2"], by_name["ghz5_pad4"]]
    real = [counts_vector(counts[job.job_id], job.num_qubits) for job in padded]

    def score(p: float) -> float:
        candidate = FittedModel(p01, p10, p, tuple(p01_q), tuple(p10_q), 0.0, ())
        return float(np.mean([
            total_variation(r, simulate(job, candidate.noise_model(job))) for job, r in zip(padded, real)
        ]))

    # Coarse grid, then a fine grid around the coarse minimum. Both grids are
    # fixed, so the fit is reproducible bit for bit.
    best = min((score(float(p)), float(p)) for p in np.linspace(0.0, p_max, coarse_points))
    step = p_max / (coarse_points - 1)
    low, high = max(0.0, best[1] - step), min(p_max, best[1] + step)
    best = min([best] + [(score(float(p)), float(p)) for p in np.linspace(low, high, fine_points)])
    fit_ids = tuple(sorted(by_name[n].job_id for n in ("readout_zero_5", "readout_one_5", "ghz5_pad2", "ghz5_pad4")))
    return FittedModel(p01, p10, best[1], tuple(p01_q), tuple(p10_q), best[0], fit_ids)


# ---------------------------------------------------------------------------
# Ingest of Open Quantum result folders
# ---------------------------------------------------------------------------


def _extract_counts(payload: Any) -> Optional[Dict[str, int]]:
    """Find a ``{bitstring: count}`` map in an Open Quantum result payload."""
    if isinstance(payload, dict):
        if payload and all(
            isinstance(k, str) and set(k.replace(" ", "")) <= {"0", "1"} and k.strip()
            and isinstance(v, (int, float)) and not isinstance(v, bool)
            for k, v in payload.items()
        ):
            result: Dict[str, int] = {}
            for key, value in payload.items():
                if float(value) != int(value) or value < 0:
                    raise IntegrityError(f"count for {key!r} is not a non-negative integer: {value!r}")
                result[key.replace(" ", "")] = int(value)
            return result
        for key in ("counts", "measurement_counts", "histogram", "results", "result", "data"):
            if key in payload:
                inner = payload[key]
                if isinstance(inner, list) and inner:
                    inner = inner[0]
                found = _extract_counts(inner)
                if found:
                    return found
    if isinstance(payload, list) and payload:
        return _extract_counts(payload[0])
    return None


@dataclass
class SuiteRun:
    """Measured counts for the suite, keyed by job ID."""

    root: Path
    backend: str
    counts: Dict[str, Dict[str, int]]
    files: Dict[str, str]
    provider_job_ids: Dict[str, str]
    calibration_files: Dict[str, str] = field(default_factory=dict)

    @property
    def dataset_sha256(self) -> str:
        joined = "".join(f"{name}:{self.files[name]}\n" for name in sorted(self.files))
        return hashlib.sha256(joined.encode("ascii")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_suite_run(root: Path, seed: int = SUITE_SEED) -> SuiteRun:
    """
    Load ``<root>/<JOB_ID>/{circuit.qasm,result.json,job.json}`` folders.

    Each folder's ``circuit.qasm`` must match the preregistered digest; a
    mismatch is an :class:`IntegrityError`, never a silent re-mapping. Width
    and bit order of every count key are checked. Missing jobs are allowed
    here; the evaluation refuses to run without the whole FIT split.
    """
    root = Path(root)
    if not root.is_dir():
        raise DatasetNotAvailableError(
            f"{root} does not exist; run scripts/run_openquantum_suite.py on a machine "
            "that can reach openquantum.com first"
        )
    jobs = {job.job_id: job for job in build_suite(seed)}
    counts: Dict[str, Dict[str, int]] = {}
    files: Dict[str, str] = {}
    provider_ids: Dict[str, str] = {}
    calibrations: Dict[str, str] = {}
    backends = set()
    for job_id, job in jobs.items():
        folder = root / job_id
        if not folder.is_dir():
            continue
        qasm = folder / "circuit.qasm"
        result = folder / "result.json"
        if not qasm.is_file() or not result.is_file():
            raise IntegrityError(f"{folder} needs circuit.qasm and result.json")
        # Compare the text, not the platform's line endings: a Windows
        # checkout or writer may store the preregistered file with CRLF.
        digest = hashlib.sha256(qasm.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if digest != job.sha256:
            raise IntegrityError(f"{qasm} has SHA-256 {digest}, preregistered {job.sha256}")
        payload = json.loads(result.read_text("utf-8"))
        found = _extract_counts(payload)
        if not found:
            raise IntegrityError(f"{result} contains no counts map")
        for key in found:
            if len(key) != job.num_qubits:
                raise IntegrityError(
                    f"{job_id}: outcome {key!r} has {len(key)} bits, expected {job.num_qubits}"
                )
        counts[job_id] = found
        files[f"{job_id}/result.json"] = _sha256_file(result)
        files[f"{job_id}/circuit.qasm"] = digest
        meta_path = folder / "job.json"
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text("utf-8"))
            job_meta = meta.get("job") or {}
            if job_meta.get("id"):
                provider_ids[job_id] = str(job_meta["id"])
            backend = (meta.get("quote") or {}).get("backend") or job_meta.get("backend")
            if backend:
                backends.add(str(backend))
        calibration = folder / "calibration.json"
        if calibration.is_file():
            calibrations[job_id] = _sha256_file(calibration)
    if not counts:
        raise DatasetNotAvailableError(f"no suite result folders under {root}")
    if len(backends) > 1:
        raise IntegrityError(f"suite results mix backends {sorted(backends)}; evaluate one backend at a time")
    return SuiteRun(
        root=root,
        backend=next(iter(backends)) if backends else "unknown",
        counts=counts,
        files=files,
        provider_job_ids=provider_ids,
        calibration_files=calibrations,
    )


def check_bit_order(run: SuiteRun, seed: int = SUITE_SEED) -> Dict[str, Any]:
    """OQ-03 applies X to qubit 0 only; the mode must be ``00001``."""
    jobs = {job.job_id: job for job in build_suite(seed)}
    probe = next(job for job in jobs.values() if job.name == "bitorder_q0_5")
    if probe.job_id not in run.counts:
        raise DatasetNotAvailableError(f"bit-order probe {probe.job_id} has no counts")
    counts = run.counts[probe.job_id]
    mode = max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return {"job_id": probe.job_id, "mode": mode, "expected": "00001", "little_endian": mode == "00001"}


def evaluate_suite(
    root: Path,
    *,
    bootstrap_samples: int = 5000,
    seed: int = SUITE_SEED,
) -> Dict[str, Any]:
    """
    Evaluate preregistered hypothesis ``H-V3-8`` on the EVAL split.

    ``delta_tv = TV(real, M-FIT) - TV(real, ideal)``. SUPPORTED needs the
    95 % bootstrap interval of the median delta (circuits resampled) to lie
    below 0. A bit-order mismatch stops the evaluation instead of flipping
    strings, because a silent reversal would hide a convention error.
    """
    run = load_suite_run(root, seed)
    jobs = {job.job_id: job for job in build_suite(seed)}
    order = check_bit_order(run, seed)
    if not order["little_endian"]:
        raise IntegrityError(
            f"bit-order probe returned {order['mode']!r}, expected '00001'; "
            "the backend's bit order differs and must be handled explicitly"
        )
    model = fit_model(jobs, run.counts)
    rows: List[Dict[str, Any]] = []
    for job_id, job in jobs.items():
        if job.split != "EVAL" or job_id not in run.counts:
            continue
        real = counts_vector(run.counts[job_id], job.num_qubits)
        ideal = simulate(job, None)
        noisy = simulate(job, model.noise_model(job))
        tv_ideal = total_variation(real, ideal)
        tv_noisy = total_variation(real, noisy)
        rows.append(
            {
                "job_id": job_id,
                "name": job.name,
                "family": job.family,
                "num_qubits": job.num_qubits,
                "cx_count": job.cx_count,
                "shots": int(sum(run.counts[job_id].values())),
                "provider_job_id": run.provider_job_ids.get(job_id),
                "tv_ideal": tv_ideal,
                "tv_noisy": tv_noisy,
                "delta_tv": tv_noisy - tv_ideal,
            }
        )
    eval_total = sum(1 for job in jobs.values() if job.split == "EVAL")
    if not rows:
        raise DatasetNotAvailableError("no EVAL job has counts")
    rng = np.random.default_rng(seed)
    median, low, high = _bootstrap_median_delta([r["delta_tv"] for r in rows], samples=bootstrap_samples, rng=rng)
    complete = len(rows) == eval_total
    verdict = "SUPPORTED" if high < 0.0 else ("REJECTED" if low > 0.0 else "INCONCLUSIVE")
    return {
        "schema_version": "1.0",
        "dataset_id": SUITE_ID,
        "suite_version": SUITE_VERSION,
        "suite_seed": seed,
        "backend": run.backend,
        "dataset_sha256": run.dataset_sha256,
        "calibration_files": run.calibration_files,
        # Explicit, never defaulted: a run without snapshots says "absent".
        "calibration_status": "present" if run.calibration_files else "absent",
        "bit_order": order,
        "model": model.to_dict(),
        "hypothesis": {
            "id": "H-V3-8",
            "statement": (
                "On the 20 held-out EVAL jobs, the M-FIT prediction has a smaller total-variation "
                "distance to the measured counts than the ideal distribution: median paired "
                "difference below 0 with a 95% bootstrap interval excluding 0."
            ),
        },
        "aggregate": {
            "n_eval": len(rows),
            "n_eval_preregistered": eval_total,
            "complete": complete,
            "median_delta_tv": median,
            "ci95_low": low,
            "ci95_high": high,
            "n_noisy_better": sum(1 for r in rows if r["delta_tv"] < 0),
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_seed": seed,
            "verdict": verdict if complete else f"{verdict} (incomplete: {len(rows)}/{eval_total})",
        },
        "circuits": rows,
    }
