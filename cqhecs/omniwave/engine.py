"""
OMNIWAVE: an experimental multi-front search engine with checked UNSAT proofs.

EXPERIMENTAL. It does not replace :func:`cqhecs.sat.solve` and carries no
performance claim. ``research/v5/OMNIWAVE.md`` describes the design, its sources
and its limits.

How it works
------------
A *front* is a cube: a set of decision literals. Every front belongs to a *wave*.
Each wave branches in its own direction (the BFS order of the variable graph
from its own start variable), so different waves sweep different regions of the
same formula, like the scan lines of a CRT. Fronts sit in one shared priority queue,
and any worker takes the next one, which amounts to work stealing.

Processing a front:

1. Unit propagation under the cube, over the original clauses plus the shared
   nogoods.
2. Conflict: the cube is refuted. The clause ``¬cube`` goes to the proof log
   (it is RUP at that point), and it is shared as a nogood if it is short
   (``share_max_len``, a size filter in the spirit of MallobSat's clause sharing).
3. All clauses satisfied: the completed assignment is verified clause by clause
   against the original CNF, and the result is ``SAT``.
4. Otherwise split on one unassigned variable: **both** children ``cube ∧ x`` and
   ``cube ∧ ¬x`` are created. Coverage is exhaustive by construction.

When both children of a node are refuted, ``¬node`` is logged. It is RUP
because both children's lemmas are already present. The root refuted means the
empty clause, which completes a DRAT refutation. That refutation is then
checked by :mod:`cqhecs.drat`, which shares no code with this module. Status rules:

* ``SAT``: only with a model verified against the original CNF.
* ``UNSAT``: only if the search covered the whole space **and** the DRAT check
  accepted the proof.
* ``UNKNOWN``: a timeout, node budget, front budget, cancellation, or a proof the
  checker rejected or could not decide.

No state is ever discarded because its hash matches another state. The
duplicate check uses the exact canonical cube, a sorted literal tuple compared
by equality.

Python threads run under the GIL here. Workers organise the work but do not
speed it up; the docs say so.
"""

from __future__ import annotations

import heapq
import itertools
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from cqhecs.drat import check_drat
from cqhecs.omniwave import bcp as batch_bcp
from cqhecs.omniwave.field import ProblemField
from cqhecs.sat import CNF, SAT, SATResult, UNKNOWN, UNSAT

Cube = Tuple[int, ...]


@dataclass
class _Node:
    cube: Cube
    wave: int
    parent: Optional["_Node"]
    depth: int
    pending: int = 2  # children not yet refuted
    refuted: bool = False


@dataclass
class WaveStats:
    """Live counters; :meth:`OmniwaveEngine.snapshot` copies them for the Studio."""

    fronts_created: int = 0
    fronts_processed: int = 0
    conflicts: int = 0
    propagations: int = 0
    splits: int = 0
    shared_nogoods: int = 0
    duplicates_skipped: int = 0
    proof_lemmas: int = 0
    max_queue: int = 0
    covered: float = 0.0  # fraction of {0,1}^n refuted so far (Σ 2^-depth)
    per_wave: Dict[int, int] = field(default_factory=dict)
    per_worker: Dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class OmniwaveConfig:
    waves: int = 4
    workers: int = 2
    seed: int = 20261031
    timeout_seconds: float = 10.0
    max_fronts: int = 2_000_000
    max_queue: int = 200_000
    share_max_len: int = 8
    check_proof: bool = True
    proof_timeout_seconds: float = 60.0
    #: "scalar" (one front at a time), "batch" (CPU batched BCP) or "vulkan" (GPU pass,
    #: every pass verified bit-for-bit against the CPU reference when verify_gpu is set).
    bcp: str = "scalar"
    batch_size: int = 64
    verify_gpu: bool = True


