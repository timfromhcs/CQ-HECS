"""Train the learned branch scorer ("JEV") for OMNIWAVE on real data.

Three stages, each reproducible from this file:

1. **Collect** - walk real fronts of the project's own instance families, compute the
   feature vector for every candidate variable, and label it with the cheapest honest
   oracle available: does assigning this variable refute at least one of its two
   branches? The label is produced by the engine's own unit propagation, so the model
   learns exactly the signal the engine can act on.
2. **Fit** - two backends on the same data:
   * logistic regression in numpy (no sklearn, deterministic, weights in JSON);
   * a fine-tuned tiny HuggingFace model (`google/bert_uncased_L-2_H-128_A-2`,
     4.4 M parameters) over the same features rendered as text.
3. **Evaluate** - accuracy on a **held-out instance** (never a front from a training
   instance), then the engine itself with `branch="jw"` versus `branch="learned"`.

Nothing here is required to run the engine: without a trained model OMNIWAVE keeps its
Jeroslow-Wang order. The weights are written next to the results, not into the
repository.

    python scripts/train_branch_jev.py --out E:/qCSHA/sha_forge_results/omniwave_jev
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time
from typing import List, Sequence, Tuple

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from cqhecs.omniwave import OmniwaveEngine, OmniwaveConfig  # noqa: E402
from cqhecs.omniwave.learned import FEATURE_NAMES, FeatureScorer, fit_logistic, front_features  # noqa: E402
from cqhecs.sat import CNF  # noqa: E402
from omniwave_efficiency import pigeonhole, random_3sat, sha_instance, tseitin_grid  # noqa: E402

TRAIN_INSTANCES = [
    ("pigeonhole", pigeonhole(7, 6)),
    ("parity", tseitin_grid(3, 3)),
    ("random", random_3sat(60, 260, 20261103)),
    ("sha", sha_instance(8, 12)),
]
TEST_INSTANCE = ("pigeonhole", pigeonhole(8, 7))


def collect(formula: CNF, family: str, max_fronts: int, budget_seconds: float, seed: int = 20261102) -> List[dict]:
    """Walk real fronts and label every candidate with the failed-literal oracle."""
    rng = random.Random(seed)
    engine = OmniwaveEngine(formula, OmniwaveConfig(waves=1, workers=1, timeout_seconds=budget_seconds))
    engine._deadline = float("inf")  # the walk is bounded by max_fronts, not by time
    rows: List[dict] = []
    frontier: List[Tuple[int, ...]] = [()]
    depth = 0
    started = time.perf_counter()
    while frontier and len(rows) < max_fronts * 8 and time.perf_counter() - started < budget_seconds:
        next_frontier: List[Tuple[int, ...]] = []
        for cube in frontier[: max_fronts]:
            outcome, value = engine._propagate(cube)
            if outcome != "open":
                continue
            # Candidate set: variables still open, capped so a front cannot dominate.
            open_vars = [v for v in range(1, formula.num_vars + 1) if v not in value]
            rng.shuffle(open_vars)
            open_vars = sorted(open_vars[:12])
            if not open_vars:
                continue
            candidates = front_features(value, open_vars, formula.clauses, engine._nogoods, depth=depth, wave=0)
            for candidate in candidates:
                pruned = 0
                for literal in (candidate.variable, -candidate.variable):
                    branch_outcome, _ = engine._propagate(cube + (literal,))
                    if branch_outcome == "conflict":
                        pruned += 1
                rows.append(
                    {
                        "family": family,
                        "source": formula.source,
                        "features": list(candidate.features),
                        "label": 1 if pruned >= 1 else 0,
                        "pruned": pruned,
                    }
                )
            # Keep walking: branch on the JW-best variable to stay on the engine's path.
            var = engine._branch_var(type("N", (), {"wave": 0, "depth": depth, "cube": cube})(), value)
            if var:
                next_frontier.append(cube + (var,))
                next_frontier.append(cube + (-var,))
        frontier = next_frontier
        depth += 1
    return rows


def accuracy(scorer: FeatureScorer, rows: Sequence[dict]) -> float:
    if not rows:
        return float("nan")
    from cqhecs.omniwave.learned import Candidate

    hits = 0
    for row in rows:
        candidate = Candidate(variable=0, features=tuple(row["features"]))
        predicted = 1 if scorer.score(candidate) >= 0.0 else 0
        hits += int(predicted == row["label"])
    return hits / len(rows)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-fronts", type=int, default=120, help="fronts walked per instance")
    parser.add_argument("--budget", type=float, default=90.0, help="seconds of collection per instance")
    parser.add_argument("--hf", action="store_true", help="also fine-tune the tiny HuggingFace model (needs transformers + torch)")
    parser.add_argument("--hf-epochs", type=int, default=3)
    args = parser.parse_args(argv)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("== collecting ==")
    train_rows: List[dict] = []
    for family, formula in TRAIN_INSTANCES:
        rows = collect(formula, family, args.max_fronts, args.budget)
        positives = sum(r["label"] for r in rows)
        print(f"  {formula.source:<26} {len(rows):>5} rows, {positives:>5} positive")
        train_rows.extend(rows)
    test_rows = collect(TEST_INSTANCE[1], TEST_INSTANCE[0], args.max_fronts, args.budget)
    print(f"  HELD OUT {TEST_INSTANCE[1].source:<17} {len(test_rows):>5} rows, {sum(r['label'] for r in test_rows):>5} positive")

    (out / "training_data.jsonl").write_text(
        "\n".join(json.dumps(row) for row in train_rows) + "\n", encoding="utf-8"
    )
    (out / "test_data.jsonl").write_text("\n".join(json.dumps(row) for row in test_rows) + "\n", encoding="utf-8")

    print("== logistic regression (numpy) ==")
    samples = [(row["features"], int(row["label"])) for row in train_rows]
    coefficients, intercept = fit_logistic(samples)
    scorer = FeatureScorer(
        coefficients,
        intercept,
        metadata={
            "trained_on": [i[1].source for i in TRAIN_INSTANCES],
            "rows": len(train_rows),
            "positives": int(sum(row["label"] for row in train_rows)),
            "held_out": TEST_INSTANCE[1].source,
        },
    )
    weights_path = out / "branch_logistic.json"
    scorer.save(weights_path)
    print(f"  train accuracy {accuracy(scorer, train_rows):.3f}, held-out accuracy {accuracy(scorer, test_rows):.3f}")
    print(f"  weights -> {weights_path}")

    if args.hf:
        print("== fine-tuning google/bert_uncased_L-2_H-128_A-2 (CPU) ==")
        import torch
        from torch.utils.data import DataLoader, Dataset
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        model_name = "google/bert_uncased_L-2_H-128_A-2"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2)

        def render(features):
            return " ".join(f"{name} {int(value)}" for name, value in zip(FEATURE_NAMES, features))

        class Rows(Dataset):
            def __init__(self, rows):
                self.rows = rows

            def __len__(self):
                return len(self.rows)

            def __getitem__(self, index):
                row = self.rows[index]
                encoded = tokenizer(render(row["features"]), truncation=True, max_length=32, padding="max_length", return_tensors="pt")
                return {k: v[0] for k, v in encoded.items()}, torch.tensor(int(row["label"]))

        loader = DataLoader(Rows(train_rows), batch_size=16, shuffle=False)
        optimiser = torch.optim.AdamW(model.parameters(), lr=5e-5)
        model.train()
        for epoch in range(args.hf_epochs):
            total = 0.0
            for batch, labels in loader:
                optimiser.zero_grad()
                loss = model(**batch, labels=labels).loss
                loss.backward()
                optimiser.step()
                total += float(loss)
            print(f"  epoch {epoch + 1}: mean loss {total / max(1, len(loader)):.4f}")
        model.eval()
        hf_dir = out / "bert-tiny-branch"
        model.save_pretrained(hf_dir)
        tokenizer.save_pretrained(hf_dir)
        # Held-out accuracy of the HF backend, scored the same way the engine uses it.
        from cqhecs.omniwave.learned import HfScorer

        hf = HfScorer(hf_dir)
        # choose() returns a variable, not a label, so the label is measured directly.
        from cqhecs.omniwave.learned import Candidate as _Candidate

        correct = 0
        for row in test_rows:
            score = hf.score(_Candidate(0, tuple(row["features"])))
            correct += int((1 if score >= 0.0 else 0) == row["label"])
        print(f"  held-out accuracy {correct / max(1, len(test_rows)):.3f}")
        (out / "hf_summary.json").write_text(
            json.dumps({"model": model_name, "epochs": args.hf_epochs, "held_out_accuracy": correct / max(1, len(test_rows))}, indent=2),
            encoding="utf-8",
        )

    print("== engine: jw vs learned on the held-out instance ==")
    formula = TEST_INSTANCE[1]
    for mode in ("jw", "learned"):
        config = OmniwaveConfig(
            waves=1,
            workers=1,
            timeout_seconds=60,
            branch=mode,
            learned_model=str(weights_path) if mode == "learned" else None,
        )
        engine = OmniwaveEngine(formula, config)
        started = time.perf_counter()
        result = engine.run()
        elapsed = time.perf_counter() - started
        snapshot = engine.snapshot()
        print(f"  {mode:<8} {result.status:<8} {elapsed:>7.2f}s  fronts={snapshot.get('fronts_created')} "
              f"learner_choices={snapshot.get('learned_choices')}")
        if mode == "jw":
            baseline = elapsed
        else:
            learned_time = elapsed
    if baseline and learned_time:
        print(f"  speed-up on the held-out instance: {baseline / learned_time:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
