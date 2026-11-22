# BMV effective-phase model: parameterisation, competing predictions, null controls (W8)

Status: `SUPPORTED_IN_SCOPE` for the arithmetic below (model quantities, dense oracles). No
statement about gravity follows. Code: `cqhecs/quantum_gravity/bmv_competing.py`; tests:
`tests/test_qg_bmv_competing.py`; frozen table: `models/bmv_competing_table.json`.

## 1. Parameterisation (derived, then tested)

| Quantity | Definition |
|---|---|
| Model | `qg.bmv.zz.v1`: `U = exp(-i (theta/2) Z(x)Z)` on `\|+\>\|+\>` |
| Invariant | `Phi = phi00 + phi11 - phi01 - phi10` (local-phase invariant) |
| Relation | `Phi = -2 theta (mod 2 pi)`; `theta = -Phi/2` (principal value in `[-pi/2, pi/2)`) |
| QGRAVITY.md 2.1 convention | `exp(-i theta_qg Z(x)Z)`, so `theta = 2 theta_qg` (`theta_code_from_qgravity`) |
| Entanglement | `C = abs(sin theta)`, `N = C/2` |
| Toy branch table | `phi_ab = kappa/d_ab` with `d_00 = d_11 = d`, `d_01 = d_10 = d + delta`; `kappa` dimensionless |

The toy table is a device for exploring the size and sign of `Phi`. It is not a physical estimate.
`theta_from_physical_parameters` is a typed refusal (`QG_NO_DIMENSIONAL_MODEL`): CQ-HECS has no
validated dimensional model mapping masses, separations or times to `theta`.

## 2. Assumptions

- A1 two-qubit reduction with local phases factored out; no motional, field or environmental degrees of freedom.
- A2 an interaction that is diagonal in the branch basis; the only entangling content is `Phi`.
- A3 pure, noiseless preparation for the ideal model; noise enters only through declared channels.
- A4 a circuit `theta` is a model parameter, not a laboratory quantity.

## 3. Competing state-preparation hypotheses

All are evaluated from the same input `\|+\>\|+\>` and compared by predicted two-qubit state.

| Model key | Construction | Entangled? |
|---|---|---|
| `quantum_zz` | coherent ZZ interaction | yes for `sin theta != 0` |
| `classical_feedback` | `Z_A` measured, B rotated conditionally (LOCC, classical-quantum state) | no, by construction |
| `shared_randomness` | fair mixture of product states with a shared sign | no, by construction |
| `decoherence` | ZZ interaction then symmetric dephasing `p` (declared channel, not a derived collapse law) | reduced; zero at `p = 1/2` |
| `null_local_only` | `theta = 0` with local phases | no |

They do not predict the same thing. At `theta = pi/3` the coherent model has `<XX> = 1`,
`<YZ> = <ZY> = sin theta`; the classical-feedback model has `<XX> = <YZ> = 0` (A fully dephased in Z)
and the shared-randomness model has `<XX> = 1/4`, `<YY> = 3/4`. `competing_predictions` lists the
correlators on which the models differ. Note that `ZZ` commutes with `XX`, so an XX measurement
carries no `theta` information; the phase is visible in YZ/ZY.

## 4. Caveats that must travel with every result (QGRAVITY.md 2.1; LITERATURE_MAP L-A3..L-A5)

- A positive entanglement witness is premise-dependent. Literature records that some classical-gravity models can
  produce entanglement under fuller field-theoretic assumptions (L-A3) and that the witness is not theory-independent (L-A4).
- The separable controls here are specific channel constructions. They exclude only those channels, not every classical-gravity theory.
- Collapse/decoherence alternatives (L-A5) are represented only by a declared dephasing channel.
- A quantum processor running `U_ZZ(theta)` emulates the model; it does not couple masses through gravity.

## 5. Null controls and the independent oracle

- Null: `theta = 0`; local-phase-only; classical feedback; shared randomness; gauge-free random separable states (witness never positive over 200 draws).
- Independent oracle: Wootters spin-flip concurrence computed from singular values of `sqrt(rho) (Y(x)Y) conj(sqrt(rho))`,
  cross-checked against `observables.concurrence_2qubit` (partial-transpose route) and the analytic `abs(sin theta)`.
- Witness: fidelity witness `F - lambda_max^2` (largest Schmidt weight). It is `<= 0` for every separable state; a positive value certifies entanglement, a negative value certifies nothing.

## 6. Falsification / failure conditions

- any separable control with concurrence above `1e-9` or a positive fidelity witness fails the construction;
- Wootters vs analytic `abs(sin theta)` deviation above `1e-9` fails the oracle;
- a physical-parameter mapping that does not refuse fails the boundary.
