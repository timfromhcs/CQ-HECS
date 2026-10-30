"""
Single source of truth for gate capabilities in the Four-Path architecture.

Before this module existed the analyzer, the router and every backend carried
their own hand-maintained gate lists.  They disagreed: the router advertised
``reset`` for Path A although the tableau cannot apply it, and it classified
``cp``/``crz``/``u`` by their *first* parameter only.  A circuit could therefore
be routed to a path that then refused it (or, worse, silently mis-simulated it).

Every gate name, arity, parameter count and per-path support now comes from the
table below.  Backends derive their ``SUPPORTED_*`` sets from it, and the router
uses the same data for capability-first routing.

Fields
------
``arity``        Number of qubit operands (``barrier`` is variable, see flag).
``min_params``   Minimum number of angle parameters.
``max_params``   Maximum number of angle parameters.
``paths``        Paths that can execute the operation faithfully.
``clifford``     True when the operation is exactly representable by the
                 stabilizer tableau without decomposition.  Parameterised
                 gates marked Clifford are only Clifford at multiples of pi/2;
                 :func:`clifford_rotation_kind` decides per angle.
``measurement``  Terminal measurement instruction.
``reset``        Non-unitary reset; currently executable by no path.
``barrier``      Pseudo-instruction with variable arity and no state effect.
``lowered``      Composite gate with no kernel of its own. ``parse_circuit``
                 rewrites it exactly into native gates (see
                 :mod:`cqhecs.gate_lowering`), so ``paths`` stays empty.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterable, Optional, Tuple


@dataclass(frozen=True)
class GateSpec:
    """Static capability record for one operation name."""

    name: str
    arity: int
    min_params: int = 0
    max_params: int = 0
    paths: FrozenSet[str] = frozenset()
    clifford: bool = False
    measurement: bool = False
    reset: bool = False
    barrier: bool = False
    lowered: bool = False

    @property
    def parameterised(self) -> bool:
        return self.max_params > 0


_ALL_PATHS = frozenset({"A", "B", "C", "D"})


def _spec(name: str, arity: int, *paths: str, params: int = 0,
          clifford: bool = False) -> GateSpec:
    return GateSpec(
        name=name,
        arity=arity,
        min_params=params,
        max_params=params,
        paths=frozenset(paths),
        clifford=clifford,
    )


#: Canonical operation table.  Names are lowercase; aliases get their own entry
#: so that error messages always name the operation the user actually wrote.
MANIFEST: Dict[str, GateSpec] = {}


def _add(spec: GateSpec) -> None:
    MANIFEST[spec.name] = spec


# -- single-qubit Clifford gates (all four paths) ---------------------------
for _name in ("h", "x", "y", "z", "s", "sdg"):
    _add(_spec(_name, 1, *_ALL_PATHS, clifford=True))

# -- single-qubit non-Clifford phase gates --------------------------------
for _name in ("t", "tdg"):
    _add(_spec(_name, 1, "B", "C", "D"))

# -- identity / barrier ----------------------------------------------------
_add(_spec("id", 1, *_ALL_PATHS, clifford=True))
_add(GateSpec(name="barrier", arity=0, paths=_ALL_PATHS, clifford=True,
              barrier=True))

# -- two-qubit Clifford gates ---------------------------------------------
for _name in ("cx", "cnot", "cz", "swap"):
    _add(_spec(_name, 2, *_ALL_PATHS, clifford=True))

# -- single-qubit angle gates ---------------------------------------------
# rz/p/u1 are Clifford only at multiples of pi/2 (Path A checks the angle);
# rx/ry are never Clifford, so Path A is absent.
for _name in ("rz", "p", "u1"):
    _add(_spec(_name, 1, *_ALL_PATHS, params=1, clifford=True))
for _name in ("rx", "ry"):
    _add(_spec(_name, 1, "B", "C", "D", params=1))

# -- two-qubit angle gates ------------------------------------------------
# Only Path C implements controlled rotations faithfully.
for _name in ("cp", "cu1", "crx", "cry", "crz"):
    _add(_spec(_name, 2, "C", params=1))

# -- composite operations ---------------------------------------------------
# No path has a dedicated kernel for these. They are exactly rewritten into
# the native gates above by ``cqhecs.gate_lowering`` during parsing, so they
# carry no ``paths`` of their own and are never silently treated as identity.
for _name, _arity, _params in (
    ("u", 1, 3), ("u3", 1, 3), ("u2", 1, 2),
    ("sx", 1, 0), ("sxdg", 1, 0),
    ("cy", 2, 0), ("ch", 2, 0), ("cs", 2, 0), ("csdg", 2, 0),
    ("rzz", 2, 1), ("rxx", 2, 1), ("ryy", 2, 1),
    ("ccx", 3, 0), ("toffoli", 3, 0), ("ccz", 3, 0),
    ("cswap", 3, 0), ("fredkin", 3, 0),
    ("r", 1, 2), ("iswap", 2, 0), ("dcx", 2, 0), ("ecr", 2, 0),
    ("cu3", 2, 3), ("cu", 2, 4), ("csx", 2, 0),
    ("c3x", 4, 0), ("c4x", 5, 0),
    # Google Sycamore gate set (v3 W5); see cqhecs.gate_lowering.
    ("fsim", 2, 2), ("syc", 2, 0), ("phased_x", 1, 2),
    ("sqrt_x", 1, 0), ("sqrt_y", 1, 0), ("sqrt_w", 1, 0),
):
    _add(GateSpec(name=_name, arity=_arity, min_params=_params,
                  max_params=_params, lowered=True))

# -- measurement / reset --------------------------------------------------
_add(GateSpec(name="measure", arity=1, paths=frozenset({"A", "C"}),
              measurement=True))
_add(GateSpec(name="reset", arity=1, reset=True))


#: Operations that are not unitary state evolution and therefore never part of
#: a capability-based "can this path execute the circuit" decision.
NON_UNITARY: FrozenSet[str] = frozenset({"measure", "reset"})


def get_gate(name: str) -> Optional[GateSpec]:
    """Returns the manifest entry for `name`, or None when it is unknown."""
    return MANIFEST.get(name.lower())


def canonical_name(name: str) -> str:
    """Lowercases a gate name without changing its spelling."""
    return name.lower()


def path_gate_names(path: str) -> FrozenSet[str]:
    """Every operation name `path` can execute (including measurement)."""
    p = path.upper()
    return frozenset(name for name, spec in MANIFEST.items() if p in spec.paths)


def clifford_rotation_kind(theta: float) -> Optional[str]:
    """
    Maps an RZ/P/U1 angle to one of ``id``, ``s``, ``z``, ``sdg``.

    Returns None when the angle is not an exact multiple of pi/2, i.e. when the
    operation is not a Clifford gate.  Non-finite input is never Clifford.
    """
    if not math.isfinite(theta):
        return None
    norm = theta % (2.0 * math.pi)
    quarters = norm / (math.pi / 2.0)
    nearest = round(quarters)
    if abs(quarters - nearest) > 1e-7:
        return None
    return {0: "id", 1: "s", 2: "z", 3: "sdg"}[nearest % 4]


def signature_errors(
    name: str,
    qubits: Iterable[int],
    params: Iterable[float],
) -> Tuple[str, ...]:
    """
    Validates arity and parameter count against the manifest.

    Returns a tuple of human-readable errors; an empty tuple means the call
    matches the documented signature.  Unknown gates produce one error.
    """
    spec = get_gate(name)
    if spec is None:
        return (f"unknown gate {name!r}",)
    errors = []
    q = list(qubits)
    p = list(params)
    if spec.barrier:
        if not q:
            errors.append("barrier requires at least one qubit operand")
        return tuple(errors)
    if len(q) != spec.arity:
        errors.append(
            f"gate {name!r} expects {spec.arity} qubit(s), got {len(q)}"
        )
    if not (spec.min_params <= len(p) <= spec.max_params):
        if spec.min_params == spec.max_params:
            expected = str(spec.min_params)
        else:
            expected = f"{spec.min_params}..{spec.max_params}"
        errors.append(
            f"gate {name!r} expects {expected} parameter(s), got {len(p)}"
        )
    return tuple(errors)
