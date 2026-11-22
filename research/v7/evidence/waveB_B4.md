# Wave B / B4 evidence (noise governance, W10)

Commands (offline, targeted, repo worktree):
- `python -m pytest tests/test_noise_governance.py -q` -> 15 passed (new; failed first on a vacuous-tamper
  test and on `dataset_sha256` being a whole-dataset digest; test fixed, not weakened).
- `python -m pytest tests/test_noise_fit.py tests/test_hardware_bridge.py tests/test_v3_calibration_bridge.py
  tests/test_v3_noisy_expectation.py tests/test_noisy_density_matrix.py -q` -> 65 passed, 4 skipped.

Files: cqhecs/calibration_v3.py, tests/test_noise_governance.py, research/v7/NOISE_QEC_RESEARCH.md,
docs/PROVENANCE.md (noise section).

NOT RUN: full pytest suite; any QPU/provider call; CLI/Studio wiring of v3; transpilation; VALIDATION split
(none exists in r-io-7); QEC/RL experiments (note only).
