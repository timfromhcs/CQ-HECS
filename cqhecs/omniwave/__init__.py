"""
OMNIWAVE — experimental multi-front constraint engine (research status).

Modules:

* :mod:`~cqhecs.omniwave.field`: one canonical CNF with exact views (CSR incidence,
  detected XOR constraints, quadratic GF(2) encoding, tensor contraction count,
  parity hashing);
* :mod:`~cqhecs.omniwave.gf2`: GF(2) elimination, rank, ``M = UV`` rank factorization;
* :mod:`~cqhecs.omniwave.quadratic`: count-preserving CNF → degree-≤2 GF(2) system;
* :mod:`~cqhecs.omniwave.engine`: multi-front search with DRAT-checked UNSAT;
* :mod:`~cqhecs.omniwave.bcp`: batched BCP, the CPU reference for the Vulkan kernel;
* :mod:`~cqhecs.omniwave.boundary`: exact separator merging and signature compression.

Nothing here changes :func:`cqhecs.sat.solve`. See ``research/v5/OMNIWAVE.md``
for the design, sources, hypotheses and limits. No performance or complexity
claim is made.
"""

from cqhecs.omniwave.engine import OmniwaveConfig, OmniwaveEngine, solve_omniwave

EXPERIMENTAL = True

__all__ = ["EXPERIMENTAL", "OmniwaveConfig", "OmniwaveEngine", "solve_omniwave"]
