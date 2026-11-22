"""Small truncating MPS with Kraus/trajectory support (research prototype).

Used by Path F (trajectories) and as the site-oriented baseline for Path G.
Sites are ``A[q]`` of shape ``(chiL, 2, chiR)``; the orthogonality centre is
tracked so SVD truncation is optimal and Kraus branch probabilities are exact
norms. ``chi_max=None`` means no bond cap; singular values below
``cutoff_rel`` x largest are still dropped (numerical rank), and every discard
is accumulated in ``discarded_weight`` (a diagnostic, not a certified bound).
"""
from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np

from _common import ResourceRefusal, gate_2q


class MPS:
    def __init__(self, n: int, chi_max: Optional[int] = None, cutoff_rel: float = 1e-14):
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.chi_max = chi_max
        self.cutoff_rel = cutoff_rel
        self.A: List[np.ndarray] = []
        for _ in range(n):
            t = np.zeros((1, 2, 1), dtype=np.complex128)
            t[0, 0, 0] = 1.0
            self.A.append(t)
        self.center = 0
        self.discarded_weight = 0.0
        self.max_chi_seen = 1

    def copy(self) -> "MPS":
        m = MPS.__new__(MPS)
        m.n, m.chi_max, m.cutoff_rel = self.n, self.chi_max, self.cutoff_rel
        m.A = [a.copy() for a in self.A]
        m.center = self.center
        m.discarded_weight = self.discarded_weight
        m.max_chi_seen = self.max_chi_seen
        return m

    # -- canonical form ---------------------------------------------------
    def _move_center(self, to: int) -> None:
        while self.center < to:
            q = self.center
            l, s, r = self.A[q].shape
            Q, R = np.linalg.qr(self.A[q].reshape(l * s, r))
            self.A[q] = Q.reshape(l, s, Q.shape[1])
            self.A[q + 1] = np.tensordot(R, self.A[q + 1], axes=([1], [0]))
            self.center += 1
        while self.center > to:
            q = self.center
            l, s, r = self.A[q].shape
            Q, R = np.linalg.qr(self.A[q].reshape(l, s * r).T)
            self.A[q] = Q.T.reshape(Q.shape[1], s, r)
            self.A[q - 1] = np.tensordot(self.A[q - 1], R.T, axes=([2], [0]))
            self.center -= 1

    def norm2(self) -> float:
        self._move_center(0)
        return float(np.real(np.vdot(self.A[0], self.A[0])))

    def normalize(self) -> None:
        nrm = np.sqrt(self.norm2())
        if nrm == 0.0:
            raise ZeroDivisionError("zero-norm MPS")
        self.A[self.center] = self.A[self.center] / nrm

    # -- gates ------------------------------------------------------------
    def apply_1q(self, q: int, U: np.ndarray) -> None:
        self._move_center(q)
        self.A[q] = np.einsum("ab,lbr->lar", U, self.A[q])

    def _theta(self, q: int) -> np.ndarray:
        return np.einsum("lsm,mtr->lstr", self.A[q], self.A[q + 1])

    def _split(self, q: int, theta: np.ndarray) -> None:
        l, _, _, r = theta.shape
        U, S, Vh = np.linalg.svd(theta.reshape(l * 2, 2 * r), full_matrices=False)
        if S.size == 0 or S[0] == 0.0:
            keep = 1
        else:
            keep = max(int(np.sum(S > self.cutoff_rel * S[0])), 1)
        if self.chi_max is not None:
            keep = min(keep, self.chi_max)
        self.discarded_weight += float(np.sum(S[keep:] ** 2) / max(np.sum(S ** 2), 1e-300))
        kept_w = float(np.sum(S[:keep] ** 2))
        total_w = float(np.sum(S ** 2))
        S = S[:keep]
        if kept_w < total_w:
            # renormalise so the state norm is unchanged by the truncation
            S = S * np.sqrt(total_w / kept_w) if kept_w > 0 else S
        U, Vh = U[:, :keep], Vh[:keep, :]
        self.max_chi_seen = max(self.max_chi_seen, keep)
        self.A[q] = U.reshape(l, 2, keep)
        self.A[q + 1] = (S[:, None] * Vh).reshape(keep, 2, r)
        self.center = q + 1

    def _apply_adjacent(self, q: int, G: np.ndarray) -> None:
        """G[o_q, o_{q+1}, i_q, i_{q+1}] on adjacent sites (q, q+1)."""
        self._move_center(q)
        theta = np.einsum("abst,lstr->labr", G, self._theta(q))
        self._split(q, theta)

    def apply_2q(self, a: int, b: int, G: np.ndarray) -> None:
        """Two-qubit tensor ``G[o_a,o_b,i_a,i_b]`` on any pair (swap routing)."""
        if a == b:
            raise ValueError("2q gate needs distinct qubits")
        G = np.asarray(G).reshape(2, 2, 2, 2)
        if a > b:
            G = G.transpose(1, 0, 3, 2)
            a, b = b, a
        sw = gate_2q("swap")
        for k in range(b - 1, a, -1):  # bring b next to a
            self._apply_adjacent(k, sw)
        self._apply_adjacent(a, G)
        for k in range(a + 1, b):
            self._apply_adjacent(k, sw)

    # -- Kraus (trajectory) ----------------------------------------------
    def kraus_branch_norms_1q(self, q: int, Ks: Sequence[np.ndarray]) -> np.ndarray:
        self._move_center(q)
        out = []
        for K in Ks:
            t = np.einsum("ab,lbr->lar", K, self.A[q])
            out.append(float(np.real(np.vdot(t, t))))
        return np.array(out)

    def kraus_branch_norms_2q(self, a: int, b: int, Ks: Sequence[np.ndarray]) -> np.ndarray:
        """Exact ||K psi||^2 for each 4x4 Kraus op (swap-routed, no truncation)."""
        trial = self.copy()
        trial.chi_max = None
        trial.cutoff_rel = 0.0
        sw = gate_2q("swap")
        a2, b2 = (a, b) if a < b else (b, a)
        flip = a > b
        for k in range(b2 - 1, a2, -1):
            trial._apply_adjacent(k, sw)
        trial._move_center(a2)
        th = trial._theta(a2)
        out = []
        for K in Ks:
            K4 = np.asarray(K).reshape(2, 2, 2, 2)
            if flip:
                K4 = K4.transpose(1, 0, 3, 2)
            t = np.einsum("abst,lstr->labr", K4, th)
            out.append(float(np.real(np.vdot(t, t))))
        return np.array(out)

    def apply_kraus_1q(self, q: int, K: np.ndarray) -> None:
        self.apply_1q(q, K)
        self.normalize()

    def apply_kraus_2q(self, a: int, b: int, K: np.ndarray) -> None:
        self.apply_2q(a, b, K)
        self.normalize()

    # -- readout ---------------------------------------------------------
    def to_dense(self, max_qubits: int = 14) -> np.ndarray:
        """Little-endian dense vector (qubit 0 = LSB)."""
        if self.n > max_qubits:
            raise ResourceRefusal(
                f"dense readout of {self.n} qubits exceeds prototype cap {max_qubits}"
            )
        cur = self.A[0].reshape(2, -1)
        for q in range(1, self.n):
            cur = np.tensordot(cur, self.A[q], axes=([cur.ndim - 1], [0]))
            cur = cur.reshape(-1, cur.shape[-1])
        vec = cur.reshape((2,) * self.n)
        return np.transpose(vec, list(range(self.n - 1, -1, -1))).reshape(-1)

    def bond_dims(self) -> List[int]:
        return [a.shape[2] for a in self.A[:-1]]
