"""
Circuit Analyzer for CQ-HECS Classical Four-Path Architecture.
Performs deterministic static circuit analysis:
- T-Count tracking (non-Clifford resource estimation)
- Clifford verification (Gottesman-Knill compatibility)
- Entanglement estimation (1D cut connectivity)
- Four-Path routing recommendation (A -> B -> C -> D)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


CLIFFORD_GATES: Set[str] = {
    "h", "s", "sdg", "x", "y", "z", "cx", "cz", "swap",
    "id", "barrier", "measure", "reset", "cnot"
}

NON_CLIFFORD_T_GATES: Set[str] = {
    "t", "tdg", "ccx", "toffoli", "ch", "cs", "csdg"
}

ROTATION_GATES: Set[str] = {
    "rz", "rx", "ry", "p", "u1", "u2", "u3", "u", "cp", "crz"
}


@dataclass
class CircuitProperties:
    """Static properties extracted from quantum circuit."""
    num_qubits: int
    total_gates: int
    gate_counts: Dict[str, int] = field(default_factory=dict)
    t_count: int = 0
    non_clifford_rotations: int = 0
    is_clifford: bool = True
    entanglement_estimate: int = 0
    max_cut_width: int = 0
    recommended_path: str = "A"
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "num_qubits": self.num_qubits,
            "total_gates": self.total_gates,
            "gate_counts": self.gate_counts,
            "t_count": self.t_count,
            "non_clifford_rotations": self.non_clifford_rotations,
            "is_clifford": self.is_clifford,
            "entanglement_estimate": self.entanglement_estimate,
            "max_cut_width": self.max_cut_width,
            "recommended_path": self.recommended_path,
            "reason": self.reason,
        }


class CircuitAnalyzer:
    """
    Deterministic static circuit analysis and Four-Path routing engine.
    """

    def __init__(
        self,
        t_rank_threshold: int = 14,
        mps_entanglement_threshold: int = 32,
        max_mps_qubits: int = 300,
    ):
        self.t_rank_threshold = t_rank_threshold
        self.mps_entanglement_threshold = mps_entanglement_threshold
        self.max_mps_qubits = max_mps_qubits

    def analyze(self, circuit: Any) -> CircuitProperties:
        """
        Analyzes a Qiskit QuantumCircuit, OpenQASM string, or list of instructions.
        """
        if isinstance(circuit, str):
            return self._analyze_qasm_str(circuit)

        # Check if Qiskit QuantumCircuit
        if hasattr(circuit, "data") and hasattr(circuit, "num_qubits"):
            return self._analyze_qiskit_circuit(circuit)

        # Check if list of instruction dicts/tuples
        if isinstance(circuit, list):
            return self._analyze_instruction_list(circuit)

        # Generic fallback
        return CircuitProperties(
            num_qubits=getattr(circuit, "num_qubits", 1),
            total_gates=0,
            recommended_path="A",
            reason="Unrecognized circuit type, default to Path A"
        )

    def _analyze_qiskit_circuit(self, qc: Any) -> CircuitProperties:
        num_qubits = qc.num_qubits
        gate_counts: Dict[str, int] = {}
        t_count = 0
        non_clifford_rotations = 0
        is_clifford = True
        two_qubit_gates: List[Tuple[int, int]] = []

        for instruction in qc.data:
            op = instruction.operation
            name = op.name.lower()
            gate_counts[name] = gate_counts.get(name, 0) + 1

            if name in ("barrier", "measure", "id"):
                continue

            q_indices = [qc.find_bit(q).index for q in instruction.qubits]

            if len(q_indices) == 2:
                two_qubit_gates.append((q_indices[0], q_indices[1]))

            if name in NON_CLIFFORD_T_GATES:
                if name in ("t", "tdg"):
                    t_count += 1
                elif name in ("ccx", "toffoli"):
                    # Toffoli has T-count of 7 in optimal Clifford+T synthesis
                    t_count += 7
                else:
                    t_count += 1
                is_clifford = False

            elif name in ROTATION_GATES:
                # Check whether angle is integer multiple of pi/2 (Clifford)
                is_angle_clifford = False
                if hasattr(op, "params") and op.params:
                    try:
                        param_val = float(op.params[0])
                        # Normalize angle to [0, 2*pi)
                        norm_angle = (param_val % (2.0 * math.pi))
                        # Check multiples of pi/2: 0, pi/2, pi, 3*pi/2
                        diff_pi2 = abs(norm_angle / (math.pi / 2.0) - round(norm_angle / (math.pi / 2.0)))
                        if diff_pi2 < 1e-7:
                            is_angle_clifford = True
                    except Exception:
                        is_angle_clifford = False

                if not is_angle_clifford:
                    is_clifford = False
                    non_clifford_rotations += 1
                    t_count += 1

            elif name not in CLIFFORD_GATES:
                is_clifford = False
                non_clifford_rotations += 1
                t_count += 1

        entanglement_estimate, max_cut = self._estimate_entanglement(num_qubits, two_qubit_gates)
        recommended_path, reason = self._determine_path(
            num_qubits=num_qubits,
            is_clifford=is_clifford,
            t_count=t_count,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut
        )

        return CircuitProperties(
            num_qubits=num_qubits,
            total_gates=len(qc.data),
            gate_counts=gate_counts,
            t_count=t_count,
            non_clifford_rotations=non_clifford_rotations,
            is_clifford=is_clifford,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut,
            recommended_path=recommended_path,
            reason=reason
        )

    def _analyze_qasm_str(self, qasm_str: str) -> CircuitProperties:
        lines = [l.strip() for l in qasm_str.splitlines() if l.strip() and not l.strip().startswith("//")]
        num_qubits = 0
        gate_counts: Dict[str, int] = {}
        t_count = 0
        non_clifford_rotations = 0
        is_clifford = True
        two_qubit_gates: List[Tuple[int, int]] = []

        import re
        qreg_pattern = re.compile(r"qreg\s+([a-zA-Z0-9_]+)\[(\d+)\]")
        gate_pattern = re.compile(r"([a-zA-Z0-9_]+)(?:\(([^)]*)\))?\s+([^;]+);")

        for line in lines:
            m_qreg = qreg_pattern.search(line)
            if m_qreg:
                num_qubits = max(num_qubits, int(m_qreg.group(2)))
                continue

            m_gate = gate_pattern.search(line)
            if m_gate:
                gname = m_gate.group(1).lower()
                params_str = m_gate.group(2)
                args_str = m_gate.group(3)

                gate_counts[gname] = gate_counts.get(gname, 0) + 1

                # Parse qubit indices from args
                q_matches = re.findall(r"\[(\d+)\]", args_str)
                q_indices = [int(x) for x in q_matches]
                if q_indices:
                    num_qubits = max(num_qubits, max(q_indices) + 1)

                if len(q_indices) == 2:
                    two_qubit_gates.append((q_indices[0], q_indices[1]))

                if gname in ("barrier", "measure", "id", "openqasm", "include"):
                    continue

                if gname in NON_CLIFFORD_T_GATES:
                    t_count += 7 if gname in ("ccx", "toffoli") else 1
                    is_clifford = False
                elif gname in ROTATION_GATES:
                    is_angle_clifford = False
                    if params_str:
                        try:
                            # Evaluate simple expressions like pi/2, 0, pi
                            expr = params_str.replace("pi", str(math.pi))
                            angle = float(eval(expr, {"__builtins__": None}, {}))
                            norm = angle % (2.0 * math.pi)
                            if abs(norm / (math.pi / 2.0) - round(norm / (math.pi / 2.0))) < 1e-7:
                                is_angle_clifford = True
                        except Exception:
                            is_angle_clifford = False
                    if not is_angle_clifford:
                        is_clifford = False
                        non_clifford_rotations += 1
                        t_count += 1
                elif gname not in CLIFFORD_GATES:
                    is_clifford = False
                    non_clifford_rotations += 1
                    t_count += 1

        entanglement_estimate, max_cut = self._estimate_entanglement(num_qubits, two_qubit_gates)
        recommended_path, reason = self._determine_path(
            num_qubits=num_qubits,
            is_clifford=is_clifford,
            t_count=t_count,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut
        )

        return CircuitProperties(
            num_qubits=num_qubits,
            total_gates=sum(gate_counts.values()),
            gate_counts=gate_counts,
            t_count=t_count,
            non_clifford_rotations=non_clifford_rotations,
            is_clifford=is_clifford,
            entanglement_estimate=entanglement_estimate,
            max_cut_width=max_cut,
            recommended_path=recommended_path,
            reason=reason
        )

    def _analyze_instruction_list(self, instrs: List[Any]) -> CircuitProperties:
        # Fallback for raw instruction list
        return CircuitProperties(
            num_qubits=1,
            total_gates=len(instrs),
            recommended_path="A",
            reason="Instruction list fallback"
        )

    def _estimate_entanglement(self, num_qubits: int, two_qubit_gates: List[Tuple[int, int]]) -> Tuple[int, int]:
        """
        Estimates entanglement via bipartite cut analysis across 1D chain.
        Returns:
            (entanglement_score, max_cut_width)
        """
        if num_qubits <= 1 or not two_qubit_gates:
            return 0, 0

        # Count gates crossing each partition cut i | i+1
        cuts = [0] * (num_qubits - 1)
        for (q1, q2) in two_qubit_gates:
            lo, hi = min(q1, q2), max(q1, q2)
            for c in range(lo, min(hi, num_qubits - 1)):
                cuts[c] += 1

        max_cut = max(cuts) if cuts else 0
        total_crossing = sum(cuts)
        return total_crossing, max_cut

    def _determine_path(
        self,
        num_qubits: int,
        is_clifford: bool,
        t_count: int,
        entanglement_estimate: int,
        max_cut_width: int
    ) -> Tuple[str, str]:
        """
        Enforces four-path selection order:
        A (Clifford) -> B (Stabilizer Rank) -> C (Exact MPS) -> D (Certified Sparse-Pauli-Dynamics)
        """
        # Path A: Stabilizer Tableau
        if is_clifford:
            return "A", f"Circuit is 100% Clifford (T-Count=0, {num_qubits} qubits). Exact polynomial Gottesman-Knill simulation."

        # Path B: Stabilizer Rank Decomposition
        if t_count <= self.t_rank_threshold:
            return "B", (
                f"Low T-Count (T={t_count} <= {self.t_rank_threshold}). Exact stabilizer rank decomposition "
                f"scales as O(2^(alpha*T)) with zero approximation."
            )

        # Path C: MPS without Cutoff + NVMe-Offload
        # Low 1D cut entanglement or small qubit chain fits exactly in MPS memory budget
        if (max_cut_width <= self.mps_entanglement_threshold or num_qubits <= 20) and num_qubits <= self.max_mps_qubits:
            return "C", (
                f"Moderate entanglement (Max cut={max_cut_width}, T={t_count}). Exact MPS without cutoff "
                f"backed by NVMe/storage paging."
            )

        # Path D: Certified Classical Approximation (Sparse-Pauli-Dynamics)
        return "D", (
            f"High T-Count (T={t_count}) and high entanglement (Cut={max_cut_width}). Routed to Path D "
            f"certified classical approximation (Sparse-Pauli-Dynamics) with rigorous error bound."
        )
