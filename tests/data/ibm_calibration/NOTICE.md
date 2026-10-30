# IBM calibration snapshots (test data)

These six JSON files are copied unchanged from the `qiskit-ibm-runtime`
0.51.0 wheel on PyPI
(`qiskit_ibm_runtime/fake_provider/backends/<name>/{props,conf}_<name>.json`).

- Copyright 2021 IBM and its contributors.
- Licensed under the Apache License, Version 2.0
  (https://www.apache.org/licenses/LICENSE-2.0), the same licence as CQ-HECS.
- They are real calibration exports of IBM Quantum devices at the
  `last_update_date` stated in each `props_*.json` (ibmq_manila 2024-05-27,
  ibm_oslo 2022-07-17, ibm_algiers 2024-02-28). They describe those devices
  at that time only.

`SHA256SUMS` pins the bytes; `tests/test_v3_calibration_bridge.py` checks
them before use.
