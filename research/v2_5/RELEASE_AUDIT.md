# CQ-HECS v2.5.0 Release Audit

## 1. Published Baseline: v2.4.0

- Version/tag: `v2.4.0`.
- Merged SHA: `74071b5519fe14dec54b7f893e3f2672198f66bb`.
- Published: 2026-10-29T22:48:17Z.
- Release URL: https://github.com/timfromhcs/CQ-HECS/releases/tag/v2.4.0
- Required CI run: https://github.com/timfromhcs/CQ-HECS/actions/runs/40967886229.
- Verified release assets:
  - `cqhecs-2.4.0-py3-none-any.whl` (sha256 `9d4f44831e19e8557e83cf0aa1f2163c47a5fceb2cf2df72d8387a3ce06cd79f`)
  - `cqhecs-2.4.0.tar.gz` (sha256 `680efadc130bd5950fc079c319ce7b1acc6d6c62e379628fad530a1d1fa76425`)
  - `cqhecs-sbom.spdx.json` (sha256 `2068477ec6bc15f4eba39c5734d09a4fb71e9766b147d155b269b53c423889e2`)
  - `RELEASE_NOTES_v2.4.0.md` (sha256 `6f72bf02ff41f8473d53cba7c8883d3d647b719fd4e24213fba71c95078ae8fd`)
  - `sha256sums.txt`.

## 2. Published Release: v2.5.0

- Version/tag: `v2.5.0`.
- Release status: `RELEASED` (Published 2026-10-30T00:00:04Z).
- Release URL: https://github.com/timfromhcs/CQ-HECS/releases/tag/v2.5.0
- Candidate branch: `agent/cq-hecs-v2.5.0-quantum-bridge`.
- Candidate commit SHA: `f97249a888c3a504ef51590fcbf61f3640b39678`.
- Merged SHA: `bd2a1142a546589ceb6a5163c300c594561e7177`.
- Pull Request: #14 (https://github.com/timfromhcs/CQ-HECS/pull/14) - MERGED.
- PR Cloud CI: https://github.com/timfromhcs/CQ-HECS/actions/runs/40975601400 (7/7 jobs passed).
- Post-merge Required CI: https://github.com/timfromhcs/CQ-HECS/actions/runs/40976167682 (7/7 jobs passed).
- Release Pipeline Run: https://github.com/timfromhcs/CQ-HECS/actions/runs/40976745534 (succeeded).
- Published release assets:
  - `cqhecs-2.5.0-py3-none-any.whl` (sha256 `ae69e7367d1ba62dd019f3f4330dfbf0207dd8bd418098eb93f9036fa6470874`)
  - `cqhecs-2.5.0.tar.gz` (sha256 `92e31ca3717e97b8a1f2534ad857b832bb0c1b433f81f8d24a1f737ed7b558c6`)
  - `cqhecs-sbom.spdx.json` (sha256 `6b6545008aad03cd7444f326627bf10a7f2d1bcdb9e405885f65cc4d1ed59552`)
  - `RELEASE_NOTES_v2.5.0.md` (sha256 `eb5ea65e89ddfda3847060914b3c20b006e8613955ce7c7d29c6c09dd7c70c49`)
  - `sha256sums.txt`.

## 3. Scope & Capabilities Shipped in v2.5.0

- **Hardware-Aware Quantum Bridge**:
  - `ExecutionMode` hierarchy (`IDEAL_CLASSICAL`, `NOISY_CLASSICAL`, `REAL_HARDWARE`).
  - Versioned `BackendProfile` schema capturing device coupling maps, gate errors, readout errors, and $T_1/T_2$.
  - Mathematically verified `NoiseModel` with Kraus completeness ($\sum K_k^\dagger K_k = I_d$), trace preservation, Hermiticity, and positive semidefiniteness.
  - `NoisyDensityMatrixBackend` exact float64 density matrix simulator for circuits <= 10 qubits with Hoeffding TV error bounds.
  - Deterministic `FakeHardwareProvider` & `FakeHardwareBackend` with coupling map topology enforcement.
  - Fail-closed `RealHardwareProvider` & `RealHardwareBackend` requiring explicit `authorized=True` and API tokens (never silently falling back to simulation).
  - CLI commands `profile list`, `profile show <NAME>`, and `--profile <NAME>` / `--noisy` options on `run`.
- **Quality Gates**:
  - CTest: 19/19 passed (100%).
  - Pytest: 452/452 passed (100%, 32 new tests including Qiskit Aer differential parity).
  - Branch Coverage: 84% (threshold >= 70%).
  - Mutation Testing: 16/16 mutants killed (100%, 2 new mutants).
  - Flake8: 0 errors.
  - Vulkan Shaders: 12/12 verified SPIR-V 1.3 shaders.
  - Version Consistency: All 15 surfaces report `2.5.0`.

## Erratum (added 2026-10-30 during the v2.5.1 audit)

The original text above is kept unchanged as historical record. Corrections:

- **Candidate commit SHA.** `f97249a888c3a504ef51590fcbf61f3640b39678` does not
  exist in the repository. The PR #14 head commit is
  `f97249a1c4ad5c5abfc70985fb6b6833072c0365` (`git rev-parse f97249a`).
- **Release notes asset.** `RELEASE_NOTES_v2.5.0.md` carries a 2.5.0 header but
  its body describes v2.4.0. The asset's hash above is correct; its content is
  not a description of v2.5.0.
- **Scope statements.** The shipped `NoisyDensityMatrixBackend` rendered
  bitstrings mirrored (qubit 0 leftmost), ignored terminal-measurement subsets,
  and never applied noise calibrated on `sx`; `fake_manila` was labelled as a
  non-synthetic IBM snapshot although its values are invented. The
  "verified against Qiskit Aer" claim rested on a mirror-symmetric Bell circuit
  that cannot detect these defects. See `research/v2_5_1/FINDINGS.md`
  (CQ-V251-01 … 07); fixed in v2.5.1.
- Asset SHA-256 values above were re-verified by download on 2026-10-30 and
  match.
