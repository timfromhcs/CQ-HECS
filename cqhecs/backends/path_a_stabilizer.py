"""
Path A: Stabilizer-Tableau Classical Backend (Exact, Clifford).
Implements the Aaronson-Gottesman (2004) Gottesman-Knill theorem.
Guarantees bit-exact polynomial-time simulation with 0.0 error bound.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from cqhecs.result import SimulationResult, hoeffding_total_variation_bound
from cqhecs.circuit_parsing import parse_circuit
from cqhecs.gate_manifest import (
    NON_UNITARY,
    clifford_rotation_kind,
    get_gate,
    path_gate_names,
)


class UnsupportedPathAOperation(ValueError):
    """Raised when a circuit uses an operation the stabilizer tableau cannot apply."""

def _load_native():
    """
    Imports the native C++20 stabilizer engine if it has been built.

    Searches the build output rather than assuming one fixed location, because
    the build writes into ${CMAKE_BINARY_DIR}/bin for both single-config
    (Ninja) and multi-config (MSVC) generators. Returns None when the
    extension has not been built; callers then use the Python tableau, which
    is exact but slower.
    """
    try:
        import _cqhecs_core as module
        return module
    except ImportError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))
    search = []
    env_dir = os.environ.get("CQ_HECS_BUILD_DIR")
    if env_dir:
        search.append(env_dir)
    search.extend([
        os.path.join(repo_root, "build", "bin", "Release"),
        os.path.join(repo_root, "build", "bin"),
        os.path.join(repo_root, "build", "Release"),
        os.path.join(repo_root, "bin", "Release"),
        os.path.join(repo_root, "bin"),
    ])
    for directory in search:
        if not os.path.isdir(directory):
            continue
        if directory not in sys.path:
            sys.path.append(directory)
        try:
            import _cqhecs_core as module
            return module
        except ImportError:
            continue
    return None


_native = _load_native()


#: Cap on per-shot tableau re-measurements for wide circuits (n > 30).
MAX_RESAMPLE_SHOTS = 100

#: Gates the native HybridEngine binding is known to implement.
#:
#: The native engine deliberately does *not* implement `cz`, and its
#: `apply_rz` takes two ints rather than an angle. Using it for a circuit
#: containing those gates would silently drop or misapply them, so circuits
#: needing them are routed to the Python tableau instead.
_NATIVE_SUPPORTED_GATES = frozenset({
    "h", "x", "y", "z", "s", "sdg", "cx", "cnot", "swap",
    "id", "barrier",
})


def _native_can_run(instructions: List[Any]) -> bool:
    """True if every gate in `instructions` is safe for the native engine."""
    return all(name in _NATIVE_SUPPORTED_GATES for name, _q, _p in instructions)


def _reverse_counts(counts: Dict[str, int]) -> Dict[str, int]:
    """
    Converts native-engine bitstrings to the Qiskit convention.

    The native HybridEngine renders qubit 0 leftmost; Qiskit (and every Python
    path in this package) renders qubit 0 rightmost. Reversing each key puts
    the two implementations into a single documented convention.
    """
    return {k[::-1]: v for k, v in counts.items()}


class StabilizerTableauSimulator:
    """
    Aaronson-Gottesman (2004) binary symplectic stabilizer tableau.
    Tableau dimension: (2n + 1) x (2n + 1).
    Rows 0 .. n-1: destabilizers
    Rows n .. 2n-1: stabilizers
    Row 2n: scratch row for deterministic measurement evaluation
    """

    #: Cap on per-shot tableau re-measurements for wide circuits (n > 30).
    MAX_RESAMPLE_SHOTS = 100

    def __init__(self, num_qubits: int, max_resample_shots: Optional[int] = None):
        self.n = num_qubits
        self.max_resample_shots = max_resample_shots
        self.tableau = np.zeros((2 * self.n + 1, 2 * self.n + 1), dtype=np.uint8)
        self.reset()

    def reset(self):
        self.tableau.fill(0)
        # Initialize |0...0> state:
        # Destabilizers: X_i on row i
        for i in range(self.n):
            self.tableau[i, i] = 1
        # Stabilizers: Z_i on row n + i
        for i in range(self.n):
            self.tableau[self.n + i, self.n + i] = 1

    def _row_sum(self, h: int, i: int):
        """Accumulates row i into row h using symplectic inner product phases."""
        x1 = self.tableau[i, :self.n].astype(np.int32)
        z1 = self.tableau[i, self.n:2 * self.n].astype(np.int32)
        x2 = self.tableau[h, :self.n].astype(np.int32)
        z2 = self.tableau[h, self.n:2 * self.n].astype(np.int32)

        terms = x1 * z2 * (2 * x2 - 1) + z1 * x2 * (1 - 2 * z2) + 2 * x1 * z1 * (z2 - x2)
        val = 2 * int(self.tableau[h, 2 * self.n]) + 2 * int(self.tableau[i, 2 * self.n]) + int(np.sum(terms))
        self.tableau[h, 2 * self.n] = 1 if ((val % 4) == 2) else 0

        # Bitwise addition mod 2
        self.tableau[h, :2 * self.n] ^= self.tableau[i, :2 * self.n]

    def apply_h(self, q: int):
        """Hadamard gate on qubit q: X <-> Z, r = r ^ (x * z)."""
        x = self.tableau[:2 * self.n, q].copy()
        z = self.tableau[:2 * self.n, self.n + q].copy()
        self.tableau[:2 * self.n, 2 * self.n] ^= (x & z)
        self.tableau[:2 * self.n, q] = z
        self.tableau[:2 * self.n, self.n + q] = x

    def apply_s(self, q: int):
        """Phase gate S on qubit q: Z = Z ^ X, r = r ^ (x * z)."""
        x = self.tableau[:2 * self.n, q]
        z = self.tableau[:2 * self.n, self.n + q]
        self.tableau[:2 * self.n, 2 * self.n] ^= (x & z)
        self.tableau[:2 * self.n, self.n + q] ^= x

    def apply_sdg(self, q: int):
        """Sdg = S * S * S."""
        self.apply_s(q)
        self.apply_s(q)
        self.apply_s(q)

    def apply_x(self, q: int):
        """Pauli X gate: r = r ^ z."""
        self.tableau[:2 * self.n, 2 * self.n] ^= self.tableau[:2 * self.n, self.n + q]

    def apply_y(self, q: int):
        """Pauli Y gate: r = r ^ x ^ z."""
        self.tableau[:2 * self.n, 2 * self.n] ^= (
            self.tableau[:2 * self.n, q] ^ self.tableau[:2 * self.n, self.n + q]
        )

    def apply_z(self, q: int):
        """Pauli Z gate: r = r ^ x."""
        self.tableau[:2 * self.n, 2 * self.n] ^= self.tableau[:2 * self.n, q]

    def apply_cx(self, ctrl: int, tgt: int):
        """CNOT gate: X_tgt ^= X_ctrl, Z_ctrl ^= Z_tgt."""
        xc = self.tableau[:2 * self.n, ctrl]
        zc = self.tableau[:2 * self.n, self.n + ctrl]
        xt = self.tableau[:2 * self.n, tgt]
        zt = self.tableau[:2 * self.n, self.n + tgt]

        self.tableau[:2 * self.n, 2 * self.n] ^= (xc & zt & (xt ^ zc ^ 1))
        self.tableau[:2 * self.n, tgt] ^= xc
        self.tableau[:2 * self.n, self.n + ctrl] ^= zt

    def apply_cz(self, ctrl: int, tgt: int):
        self.apply_h(tgt)
        self.apply_cx(ctrl, tgt)
        self.apply_h(tgt)

    def apply_swap(self, q1: int, q2: int):
        self.tableau[:2 * self.n, [q1, q2]] = self.tableau[:2 * self.n, [q2, q1]]
        self.tableau[:2 * self.n, [self.n + q1, self.n + q2]] = self.tableau[:2 * self.n, [self.n + q2, self.n + q1]]

    def measure(self, q: int, rng: Optional[np.random.Generator] = None) -> int:
        """Measures qubit q in computational basis."""
        if rng is None:
            rng = np.random.default_rng()

        p = -1
        for i in range(self.n, 2 * self.n):
            if self.tableau[i, q] == 1:
                p = i
                break

        if p != -1:
            # Case 1: Random outcome (0 or 1 with 50% probability)
            outcome = int(rng.integers(0, 2))
            for i in range(2 * self.n):
                if i != p and self.tableau[i, q] == 1:
                    self._row_sum(i, p)
            # Copy row p to row p - n (destabilizer)
            self.tableau[p - self.n, :] = self.tableau[p, :]
            # Set row p to Z_q with phase = outcome
            self.tableau[p, :] = 0
            self.tableau[p, self.n + q] = 1
            self.tableau[p, 2 * self.n] = outcome
            return outcome
        else:
            # Case 2: Deterministic outcome
            self.tableau[2 * self.n, :] = 0
            for i in range(self.n):
                if self.tableau[i, q] == 1:
                    self._row_sum(2 * self.n, self.n + i)
            return int(self.tableau[2 * self.n, 2 * self.n])

    def sample(
        self,
        shots: int = 1024,
        seed: int = 42,
        measured_qubits: Optional[List[int]] = None
    ) -> Tuple[Dict[str, int], int]:
        """
        Samples measurement outcomes shots times.

        Args:
            shots: Number of samples requested.
            seed: RNG seed.
            measured_qubits: Ordered qubit indices to report. ``None`` reports
                all qubits. Measuring only these qubits marginalizes the joint
                distribution onto them.

        Returns:
            (counts, sampled_shots). ``counts`` is keyed by bitstring with
            qubit 0 rightmost (Qiskit convention). ``sampled_shots`` is the
            number of shots actually drawn, which can be less than requested
            for wide tableaux; counts are never inflated to match.
        """
        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        rng = np.random.default_rng(seed)
        counts: Dict[str, int] = {}
        targets = list(range(self.n)) if measured_qubits is None else list(measured_qubits)
        for q in targets:
            if not (0 <= q < self.n):
                raise ValueError(
                    f"Measured qubit index {q} out of range for {self.n} qubits."
                )
        n_out = len(targets)

        # If X^(x)n is a stabilizer generator (all-X, no Z part) the state lies
        # in span{|0..0>, |1..1>}, so every qubit is deterministically equal.
        # The Z block must be zero for this to hold; a row that is all-X with a
        # non-zero Z part is Y-like and does not imply this structure.
        is_all_equal = False
        if self.n > 20 and n_out == self.n:
            x_block = self.tableau[self.n:, :self.n]
            z_block = self.tableau[self.n:, self.n:2 * self.n]
            is_all_equal = bool(
                np.any(np.all(x_block == 1, axis=1) & np.all(z_block == 0, axis=1))
            )

        if is_all_equal:
            c0 = int(rng.binomial(shots, 0.5))
            c1 = shots - c0
            if c0 > 0:
                counts["0" * n_out] = c0
            if c1 > 0:
                counts["1" * n_out] = c1
            return counts, shots

        # General sampling: re-measure from a copy of the tableau per shot.
        saved_tableau = self.tableau.copy()
        # Re-measurement is O(n^2) per shot in general; cap if specified or default to MAX_RESAMPLE_SHOTS for n > 30.
        cap = self.max_resample_shots if self.max_resample_shots is not None else self.MAX_RESAMPLE_SHOTS
        actual_shots = min(shots, cap) if (self.n > 30 and cap is not None) else shots
        for _ in range(actual_shots):
            self.tableau[:] = saved_tableau
            bits = [str(self.measure(q, rng)) for q in targets]
            # Qiskit renders qubit 0 rightmost; targets are in qubit order.
            bs = "".join(bits)[::-1]
            counts[bs] = counts.get(bs, 0) + 1

        self.tableau[:] = saved_tableau

        return counts, actual_shots

class PathAStabilizerBackend:
    """
    Path A Classical Backend: Exact Stabilizer Tableau Simulation.

    Correctness class
    -----------------
    Gottesman-Knill simulation is algebraically exact for Clifford circuits: the
    tableau is carried in exact symplectic arithmetic over GF(2), so there is
    no numerical approximation and ``error_bound`` is 0.0. The returned
    ``counts`` are a finite-shot sample and carry ``sampling_error_bound``.
    """

    #: Gates the stabilizer tableau can apply without decomposition, derived
    #: from the shared manifest. Includes measurement and the angle gates that
    #: are Clifford only at multiples of pi/2.
    SUPPORTED_GATES = frozenset(
        name
        for name in path_gate_names("A")
        if name not in NON_UNITARY and not get_gate(name).parameterised
    )

    #: Angle-gated rotations that are Clifford only at multiples of pi/2.
    _CLIFFORD_ROTATIONS = frozenset(
        name
        for name in path_gate_names("A")
        if name not in NON_UNITARY and get_gate(name).parameterised
    )

    #: Table of gate name -> simulator method name. Absent entries are no-ops.
    _GATE_DISPATCH: Dict[str, str] = {
        "h": "apply_h", "x": "apply_x", "y": "apply_y", "z": "apply_z",
        "s": "apply_s", "sdg": "apply_sdg",
        "cx": "apply_cx", "cnot": "apply_cx",
        "cz": "apply_cz", "swap": "apply_swap",
    }

    @staticmethod
    def _clifford_rotation_kind(theta: float) -> Optional[str]:
        """Delegates to the shared manifest implementation."""
        return clifford_rotation_kind(theta)

    def _validate(self, instructions: List[Any]) -> Optional[List[int]]:
        """
        Fail closed: refuse gates the tableau cannot represent.

        Terminal measurements are accepted and the measured qubits returned, so
        the final state can be marginalized onto them. Mid-circuit measurement
        is refused, since it is not a unitary evolution.

        Returns:
            Ordered measured qubit indices, or None when there is no
            measurement.
        """
        measure_positions = [
            i for i, (name, _, _) in enumerate(instructions) if name == "measure"
        ]
        last_state_op = max(
            (i for i, (name, _, _) in enumerate(instructions)
             if name not in ("measure", "id", "barrier")),
            default=-1,
        )

        measured: List[int] = []
        for i, (name, qubits, params) in enumerate(instructions):
            if name == "measure":
                if i < last_state_op:
                    raise UnsupportedPathAOperation(
                        "Path A does not support mid-circuit measurement "
                        f"(instruction {i} of {len(instructions)})."
                    )
                if not qubits:
                    raise UnsupportedPathAOperation(
                        "Measurement instruction has no qubit operand."
                    )
                if len(qubits) != 1:
                    raise UnsupportedPathAOperation(
                        f"Measurement expects 1 qubit, got {len(qubits)}: {qubits}"
                    )
                measured.append(int(qubits[0]))
                continue
            spec = get_gate(name)
            if spec is not None and not spec.barrier:
                if len(qubits) != spec.arity:
                    raise UnsupportedPathAOperation(
                        f"Gate '{name}' expects {spec.arity} qubit(s), got "
                        f"{len(qubits)}: {qubits}"
                    )
                if not (spec.min_params <= len(params) <= spec.max_params):
                    raise UnsupportedPathAOperation(
                        f"Gate '{name}' expects {spec.min_params}.."
                        f"{spec.max_params} parameter(s), got {len(params)}."
                    )
            if name in self.SUPPORTED_GATES:
                continue
            if name in self._CLIFFORD_ROTATIONS and params:
                if self._clifford_rotation_kind(float(params[0])) is not None:
                    continue
                raise UnsupportedPathAOperation(
                    f"Rotation angle {params[0]!r} for '{name}' is not a "
                    "Clifford multiple of pi/2 and cannot be applied to a "
                    "stabilizer tableau."
                )
            raise UnsupportedPathAOperation(
                f"Path A supports Clifford gates only and cannot apply '{name}'. "
                "Dropping a non-Clifford gate would silently produce a wrong state."
            )
        return measured or None

    def _apply_instructions(self, target: Any, instructions: List[Any]) -> None:
        """Applies each validated non-measurement instruction to a simulator."""
        for name, qubits, params in instructions:
            if name == "measure":
                continue
            method_name = self._GATE_DISPATCH.get(name)
            if method_name is not None:
                getattr(target, method_name)(*qubits)
                continue
            if name in self._CLIFFORD_ROTATIONS and params:
                kind = self._clifford_rotation_kind(float(params[0]))
                if kind not in (None, "id"):
                    getattr(target, self._GATE_DISPATCH[kind])(qubits[0])
                continue
            # id / barrier: no-ops

    def __init__(self, max_resample_shots: Optional[int] = None):
        self.max_resample_shots = max_resample_shots

    def execute(self, circuit: Any, shots: int = 1024, seed: int = 42) -> SimulationResult:
        t0 = time.perf_counter()

        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        instructions, n_q = parse_circuit(circuit)
        if n_q <= 0:
            raise ValueError("Path A requires a circuit with at least one qubit.")
        measured_qubits = self._validate(instructions)

        # The native engine cannot marginalize onto a subset of qubits, and it lacks
        # CZ / angle-valued RZ. Use it only when it can faithfully run this
        # circuit; otherwise fall back to the Python tableau, which is exact.
        use_native = bool(
            _native
            and hasattr(_native, "HybridEngine")
            and _native_can_run(instructions)
        )

        if use_native:
            engine = _native.HybridEngine(n_q)
            for name, qubits, _params in instructions:
                method_name = self._GATE_DISPATCH.get(name)
                if method_name is not None:
                    getattr(engine, method_name)(*qubits)
            counts = _reverse_counts(engine.sample_counts(shots, seed))
            sampled = shots
            method = "C++20 HybridEngine Stabilizer Tableau (Native SOTA)"
        else:
            sim = StabilizerTableauSimulator(n_q, max_resample_shots=self.max_resample_shots)
            self._apply_instructions(sim, instructions)
            counts, sampled = sim.sample(
                shots=shots, seed=seed, measured_qubits=measured_qubits
            )
            method = "Aaronson-Gottesman 2004 (Python Symplectic)"

        t1 = time.perf_counter()

        return SimulationResult(
            path="A",
            exact=True,
            error_bound=0.0,
            unresolved=False,
            counts=counts,
            # The bound depends on the number of distinct measurement outcomes.
            # Only the measured qubits contribute.
            sampling_error_bound=hoeffding_total_variation_bound(
                sampled,
                support_size=1 << len(
                    measured_qubits if measured_qubits is not None
                    else range(n_q)
                ),
            ),
            execution_time_ms=(t1 - t0) * 1000.0,
            metadata={
                "backend": "PathAStabilizerBackend",
                "qubit_count": n_q,
                "shots": shots,
                "sampled_shots": sampled,
                "seed": seed,
                "method": method,
                "native_engine": use_native,
                "truncation_applied": False,
                "numerical_mode": "exact-symplectic-gf2",
                "numerical_note": (
                    "Tableau uses exact GF(2) symplectic arithmetic; counts are "
                    "a finite-shot sample."
                ),
            }
        )

    def _parse_qiskit(self, qc: Any) -> List[Tuple[str, List[int]]]:
        instructions = []
        for instruction in qc.data:
            op = instruction.operation
            name = op.name.lower()
            q_idx = [qc.find_bit(q).index for q in instruction.qubits]
            if name in ("barrier", "measure", "id"):
                continue
            instructions.append((name, q_idx))
        return instructions

    def _parse_qasm_str(self, qasm_str: str) -> List[Tuple[str, List[int]]]:
        import re
        gate_pattern = re.compile(r"([a-zA-Z0-9_]+)(?:\(([^)]*)\))?\s+([^;]+);")
        instructions = []
        for line in qasm_str.splitlines():
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("openqasm") or line.startswith("include") or line.startswith("qreg") or line.startswith("creg"):
                continue
            m = gate_pattern.search(line)
            if m:
                gname = m.group(1).lower()
                args_str = m.group(3)
                q_matches = re.findall(r"\[(\d+)\]", args_str)
                q_idx = [int(x) for x in q_matches]
                if gname in ("barrier", "measure", "id"):
                    continue
                instructions.append((gname, q_idx))
        return instructions
