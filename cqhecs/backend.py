from __future__ import annotations
import time
from typing import Any, List, Optional, Union, Dict
import numpy as np

from qiskit.providers import BackendV2, Options
from qiskit.transpiler import Target
from qiskit.circuit.library import (
    CXGate, HGate, SGate, SdgGate, TGate, TdgGate,
    XGate, YGate, ZGate, RZGate, Measure
)
from qiskit.result import Result
from qiskit.result.models import ExperimentResult, ExperimentResultData

from cqhecs.router import FourPathRouter
from cqhecs.result import SimulationResult


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
        super().__init__(name=name, backend_version="5.0.0")
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
        # 1-Qubit Gates
        self._target.add_instruction(HGate())
        self._target.add_instruction(SGate())
        self._target.add_instruction(SdgGate())
        self._target.add_instruction(TGate())
        self._target.add_instruction(TdgGate())
        self._target.add_instruction(XGate())
        self._target.add_instruction(YGate())
        self._target.add_instruction(ZGate())
        self._target.add_instruction(RZGate(0.0))
        self._target.add_instruction(Measure())

        # 2-Qubit CX across all adjacent linear pairs
        cx_props = {}
        for q in range(self._num_qubits - 1):
            cx_props[(q, q + 1)] = None
            cx_props[(q + 1, q)] = None
        self._target.add_instruction(CXGate(), cx_props)

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

    def run(self, run_input: Any, **options) -> Any:
        shots = options.get("shots", self.options.shots)
        seed = options.get("seed_simulator", self.options.seed_simulator)
        preferred_path = options.get("preferred_path", self._preferred_path)
        error_tolerance = options.get("error_tolerance", self._error_tolerance)

        circuits = run_input if isinstance(run_input, list) else [run_input]
        experiment_results = []
        sim_results: List[SimulationResult] = []

        start_time = time.time()
        for idx, qc in enumerate(circuits):
            t_exp_start = time.time()
            sim_res = self._router.route_and_execute(
                qc,
                shots=shots,
                seed=seed,
                preferred_path=preferred_path,
                error_tolerance=error_tolerance
            )
            sim_results.append(sim_res)
            counts = sim_res.counts
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