class OmniwaveEngine:
    def __init__(self, formula: CNF, config: OmniwaveConfig = OmniwaveConfig()):
        if config.waves < 1 or config.workers < 1:
            raise ValueError("waves and workers must be >= 1")
        if config.bcp not in ("scalar", "batch", "vulkan"):
            raise ValueError("bcp must be scalar, batch or vulkan")
        if config.bcp == "vulkan":
            from cqhecs.omniwave import gpu

            if not gpu.available():
                raise gpu.GpuUnavailable(str(gpu.status().get("reason")))
        self.formula = formula
        self.field = ProblemField(formula)
        self.config = config
        self.stats = WaveStats()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._queue: List[Tuple[int, int, int, _Node]] = []
        self._tie = itertools.count()
        self._seen: set = set()  # exact canonical cubes (tuples compared by equality)
        self._nogoods: List[Tuple[int, ...]] = []
        self._proof: List[str] = []
        self._in_flight = 0
        self._model: Optional[Dict[int, bool]] = None
        self._root_refuted = False
        self._stop = threading.Event()
        self._resume = threading.Event()
        self._deadline = float("inf")
        self._resume.set()
        self._abort_reason: Optional[str] = None
        n = formula.num_vars
        starts = self._wave_starts()
        self._orders = [self.field.bfs_order(s) if n else [] for s in starts]
        self.wave_starts = starts

    # ------------------------------------------------------------------ setup

    def _wave_starts(self) -> List[int]:
        """Spread the start variables: the first is the busiest; each next one is far from the previous ones."""
        n = self.formula.num_vars
        if n == 0:
            return [0] * self.config.waves
        adj = self.field.neighbours()
        busiest = max(range(1, n + 1), key=lambda v: (len(adj[v]), -v))
        starts = [busiest]
        for _ in range(1, self.config.waves):
            dist = self._distances(starts, adj)
            far = max(range(1, n + 1), key=lambda v: (dist.get(v, n + 1), -v))
            starts.append(far)
        return starts

    @staticmethod
    def _distances(sources: Sequence[int], adj: Dict[int, set]) -> Dict[int, int]:
        dist = {s: 0 for s in sources}
        frontier = list(sources)
        while frontier:
            nxt = []
            for v in frontier:
                for w in adj[v]:
                    if w not in dist:
                        dist[w] = dist[v] + 1
                        nxt.append(w)
            frontier = nxt
        return dist

    # ------------------------------------------------------------------ control

    def cancel(self, reason: str = "cancelled") -> None:
        self._abort_reason = self._abort_reason or reason
        self._stop.set()
        self._resume.set()
        with self._cv:
            self._cv.notify_all()

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    # ------------------------------------------------------------------ propagation

    def _propagate(self, cube: Cube) -> Tuple[str, Dict[int, bool]]:
        """Unit propagation. Returns ("conflict"|"sat"|"open", assignment)."""
        value: Dict[int, bool] = {}
        for lit in cube:
            if value.get(abs(lit), lit > 0) != (lit > 0):
                return "conflict", value
            value[abs(lit)] = lit > 0
        clauses = list(self.formula.clauses)
        with self._lock:
            clauses.extend(self._nogoods)
        propagations = 0
        changed = True
        while changed:
            changed = False
            all_sat = True
            for clause in clauses:
                open_lit, open_count, sat = 0, 0, False
                for lit in clause:
                    v = value.get(abs(lit))
                    if v is None:
                        open_count += 1
                        open_lit = lit
                    elif v == (lit > 0):
                        sat = True
                        break
                if sat:
                    continue
                all_sat = False
                if open_count == 0:
                    self._count("propagations", propagations)
                    return "conflict", value
                if open_count == 1:
                    value[abs(open_lit)] = open_lit > 0
                    propagations += 1
                    changed = True
            if all_sat:
                self._count("propagations", propagations)
                return "sat", value
        self._count("propagations", propagations)
        return "open", value

    def _count(self, name: str, amount: int = 1) -> None:
        with self._lock:
            setattr(self.stats, name, getattr(self.stats, name) + amount)

    # ------------------------------------------------------------------ queue

    def _push(self, node: _Node) -> None:
        key = tuple(sorted(node.cube))
        with self._cv:
            if key in self._seen:  # exact equality, never hash-only
                self.stats.duplicates_skipped += 1
                return
            self._seen.add(key)
            # Deeper fronts first keeps the queue small; waves rotate at equal depth.
            heapq.heappush(self._queue, (-node.depth, node.wave, next(self._tie), node))
            self.stats.fronts_created += 1
            self.stats.max_queue = max(self.stats.max_queue, len(self._queue))
            if len(self._queue) > self.config.max_queue:
                self._abort_reason = self._abort_reason or f"front queue exceeded {self.config.max_queue}"
                self._stop.set()
            self._cv.notify()

    def _refute(self, node: _Node) -> None:
        """Log ¬cube for node and propagate refutation to its ancestors (lock held by caller)."""
        while node is not None:
            node.refuted = True
            self._proof.append(" ".join(str(-l) for l in node.cube) + (" 0" if node.cube else "0"))
            self.stats.proof_lemmas += 1
            if node.cube and len(node.cube) <= self.config.share_max_len:
                self._nogoods.append(tuple(-l for l in node.cube))
                self.stats.shared_nogoods += 1
            parent = node.parent
            if parent is None:
                self._root_refuted = True
                self.stats.covered = 1.0
                self._stop.set()
                self._cv.notify_all()
                return
            self.stats.covered += 2.0 ** -node.depth
            parent.pending -= 1
            if parent.pending > 0:
                return
            # Both children refuted: the parent's own contribution replaces theirs.
            self.stats.covered -= 2 * 2.0 ** -node.depth
            node = parent

    # ------------------------------------------------------------------ worker

    def _branch_var(self, node: _Node, value: Dict[int, bool]) -> int:
        for v in self._orders[node.wave]:
            if v not in value:
                return v
        return 0

    def _worker(self, wid: int, deadline: float) -> None:
        while not self._stop.is_set():
            self._resume.wait()
            with self._cv:
                while not self._queue and self._in_flight and not self._stop.is_set():
                    self._cv.wait(0.05)
                if self._stop.is_set() or not self._queue:
                    if not self._queue and not self._in_flight:
                        self._cv.notify_all()
                        return
                    continue
                take = 1 if self.config.bcp == "scalar" else self.config.batch_size
                nodes = [heapq.heappop(self._queue)[3] for _ in range(min(take, len(self._queue)))]
                self._in_flight += len(nodes)
            try:
                if self.config.bcp == "scalar":
                    self._process(nodes[0], wid, deadline)
                else:
                    self._process_batch(nodes, wid, deadline)
            finally:
                with self._cv:
                    self._in_flight -= len(nodes)
                    self._cv.notify_all()

    def _admit(self, node: _Node, wid: int, deadline: float) -> bool:
        # Paused time does not count against the budget (run() moves self._deadline).
        if time.perf_counter() > max(deadline, self._deadline):
            self.cancel(f"timeout after {self.config.timeout_seconds:g} s")
            return False
        with self._lock:
            self.stats.fronts_processed += 1
            self.stats.per_wave[node.wave] = self.stats.per_wave.get(node.wave, 0) + 1
            self.stats.per_worker[wid] = self.stats.per_worker.get(wid, 0) + 1
            if self.stats.fronts_processed > self.config.max_fronts:
                self._abort_reason = self._abort_reason or f"front budget {self.config.max_fronts} exhausted"
                self._stop.set()
                return False
        return True

    def _process(self, node: _Node, wid: int, deadline: float) -> None:
        if not self._admit(node, wid, deadline):
            return
        outcome, value = self._propagate(node.cube)
        self._handle(node, outcome, value)

    def _process_batch(self, nodes: List[_Node], wid: int, deadline: float) -> None:
        nodes = [n for n in nodes if self._admit(n, wid, deadline)]
        if not nodes or self._stop.is_set():
            return
        with self._lock:
            clauses = list(self.formula.clauses) + list(self._nogoods)
        n = self.formula.num_vars
        fronts = batch_bcp.Fronts.from_cubes(n, [node.cube for node in nodes])
        if self.config.bcp == "vulkan":
            from cqhecs.omniwave import gpu

            def evaluate(cl, fr):
                return gpu.evaluate_batch_vulkan(cl, fr, verify=self.config.verify_gpu)
        else:
            evaluate = batch_bcp.evaluate_batch
        # A cube with x and ¬x is contradictory before any clause is read.
        outcomes = []
        for node in nodes:
            lits = set(node.cube)
            outcomes.append("conflict" if any(-l in lits for l in lits) else None)
        pending = [i for i, o in enumerate(outcomes) if o is None]
        if pending:
            sub = batch_bcp.Fronts(n, [fronts.assigned[i] for i in pending], [fronts.value[i] for i in pending])
            for i, o in zip(pending, batch_bcp.propagate_batch(clauses, sub, evaluate=evaluate)):
                outcomes[i] = o
                fronts.assigned[i], fronts.value[i] = sub.assigned[pending.index(i)], sub.value[pending.index(i)]
        for i, node in enumerate(nodes):
            value = {v: bool(fronts.get(i, v)) for v in range(1, n + 1) if fronts.get(i, v) is not None}
            self._handle(node, outcomes[i], value)

    def _handle(self, node: _Node, outcome: str, value: Dict[int, bool]) -> None:
        if self._stop.is_set():
            return
        if outcome == "conflict":
            with self._cv:
                self.stats.conflicts += 1
                self._refute(node)
            return
        if outcome == "sat":
            model = {v: value.get(v, False) for v in range(1, self.formula.num_vars + 1)}
            if self.formula.is_satisfied(model):  # independent check against the original CNF
                with self._cv:
                    self._model = model
                    self._stop.set()
                    self._cv.notify_all()
            else:  # pragma: no cover - would be an engine defect
                self.cancel("internal model failed verification")
            return
        var = self._branch_var(node, value)
        if var == 0:  # pragma: no cover - "open" implies an unassigned variable
            self.cancel("no branching variable on an open front")
            return
        self._count("splits")
        # The first splits fan the root out over the waves; deeper fronts keep their wave.
        waves = self.config.waves
        for k, lit in enumerate((var, -var)):
            wave = (node.wave * 2 + k) % waves if node.depth < max(1, waves.bit_length()) else node.wave
            self._push(_Node(node.cube + (lit,), wave, node, node.depth + 1))

    # ------------------------------------------------------------------ run

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            s = self.stats
            return {
                "fronts_created": s.fronts_created,
                "fronts_processed": s.fronts_processed,
                "queue": len(self._queue),
                "in_flight": self._in_flight,
                "conflicts": s.conflicts,
                "propagations": s.propagations,
                "splits": s.splits,
                "shared_nogoods": s.shared_nogoods,
                "duplicates_skipped": s.duplicates_skipped,
                "proof_lemmas": s.proof_lemmas,
                "max_queue": s.max_queue,
                "covered": min(1.0, s.covered),
                "per_wave": dict(s.per_wave),
                "per_worker": dict(s.per_worker),
                "wave_starts": list(self.wave_starts),
                "paused": not self._resume.is_set(),
            }

    def run(self, on_tick: Optional[Callable[[Dict[str, object]], None]] = None) -> SATResult:
        started = time.perf_counter()
        deadline = started + self.config.timeout_seconds
        self._deadline = deadline
        if any(len(c) == 0 for c in self.formula.clauses):
            self._proof = ["0"]
            self._root_refuted = True
        else:
            self._push(_Node((), 0, None, 0))
            threads = [
                threading.Thread(target=self._worker, args=(w, deadline), daemon=True)
                for w in range(self.config.workers)
            ]
            for t in threads:
                t.start()
            while any(t.is_alive() for t in threads):
                tick_start = time.perf_counter()
                for t in threads:
                    t.join(0.05)
                if not self._resume.is_set() and not self._stop.is_set():
                    self._deadline += time.perf_counter() - tick_start
                if on_tick:
                    on_tick(self.snapshot())
                if time.perf_counter() > self._deadline and not self._stop.is_set():
                    self.cancel(f"timeout after {self.config.timeout_seconds:g} s")
        return self._result(started)

    def proof(self) -> List[str]:
        with self._lock:
            return list(self._proof)

    def _result(self, started: float) -> SATResult:
        elapsed = lambda: (time.perf_counter() - started) * 1000.0  # noqa: E731
        s = self.stats
        common = dict(
            decisions=s.splits, propagations=s.propagations, conflicts=s.conflicts,
            nodes=s.fronts_processed, max_depth=0, timeout_seconds=float(self.config.timeout_seconds),
            formula_sha256=self.formula.sha256,
            formula_original_sha256=self.formula.original_sha256,
            engine="omniwave",
        )
        if self._model is not None:
            return SATResult(status=SAT, assignment=self._model, elapsed_ms=elapsed(), model_verified=True,
                             note=f"OMNIWAVE ({self.config.waves} waves); model verified clause by clause", **common)
        if self._root_refuted:
            if not self.config.check_proof:
                return SATResult(status=UNKNOWN, assignment=None, elapsed_ms=elapsed(), model_verified=False,
                                 note="search covered the whole space, but proof checking is disabled; UNKNOWN", **common)
            check = check_drat(self.formula.clauses, self._proof, timeout_seconds=self.config.proof_timeout_seconds)
            if check.valid is True:
                return SATResult(status=UNSAT, assignment=None, elapsed_ms=elapsed(), model_verified=False,
                                 certified=True, proof_system="DRAT",
                                 note=f"OMNIWAVE complete coverage; DRAT proof ({check.lemmas} lemmas) checked by cqhecs.drat",
                                 **common)
            return SATResult(status=UNKNOWN, assignment=None, elapsed_ms=elapsed(), model_verified=False,
                             note=f"search complete but the proof was not accepted ({check.reason}); UNKNOWN", **common)
        reason = self._abort_reason or "stopped before a decision"
        return SATResult(status=UNKNOWN, assignment=None, elapsed_ms=elapsed(), model_verified=False,
                         note=f"{reason}; coverage {min(1.0, s.covered):.3%}", **common)


def solve_omniwave(formula: CNF, **kwargs) -> SATResult:
    """Convenience wrapper: ``solve_omniwave(cnf, waves=4, workers=2, timeout_seconds=10)``."""
    return OmniwaveEngine(formula, OmniwaveConfig(**kwargs)).run()
