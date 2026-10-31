"""
OMNIWAVE Research Lab: one background OMNIWAVE run behind the Studio HTTP API.

Every number the Lab shows comes from :meth:`OmniwaveEngine.snapshot` of the run
that is actually executing; nothing is simulated for display. The timeline keeps
one sample per engine tick (about 20 per second, capped), so the charts show the
real progress of the search.

Only one run is active at a time. Starting a new run while one is active is an
error; cancel it first. A finished run keeps its result and timeline until the
next start.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Mapping, Optional

from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine
from cqhecs.sat import CNF

TIMELINE_LIMIT = 600
NON_CLAIM = (
    "OMNIWAVE is an experimental exact search. SAT is reported only with a verified model and "
    "UNSAT only with a DRAT proof checked by cqhecs.drat; everything else is UNKNOWN. Worker "
    "threads share one Python interpreter (GIL), so more workers are not a speedup claim, and "
    "no complexity claim (P vs NP, ETH) follows from any run."
)


class LabError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request"):
        super().__init__(message)
        self.status = status
        self.code = code


class OmniwaveLab:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._engine: Optional[OmniwaveEngine] = None
        self._thread: Optional[threading.Thread] = None
        self._run_id = 0
        self._state = "idle"
        self._config: Dict[str, Any] = {}
        self._formula: Dict[str, Any] = {}
        self._timeline: List[Dict[str, Any]] = []
        self._started = 0.0
        self._result: Optional[Dict[str, Any]] = None
        self._error: Optional[str] = None

    # ------------------------------------------------------------ control

    def start(self, formula: CNF, request: Mapping[str, Any],
              summary: Callable[[CNF], Dict[str, Any]]) -> Dict[str, Any]:
        config = OmniwaveConfig(
            waves=_int(request.get("waves"), "waves", 1, 16, 4),
            workers=_int(request.get("workers"), "workers", 1, 8, 2),
            seed=_int(request.get("seed"), "seed", 0, 2**31 - 1, 20261031),
            timeout_seconds=_float(request.get("timeout"), "timeout", 0.1, 120.0, 10.0),
            max_fronts=_int(request.get("max_fronts"), "max_fronts", 1, 5_000_000, 200_000),
            bcp=_choice(request.get("bcp"), "bcp", ("scalar", "batch", "vulkan"), "scalar"),
            batch_size=_int(request.get("batch_size"), "batch_size", 1, 4096, 64),
        )
        with self._lock:
            if self._state in ("running", "paused"):
                raise LabError("a run is already active; cancel it first", status=409, code="run_active")
            try:
                engine = OmniwaveEngine(formula, config)
            except ValueError as exc:
                raise LabError(str(exc), code="invalid_config") from exc
            except RuntimeError as exc:  # GpuUnavailable for bcp="vulkan"
                raise LabError(str(exc), status=503, code="gpu_unavailable") from exc
            self._run_id += 1
            self._engine = engine
            self._state = "running"
            self._config = {
                "waves": config.waves, "workers": config.workers, "seed": config.seed,
                "timeout_seconds": config.timeout_seconds, "max_fronts": config.max_fronts,
                "bcp": config.bcp, "batch_size": config.batch_size,
            }
            self._formula = summary(formula)
            self._timeline = []
            self._result = None
            self._error = None
            self._started = time.perf_counter()
            run_id = self._run_id
            self._thread = threading.Thread(target=self._run, args=(engine, run_id), daemon=True)
            self._thread.start()
        return self.status()

    def _run(self, engine: OmniwaveEngine, run_id: int) -> None:
        def tick(snap: Dict[str, Any]) -> None:
            with self._lock:
                if run_id != self._run_id:
                    return
                sample = {"t_ms": round((time.perf_counter() - self._started) * 1000.0, 1)}
                sample.update({k: snap[k] for k in ("fronts_processed", "queue", "conflicts",
                                                    "shared_nogoods", "covered", "propagations")})
                self._timeline.append(sample)
                if len(self._timeline) > TIMELINE_LIMIT:
                    # Keep the first sample and thin the rest evenly.
                    self._timeline = self._timeline[:1] + self._timeline[2::2]

        try:
            result = engine.run(on_tick=tick)
            payload: Optional[Dict[str, Any]] = result.to_dict()
            error = None
        except Exception as exc:  # noqa: BLE001 - reported to the Lab, never swallowed silently
            payload, error = None, f"{type(exc).__name__}: {exc}"
        with self._lock:
            if run_id != self._run_id:
                return
            self._result = payload
            self._error = error
            self._state = "error" if error else "finished"

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if self._state != "running" or self._engine is None:
                raise LabError("no running run to pause", status=409, code="not_running")
            self._engine.pause()
            self._state = "paused"
        return self.status()

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if self._state != "paused" or self._engine is None:
                raise LabError("no paused run to resume", status=409, code="not_paused")
            self._engine.resume()
            self._state = "running"
        return self.status()

    def cancel(self) -> Dict[str, Any]:
        with self._lock:
            engine, thread = self._engine, self._thread
            if self._state not in ("running", "paused") or engine is None:
                raise LabError("no active run to cancel", status=409, code="not_active")
        engine.cancel("cancelled from the Lab")
        engine.resume()  # a paused worker must wake up to see the stop flag
        if thread is not None:
            thread.join(timeout=10.0)
        return self.status()

    def wait(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Block until the active run ends (tests and scripts)."""
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        return self.status()

    # ------------------------------------------------------------- status

    def status(self) -> Dict[str, Any]:
        from cqhecs.omniwave import gpu

        with self._lock:
            engine = self._engine
            out: Dict[str, Any] = {
                "schema_version": "1.0",
                "run_id": self._run_id,
                "state": self._state,
                "config": dict(self._config),
                "formula": dict(self._formula),
                "elapsed_ms": round((time.perf_counter() - self._started) * 1000.0, 1) if engine else 0.0,
                "timeline": list(self._timeline),
                "result": self._result,
                "error": self._error,
            }
        out["live"] = engine.snapshot() if engine is not None else None
        if engine is not None:
            out["proof_lemmas"] = len(engine.proof())
        out["gpu"] = gpu.status()
        out["non_claim"] = NON_CLAIM
        return out


def _int(value: Any, name: str, lo: int, hi: int, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise LabError(f"{name} must be an integer", code="invalid_parameter") from exc
    if not lo <= number <= hi:
        raise LabError(f"{name} must be between {lo} and {hi}", code="invalid_parameter")
    return number


def _float(value: Any, name: str, lo: float, hi: float, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise LabError(f"{name} must be a number", code="invalid_parameter") from exc
    if not lo <= number <= hi:
        raise LabError(f"{name} must be between {lo:g} and {hi:g}", code="invalid_parameter")
    return number


def _choice(value: Any, name: str, options: tuple, default: str) -> str:
    if value in (None, ""):
        return default
    if value not in options:
        raise LabError(f"{name} must be one of {', '.join(options)}", code="invalid_parameter")
    return str(value)
