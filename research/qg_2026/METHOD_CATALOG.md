# METHOD_CATALOG.md — methods, assumptions and limits

Executable surfaces use the §0.2 categories. A method is listed only with its assumptions.

## A. BMV effective two-qubit phase model (`qg.bmv.zz.v1`)

- **Claim scope:** a *model* of a gravity-mediated interaction between two probe
  degrees of freedom, after local phases are factored out.
- **Construction:** local phase operations (net effect factored out) + an entangling
  combination `φ00+φ11−φ01−φ10 = θ`. Realised as `U_ZZ(θ)=exp(−i(θ/2)Z⊗Z)` on `|+>|+>`
  (possibly with per-probe local phases `Rz(α)`, `Rz(β)` that must cancel from all
  entanglement measures).
- **Derived results (unit-tested against the dense matrix):**
  - state = `cos(θ/2)|Φ+> − i sin(θ/2)|Φ−>` (up to documented local phases),
  - concurrence `C(θ)=|sin θ|`, negativity `𝒩(θ)=|sin θ|/2`.
- **Observables:** statevector, concurrence, negativity, entanglement entropy, CHSH.
- **Nulls:** θ=0 (separable); explicit LOCC/classical channel (separability preserved).
- **Engine surfaces:** `CLASSICAL_REFERENCE` (numpy/Qiskit Statevector), `CQ_HECS_CPU`.
- **Limits:** no physical mass/separation mapping; a witness is premise-dependent.

## B. Small-N sparse SYK (`qg.syk.q4.v1`)

- **Ensemble:** `H = Σ_{i<j<k<l} J_{ijkl} γ_iγ_jγ_kγ_l`, Gaussian couplings
  `E[J²]=` (documented convention), `q=4`, seeded.
- **Encoding:** Majorana `γ_{2k}=σ_z^{⊗k}⊗X⊗I…`, `γ_{2k+1}=σ_z^{⊗k}⊗Y⊗I…` on `n` qubits
  (`N=2n` Majoranas); Jordan–Wigner.
- **Oracle:** dense spectrum + SciPy `expm` for tiny N; Majorana anticommutator tests.
- **Sparsification:** keep a seeded subset of terms; report kept/discarded weight fraction
  and its effect on the spectrum (no bound claimed unless derived).
- **Evolution:** exact (dense) for tiny N; product-formula/randomised for circuits later;
  Trotter/randomisation error reported separately from shot noise.
- **Observables:** Loschmidt amplitude, OTOC, spectral density (small N), entanglement.
- **Limits:** finite-N, no spacetime interpretation; sparsification changes the model.

## C. Lattice gauge bridge (deferred slice)

- Z2 / tiny model only, with explicit matter/link encoding, Gauss generators, physical
  subspace, `[H,G_x]=0` test. A QFT tool, not a gravity claim. Not yet implemented.

## D. Engines & routing (CQ-HECS integration targets)

- `CLASSICAL_REFERENCE` (numpy / Qiskit Statevector / SciPy).
- `CQ_HECS_CPU` (existing four paths A–D via the router).
- `OPENQUANTUM_SIMULATOR` / `OPENQUANTUM_QPU` (SDK; type from live metadata, never assumed).
- `WEB_WASM_F64` / `WEBGPU_F32` (browser) — planned, labelled by precision.
- Routing is capability-first and fail-closed; estimates are labelled estimates.
