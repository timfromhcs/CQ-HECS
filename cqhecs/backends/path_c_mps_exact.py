"""
Path C: MPS without Cutoff + NVMe-Offload Classical Backend (Exact up to Memory Limit).
Guarantees:
- NO silent bond-dimension truncation (chi=48 eliminated).
- Bond dimension expands dynamically to exact rank.
- Tiered Memory / NVMe-Offload pages tensors when RAM budget is reached.
- If memory limit is reached without user approximation opt-in, marks 'unresolved=True'.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from cqhecs.circuit_parsing import parse_circuit
from cqhecs.result import SimulationResult, hoeffding_total_variation_bound


def _controlled_phase_matrix(theta: float) -> np.ndarray:
    """Diagonal controlled-phase matrix diag(1, 1, 1, exp(i*theta))."""
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, np.exp(1j * theta)]
    ], dtype=np.complex128)


def _marginalize(
    probs: np.ndarray,
    num_qubits: int,
    measured_qubits: List[int],
) -> np.ndarray:
    """
    Marginalizes a full 2**n probability vector onto `measured_qubits`.

    Qiskit index convention: qubit 0 is the least significant bit, and the
    output bitstring lists `measured_qubits[0]` first.

    Args:
        probs: Flat array of length 2**num_qubits.
        num_qubits: Width of the input distribution.
        measured_qubits: Ordered qubit indices to keep.

    Returns:
        Flat array of length 2**len(measured_qubits).

    Raises:
        ValueError: If a measured index is out of range.
    """
    for q in measured_qubits:
        if not (0 <= q < num_qubits):
            raise ValueError(
                f"Measured qubit index {q} out of range for {num_qubits} qubits."
            )

    # out_index = sum over j of bit(measured_qubits[j]) << (len-1-j)
    out_dim = 1 << len(measured_qubits)
    shift_of = [num_qubits - 1 - q for q in measured_qubits]
    out = np.zeros(out_dim, dtype=np.float64)

    total = float(np.sum(probs))
    if total <= 0.0:
        return out

    for idx, p in enumerate(probs):
        if p <= 0.0:
            continue
        out_idx = 0
        for j, shift in enumerate(shift_of):
            bit = (idx >> shift) & 1
            out_idx |= bit << (len(shift_of) - 1 - j)
        out[out_idx] += p

    return out


class ExactMPSTensorChain:
    """
    1D Matrix Product State (MPS) with unbounded exact bond dimension
    and NVMe/disk tiered swap paging.

    Floating-point contract
    -----------------------
    The tensor network is contracted in ``numpy.complex128`` (IEEE-754 double
    precision). SVD rank selection therefore uses a *roundoff* threshold rather
    than an approximation threshold: singular values below it are numerically
    indistinguishable from zero, not physically small. The discarded mass is
    measured and reported rather than discarded silently:

    * ``discarded_spectral_norm`` - sum of discarded singular values.
    * ``max_retained_singular_value`` - reference scale for the cutoff.

    Because double precision cannot represent the norm of a state exactly, this
    backend is **not** mathematically exact; see ``PathCMPSExactBackend`` for the
    resulting guarantee.
    """

    #: Singular values at or below this fraction of the largest retained
    #: singular value are treated as roundoff noise (numerically rank-deficient),
    #: not as a deliberate approximation.
    SINGULAR_VALUE_ROUNDOFF_RATIO = 1e-13

    #: Dense statevector sampling costs O(2**n); refuse beyond this width.
    MAX_SAMPLING_QUBITS = 20

    def __init__(
        self,
        num_qubits: int,
        ram_budget_mb: float = 120.0,
        max_storage_mb: float = 5120.0,
        temp_dir: Optional[str] = None
    ):
        self.num_qubits = num_qubits
        self.ram_budget_bytes = int(ram_budget_mb * 1024 * 1024)
        self.max_storage_bytes = int(max_storage_mb * 1024 * 1024)
        # Use a private subdirectory so concurrent runs never collide on the
        # fixed `mps_site_{q}.npy` names.
        self._owns_temp_dir = temp_dir is None
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="cqhecs_mps_")
        self.swap_files: Dict[int, str] = {}

        # Site tensors: list of numpy arrays, shape (chi_left, 2, chi_right)
        # Initially in state |0...0>: each site is (1, 2, 1) with amplitude [1, 0]
        self.sites: List[Optional[np.ndarray]] = []
        self.active_ram_bytes = 0
        self.total_allocated_bytes = 0
        self.max_observed_chi = 1
        self.memory_limit_exceeded = False

        # Roundoff accounting (see floating-point contract above).
        self.discarded_spectral_norm = 0.0
        self.max_retained_singular_value = 0.0
        self.num_two_qubit_rewrites = 0

        self._initialize_state()

    def _initialize_state(self):
        self.sites = []
        self.active_ram_bytes = 0
        for i in range(self.num_qubits):
            t = np.zeros((1, 2, 1), dtype=np.complex128)
            t[0, 0, 0] = 1.0  # |0>
            self.sites.append(t)
            self.active_ram_bytes += t.nbytes
        self.total_allocated_bytes = self.active_ram_bytes

    def apply_single_qubit_gate(self, q: int, gate_matrix: np.ndarray):
        """Applies 2x2 unitary gate to site q."""
        self._ensure_site_in_ram(q)
        # site shape: (chi_L, 2, chi_R)
        t = self.sites[q]
        # t'_l, s', r = sum_s U_s',s * t_l, s, r
        new_t = np.einsum("ab,lbr->lar", gate_matrix, t)
        self.sites[q] = np.ascontiguousarray(new_t)

    def apply_two_qubit_gate(self, q1: int, q2: int, gate_4x4: np.ndarray):
        """
        Applies 4x4 unitary to adjacent qubits (q1, q2).
        Retains ALL non-zero singular values (exact rank). NO chi=48 cutoff!
        """
        if abs(q1 - q2) != 1:
            # For non-adjacent qubits in 1D chain, swap to adjacent, apply, swap back
            self._apply_non_adjacent_two_qubit_gate(q1, q2, gate_4x4)
            return

        left = min(q1, q2)
        right = max(q1, q2)

        self._ensure_site_in_ram(left)
        self._ensure_site_in_ram(right)

        t_left = self.sites[left]    # (chi_L, 2, chi_M)
        t_right = self.sites[right]  # (chi_M, 2, chi_R)

        chi_L = t_left.shape[0]
        chi_R = t_right.shape[2]

        # 1. Contract over shared bond chi_M: (chi_L, 2, 2, chi_R)
        two_site = np.einsum("lsr,rmp->lsmp", t_left, t_right)

        # 2. Apply 4x4 gate: gate_4x4 shape (2, 2, 2, 2)
        u_tensor = gate_4x4.reshape(2, 2, 2, 2)
        # two_site: l, s, m, p. Apply U on s, m -> a, b
        if q1 < q2:
            evolved = np.einsum("absm,lsmp->labp", u_tensor, two_site)
        else:
            # reversed order
            evolved = np.einsum("basm,lsmp->labp", u_tensor, two_site)

        # 3. Reshape into matrix for SVD: (chi_L * 2, 2 * chi_R)
        mat = evolved.reshape(chi_L * 2, 2 * chi_R)

        # 4. SVD without approximation: keep every singular value that is
        #    numerically non-zero in double precision.
        U, S, Vt = np.linalg.svd(mat, full_matrices=False)

        # Rank selection is a *roundoff* decision, not an approximation: we keep
        # every singular value above the numerical noise floor relative to the
        # largest one. The discarded mass is measured so the caller can report
        # it, instead of being silently dropped.
        if S.size:
            s_max = float(S[0])
            cutoff = s_max * self.SINGULAR_VALUE_ROUNDOFF_RATIO
            keep_mask = S > cutoff
            exact_rank = int(np.count_nonzero(keep_mask))
            discarded = float(np.sum(S[~keep_mask])) if (~keep_mask).any() else 0.0
            self.max_retained_singular_value = max(self.max_retained_singular_value, s_max)
        else:
            s_max = 0.0
            cutoff = 0.0
            exact_rank = 0
            discarded = 0.0

        if exact_rank < 1:
            # The two-site block is numerically zero. Keep one slot so the
            # tensor shapes stay valid; the state magnitude is preserved as 0.
            exact_rank = 1

        self.discarded_spectral_norm += discarded
        self.num_two_qubit_rewrites += 1
        self.max_observed_chi = max(self.max_observed_chi, exact_rank)

        # Slice to exact rank (NO truncation of physical information)
        U_kept = U[:, :exact_rank]
        S_kept = S[:exact_rank]
        Vt_kept = Vt[:exact_rank, :]

        # 5. Absorb singular values symmetrically or into right site
        new_left = U_kept.reshape(chi_L, 2, exact_rank)
        new_right = (np.diag(S_kept) @ Vt_kept).reshape(exact_rank, 2, chi_R)

        # 6. Memory check *before* mutating any state, so a refused allocation
        #    leaves the chain exactly as it was (no partial/incoherent update).
        old_bytes = t_left.nbytes + t_right.nbytes
        new_bytes = new_left.nbytes + new_right.nbytes
        projected_total = self.total_allocated_bytes + (new_bytes - old_bytes)

        if projected_total > self.max_storage_bytes:
            # Do NOT silently truncate and do NOT leave a half-applied rewrite.
            self.memory_limit_exceeded = True
            return

        self.active_ram_bytes += (new_bytes - old_bytes)
        self.total_allocated_bytes = projected_total

        self.sites[left] = np.ascontiguousarray(new_left)
        self.sites[right] = np.ascontiguousarray(new_right)

        # Trigger NVMe offload if RAM budget exceeded
        if self.active_ram_bytes > self.ram_budget_bytes:
            self._offload_distant_sites_to_nvme(left, right)

    def _apply_non_adjacent_two_qubit_gate(self, q1: int, q2: int, gate_4x4: np.ndarray):
        """SWAP network for non-adjacent gates."""
        lo, hi = min(q1, q2), max(q1, q2)
        swap_mat = np.array([
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1]
        ], dtype=np.complex128)

        # Swap up to adjacent
        for i in range(lo, hi - 1):
            self.apply_two_qubit_gate(i, i + 1, swap_mat)
        # Apply gate
        if q1 < q2:
            self.apply_two_qubit_gate(hi - 1, hi, gate_4x4)
        else:
            self.apply_two_qubit_gate(hi, hi - 1, gate_4x4)
        # Swap back
        for i in range(hi - 2, lo - 1, -1):
            self.apply_two_qubit_gate(i, i + 1, swap_mat)

    def _ensure_site_in_ram(self, q: int):
        if self.sites[q] is None:
            # Fetch from NVMe/disk swap
            swap_path = self.swap_files.get(q)
            if swap_path and os.path.exists(swap_path):
                self.sites[q] = np.load(swap_path)
                self.active_ram_bytes += self.sites[q].nbytes

    def _offload_distant_sites_to_nvme(self, keep_q1: int, keep_q2: int):
        """Pages out inactive sites to NVMe/disk storage."""
        for q in range(self.num_qubits):
            if q not in (keep_q1, keep_q2) and self.sites[q] is not None:
                swap_path = os.path.join(self.temp_dir, f"mps_site_{q}.npy")
                np.save(swap_path, self.sites[q])
                self.swap_files[q] = swap_path
                self.active_ram_bytes -= self.sites[q].nbytes
                self.sites[q] = None
                if self.active_ram_bytes <= self.ram_budget_bytes:
                    break

    def sample(
        self,
        shots: int = 1024,
        seed: int = 42,
        measured_qubits: Optional[List[int]] = None
    ) -> Tuple[Dict[str, int], bool]:
        """
        Samples measurement outcomes from the state.

        Sampling is performed from the exact statevector. Building that dense
        vector costs O(2^n) memory, so this is only attempted for chains small
        enough to fit comfortably in RAM.

        Args:
            shots: Number of samples.
            seed: RNG seed.
            measured_qubits: Ordered qubit indices to report, in Qiskit
                bitstring order (most significant first). ``None`` reports all
                qubits.

        Returns:
            (counts, supported). ``supported`` is False when the chain is too
            large to sample exactly; the caller must then report the result as
            unsupported rather than inventing counts.
        """
        if self.num_qubits <= self.MAX_SAMPLING_QUBITS:
            sv = self.to_statevector()
            probs = np.abs(sv) ** 2
            norm = float(np.sum(probs))
            if norm <= 0.0:
                raise ValueError(
                    "State has zero norm; cannot sample. The MPS chain likely "
                    "lost its state during a refused memory allocation."
                )
            probs /= norm

            n_out = self.num_qubits if measured_qubits is None else len(measured_qubits)
            if measured_qubits is not None:
                probs = _marginalize(probs, self.num_qubits, measured_qubits)

            rng = np.random.default_rng(seed)
            samples = rng.choice(1 << n_out, size=shots, p=probs)
            counts: Dict[str, int] = {}
            for s in samples:
                # Statevector index i encodes qubit q as bit q (qubit 0 is the
                # LSB), whereas Qiskit renders qubit 0 rightmost. format()
                # prints most-significant bit first, so the index must be
                # reversed to obtain the conventional bitstring.
                bs = format(s, f"0{n_out}b")[::-1]
                counts[bs] = counts.get(bs, 0) + 1
            return counts, True

        # Exact dense sampling is not implemented for this width. Returning a
        # placeholder here would fabricate a measurement result.
        return {}, False

    def to_statevector(self) -> np.ndarray:
        """Contracts MPS into exact dense statevector."""
        for q in range(self.num_qubits):
            self._ensure_site_in_ram(q)

        curr = self.sites[0] # (1, 2, chi1)
        # Reshape to (2, chi1)
        curr = curr.reshape(2, curr.shape[2])

        for q in range(1, self.num_qubits):
            sq = self.sites[q] # (chi_q, 2, chi_next)
            # Contract curr (..., chi_q) with sq (chi_q, 2, chi_next)
            dim_prev = curr.shape[0]
            chi_q = curr.shape[1]
            sq_reshaped = sq.reshape(chi_q, 2 * sq.shape[2])
            curr = curr @ sq_reshaped # (dim_prev, 2 * chi_next)
            curr = curr.reshape(dim_prev * 2, sq.shape[2])

        return curr.flatten()

    def cleanup(self):
        """Removes temporary swap files and any private scratch directory."""
        for path in list(self.swap_files.values()):
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        self.swap_files.clear()
        if self._owns_temp_dir and os.path.isdir(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except OSError:
                pass


class PathCMPSExactBackend:
    """
    Path C Classical Backend: MPS with unbounded bond dimension & NVMe offload.

    Correctness class
    -----------------
    No bond-dimension truncation is performed: the bond dimension always grows
    to the full numerical rank of the two-site block, so ``error_bound`` is 0.0
    (no *deliberate approximation*). Rank selection discards only singular
    values below the double-precision roundoff floor; that residual is a
    floating-point effect and is reported separately as
    ``numerical_error_bound`` (measured, never assumed).

    ``exact=True`` therefore means "no approximation was applied", not
    "mathematically exact". Finite-shot sampling error is reported separately as
    ``sampling_error_bound``.
    """

    #: Gates this backend actually implements as matrices.
    SUPPORTED_GATES = frozenset({
        "h", "x", "y", "z", "s", "sdg", "t", "tdg",
        "rz", "p", "u1", "rx", "ry",
        "cx", "cnot", "cz", "swap", "cp", "crx", "cry", "crz", "cu1",
    })

    #: Instructions that carry no state change.
    IGNORED_GATES = frozenset({"barrier", "id"})

    def __init__(self, ram_budget_mb: float = 120.0, max_storage_mb: float = 5120.0):
        self.ram_budget_mb = ram_budget_mb
        self.max_storage_mb = max_storage_mb

    def execute(self, circuit: Any, shots: int = 1024, seed: int = 42) -> SimulationResult:
        t0 = time.perf_counter()

        instructions, n_q = parse_circuit(circuit)

        # Fail closed: refuse any gate this backend cannot represent, instead of
        # silently leaving the state untouched and reporting a clean result.
        measured_qubits = self._validate_instructions(instructions)

        mps = ExactMPSTensorChain(
            num_qubits=n_q,
            ram_budget_mb=self.ram_budget_mb,
            max_storage_mb=self.max_storage_mb
        )

        try:
            for name, qubits, params in instructions:
                if name in self.IGNORED_GATES:
                    continue

                if name == "h":
                    h_mat = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=np.complex128) / np.sqrt(2.0)
                    mps.apply_single_qubit_gate(qubits[0], h_mat)
                elif name == "x":
                    x_mat = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], x_mat)
                elif name == "y":
                    y_mat = np.array([[0.0, -1j], [1j, 0.0]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], y_mat)
                elif name == "z":
                    z_mat = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], z_mat)
                elif name == "s":
                    s_mat = np.array([[1.0, 0.0], [0.0, 1j]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], s_mat)
                elif name == "sdg":
                    sdg_mat = np.array([[1.0, 0.0], [0.0, -1j]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], sdg_mat)
                elif name == "t":
                    t_mat = np.array([[1.0, 0.0], [0.0, np.exp(1j * np.pi / 4.0)]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], t_mat)
                elif name == "tdg":
                    tdg_mat = np.array([[1.0, 0.0], [0.0, np.exp(-1j * np.pi / 4.0)]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], tdg_mat)
                elif name in ("rz", "p", "u1"):
                    th = self._require_params(name, params)
                    rz_mat = np.array([[np.exp(-1j * th / 2.0), 0.0], [0.0, np.exp(1j * th / 2.0)]], dtype=np.complex128)
                    mps.apply_single_qubit_gate(qubits[0], rz_mat)
                elif name == "rx":
                    th = self._require_params(name, params)
                    c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                    mps.apply_single_qubit_gate(
                        qubits[0],
                        np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)
                    )
                elif name == "ry":
                    th = self._require_params(name, params)
                    c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                    mps.apply_single_qubit_gate(
                        qubits[0],
                        np.array([[c, -s], [s, c]], dtype=np.complex128)
                    )
                elif name in ("cx", "cnot"):
                    cx_mat = np.array([
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1],
                        [0, 0, 1, 0]
                    ], dtype=np.complex128)
                    mps.apply_two_qubit_gate(qubits[0], qubits[1], cx_mat)
                elif name == "cz":
                    cz_mat = np.array([
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 1, 0],
                        [0, 0, 0, -1]
                    ], dtype=np.complex128)
                    mps.apply_two_qubit_gate(qubits[0], qubits[1], cz_mat)
                elif name == "swap":
                    swap_mat = np.array([
                        [1, 0, 0, 0],
                        [0, 0, 1, 0],
                        [0, 1, 0, 0],
                        [0, 0, 0, 1]
                    ], dtype=np.complex128)
                    mps.apply_two_qubit_gate(qubits[0], qubits[1], swap_mat)
                elif name == "cp":
                    th = self._require_params(name, params)
                    mps.apply_two_qubit_gate(
                        qubits[0], qubits[1], _controlled_phase_matrix(th)
                    )
                elif name == "crz":
                    th = self._require_params(name, params)
                    e_m = np.exp(-1j * th / 2.0)
                    e_p = np.exp(1j * th / 2.0)
                    mps.apply_two_qubit_gate(
                        qubits[0], qubits[1],
                        np.array([
                            [1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, e_m, 0],
                            [0, 0, 0, e_p]
                        ], dtype=np.complex128)
                    )
                elif name == "crx":
                    th = self._require_params(name, params)
                    c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                    mps.apply_two_qubit_gate(
                        qubits[0], qubits[1],
                        np.array([
                            [1, 0, 0, 0],
                            [0, c, -1j * s, 0],
                            [0, -1j * s, c, 0],
                            [0, 0, 0, 1]
                        ], dtype=np.complex128)
                    )
                elif name == "cry":
                    th = self._require_params(name, params)
                    c, s = np.cos(th / 2.0), np.sin(th / 2.0)
                    mps.apply_two_qubit_gate(
                        qubits[0], qubits[1],
                        np.array([
                            [1, 0, 0, 0],
                            [0, c, -s, 0],
                            [0, s, c, 0],
                            [0, 0, 0, 1]
                        ], dtype=np.complex128)
                    )
                elif name == "cu1":
                    th = self._require_params(name, params)
                    mps.apply_two_qubit_gate(
                        qubits[0], qubits[1], _controlled_phase_matrix(th)
                    )

                if mps.memory_limit_exceeded:
                    # The chain was left untouched at the refused allocation:
                    # report UNRESOLVED, never a partial state.
                    t1 = time.perf_counter()
                    return SimulationResult(
                        path="C",
                        exact=False,
                        error_bound=float("inf"),
                        unresolved=True,
                        counts={},
                        execution_time_ms=(t1 - t0) * 1000.0,
                        metadata={
                            "reason": (
                                "Memory ceiling exceeded during MPS expansion. "
                                "No truncation is permitted, so the circuit is unresolved."
                            ),
                            "max_observed_chi": mps.max_observed_chi,
                            "allocated_bytes": mps.total_allocated_bytes,
                            "max_storage_bytes": mps.max_storage_bytes,
                            "truncation_applied": False,
                        }
                    )

            if n_q > ExactMPSTensorChain.MAX_SAMPLING_QUBITS:
                # We can still report the exact structure, but not counts.
                t1 = time.perf_counter()
                return SimulationResult(
                    path="C",
                    exact=True,
                    error_bound=0.0,
                    numerical_error_bound=float(mps.discarded_spectral_norm),
                    unresolved=False,
                    counts={},
                    execution_time_ms=(t1 - t0) * 1000.0,
                    metadata={
                        "backend": "ExactMPSTensorChain",
                        "qubit_count": n_q,
                        "max_observed_chi": mps.max_observed_chi,
                        "counts_supported": False,
                        "reason": (
                            f"Exact dense sampling is limited to "
                            f"{ExactMPSTensorChain.MAX_SAMPLING_QUBITS} qubits; "
                            f"this circuit has {n_q}. No counts were fabricated."
                        ),
                        "discarded_spectral_norm": mps.discarded_spectral_norm,
                        "truncation_applied": False,
                        "numerical_mode": "float64-untruncated-mps",
                    }
                )

            counts, supported = mps.sample(
                shots=shots, seed=seed, measured_qubits=measured_qubits
            )
            t1 = time.perf_counter()

            return SimulationResult(
                path="C",
                exact=True,
                error_bound=0.0,
                numerical_error_bound=float(mps.discarded_spectral_norm),
                unresolved=False,
                counts=counts if supported else {},
                sampling_error_bound=(
                    hoeffding_total_variation_bound(shots) if supported else None
                ),
                execution_time_ms=(t1 - t0) * 1000.0,
                metadata={
                    "backend": "ExactMPSTensorChain",
                    "qubit_count": n_q,
                    "max_observed_chi": mps.max_observed_chi,
                    "active_ram_mb": mps.active_ram_bytes / (1024 * 1024),
                    "total_storage_mb": mps.total_allocated_bytes / (1024 * 1024),
                    "nvme_swap_pages": len(mps.swap_files),
                    "shots": shots,
                    "seed": seed,
                    # Roundoff discarded at the rank-selection floor. This is a
                    # floating-precision measure, not an approximation budget.
                    "discarded_spectral_norm": mps.discarded_spectral_norm,
                    "max_retained_singular_value": mps.max_retained_singular_value,
                    "two_qubit_rewrites": mps.num_two_qubit_rewrites,
                    "singular_value_roundoff_ratio":
                        ExactMPSTensorChain.SINGULAR_VALUE_ROUNDOFF_RATIO,
                    # Retained key: asserts no bond-dimension truncation occurred.
                    "silent_truncation": False,
                    "truncation_applied": False,
                    "numerical_mode": "float64-untruncated-mps",
                }
            )
        finally:
            mps.cleanup()

    @staticmethod
    def _require_params(name: str, params: List[float]) -> float:
        if not params:
            raise ValueError(f"Gate '{name}' requires a rotation angle parameter.")
        return float(params[0])

    def _validate_instructions(
        self, instructions: List[Tuple[str, List[int], List[float]]]
    ) -> Optional[List[int]]:
        """
        Fail closed on any instruction this backend cannot faithfully execute.

        Terminal measurements are accepted: Path C samples from the final state,
        so the measured qubits are recorded and used to marginalize the
        distribution. Mid-circuit measurement is refused, because it would make
        the evolution non-unitary and cannot be reproduced by final sampling.

        Returns:
            Ordered measured qubit indices, or None if the circuit has no
            measurement instructions.

        Raises:
            ValueError: On an unsupported gate, wrong arity, a missing
                parameter, or a measurement that is not terminal.
        """
        arity = {
            "h": 1, "x": 1, "y": 1, "z": 1, "s": 1, "sdg": 1, "t": 1, "tdg": 1,
            "rz": 1, "p": 1, "u1": 1, "rx": 1, "ry": 1,
            "cx": 2, "cnot": 2, "cz": 2, "swap": 2,
            "cp": 2, "cu1": 2, "crx": 2, "cry": 2, "crz": 2,
            "barrier": 0, "id": 1, "measure": 1,
        }
        needs_params = {"rz", "p", "u1", "rx", "ry", "cp", "cu1", "crx", "cry", "crz"}

        # Identify measurement instructions and verify they are all terminal.
        measure_positions = [
            i for i, (name, _, _) in enumerate(instructions) if name == "measure"
        ]
        last_state_op = max(
            (i for i, (name, _, _) in enumerate(instructions)
             if name not in self.IGNORED_GATES and name != "measure"),
            default=-1,
        )
        measured_qubits: List[int] = []
        for i, (name, qubits, params) in enumerate(instructions):
            if name == "measure":
                if i < last_state_op:
                    raise ValueError(
                        "Path C does not support mid-circuit measurement "
                        f"(instruction {i} of {len(instructions)}). Path C evolves "
                        "a unitary statevector and samples only at the end."
                    )
                if not qubits:
                    raise ValueError("Measurement instruction has no qubit operand.")
                measured_qubits.append(int(qubits[0]))
                continue
            if name not in arity and name not in self.IGNORED_GATES:
                raise ValueError(
                    f"Path C does not support gate '{name}'. "
                    f"Supported gates: {sorted(self.SUPPORTED_GATES)}."
                )
            if name == "barrier":
                # A barrier spans an arbitrary number of qubits and is a no-op.
                continue
            if len(qubits) != arity[name]:
                raise ValueError(
                    f"Gate '{name}' expects {arity[name]} qubit(s), got {len(qubits)}: {qubits}"
                )
            if name in needs_params and not params:
                raise ValueError(f"Gate '{name}' requires a rotation angle parameter.")

        return measured_qubits or None
