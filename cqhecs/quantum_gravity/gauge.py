"""Track C: a deliberately bounded Z2 lattice gauge toy model (bridge, not a gravity claim).

This is an enabling tool for constraint simulation. It is **not** a quantum-gravity
result and **not** a claim about loop quantum gravity. Layout on a ``rows x cols`` square
lattice:

* vertices ``(rows+1) x (cols+1)``;
* horizontal links ``h[i][j]`` (``i in 0..rows``, ``j in 0..cols-1``);
* vertical links ``v[i][j]`` (``i in 0..rows-1``, ``j in 0..cols``);
* plaquettes ``(r, c)`` bounded by ``h[r][c], h[r+1][c], v[r][c], v[r][c+1]``.

Operators (``X``/``Z`` are Pauli operators on link qubits):

* Gauss generator at vertex ``(i, j)``: ``G = prod X`` over the links touching the vertex;
* plaquette operator: ``B_p = prod Z`` over the four plaquette links;
* Hamiltonian: ``H = -sum_p B_p`` (magnetic / pure-gauge toy).

``[H, G_v] = 0`` because a plaquette and a vertex star share an even number (0, 2 or 4) of
links. The physical (gauge-invariant) subspace is the ``+1`` eigenspace of every ``G_v``.
Dense construction is capped at ``<= 8`` links (dim 256).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError
from cqhecs.quantum_gravity.fermions import pauli_matrix

MODEL_ID = "qg.gauge.z2.v1"
MODEL_VERSION = "1.0.0"
LINK_QUBIT_CEILING = 8


def _label(num_links: int, indices: List[int], char: str) -> str:
    chars = ["I"] * num_links
    for index in indices:
        chars[index] = char
    return "".join(chars)


@dataclass(frozen=True)
class Z2Lattice:
    rows: int
    cols: int
    model_id: str = MODEL_ID
    model_version: str = MODEL_VERSION

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise QGModelError("rows and cols must be >= 1")
        if self.num_links > LINK_QUBIT_CEILING:
            raise QGResourceError(
                f"dense Z2 lattice limited to {LINK_QUBIT_CEILING} links (2^{LINK_QUBIT_CEILING}); "
                f"this lattice has {self.num_links}",
                estimate={"rows": self.rows, "cols": self.cols, "links": self.num_links},
            )

    # -- indexing ------------------------------------------------------------------
    @property
    def num_horizontal(self) -> int:
        return (self.rows + 1) * self.cols

    @property
    def num_vertical(self) -> int:
        return self.rows * (self.cols + 1)

    @property
    def num_links(self) -> int:
        return self.num_horizontal + self.num_vertical

    @property
    def num_vertices(self) -> int:
        return (self.rows + 1) * (self.cols + 1)

    def h_index(self, i: int, j: int) -> int:
        return i * self.cols + j

    def v_index(self, i: int, j: int) -> int:
        return self.num_horizontal + i * (self.cols + 1) + j

    def plaquette_links(self, r: int, c: int) -> List[int]:
        return [self.h_index(r, c), self.h_index(r + 1, c), self.v_index(r, c), self.v_index(r, c + 1)]

    def vertex_links(self, i: int, j: int) -> List[int]:
        links: List[int] = []
        if j - 1 >= 0:
            links.append(self.h_index(i, j - 1))
        if j <= self.cols - 1:
            links.append(self.h_index(i, j))
        if i - 1 >= 0:
            links.append(self.v_index(i - 1, j))
        if i <= self.rows - 1:
            links.append(self.v_index(i, j))
        return links

    # -- operators -----------------------------------------------------------------
    def _operator(self, indices: List[int], char: str) -> np.ndarray:
        return pauli_matrix(_label(self.num_links, sorted(set(indices)), char))

    def gauss_generators(self) -> List[Tuple[Tuple[int, int], np.ndarray]]:
        out: List[Tuple[Tuple[int, int], np.ndarray]] = []
        for i in range(self.rows + 1):
            for j in range(self.cols + 1):
                links = self.vertex_links(i, j)
                if links:
                    out.append(((i, j), self._operator(links, "X")))
        return out

    def plaquette_operators(self) -> List[Tuple[Tuple[int, int], np.ndarray]]:
        return [((r, c), self._operator(self.plaquette_links(r, c), "Z")) for r in range(self.rows) for c in range(self.cols)]

    def hamiltonian(self) -> np.ndarray:
        dim = 2 ** self.num_links
        ham = np.zeros((dim, dim), dtype=complex)
        for _, operator in self.plaquette_operators():
            ham -= operator
        return ham

    # -- checks --------------------------------------------------------------------
    def commutation_residuals(self) -> Dict[str, float]:
        ham = self.hamiltonian()
        residual = 0.0
        for _, generator in self.gauss_generators():
            commutator = ham @ generator - generator @ ham
            residual = max(residual, float(np.max(np.abs(commutator))))
        return {"max_commutator": residual}

    def manifest(self) -> Dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "kind": "z2_lattice_gauge",
            "rows": self.rows,
            "cols": self.cols,
            "num_links": self.num_links,
            "num_vertices": self.num_vertices,
            "num_plaquettes": self.rows * self.cols,
            "hamiltonian": "H = -sum_p B_p (B_p = prod Z over plaquette links)",
            "gauss_law": "G_v = prod X over incident links; physical subspace G_v = +1",
            "limitations": [
                "toy Z2 model; a QFT/constraint bridge, not a quantum-gravity result",
                "no continuum limit and no matter coupling in this slice",
            ],
        }


def gauss_law_satisfied(state: np.ndarray, lattice: Z2Lattice, *, tol: float = 1e-9) -> bool:
    """True when ``state`` lies in the ``+1`` eigenspace of every Gauss generator."""
    vec = np.asarray(state, dtype=complex).reshape(-1)
    for _, generator in lattice.gauss_generators():
        if not np.allclose(generator @ vec, vec, atol=tol):
            return False
    return True
