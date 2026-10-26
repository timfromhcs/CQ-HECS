from __future__ import annotations
import time
from typing import Any, List, Optional, Union, Dict
import numpy as np

from qiskit.providers import BackendV2, Options
from qiskit.transpiler import Target
from qiskit.circuit.library import (
    CPhaseGate, CRXGate, CRYGate, CRZGate, CU1Gate, CXGate, CZGate,
    HGate, IGate, Measure, PhaseGate, RXGate, RYGate, RZGate,
    SGate, SdgGate, SwapGate, TGate, TdgGate, XGate, YGate, ZGate,
)
from qiskit.result import Result
from qiskit.result.models import ExperimentResult, ExperimentResultData

from cqhecs.router import FourPathRouter
from cqhecs.result import SimulationResult
from cqhecs import __version__ as _cqhecs_version


def cqhecs_version() -> str:
    """The Qiskit backend must report the package version, not a stale constant."""
    return _cqhecs_version


class CQHecsBackend(BackendV2):
    """
    CQ-HECS Quantum Engine Classical Backend (Qiskit BackendV2 Compatible).
    Powered by Verified Four-Path Architecture:
      Path A: Stabilizer-Tableau (exact, Clifford)
      Path B: Stabilizer-Rank-Decomposition (exact, scales with T-Count)
      Path C: MPS without Cutoff + NVMe-Offload (exact up to memory limit)
      Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics) with proven error bound
    """

    def __init__(
        self,
        num_qubits: int = 300,
        name: str = "cq_hecs_backend",
        preferred_path: Optional[str] = None,
        error_tolerance: float = 0.05,
        max_storage_mb: float = 5120.0
    ):
        super().__init__(
            name=name,
            backend_version=cqhecs_version(),
        )
        self._num_qubits = num_qubits
        self._preferred_path = preferred_path
        self._error_tolerance = error_tolerance
        self._router = FourPathRouter(
            max_storage_mb=max_storage_mb,
            error_tolerance=error_tolerance
        )
        self._target = Target(num_qubits=num_qubits)
        self._init_target()

    def _init_target(self):
        """
        Declare the instructions Qiskit's transpiler may emit.

        This is the *transpilation* view of the same manifest the router uses:
        every instruction here is executable by at least one path. Aliases that
        Qiskit canonicalises (``cnot`` -> ``cx``, ``u1`` -> ``p``) are omitted;
        pseudo-instructions such as ``barrier`` need no target entry. Gates
        without any path (``u2``/``u3``/``ccx``/``toffoli``/``reset``) are
        deliberately absent so the transpiler cannot emit them.

        Connectivity is the linear chain. The backends themselves accept
        non-adjacent two-qubit gates (Path C swaps internally), but a linear
        target keeps transpilation deterministic and conservative.
        """
        # 1-Qubit Gates
        for gate in (
            HGate(), IGate(), SGate(), SdgGate(), TGate(), TdgGate(),
            XGate(), YGate(), ZGate(),
        ):
            self._target.add_instruction(gate)
        for gate in (
            RZGate(0.0), PhaseGate(0.0), RXGate(0.0), RYGate(0.0),
        ):
            self._target.add_instruction(gate)
        self._target.add_instruction(Measure())

        # 2-Qubit gates across the adjacent linear pairs.
        pair_props = {}
        for q in range(self._num_qubits - 1):
            pair_props[(q, q + 1)] = None
            pair_props[(q + 1, q)] = None
        for gate in (
            CXGate(), CZGate(), SwapGate(),
            CPhaseGate(0.0), CU1Gate(0.0),
            CRXGate(0.0), CRYGate(0.0), CRZGate(0.0),
        ):
            self._target.add_instruction(gate, pair_props)

    @property
    def target(self) -> Target:
        return self._target

    @property
    def max_circuits(self) -> int:
        return 1024

    @classmethod
    def _default_options(cls) -> Options:
        return Options(
            shots=1024,
            seed_simulator=42,
            preferred_path=None,
            error_tolerance=0.05
        )

    @staticmethod
    def _normalize_measurements(qc: Any) -> tuple:
        """
        Returns a plain instruction list to simulate plus a layout description.

        Only *terminal* measurements are accepted. Moving a mid-circuit
        measurement to the end would silently change the state seen by later
        gates, so such circuits are rejected here - before any simulation.

        Repeated measurements of one qubit into several classical bits are
        preserved: the layout keeps every (qubit, clbit) pair instead of
        collapsing them with ``setdefault``. The measured qubits are sampled
        once each, in ascending qubit order (Qiskit renders qubit 0 rightmost).
        """
        from cqhecs.router import UnsupportedCircuitError

        control_flow = {
            "if_else", "while_loop", "for_loop", "switch_case",
            "break_loop", "continue_loop",
        }
        instructions = []
        pairs = []
        saw_measure = False
        for idx, inst in enumerate(qc.data):
            name = inst.operation.name.lower()
            if name in control_flow or getattr(inst.operation, "condition", None) is not None:
                raise UnsupportedCircuitError(
                    f"Instruction {idx} is the classically controlled operation "
                    f"{name!r}. Dynamic circuits (measurement -> classical "
                    "condition) are not implemented and are refused before "
                    "execution."
                )
            if name == "reset":
                raise UnsupportedCircuitError(
                    f"Instruction {idx} is 'reset'. Reset is non-unitary and is "
                    "not implemented by any path; refusing to ignore it."
                )
            if name == "measure":
                saw_measure = True
                qubits = [qc.find_bit(q).index for q in inst.qubits]
                clbits = [qc.find_bit(c).index for c in inst.clbits]
                if len(qubits) != 1 or len(clbits) != 1:
                    raise UnsupportedCircuitError(
                        f"Measurement {idx} must target exactly one qubit and "
                        f"one classical bit, got {len(qubits)} qubit(s) and "
                        f"{len(clbits)} classical bit(s)."
                    )
                pairs.append((qubits[0], clbits[0]))
                continue
            if saw_measure and name in ("barrier", "id"):
                # No state effect: a barrier or identity after the last
                # measurement does not turn it into a mid-circuit measurement.
                continue
            if saw_measure:
                raise UnsupportedCircuitError(
                    f"Instruction {idx} ({name!r}) follows a measurement. "
                    "Mid-circuit measurement is not implemented; moving the "
                    "measurement to the end would produce a different state."
                )
            instructions.append((
                name,
                [qc.find_bit(q).index for q in inst.qubits],
                [float(p) for p in getattr(inst.operation, "params", [])],
            ))

        if not pairs:
            return instructions, None

        sampled_qubits = sorted({q for q, _ in pairs})
        # One 'measure' instruction per qubit, so each backend's arity check
        # sees the 1-qubit form it expects.
        for q in sampled_qubits:
            instructions.append(("measure", [q], []))
        layout = {
            "sampled_qubits": sampled_qubits,
            "pairs": pairs,
            "width": qc.num_clbits,
        }
        return instructions, layout

    @staticmethod
    def _pad_counts(counts, layout, width):
        """
        Expands backend counts to the circuit's classical-register width.

        Backend keys are ordered by ascending measured qubit, with qubit 0
        rightmost. Each classical bit then receives the outcome of the qubit
        that was measured into it; unmeasured classical bits stay ``0``.
        """
        if not counts or layout is None:
            return counts

        from cqhecs.router import UnsupportedCircuitError

        sampled = layout["sampled_qubits"]
        pairs = layout["pairs"]
        width = layout["width"]
        padded = {}
        for key, value in counts.items():
            chars = key.replace(" ", "")
            if len(chars) != len(sampled):
                raise UnsupportedCircuitError(
                    f"Backend returned a {len(chars)}-bit result for "
                    f"{len(sampled)} sampled qubit(s); refusing to guess the "
                    "classical-bit layout."
                )
            qubit_bit = {
                q: chars[len(chars) - 1 - position]
                for position, q in enumerate(sampled)
            }
            out = ["0"] * width
            for qubit, clbit in pairs:
                out[width - 1 - clbit] = qubit_bit[qubit]
            bits = "".join(out)
            padded[bits] = padded.get(bits, 0) + value
        return padded

    def run(self, run_input: Any, **options) -> Any:
        shots = options.get("shots", self.options.shots)
        seed = options.get("seed_simulator", self.options.seed_simulator)
        preferred_path = options.get("preferred_path", self._preferred_path)
        error_tolerance = options.get("error_tolerance", self._error_tolerance)

        if not isinstance(shots, int) or isinstance(shots, bool):
            raise ValueError(f"shots must be an int, got {type(shots).__name__}")
        if shots <= 0:
            raise ValueError(f"shots must be a positive integer, got {shots}")

        circuits = run_input if isinstance(run_input, list) else [run_input]
        for index, candidate in enumerate(circuits):
            if not (hasattr(candidate, "data") and hasattr(candidate, "num_qubits")):
                raise TypeError(
                    f"run_input[{index}] is {type(candidate).__name__!r}; "
                    "expected a Qiskit QuantumCircuit."
                )
        experiment_results = []
        sim_results: List[SimulationResult] = []

        start_time = time.time()
        for idx, qc in enumerate(circuits):
            t_exp_start = time.time()

            # Measurements must be expressed against classical bits, otherwise
            # the bitstring width would not match the circuit's memory layout.
            # `measure_all()` appends an extra register, so the counts must
            # carry that register's zeros too.
            measured_qc, measure_layout = self._normalize_measurements(qc)

            sim_res = self._router.route_and_execute(
                measured_qc,
                shots=shots,
                seed=seed,
                preferred_path=preferred_path,
                error_tolerance=error_tolerance,
                require_counts=True,
            )
            sim_results.append(sim_res)

            counts = self._pad_counts(
                sim_res.counts,
                measure_layout,
                getattr(qc, "num_clbits", qc.num_qubits),
            )
            t_exp_end = time.time()

            exp_res = ExperimentResult(
                shots=shots,
                success=not sim_res.unresolved,
                data=ExperimentResultData(counts=counts),
                header={
                    "name": getattr(qc, "name", f"circuit_{idx}"),
                    "memory_slots": getattr(qc, "num_clbits", qc.num_qubits),
                    "path": sim_res.path,
                    "exact": sim_res.exact,
                    "error_bound": sim_res.error_bound,
                    "numerical_error_bound": sim_res.numerical_error_bound,
                    "sampling_error_bound": sim_res.sampling_error_bound,
                    "total_error_bound": sim_res.total_error_bound,
                    "unresolved": sim_res.unresolved,
                },
                status="UNRESOLVED" if sim_res.unresolved else "DONE",
                time_taken=t_exp_end - t_exp_start
            )
            experiment_results.append(exp_res)

        end_time = time.time()

        class JobResult:
            def __init__(self, res: Result, s_results: List[SimulationResult]):
                self._res = res
                self.simulation_results = s_results

            def result(self) -> Result:
                return self._res

            def status(self) -> str:
                return "COMPLETED"

            def get_counts(self) -> Dict[str, int]:
                return self._res.get_counts()

        result_obj = Result(
            backend_name=self.name,
            backend_version=self.backend_version,
            qobj_id="cq_hecs_run",
            job_id="job_0",
            success=all(not r.unresolved for r in sim_results),
            results=experiment_results,
            date=time.strftime("%Y-%m-%d %H:%M:%S"),
            status="COMPLETED",
            time_taken=end_time - start_time
        )
        return JobResult(result_obj, sim_results)
