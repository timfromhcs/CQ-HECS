# waveE_E5 - skip budget, Lean re-run, WebGPU real adapter, preview E2E

Tree: branch `release/v7-stable`, HEAD `38e799b`, version 7.0.0 (not changed). Run 2026-11-22 on the
local Windows 11 machine (AMD Radeon, RDNA-2). Nothing committed, pushed, deployed or uploaded.

## 1. Skip budget (freeze pytest: 134 skipped)

Cause: the freeze ran on Python 3.13 with no `CQ_HECS_BUILD_DIR`, so every native-dependent test
skipped. The native cp314 extension (`_cqhecs_core.cp314-win_amd64.pyd`) also needs Python 3.14.

Native Vulkan lane built in an own build dir (not the repo `build/`):
`cmake -S . -B <scratch>/e5build -G "Visual Studio 17 2022" -A x64 -DCQ_ENABLE_VULKAN=ON`, then
`cmake --build ... --config Release --parallel` -> exit 0 (cq_hecs.exe, cq_hecs.dll, cq_hecs_core.dll,
both .pyd, the native test executables). Vulkan SDK 1.4.357.0, MSVC 2022. The native ctest binaries
were NOT run in this wave (only the Python tests that consume the build); ctest status stays as recorded
by the packaging lane.

Re-run of exactly the skip-bearing files with `CQ_HECS_BUILD_DIR=<build>/bin/Release`,
`PYTHONPATH=<build>/bin/Release`, `C:\Program Files\Python314\python.exe`:

| Group | Files | Result |
|---|---|---|
| native-dependent | test_c_api, test_cli_powershell, test_dimacs_parity, test_fuzz_qasm, test_fuzz_sat, test_hardening_v221, test_correctness_contracts, test_native_c_abi_hardening, test_native_vulkan_refusal, test_omniwave, test_qiskit_and_transpiler | **691 passed, 0 skipped** (38.6 s) |
| others (env-bound) | test_exe_smoke, test_lrat_external, test_drat_external_vector, test_sat_external_isolated, test_sat_certificates, test_sat_external, test_schema_contracts, test_studio_plan_ui, test_v3_calibration_bridge, test_v3_noisy_expectation, test_skip_budget | 71 passed, **13 skipped** (75.3 s) |

Corrections found on the way:
* Setting `CQ_HECS_EXE` to the NATIVE `cq_hecs.exe` is wrong: `tests/test_exe_smoke.py` targets the
  PyInstaller onedir Python CLI (`dist/cq-hecs/cq-hecs.exe`, `scripts/build_exe.ps1`). With the native
  exe 6 tests fail (that program has no `--format`/`version` CLI). Left unset they skip. NOT_RUN here
  (PyInstaller is not installed in this interpreter; the CI job "Windows onedir folder" passed on the PR head).
* The 4 `qiskit-ibm-runtime` skips and the Studio-plan UI skip are interpreter/dir specific: they pass
  under the py3.14 interpreter and with `web/node_modules` present.

Budget reconciliation (`research/v7/SKIP_BUDGET.json`, `scripts/skip_budget.py`):
* The old budget said 105 (predating the native/CLI-hardening test files); the freeze junit exceeded it
  in 8 reasons, so `--check` failed. That was a real gate failure.
* Not raised blindly. The budget is now per reason AND per environment:
  * `default` (= top-level `reasons`): the freeze environment, 134 total, each reason at its observed
    count with a justification (116 native-dependent, 6 frozen-exe, 2+1 python-sat, 3 external proof
    checkers, 1 optional validator, 4 qiskit-ibm-runtime, 1 node).
  * `with_native`: 13 total. The nine native reasons are intentionally absent, i.e. budget 0: one native
    skip in that environment fails the gate.
* `scripts/skip_budget.py` gained `--environment NAME` (check selects that environment's reasons;
  `--record --environment` updates only that block). Default behaviour is unchanged.
* Results:
  * `skip_budget.py --junitxml freeze_junit.xml --check` -> OK, 134, rc 0 (was FAIL).
  * same junit with `--environment with_native` -> FAIL listing the 11 native/env reasons (expected: shows
    the with-native budget is strict).
  * merged skip-bearing junit of the two re-runs above with `--environment with_native` -> OK, 13, rc 0.
    That is a union of the skip-bearing files, not a full-suite run; the full suite was not re-run.
  * `tests/test_skip_budget.py`: 5 passed.
* No test was added for `--environment` (tests/ is outside this slice); suggested follow-up.

## 2. Lean (`formal/`, Lean 4.33.1 / Lake 5.0.0-src+819816b)

* `lake build` (stdin /dev/null, output to file): "Build completed successfully (8711 jobs)", exit 0
  (the 2026-11-21 record had 8708 jobs; the three extra are the Pauli/Stabilizer/Result modules).
  File: `research/v7/evidence/lean_freeze_build.txt`.
* PrintAxioms: section 5.
* No theorem or lakefile change.

## 3. WebGPU real-adapter evidence

Served `web/dist` (built 07:55 for HEAD 38e799b) with `vite preview` on 127.0.0.1:4183. A secure
context is required: `about:blank` has no `navigator.gpu`.

