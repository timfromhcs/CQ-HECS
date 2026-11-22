"""Path G research prototype: Matrix Product Evolution (depth-oriented tensor train).

EXPERIMENTAL / RESEARCH_ONLY. Not imported by the router or any stable module.

Follows the structure described in Kawabe et al., arXiv:2608.03472 (preprint,
read sections I-III.2; see the research record for what was NOT read):
  * the circuit is a rectangular 2D network, one tensor per (qubit, layer);
    idle slots get identity tensors; 2-qubit gates are split by operator-
    Schmidt (SVD) into an MPO with bond <= 4;
  * each qubit row is an MPE: a tensor train along time whose bonds are the
    qubit wire segments;
  * neighbouring MPEs are merged along the qubit direction; the temporal
    bonds of the merged train are compressed by canonicalisation + SVD
    truncation at ``chi_max``;
  * the final train is contracted to a dense state (tiny sizes only).

Deliberate simplifications (stated, not hidden): merge-then-compress instead
of the paper's zip-up (we materialise each merged tensor, so memory is higher
than zip-up); no temporal compression of identity blocks (Sec. II.3); no
post-selection; product initial state only; nearest-neighbour 2-qubit gates
only (anything else is a typed refusal). Conventions: tensors ``(bl, k, br)``
with ``bl``/``br`` temporal bonds and ``k`` the open spatial leg to the next
row; qubit 0 is the least significant bit of the dense readout.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from _common import Instruction, ResourceRefusal, UnsupportedPrototypeInput, instruction_tensor

Op = Tuple[Tuple[int, ...], np.ndarray]  # (qubits, tensor of shape (2,)*(2k): outs then ins)
CUT = 1e-14


def instructions_to_ops(instructions: Sequence[Instruction]) -> List[Op]:
    return [(tuple(i[1]), instruction_tensor(i)) for i in instructions]


def asap_layers(ops: Sequence[Op], n: int) -> List[List[Op]]:
    """Greedy as-soon-as-possible layering; each qubit has <= 1 op per layer."""
    depth = [0] * n
    layers: List[List[Op]] = []
    for qs, U in ops:
        if len(qs) == 2 and abs(qs[0] - qs[1]) != 1:
            raise UnsupportedPrototypeInput(
                f"Path G prototype supports nearest-neighbour 2q gates only, got qubits {qs}"
            )
        if len(qs) > 2:
            raise UnsupportedPrototypeInput("gates on >2 qubits are out of scope")
        t = max(depth[q] for q in qs)
        while len(layers) <= t:
            layers.append([])
        layers[t].append((qs, U))
        for q in qs:
            depth[q] = t + 1
    return layers


def dense_from_ops(ops: Sequence[Op], n: int) -> np.ndarray:
    """Independent dense simulator for generic ops (tensordot; qubit 0 = LSB)."""
    psi = np.zeros((2,) * n, dtype=np.complex128)
    psi[(0,) * n] = 1.0  # axis q = qubit q
    for qs, U in ops:
        k = len(qs)
        out = np.tensordot(U, psi, axes=(list(range(k, 2 * k)), list(qs)))
        psi = np.moveaxis(out, list(range(k)), list(qs))
    return np.transpose(psi, list(range(n - 1, -1, -1))).reshape(-1)


def _row_tensors(layers: List[List[Op]], q: int) -> List[np.ndarray]:
    """Row ``q``: list of W[win, wout, sl, sr] over time (identity where idle)."""
    row = []
    for layer in layers:
        w = np.zeros((2, 2, 1, 1), dtype=np.complex128)
        w[0, 0, 0, 0] = w[1, 1, 0, 0] = 1.0
        for qs, U in layer:
            if q not in qs:
                continue
            if len(qs) == 1:
                w = np.zeros((2, 2, 1, 1), dtype=np.complex128)
                w[:, :, 0, 0] = U.T  # W[win,wout] = U[wout,win]
            else:
                a, b = qs
                if a > b:  # reorient so the gate acts on (low, high)
                    U = U.transpose(1, 0, 3, 2)
                    a, b = b, a
                M = U.transpose(0, 2, 1, 3).reshape(4, 4)  # (o_a,i_a),(o_b,i_b)
                u, s, vh = np.linalg.svd(M)
                kk = max(int(np.sum(s > CUT * s[0])), 1)
                if q == a:
                    L = (u[:, :kk] * np.sqrt(s[:kk])).reshape(2, 2, kk)  # o,i,k
                    w = np.zeros((2, 2, 1, kk), dtype=np.complex128)
                    w[:, :, 0, :] = L.transpose(1, 0, 2)               # [win=i, wout=o, k]
                else:
                    R = (np.sqrt(s[:kk])[:, None] * vh[:kk, :]).reshape(kk, 2, 2)  # k,o,i
                    w = np.zeros((2, 2, kk, 1), dtype=np.complex128)
                    w[:, :, :, 0] = R.transpose(2, 1, 0)               # [win=i, wout=o, k]
        row.append(w)
    return row


def _compress(train: List[np.ndarray], chi_max: Optional[int]) -> Tuple[List[np.ndarray], float, int]:
    """Canonicalise (QR left->right) then truncate (SVD right->left) interior temporal bonds.

    The last tensor's right leg is a physical output leg and is never truncated.
    Returns (train, discarded relative weight sum, max bond after).
    """
    T = len(train)
    disc = 0.0
    if T == 1:
        return train, disc, 1
    tr = [t.copy() for t in train]
    for t in range(T - 1):
        bl, k, br = tr[t].shape
        Q, R = np.linalg.qr(tr[t].reshape(bl * k, br))
        tr[t] = Q.reshape(bl, k, Q.shape[1])
        tr[t + 1] = np.tensordot(R, tr[t + 1], axes=([1], [0]))
    maxb = 1
    for t in range(T - 1, 0, -1):
        bl, k, br = tr[t].shape
        U, S, Vh = np.linalg.svd(tr[t].reshape(bl, k * br), full_matrices=False)
        keep = max(int(np.sum(S > CUT * S[0])), 1) if S.size and S[0] > 0 else 1
        if chi_max is not None:
            keep = min(keep, chi_max)
        disc += float(np.sum(S[keep:] ** 2) / max(np.sum(S ** 2), 1e-300))
        U, S, Vh = U[:, :keep], S[:keep], Vh[:keep, :]
        tr[t] = Vh.reshape(keep, k, br)
        tr[t - 1] = np.tensordot(tr[t - 1], U * S[None, :], axes=([2], [0]))
        maxb = max(maxb, keep)
    return tr, disc, maxb


@dataclass
class MPEResult:
    state: np.ndarray
    chi_max: Optional[int]
    depth: int
    max_bond_before: int
    max_bond_after: int
    discarded_weight: float
    max_stored_elements: int
    wall_s: float
    notes: List[str] = field(default_factory=list)


def mpe_state(
    ops: Sequence[Op],
    n: int,
    chi_max: Optional[int] = None,
    max_elements: int = 1 << 22,
    max_qubits: int = 12,
) -> MPEResult:
    """Simulate ``ops`` on |0..0> with the MPE method; dense readout (tiny n)."""
    if n > max_qubits:
        raise ResourceRefusal(f"dense readout of {n} qubits exceeds prototype cap {max_qubits}")
    t0 = time.perf_counter()
    layers = asap_layers(ops, n)
    T = len(layers)
    if T == 0:
        v = np.zeros(1 << n, dtype=np.complex128)
        v[0] = 1.0
        return MPEResult(v, chi_max, 0, 1, 1, 0.0, 0, time.perf_counter() - t0)
    rows = [_row_tensors(layers, q) for q in range(n)]
    # group = row 0 with input leg sliced to |0>: tensors (bl, k, br)
    grp: List[np.ndarray] = []
    for t, w in enumerate(rows[0]):
        g = w[:, :, 0, :]  # [win, wout, k]
        g = g.transpose(0, 2, 1)  # (bl=win, k, br=wout)
        if t == 0:
            g = g[:1]  # input fixed to |0>
        grp.append(np.ascontiguousarray(g))
    disc = 0.0
    maxb_before = 1
    maxb_after = 1
    stored = max(g.size for g in grp)
    for q in range(1, n):
        new = []
        for t, w in enumerate(rows[q]):
            ww = w if t > 0 else w[:1]  # slice input |0> at t=0 (win index 0)
            # new[(bg,win), sr, (brg,wout)] = grp[bg,k,brg] * ww[win,wout,k,sr]
            nt = np.einsum("akb,ioks->aisbo", grp[t], ww)
            a, i, s, b, o = nt.shape
            new.append(nt.reshape(a * i, s, b * o))
        est = max(x.size for x in new)
        if est > max_elements:
            raise ResourceRefusal(f"merged MPE tensor of {est} elements exceeds budget {max_elements}")
        maxb_before = max(maxb_before, max(x.shape[2] for x in new[:-1]) if T > 1 else 1)
        new, d, mb = _compress(new, chi_max)
        disc += d
        maxb_after = max(maxb_after, mb)
        grp = new
        stored = max(stored, est, max(x.size for x in grp))
    # contract the train over time; spatial leg k must be 1 at the right boundary
    cur = grp[0][0, 0, :]
    for t in range(1, T):
        cur = cur @ grp[t][:, 0, :]
    vec = cur.reshape((2,) * n)  # axes = qubit 0..n-1 (qubit 0 most significant in C-order)
    state = np.transpose(vec, list(range(n - 1, -1, -1))).reshape(-1)
    return MPEResult(state, chi_max, T, maxb_before, maxb_after, disc, int(stored), time.perf_counter() - t0)


# -- tiny Hamiltonians --------------------------------------------------------
def _pauli_on(n: int, ops_by_qubit) -> np.ndarray:
    mats = {"I": np.eye(2), "X": np.array([[0, 1], [1, 0]]), "Z": np.diag([1.0, -1.0])}
    full = np.array([[1.0 + 0j]])
    for q in range(n - 1, -1, -1):  # little-endian: qubit 0 is the rightmost kron factor
        full = np.kron(full, mats[ops_by_qubit.get(q, "I")])
    return full


def tfim_hamiltonian(n: int, J: float, h: float) -> np.ndarray:
    """H = -J sum_i Z_i Z_{i+1} - h sum_i X_i (open chain), dense, qubit 0 = LSB."""
    H = np.zeros((1 << n, 1 << n), dtype=np.complex128)
    for i in range(n - 1):
        H -= J * _pauli_on(n, {i: "Z", i + 1: "Z"})
    for i in range(n):
        H -= h * _pauli_on(n, {i: "X"})
    return H


def exact_evolution(n: int, J: float, h: float, t: float) -> np.ndarray:
    from scipy.linalg import expm

    psi0 = np.zeros(1 << n, dtype=np.complex128)
    psi0[0] = 1.0
    return expm(-1j * t * tfim_hamiltonian(n, J, h)) @ psi0


def tfim_trotter_instructions(n: int, J: float, h: float, t: float, steps: int) -> List[Instruction]:
    """First-order Trotter of exp(-iHt): per step exp(iJdt ZZ) via cx-rz-cx, then exp(ihdt X)."""
    dt = t / steps
    out: List[Instruction] = []
    for _ in range(steps):
        for i in range(n - 1):
            out += [("cx", [i, i + 1], []), ("rz", [i + 1], [-2.0 * J * dt]), ("cx", [i, i + 1], [])]
        for i in range(n):
            out.append(("rx", [i], [-2.0 * h * dt]))
    return out


def random_brickwork_ops(n: int, depth: int, seed: int) -> List[Op]:
    """Random 2-qubit unitaries (QR of complex Gaussian) on a brickwork pattern."""
    rng = np.random.default_rng(seed)
    ops: List[Op] = []
    for d in range(depth):
        for a in range(d % 2, n - 1, 2):
            z = rng.normal(size=(4, 4)) + 1j * rng.normal(size=(4, 4))
            qm, r = np.linalg.qr(z)
            qm = qm * (np.diag(r) / np.abs(np.diag(r)))
            ops.append(((a, a + 1), qm.reshape(2, 2, 2, 2)))
    return ops
