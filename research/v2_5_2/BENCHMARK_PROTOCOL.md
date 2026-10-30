# CQ-HECS v2.5.2 Benchmark Protocol

No benchmark was run and **no performance claim** is made for v2.5.2. The
changes are correctness fixes:

- Path B: one coefficient changed; branch count and work are unchanged.
- Native SWAP: three fewer CX applications on the tableau per SWAP.
- Profile validation: O(size of profile), once per profile.
- Noise model: same channel types and Kraus counts as before.

Gate D (performance evidence) is `NOT RUN` for this release.
`docs/BENCHMARKS.md` remains historical and is not updated.