| Browser / flags | requestAdapter | requestDevice |
|---|---|---|
| Playwright Chromium 156 headless, no flags | null | - |
| same + `--enable-unsafe-webgpu` | null | - |
| same + `--enable-unsafe-webgpu --enable-features=Vulkan --use-angle=vulkan` | null | - |
| same + `--enable-unsafe-webgpu --use-angle=d3d11 --ignore-gpu-blocklist` | AMD rdna-2 | FAILS: `DynamicLib.Open: dxcompiler.dll Windows Error: 87` (works with `--disable-dawn-features=use_dxc`) |
| installed Google Chrome 157.0.8103.79 (`channel: "chrome"`) + `--enable-unsafe-webgpu --ignore-gpu-blocklist` | AMD rdna-2 | OK (also OK with default ANGLE) |

`isFallbackAdapter` is undefined in these builds, so "not a software fallback" is inferred from vendor
`amd` / architecture `rdna-2`, not from that flag.

Measured with a scratch script mirroring `web/e2e/conformance.spec.ts` (UI -> worker -> WebGPU f32 ->
exported run card compared with `tests/fixtures/shared_conformance.json`); the scratch Playwright
config was deleted afterwards:

* 20 of the 21 corpus cases flagged `webgpu.in_declared_range` ran with `engine.kind == "webgpu"`.
* worst max |p - p_ref| = 1.73e-8 (mixed-6-seed11); worst cross-check TV vs f64 = 7.77e-8
  (mixed-10-seed7). Declared tolerance 5e-6 / 1e-5, margin about 290x / 130x.
* The 21st case `measure-mid-circuit` (2 qubits): the page REFUSES WebGPU ("WebGPU runs circuits
  without mid-circuit measurement, reset or gate noise only. Please choose WebAssembly.") although the
  corpus marks it `in_declared_range: true`. Running the committed spec on a GPU machine therefore FAILS
  at that case (45 s `#stats .chip` timeout) and writes no `webgpu_conformance.json`. Corpus/spec
  inconsistency (the typed refusal is right app behaviour). Not fixed here: `web/e2e/` and
  `tests/fixtures/` are outside slice E5. The 21 WASM f64 corpus tests passed in the same run.

Verdict: WebGPU f32 on a real AMD RDNA-2 adapter is MEASURED for 20/21 declared cases within the declared
tolerance; the committed conformance spec is NOT green on a GPU machine until the mid-circuit case is
reconciled. Raw data: `research/v7/evidence/waveE_E5_webgpu_real_adapter.json`. In CI / headless
Playwright Chromium the WebGPU column stays NOT_RUN.

## 4. Preview E2E (PR #55)

* PR head `38e799b3650e74a47d3a72184da50b5a85d5bb8b`. GitHub deployment 7975070168 (Preview, same sha)
  success -> `https://cq-hecs-ficepgi1m-hcsmediacorp.vercel.app`; the Vercel check is SUCCESS. The URL
  answers 200 anonymously.
* The deployed bundle contains the full SHA 38e799b3650e74a47d3a72184da50b5a85d5bb8b (matches HEAD).
* `E2E_BASE_URL=<preview> npx playwright test --project=chromium`: 110 passed, 1 skipped (WebGPU, NOT_RUN),
  4 failed (3.2 min).
  * 3 failures are preview-environment artifacts: Vercel injects the Vercel Live toolbar on preview
    deployments and the "no third-party request" assertions see `https://vercel.live/_next-live/feedback/*`
    and `POST vercel.live/login/validate` (forge.spec.ts:10, qg.spec.ts:20, qg.spec.ts:112). The same specs
    against the local `web/dist`: forge.spec.ts + qg.spec.ts 42 passed. Not a product defect, but the preview
    E2E is NOT green as run; the specs are not tolerant of the toolbar.
  * 1 failure, states.spec.ts:56 (classical-control `if` refusal, `#code-error` hidden) passed when re-run
    alone against both the preview and the local server (2/2). FLAKY under full-suite load, cause unproven.
* mobile-360/390 projects not run (task: chromium project only).

Other observation (not my slice): the PR #55 check rollup at read time shows FAILURE for Linux Vulkan+full
Python, Python 3.12/3.13/3.14, Native MSVC packaging, and Wheel+sdist; Windows full-suite pending.

## 5. Lean PrintAxioms

`lake env lean scripts/PrintAxioms.lean` (stdin /dev/null): exit 0, 26 `#print axioms` lines, file
`research/v7/evidence/lean_freeze_axioms.txt`. Cold-cache run took about 55 min wall (the mmap of Mathlib
oleans on this disk was I/O bound, CPU about 30 s); not a hang.
* 19 lemmas (truncation bound, Pauli mul/comm, gate conjugations, omega_* tableau lemmas,
  `tableau_invariant`, `ResultContract.unresolved_has_no_certified_value`,
  `unresolved_flags_expose_no_value`, `value_only_for_exact_or_certified`) depend on exactly
  [propext, Classical.choice, Quot.sound].
* 4 `ResultContract` lemmas (`unresolved_derives_unresolved`, `failed_wins`,
  `unresolved_never_certified_or_exact`, `exact_requires`) depend only on [propext].
* No `sorryAx`, no other axiom. Level: FORMALIZED_LEMMA for the named lemmas only, not a refinement
  proof of the shipped implementation.

## Files
* research/v7/SKIP_BUDGET.json, scripts/skip_budget.py (modified)
* research/v7/evidence/lean_freeze_build.txt, lean_freeze_axioms.txt
* research/v7/evidence/waveE_E5_webgpu_real_adapter.json
