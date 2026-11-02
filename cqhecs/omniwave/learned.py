"""Learned branching for OMNIWAVE.

A small trained model picks *which unassigned variable a front splits on*. Nothing
else is learned: SAT/UNSAT still come from the search, `SAT` only with a model verified
against the original CNF, `UNSAT` only with a DRAT proof checked by :mod:`cqhecs.drat`.
A wrong, missing or adversarial model can therefore only make the search slower - never
make a wrong answer appear. `tests/test_omniwave_learned.py` asserts that.

Two backends behind one protocol:

* :class:`FeatureScorer` - logistic regression over integer features, weights in a
  small JSON file, numpy only. This is what runs by default when a model is configured.
* :class:`HfScorer` - an optional fine-tuned tiny BERT
  (``google/bert_uncased_L-2_H-128_A-2``) over the same features rendered as text. It
  exists because the operator asked for a HuggingFace fine-tune, and it is only used
  if it measurably wins; the engine does not care which backend answers.

Without a configured model the engine keeps its Jeroslow-Wang order, unchanged.

Design record: ``research/sha_forge/LEARNED_BRANCHING.md``.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: Feature order is fixed and part of the weights file's contract. Appending is a
#: schema change; reordering silently invalidates every stored model.
FEATURE_NAMES: Tuple[str, ...] = (
    "occ2",
    "occ3",
    "occk",
    "pos",
    "neg",
    "balance",
    "depth",
    "nogood",
    "wave",
    "jwd",
)


@dataclass(frozen=True)
class Candidate:
    """One possible branch variable at one front, with its features."""

    variable: int
    features: Tuple[float, ...]

    def as_dict(self) -> Dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.features))


def _quantise(jw: float, scale: float = 64.0) -> float:
    """Quantise a float score so features are stable across machines.

    The Jeroslow-Wang score is a sum of powers of two; rounding it to 1/64 keeps the
    ordering that matters and keeps the feature vector identical on every platform.
    """
    if jw <= 0.0:
        return 0.0
    return min(255.0, math.floor(jw * scale))


def front_features(
    value: Dict[int, bool],
    candidates: Iterable[int],
    clauses: Sequence[Sequence[int]],
    nogoods: Sequence[Sequence[int]],
    jw_scores: Optional[Dict[int, float]] = None,
    depth: int = 0,
    wave: int = 0,
) -> List[Candidate]:
    """Features for every candidate at one front.

    Pure and deterministic: same inputs, same output, no floating-point accumulation
    beyond the quantised Jeroslow-Wang score.
    """
    occ2 = {v: 0 for v in candidates}
    occ3 = {v: 0 for v in candidates}
    occk = {v: 0 for v in candidates}
    pos = {v: 0 for v in candidates}
    neg = {v: 0 for v in candidates}
    nog = {v: 0 for v in candidates}

    for clause in clauses:
        satisfied = False
        open_literals: List[int] = []
        for literal in clause:
            current = value.get(abs(literal))
            if current is None:
                open_literals.append(literal)
            elif current == (literal > 0):
                satisfied = True
                break
        if satisfied or not open_literals:
            continue
        bucket = occ2 if len(clause) == 2 else occ3 if len(clause) == 3 else occk
        for literal in open_literals:
            variable = abs(literal)
            if variable not in occ2:
                continue
            bucket[variable] += 1
            if literal > 0:
                pos[variable] += 1
            else:
                neg[variable] += 1

    for clause in nogoods:
        for literal in clause:
            variable = abs(literal)
            if variable in nog:
                nog[variable] += 1

    out: List[Candidate] = []
    for variable in candidates:
        p = pos[variable]
        n = neg[variable]
        jw = (jw_scores or {}).get(variable, 0.0)
        features = (
            float(occ2[variable]),
            float(occ3[variable]),
            float(occk[variable]),
            float(p),
            float(n),
            float(min(p, n)),
            float(depth),
            float(nog[variable]),
            float(wave),
            _quantise(jw),
        )
        out.append(Candidate(variable=variable, features=features))
    return out


class BranchPolicy:
    """Interface every scorer implements. ``None`` means "no opinion"."""

    kind = "none"

    def choose(self, candidates: Sequence[Candidate]) -> Optional[int]:  # pragma: no cover - interface
        raise NotImplementedError

    def describe(self) -> Dict[str, object]:
        return {"kind": self.kind}


class FeatureScorer(BranchPolicy):
    """Logistic regression over :data:`FEATURE_NAMES`, weights in a JSON file."""

    kind = "logistic"

    def __init__(self, coefficients: Sequence[float], intercept: float = 0.0, metadata: Optional[Dict[str, object]] = None):
        if len(coefficients) != len(FEATURE_NAMES):
            raise ValueError(f"expected {len(FEATURE_NAMES)} coefficients, got {len(coefficients)}")
        self.coefficients = tuple(float(c) for c in coefficients)
        self.intercept = float(intercept)
        self.metadata = dict(metadata or {})

    def score(self, candidate: Candidate) -> float:
        total = self.intercept
        for weight, feature in zip(self.coefficients, candidate.features):
            total += weight * feature
        return total

    def choose(self, candidates: Sequence[Candidate]) -> Optional[int]:
        if not candidates:
            return None
        best = max(candidates, key=lambda c: (self.score(c), -c.variable))
        return best.variable

    @classmethod
    def load(cls, path) -> "FeatureScorer":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if tuple(data.get("features", ())) != FEATURE_NAMES:
            raise ValueError("weights file was trained on a different feature set")
        return cls(data["coefficients"], data.get("intercept", 0.0), data.get("metadata"))

    def save(self, path) -> None:
        Path(path).write_text(
            json.dumps(
                {
                    "schema": "hcs.omniwave.branch.v1",
                    "features": list(FEATURE_NAMES),
                    "coefficients": list(self.coefficients),
                    "intercept": self.intercept,
                    "metadata": self.metadata,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def describe(self) -> Dict[str, object]:
        return {"kind": self.kind, "features": list(FEATURE_NAMES), "metadata": self.metadata}


class HfScorer(BranchPolicy):
    """Optional fine-tuned tiny BERT over the same features rendered as text.

    Imported lazily so the engine has no transformers dependency unless a caller
    actually configures this backend.
    """

    kind = "hf"

    def __init__(self, model_dir, max_length: int = 32):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer  # local import on purpose

        self.model_dir = str(model_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_dir)
        self.model.eval()
        self.max_length = max_length

    @staticmethod
    def render(candidate: Candidate) -> str:
        return " ".join(f"{name} {int(value)}" for name, value in zip(FEATURE_NAMES, candidate.features))

    def score(self, candidate: Candidate) -> float:
        import torch

        with torch.no_grad():
            encoded = self.tokenizer(self.render(candidate), return_tensors="pt", truncation=True, max_length=self.max_length)
            logits = self.model(**encoded).logits[0]
            return float(logits[1] - logits[0])

    def choose(self, candidates: Sequence[Candidate]) -> Optional[int]:
        if not candidates:
            return None
        best = max(candidates, key=lambda c: (self.score(c), -c.variable))
        return best.variable

    def describe(self) -> Dict[str, object]:
        return {"kind": self.kind, "model_dir": self.model_dir}


def load_policy(path) -> BranchPolicy:
    """Loads whatever backend a directory or file describes."""
    target = Path(path)
    if target.is_dir():
        return HfScorer(target)
    return FeatureScorer.load(target)


# ---------------------------------------------------------------- training

def fit_logistic(samples: Sequence[Tuple[Sequence[float], int]], epochs: int = 400, learning_rate: float = 0.05,
                 l2: float = 1e-3) -> Tuple[List[float], float]:
    """Plain batch logistic regression in numpy. Returns (coefficients, intercept).

    Deliberately dependency-light and deterministic: no shuffling, no seeds, so the
    same data always produces the same weights.
    """
    import numpy as np

    if not samples:
        raise ValueError("no training samples")
    x = np.array([list(features) for features, _ in samples], dtype=np.float64)
    y = np.array([label for _, label in samples], dtype=np.float64)
    # Standardise per feature so the L2 term treats them comparably; the scaler is
    # stored with the weights in metadata by the training script.
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std[std == 0.0] = 1.0
    z = (x - mean) / std
    n, d = z.shape
    weights = np.zeros(d)
    intercept = 0.0
    for _ in range(epochs):
        logits = z @ weights + intercept
        # Numerically stable sigmoid
        preds = 1.0 / (1.0 + np.exp(-np.clip(logits, -60.0, 60.0)))
        error = preds - y
        grad_w = (z.T @ error) / n + l2 * weights
        grad_b = float(error.mean())
        weights -= learning_rate * grad_w
        intercept -= learning_rate * grad_b
    # Un-standardise, so the returned coefficients apply to raw features and
    # FeatureScorer needs no scaler at scoring time: w_raw = w/std,
    # b_raw = b - sum(w * mean / std).
    weights_raw = weights / std
    intercept_raw = intercept - float((weights * mean / std).sum())
    return list(map(float, weights_raw)), float(intercept_raw)
