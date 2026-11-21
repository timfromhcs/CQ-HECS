"""Track B: the Sachdev-Ye-Kitaev (SYK) model, q=4, small N.

Definition (model ``qg.syk.q4.v1``)
-----------------------------------
For ``N = 2 * num_qubits`` Majorana modes with ``q = 4``:

    H = sum_{i<j<k<l} J_{ijkl} * gamma_i gamma_j gamma_k gamma_l

The couplings ``J_{ijkl}`` are drawn from a seeded Gaussian (``E[J^2] = scale^2``). A
preregistered *seeded* subset of terms may be kept (sparsification); the kept weight
fraction is reported and never claimed to bound the spectrum error.

All Majorana indices are distinct, so each product ``gamma_i gamma_j gamma_k gamma_l`` is
Hermitian and ``H`` commutes with the fermion-parity operator ``prod_i gamma_i``. Both are
asserted by the tests. Dense construction is limited to ``num_qubits <= 8`` (dim 256).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from cqhecs.quantum_gravity.errors import QGModelError, QGResourceError
from cqhecs.quantum_gravity.fermions import (
    DENSE_QUBIT_CEILING,
    majorana_labels,
    pauli_matrix,
    pauli_multiply,
    parity_operator,
)

MODEL_ID = "qg.syk.q4.v1"
MODEL_VERSION = "1.0.0"


def _pauli_terms_for_indices(
    labels: List[str], indices: Tuple[int, ...]
) -> Tuple[complex, str]:
    """Multiply the Majorana Pauli labels at ``indices``; return ``(phase, label)``."""
    phase: complex = 1.0
    label = "I" * len(labels[0])
    for idx in indices:
        p, label = pauli_multiply(label, labels[idx])
        phase *= p
    return phase, label


@dataclass(frozen=True)
class SYKHamiltonian:
    """A frozen, seeded q=4 SYK instance with an explicit encoding and limits."""

    num_qubits: int
    seed: int
    q: int = 4
    scale: float = 1.0
    num_terms: Optional[int] = None
    normalize: bool = False
    model_id: str = MODEL_ID
    model_version: str = MODEL_VERSION
    couplings: Dict[Tuple[int, ...], float] = field(default_factory=dict)
    _pauli: Dict[str, complex] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.q < 2 or self.q % 2 != 0:
            raise QGModelError("SYK interaction order q must be an even integer >= 2")
        if self.num_qubits < 1:
            raise QGModelError("num_qubits must be >= 1")
        if 2 * self.num_qubits < self.q:
            raise QGModelError("need at least q Majorana modes")
        self._build()

    # -- construction --------------------------------------------------------------
    def _build(self) -> None:
        n = self.num_qubits
        num_majorana = 2 * n
        all_indices = list(itertools.combinations(range(num_majorana), self.q))
        total_terms = len(all_indices)

        rng = np.random.default_rng(self.seed)
        if self.num_terms is not None and self.num_terms < total_terms:
            chosen = rng.choice(total_terms, size=int(self.num_terms), replace=False)
            chosen = np.sort(np.asarray(chosen, dtype=int))
            selected = [all_indices[int(i)] for i in chosen]
        else:
            selected = all_indices

        couplings: Dict[Tuple[int, ...], float] = {}
        for combo in selected:
            couplings[combo] = float(rng.normal(0.0, self.scale if self.scale else 1.0))

        pauli: Dict[str, complex] = {}
        labels = majorana_labels(n)
        norm = 1.0
        if self.normalize and total_terms > 0:
            norm = float(np.sqrt(total_terms))
        for combo, coupling in couplings.items():
            phase, label = _pauli_terms_for_indices(labels, combo)
            pauli[label] = pauli.get(label, 0.0 + 0.0j) + (coupling / norm) * phase

        object.__setattr__(self, "couplings", couplings)
        object.__setattr__(self, "_pauli", {k: v for k, v in pauli.items() if abs(v) > 1e-15})

    @property
    def num_majorana(self) -> int:
        return 2 * self.num_qubits

    @property
    def total_terms(self) -> int:
        import math

        return math.comb(self.num_majorana, self.q)

    @property
    def kept_terms(self) -> int:
        return len(self.couplings)

    @property
    def kept_weight_fraction(self) -> float:
        return self.kept_terms / self.total_terms if self.total_terms else 0.0

    # -- matrices ------------------------------------------------------------------
    def matrix(self) -> np.ndarray:
        if self.num_qubits > DENSE_QUBIT_CEILING:
            raise QGResourceError(
                f"dense SYK matrix limited to {DENSE_QUBIT_CEILING} qubits",
                estimate={
                    "num_qubits": self.num_qubits,
                    "ceiling": DENSE_QUBIT_CEILING,
                },
            )
        dim = 2 ** self.num_qubits
        ham = np.zeros((dim, dim), dtype=complex)
        for label, coeff in self._pauli.items():
            ham += coeff * pauli_matrix(label)
        return ham

    def spectrum(self) -> np.ndarray:
        """Real eigenvalues of the (Hermitian) Hamiltonian, ascending."""
        ham = self.matrix()
        if not np.allclose(ham, ham.conj().T, atol=1e-10):
            raise QGModelError("SYK Hamiltonian is not Hermitian")
        return np.linalg.eigvalsh(ham)

    def hermitian_terms(self) -> List[np.ndarray]:
        """Return the individual Hermitian term matrices ``{J * gamma_i gamma_j gamma_k gamma_l}``.

        Used for Trotter/product-formula evolution so that its error can be measured
        against the exact evolution separately from any sampling error.
        """
        from cqhecs.quantum_gravity.fermions import majorana_operators

        if self.num_qubits > DENSE_QUBIT_CEILING:
            raise QGResourceError(
                "dense SYK terms limited to the dense qubit ceiling",
                estimate={"num_qubits": self.num_qubits, "ceiling": DENSE_QUBIT_CEILING},
            )
        ops = majorana_operators(self.num_qubits)
        dim = 2 ** self.num_qubits
        norm = float(np.sqrt(self.total_terms)) if (self.normalize and self.total_terms) else 1.0
        terms: List[np.ndarray] = []
        for combo, coupling in sorted(self.couplings.items()):
            mat = np.eye(dim, dtype=complex)
            for idx in combo:
                mat = mat @ ops[idx]
            terms.append((coupling / norm) * mat)
        return terms

    def parity_commutation_residual(self) -> float:
        parity = parity_operator(self.num_qubits)
        ham = self.matrix()
        commutator = ham @ parity - parity @ ham
        return float(np.max(np.abs(commutator)))

    # -- manifests -----------------------------------------------------------------
    def manifest(self) -> Dict[str, Any]:
        # Couplings are large; store a deterministic digest rather than every float.
        import hashlib

        payload = ";".join(
            f"{','.join(map(str, k))}={v:.17g}" for k, v in sorted(self.couplings.items())
        )
        digest = hashlib.sha256(payload.encode("ascii")).hexdigest()
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "kind": "syk_q4",
            "num_qubits": self.num_qubits,
            "num_majorana": self.num_majorana,
            "q": self.q,
            "seed": self.seed,
            "scale": self.scale,
            "normalize": self.normalize,
            "total_terms": self.total_terms,
            "kept_terms": self.kept_terms,
            "kept_weight_fraction": self.kept_weight_fraction,
            "couplings_sha256": digest,
            "encoding": "jordan_wigner",
            "limitations": [
                "finite-N model; no continuum holographic limit",
                "sparsification changes the model; the fraction is reported, not bounded",
            ],
        }


def build_syk(
    num_qubits: int,
    *,
    seed: int,
    q: int = 4,
    scale: float = 1.0,
    num_terms: Optional[int] = None,
    normalize: bool = False,
) -> SYKHamiltonian:
    """Build a frozen SYK Hamiltonian. ``num_terms`` triggers seeded sparsification."""
    return SYKHamiltonian(
        num_qubits=num_qubits,
        seed=int(seed),
        q=q,
        scale=float(scale),
        num_terms=num_terms,
        normalize=normalize,
    )
