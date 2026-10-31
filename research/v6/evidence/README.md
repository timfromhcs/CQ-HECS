# v6 evidence

`sat_propagation_benchmark.json` was produced by:

```powershell
python scripts/sat_propagation_benchmark.py --repeat 5 `
  --out research/v6/evidence/sat_propagation_benchmark.json
```

- Source: this branch, after the watched engine and predicate fixes.
- Machine: Windows 11 10.0.26200, AMD Ryzen 7 7735HS (8C/16T), Python 3.14.6.
- Families and seeds are in `scripts/sat_propagation_benchmark.py`; each row
  records the formula SHA-256 and timeout.
- The script fails if the engines disagree, a SAT model fails the original CNF,
  or an UNSAT result lacks a replayed certificate.
- The JSON records 5 timed repetitions per engine. `certify=False` is used for
  timing; the certificate pass is run separately and is not part of the timing.
- This is a finite measurement, not an asymptotic or universal speedup claim.

To reproduce on another machine, use the same script and compare the `failures`
array and per-family verdicts first; timings will differ.
