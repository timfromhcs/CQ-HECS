"""Makes the research prototypes importable for their own tests only."""
import os
import sys

_PROTO = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "research", "v7", "prototypes")
)
if _PROTO not in sys.path:
    sys.path.insert(0, _PROTO)
