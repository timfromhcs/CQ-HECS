"""
Unified ``cq-hecs`` command-line interface.

This is the single supported command-line entry point. Commands:

    cq-hecs version
    cq-hecs doctor
    cq-hecs backend list
    cq-hecs analyze CIRCUIT
    cq-hecs run CIRCUIT [--backend auto|A|B|C|D] [--shots N] [--seed N]
    cq-hecs verify CIRCUIT --reference aer
    cq-hecs expect CIRCUIT -o PAULI [-o PAULI ...] [--method auto|stabilizer|dense|sparse_pauli]
    cq-hecs reference list|run
    cq-hecs selftest [--cases N]
    cq-hecs benchmark smoke

Output contract
---------------
* ``--format json`` writes exactly one JSON document to stdout with no banner,
  progress or log output.
* Human-readable progress and diagnostics always go to stderr.
* Exit codes: 0 success, 1 unexpected error, 2 usage error,
  3 circuit unresolved / verification failed, 4 environment unavailable.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

# Version is read from the package rather than duplicated here.
from cqhecs import __version__
from cqhecs.hardware_bridge import HardwareBridgeError

LOG = logging.getLogger("cqhecs.cli")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_UNRESOLVED = 3
EXIT_ENVIRONMENT = 4

#: Schema version for the ``--format json`` document.
JSON_SCHEMA_VERSION = "1.0"

VALID_PATHS = ("A", "B", "C", "D")


def _emit_json(payload: Dict[str, Any]) -> None:
    """Writes exactly one JSON document to stdout."""
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")


def _load_circuit(path: str) -> Any:
    """
    Loads a circuit from a .qasm file or a Python literal circuit spec.

    Supported forms:
      * ``file.qasm``                - OpenQASM 2.0 source
      * ``name:python``              - build a Qiskit circuit from a builtin
      * ``path/to/circuit.py:NAME``  - import ``NAME`` from the module

    Raises:
        FileNotFoundError, ValueError
    """
    if path.startswith("name:"):
        from cqhecs.circuit_library import build_builtin_circuit
        return build_builtin_circuit(path[len("name:"):])

    if path.endswith(".py") and ":" in path:
        module_path, _, attr = path.rpartition(":")
        import importlib.util
        spec = importlib.util.spec_from_file_location("cqhecs_user_circuit", module_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot import circuit module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            return getattr(module, attr)
        except AttributeError as exc:
            raise ValueError(
                f"Module {module_path} has no attribute '{attr}'"
            ) from exc

    if not os.path.exists(path):
        raise FileNotFoundError(f"Circuit file not found: {path}")

    if path.endswith(".qasm") or path.endswith(".qasm2"):
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    raise ValueError(
        f"Unsupported circuit file '{path}'. Use a .qasm file, "
        "'name:<builtin>', or 'module.py:NAME'."
    )


# ---------------------------------------------------------------- commands
def cmd_version(args: argparse.Namespace) -> int:
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "name": "cq-hecs",
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"cq-hecs {__version__}")
        print(f"Python {payload['python']} on {payload['platform']}")
    return EXIT_OK


def cmd_doctor(args: argparse.Namespace) -> int:
    """
    Reports the execution environment.

    Distinguishes "not installed", "not available", "not tested" and "failed"
    rather than collapsing them into one silent default.
    """
    report: Dict[str, Any] = {
        "schema_version": JSON_SCHEMA_VERSION,
        "version": __version__,
        "os": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
        },
        "components": {},
    }
    exit_code = EXIT_OK

    def record(name: str, status: str, detail: str = "", **extra: Any) -> None:
        report["components"][name] = {"status": status, "detail": detail, **extra}
        nonlocal exit_code
        if status == "failed":
            exit_code = EXIT_ENVIRONMENT

    # Optional Python dependencies
    for module, label in (
        ("numpy", "numpy"),
        ("qiskit", "qiskit"),
        ("qiskit_aer", "qiskit-aer"),
        ("stim", "stim"),
    ):
        try:
            mod = __import__(module)
            record(label, "available", getattr(mod, "__version__", "unknown"))
        except ImportError:
            record(label, "not_installed", f"optional dependency '{module}' missing")

    # Native binding
    try:
        import cqhecs.backends.path_a_stabilizer as path_a
        if path_a._native is not None:
            record(
                "native_binding", "available",
                getattr(path_a._native, "__file__", "built-in"),
                version=getattr(path_a._native, "__version__", None),
            )
        else:
            record(
                "native_binding", "not_available",
                "_cqhecs_core could not be imported; Python fallbacks will be used",
            )
    except Exception as exc:  # pragma: no cover - defensive
        record("native_binding", "failed", str(exc))

    # Vulkan: loader, then physical devices
    try:
        import ctypes

        vulkan_ok = False
        for dll in ("vulkan-1.dll", "libvulkan.so.1", "libvulkan.dylib"):
            try:
                ctypes.CDLL(dll)
                vulkan_ok = True
                record("vulkan_loader", "available", f"loaded {dll}")
                break
            except OSError:
                continue
        if not vulkan_ok:
            record("vulkan_loader", "not_available", "no Vulkan loader found on PATH")
    except Exception as exc:  # pragma: no cover - defensive
        record("vulkan_loader", "failed", str(exc))

    # Backend capability matrix
    try:
        from cqhecs.router import EntanglementAdaptiveRouter
        report["backends"] = {
            path: sorted(gates)
            for path, gates in EntanglementAdaptiveRouter.PATH_CAPABILITIES.items()
        }
    except Exception as exc:  # pragma: no cover - defensive
        record("backends", "failed", str(exc))

    # Vulkan compute is exercised only through the native engine; this Python
    # path does not dispatch work to a GPU, so it is reported as not exercised.
    report["notes"] = [
        "The Python backends run on CPU. Vulkan acceleration, when present, is "
        "exercised only by the native _cqhecs_core engine.",
        "No statement is made here about physical GPU verification.",
    ]

    if args.format == "json":
        _emit_json(report)
    else:
        print(f"cq-hecs {__version__} doctor report")
        print(f"  OS      : {report['os']['platform']}")
        print(f"  Python  : {report['python']['version']}")
        for name, info in report["components"].items():
            print(f"  {name:<16}: {info['status']:<14} {info['detail']}")
    return exit_code


def cmd_backend(args: argparse.Namespace) -> int:
    if args.backend_command != "list":
        print(f"Unknown backend subcommand: {args.backend_command}", file=sys.stderr)
        return EXIT_USAGE

    from cqhecs.router import EntanglementAdaptiveRouter
    capabilities = EntanglementAdaptiveRouter.PATH_CAPABILITIES
    descriptions = {
        "A": "Stabilizer tableau (Gottesman-Knill). Exact for Clifford circuits.",
        "B": "Stabilizer rank decomposition. Exact, cost grows as O(2^(alpha*T)).",
        "C": "MPS with unbounded bond dimension and storage paging. "
             "No truncation; limited by memory.",
        "D": "Certified Sparse-Pauli dynamics. Reports expectation values with a "
             "rigorous error bound; does not produce joint counts.",
    }
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "backends": [
            {
                "path": path,
                "description": descriptions[path],
                "supported_gates": sorted(capabilities[path]),
            }
            for path in VALID_PATHS
        ],
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        for entry in payload["backends"]:
            print(f"Path {entry['path']}: {entry['description']}")
            print(f"    gates: {', '.join(entry['supported_gates'])}")
    return EXIT_OK



def cmd_profile(args: argparse.Namespace) -> int:
    from cqhecs.hardware_bridge import FakeHardwareProvider

    provider = FakeHardwareProvider()
    if args.profile_command == "list":
        backends = provider.backends()
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "profiles": [b.profile.to_dict() for b in backends],
        }
        if args.format == "json":
            _emit_json(payload)
        else:
            for b in backends:
                p = b.profile
                print(f"Profile: {p.name} (qubits: {p.num_qubits}, provider: {p.provider_name}, synthetic: {p.is_synthetic})")
                print(f"  Coupling edges: {len(p.coupling_map)}")
                print(f"  Basis gates: {', '.join(p.basis_gates)}")
        return EXIT_OK
    elif args.profile_command == "migrate":
        from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError

        try:
            source = json.loads(Path(args.input).read_text("utf-8"))
            if isinstance(source, dict) and isinstance(source.get("profile"), dict):
                source = source["profile"]
            original = BackendProfile.from_dict(source)
            migrated = original.migrated_to_v2()
        except (OSError, ValueError, KeyError, TypeError, InvalidProfileError) as exc:
            LOG.error("cannot migrate %s: %s", args.input, exc)
            return EXIT_USAGE
        Path(args.output).write_text(json.dumps(migrated.to_dict(), indent=2) + "\n", "utf-8")
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "input": args.input,
            "output": args.output,
            "from_schema": original.schema_version,
            "to_schema": migrated.schema_version,
            "profile": migrated.name,
        }
        if args.format == "json":
            _emit_json(payload)
        else:
            print(f"Migrated {migrated.name}: schema {original.schema_version} -> {migrated.schema_version}")
            print(f"Wrote   : {args.output}")
        return EXIT_OK
    elif args.profile_command == "show":
        try:
            b = provider.get_backend(args.name)
        except KeyError as e:
            LOG.error("%s", e)
            return EXIT_USAGE
        p = b.profile
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "profile": p.to_dict(),
        }
        if args.format == "json":
            _emit_json(payload)
        else:
            print(f"Name         : {p.name}")
            print(f"Provider     : {p.provider_name}")
            print(f"Qubits       : {p.num_qubits}")
            print(f"Schema ver   : {p.schema_version}")
            print(f"Captured     : {p.capture_timestamp}")
            print(f"Synthetic    : {p.is_synthetic}")
            print(f"Basis gates  : {', '.join(p.basis_gates)}")
            print(f"Coupling     : {p.coupling_map}")
            print(f"Readout errs : {p.readout_errors}")
        return EXIT_OK
    return EXIT_USAGE


def cmd_reference(args: argparse.Namespace) -> int:
    from cqhecs.openquantum_suite import SUITE_ID, evaluate_suite
    from cqhecs.reference import DATASETS, ReferenceDataError, evaluate

    if args.reference_command == "list":
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "datasets": [
                {
                    "dataset_id": record.dataset_id,
                    "title": record.title,
                    "licence": record.licence,
                    "source": record.source,
                    "pinned_revision": record.pinned_revision,
                    "complete_circuits": record.complete_circuits,
                    "files": [entry.path for entry in record.files],
                    "notes": list(record.notes),
                }
                for record in DATASETS.values()
            ] + [
                {
                    "dataset_id": SUITE_ID,
                    "title": "Preregistered 25-job Open Quantum suite (own real-QPU runs)",
                    "licence": "results owned by the submitter; Public plan requires citing Open Quantum",
                    "source": "research/v3/openquantum_suite/manifest.json",
                    "pinned_revision": None,
                    "complete_circuits": True,
                    "files": [],
                    "notes": [
                        "Circuits are SHA-256-pinned before submission.",
                        "Results are produced by scripts/run_openquantum_suite.py; none ship with the package.",
                    ],
                }
            ],
        }
        if args.format == "json":
            _emit_json(payload)
        else:
            for item in payload["datasets"]:
                print(f"{item['dataset_id']}: {item['title']}")
                print(f"  licence: {item['licence']}  circuits: {item['complete_circuits']}")
                print(f"  source : {item['source']}")
        return EXIT_OK

    if args.dataset == SUITE_ID:
        try:
            payload = evaluate_suite(Path(args.data_dir), bootstrap_samples=args.bootstrap, seed=args.seed)
        except ReferenceDataError as exc:
            LOG.error("%s", exc)
            return EXIT_USAGE
        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
        if args.format == "json":
            _emit_json(payload)
        else:
            aggregate = payload["aggregate"]
            print(f"Dataset : {SUITE_ID} on {payload['backend']} ({payload['dataset_sha256'][:16]}...)")
            print(f"EVAL    : {aggregate['n_eval']}/{aggregate['n_eval_preregistered']} jobs")
            print(f"Median delta TV (M-FIT - ideal): {aggregate['median_delta_tv']:+.6f}")
            print(f"95% bootstrap CI: [{aggregate['ci95_low']:+.6f}, {aggregate['ci95_high']:+.6f}]")
            print(f"Verdict : {aggregate['verdict']}")
        return EXIT_OK

    if args.dataset not in DATASETS:
        LOG.error("unknown reference dataset %r", args.dataset)
        return EXIT_USAGE
    try:
        result = evaluate(
            Path(args.data_dir),
            bootstrap_samples=args.bootstrap,
            seed=args.seed,
        )
    except ReferenceDataError as exc:
        LOG.error("%s", exc)
        return EXIT_USAGE

    payload = result.to_dict()
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    if args.format == "json":
        _emit_json(payload)
    else:
        aggregate = payload["aggregate"]
        print(f"Dataset : {payload['dataset_id']} ({payload['dataset_sha256'][:16]}...)")
        print(f"Circuits: {aggregate['n_circuits']} unique")
        print(f"Median delta TV (noisy - ideal): {aggregate['median_delta_tv']:+.6f}")
        print(f"95% bootstrap CI: [{aggregate['ci95_low']:+.6f}, {aggregate['ci95_high']:+.6f}]")
        print(f"Verdict : {aggregate['verdict']}")
        for family, summary in aggregate["by_family"].items():
            print(
                f"  {family:4s} n={summary['n']:2d} "
                f"median dTV={summary['median_delta_tv']:+.6f} "
                f"noisy-better={summary['n_noisy_better']}/{summary['n']}"
            )
        if args.json_out:
            print(f"Wrote   : {args.json_out}")
    return EXIT_OK


def cmd_noise_fit(args: argparse.Namespace) -> int:
    from cqhecs.noise_fit import dump_profile, evaluate_exploratory, fit_profile
    from cqhecs.openquantum_suite import SUITE_ID
    from cqhecs.reference import ReferenceDataError

    if args.dataset != SUITE_ID:
        LOG.error("noise-fit supports only %s, got %r", SUITE_ID, args.dataset)
        return EXIT_USAGE
    try:
        if args.evaluate:
            payload = evaluate_exploratory(Path(args.data_dir), bootstrap_samples=args.bootstrap)
            document = payload["profile"]
        else:
            payload = None
            _model, document = fit_profile(Path(args.data_dir))
    except ReferenceDataError as exc:
        LOG.error("%s", exc)
        return EXIT_USAGE
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(dump_profile(document), "utf-8")
    if args.format == "json":
        _emit_json(payload if payload is not None else document)
        return EXIT_OK
    cx = document["cx_depolarizing"]
    print(f"Model   : {document['model']} ({document['status']})")
    print(f"Backend : {document['provenance']['backend']}")
    print(f"Calib.  : {document['provenance']['calibration']['status']}")
    for row in document["readout"]:
        print(
            f"  q{row['qubit']}: P(1|0)={row['p01']:.3f}+-{row['p01_se']:.3f} "
            f"P(0|1)={row['p10']:.3f}+-{row['p10_se']:.3f}"
        )
    print(f"CX p    : {cx['readout_corrected']:.5f} readout-corrected, {cx['uncorrected']:.5f} uncorrected")
    for anomaly in document.get("anomalies", []):
        print(
            f"Anomaly : q{anomaly['qubit']} OQ-02 P(0|1)={anomaly['observed_p10_from_OQ02']:.3f} "
            f"is an X-gate flip (fitted p10={anomaly['fitted_p10']:.3f}, "
            f"x bit-flip={anomaly['x_bitflip']:.3f})"
        )
    if payload is not None:
        for key in ("vs_ideal", "vs_m_fit"):
            item = payload[key]
            print(
                f"{key:8s}: median dTV={item['median']:+.6f} "
                f"CI=[{item['ci95_low']:+.6f}, {item['ci95_high']:+.6f}] {item['direction']}"
            )
        print("Note    : post-hoc and exploratory; not a confirmation")
    if args.out:
        print(f"Wrote   : {args.out}")
    return EXIT_OK


def cmd_sat(args: argparse.Namespace) -> int:
    """Sound DIMACS solving and an empirical random-3-SAT sweep."""
    from cqhecs.sat import parse_dimacs, random_3sat, solve, sweep

    if args.sat_command == "solve":
        try:
            if args.file:
                text = Path(args.file).read_text("utf-8")
                formula = parse_dimacs(text, source=args.file)
            elif args.cnf:
                formula = parse_dimacs(args.cnf, source="argument")
            elif args.random is not None:
                ratio = args.ratio if args.ratio is not None else 4.26
                formula = random_3sat(args.random, int(round(ratio * args.random)), seed=args.seed)
            else:
                LOG.error("provide a DIMACS file, --cnf TEXT, or --random N")
                return EXIT_USAGE
        except (OSError, ValueError) as exc:
            LOG.error("%s", exc)
            return EXIT_USAGE
        if getattr(args, "engine", "dpll") == "cadical":
            from cqhecs.sat_external import BackendUnavailable, solve_external

            try:
                result = solve_external(formula, timeout_seconds=args.timeout)
            except BackendUnavailable as exc:
                LOG.error("%s", exc)
                return EXIT_USAGE
        omniwave_stats = None
        if getattr(args, "engine", "dpll") == "omniwave":
            from cqhecs.omniwave import OmniwaveConfig, OmniwaveEngine

            try:
                engine = OmniwaveEngine(formula, OmniwaveConfig(
                    waves=args.waves, workers=args.workers, seed=args.seed, timeout_seconds=args.timeout,
                    bcp=args.bcp, batch_size=args.batch_size, branch=args.branch,
                ))
            except (ValueError, RuntimeError) as exc:
                LOG.error("%s", exc)
                return EXIT_USAGE
            result = engine.run()
            omniwave_stats = engine.snapshot()
            omniwave_stats["bcp"] = args.bcp
            if args.proof_out and result.status == "UNSAT":
                Path(args.proof_out).parent.mkdir(parents=True, exist_ok=True)
                Path(args.proof_out).write_text("\n".join(engine.proof()) + "\n", "utf-8")
        elif getattr(args, "engine", "dpll") != "cadical":
            result = solve(
                formula,
                timeout_seconds=args.timeout,
                propagation="watched" if getattr(args, "engine", "dpll") == "watched" else "scan",
            )
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "version": __version__,
            "formula": {
                "num_vars": formula.num_vars,
                "num_clauses": formula.num_clauses,
                "sha256": formula.sha256,
                "original_sha256": formula.original_sha256,
                "source": formula.source,
            },
            "result": result.to_dict(),
        }
        if omniwave_stats is not None:
            payload["omniwave"] = omniwave_stats
        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
        if args.format == "json":
            _emit_json(payload)
        else:
            print(f"Formula    : {formula.num_vars} vars, {formula.num_clauses} clauses")
            print(f"Status     : {result.status}")
            if omniwave_stats is not None:
                print(f"OMNIWAVE   : {args.waves} waves, {args.workers} workers, bcp={args.bcp}; "
                      f"fronts {omniwave_stats['fronts_processed']}, nogoods {omniwave_stats['shared_nogoods']}, "
                      f"coverage {omniwave_stats['covered']:.3%}")
            print(f"Engine     : {result.engine}")
            labels = {
                "MODEL_VERIFIED": "model verified clause by clause",
                "TREE_RESOLUTION_CHECKED": "tree-resolution certificate replayed by check_refutation",
                "DRAT_CHECKED": "DRAT proof checked by cqhecs.drat (independent of the solver)",
                "UNCERTIFIED": "none checked (UNSAT is the solver's verdict only)",
                "NONE": "not decided",
            }
            print(f"Evidence   : {result.certification} - {labels[result.certification]}")
            print(f"Decisions  : {result.decisions}  conflicts {result.conflicts}  nodes {result.nodes}")
            print(f"Time (ms)  : {result.elapsed_ms:.2f}")
            print(f"Note       : {result.note}")
            if result.assignment is not None and args.show_model:
                print("Model      :", " ".join(f"{k}={'1' if v else '0'}" for k, v in sorted(result.assignment.items())))
        return EXIT_OK

    if args.sat_command == "count":
        from cqhecs.sat import count_models

        try:
            if args.file:
                formula = parse_dimacs(Path(args.file).read_text("utf-8"), source=args.file)
            elif args.cnf:
                formula = parse_dimacs(args.cnf, source="argument")
            else:
                LOG.error("provide a DIMACS file or --cnf TEXT")
                return EXIT_USAGE
        except (OSError, ValueError) as exc:
            LOG.error("%s", exc)
            return EXIT_USAGE
        counted = count_models(formula, timeout_seconds=args.timeout)
        payload = {"schema_version": JSON_SCHEMA_VERSION, "version": __version__, "result": counted}
        if args.format == "json":
            _emit_json(payload)
        else:
            print(f"Formula    : {formula.num_vars} vars, {formula.num_clauses} clauses")
            print(f"Status     : {counted['status']}")
            print(f"#Models    : {counted['count'] if counted['count'] is not None else 'not determined'}")
            print(f"Method     : {counted['method']}")
            print(f"Nodes      : {counted['nodes']}  cache hits {counted['cache_hits']}")
            print(f"Time (ms)  : {counted['elapsed_ms']:.2f}")
            print(f"Note       : {counted['note']}")
        return EXIT_OK

    if args.sat_command in ("models", "maxsat"):
        from cqhecs.sat import enumerate_models, max_sat

        try:
            if args.file:
                formula = parse_dimacs(Path(args.file).read_text("utf-8"), source=args.file)
            elif args.cnf:
                formula = parse_dimacs(args.cnf, source="argument")
            elif args.random is not None:
                ratio = args.ratio if args.ratio is not None else 4.26
                formula = random_3sat(args.random, int(round(ratio * args.random)), seed=args.seed)
            else:
                LOG.error("provide a DIMACS file, --cnf TEXT, or --random N")
                return EXIT_USAGE
        except (OSError, ValueError) as exc:
            LOG.error("%s", exc)
            return EXIT_USAGE
        if args.sat_command == "models":
            payload = enumerate_models(formula, limit=args.limit, timeout_seconds=args.timeout)
            payload = {
                "schema_version": JSON_SCHEMA_VERSION,
                "version": __version__,
                "formula": {"num_vars": formula.num_vars, "num_clauses": formula.num_clauses, "sha256": formula.sha256},
                **payload,
            }
        else:
            weights = [float(w) for w in args.weights.split(",")] if args.weights else None
            payload = max_sat(formula, weights)
            payload = {
                "schema_version": JSON_SCHEMA_VERSION,
                "version": __version__,
                "formula": {"num_vars": formula.num_vars, "num_clauses": formula.num_clauses, "sha256": formula.sha256},
                **payload,
            }
        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
        if args.format == "json":
            _emit_json(payload)
        else:
            if args.sat_command == "models":
                print(f"Status     : {payload['status']} ({payload['count']}/{payload['limit']} models)")
                for index, model in enumerate(payload["models"], 1):
                    print(f"  {index}:", " ".join(f"{k}={'1' if v else '0'}" for k, v in sorted(model.items())))
            else:
                print(f"Status     : {payload['status']}")
                print(f"Score      : {payload['satisfied_weight']} / {payload['total_weight']}")
                print(f"Unsatisfied: {payload['unsatisfied_clauses']}")
                print("Model      :", " ".join(f"{k}={'1' if v else '0'}" for k, v in sorted(payload["assignment"].items())))
        return EXIT_OK

    if args.sat_command == "sweep":
        try:
            payload = sweep(
                sizes=args.sizes,
                ratios=args.ratios,
                trials=args.trials,
                timeout_seconds=args.timeout,
                seed=args.seed,
            )
        except ValueError as exc:
            LOG.error("%s", exc)
            return EXIT_USAGE
        payload = {"schema_version": JSON_SCHEMA_VERSION, "version": __version__, **payload}
        if args.json_out:
            Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_out).write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
        if args.format == "json":
            _emit_json(payload)
        else:
            print(" n ratio  clauses  sat/unsat/unknown  median decisions  median ms")
            for row in payload["rows"]:
                print(
                    f"{row['num_vars']:2d} {row['ratio']:5.2f} {row['num_clauses']:7d}  "
                    f"{row['sat']:2d}/{row['unsat']:2d}/{row['unknown']:2d}          "
                    f"{row['median_decisions']:8.1f}      {row['median_ms']:8.2f}"
                )
            print(payload["non_claim"])
        return EXIT_OK
    return EXIT_USAGE


def cmd_devices(args: argparse.Namespace) -> int:
    """List the measured device noise profiles."""
    from cqhecs.device_profiles import list_profiles, summary

    rows = [summary(profile) for profile in list_profiles()]
    if args.format == "json":
        _emit_json({"schema_version": JSON_SCHEMA_VERSION, "version": __version__, "devices": rows})
        return EXIT_OK
    print(f"{'id':16s} {'vendor':8s} {'qubits':>6s} {'shots':>6s} {'cx dep':>8s} {'p01':>7s} {'p10':>7s}  H-V3-8")
    for r in rows:
        print(f"{r['id']:16s} {r['vendor']:8s} {r['measured_qubits']:>6d} {r['shots_per_circuit']:>6d} "
              f"{r['cx_depolarizing']:>8.4f} {r['mean_p01']:>7.4f} {r['mean_p10']:>7.4f}  {r['h_v3_8']}")
    print("Measured M-FIT-2 profiles (post-hoc). Use: cq-hecs run <circuit> --device <id>")
    return EXIT_OK


def cmd_mcp(args: argparse.Namespace) -> int:
    """Start the stdio MCP server."""
    from cqhecs.mcp_server import main as mcp_main

    return mcp_main()


def cmd_studio(args: argparse.Namespace) -> int:
    """Start the local experiment UI."""
    from cqhecs.studio import serve

    serve(
        host=args.host,
        port=args.port,
        root=args.root or os.getcwd(),
        open_browser=not args.no_browser,
    )
    return EXIT_OK


def cmd_selftest(args: argparse.Namespace) -> int:
    from cqhecs.selftest import run_selftest

    try:
        report = run_selftest(cases=args.cases, seed=args.seed)
    except ValueError as exc:
        LOG.error("%s", exc)
        return EXIT_USAGE
    payload = report.to_dict()
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"Metamorphic self-test: {len(report.checks)} checks, seed {report.seed}, cases {report.cases}")
        for check in report.checks:
            status = "PASS" if check.passed else "FAIL"
            print(f"  [{status}] {check.name:24s} {check.duration_ms:7.1f} ms  {check.detail}")
        print("Result:", "PASS" if report.passed else "FAIL")
    return EXIT_OK if report.passed else EXIT_ERROR


def cmd_analyze(args: argparse.Namespace) -> int:
    from cqhecs.circuit_analyzer import CircuitAnalyzer

    circuit = _load_circuit(args.circuit)
    props = CircuitAnalyzer().analyze(circuit)
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "version": __version__,
        "analysis": props.to_dict(),
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"Qubits      : {props.num_qubits}")
        print(f"Gates       : {props.total_gates} {props.gate_counts}")
        print(f"T-Count     : {props.t_count}")
        print(f"Clifford    : {props.is_clifford}")
        print(f"Entanglement: {props.entanglement_estimate} (max cut {props.max_cut_width})")
        print(f"Recommended : Path {props.recommended_path}")
        print(f"Reason      : {props.reason}")
    return EXIT_OK


def cmd_run(args: argparse.Namespace) -> int:
    from cqhecs.router import (
        EntanglementAdaptiveRouter,
    )
    from cqhecs.result import SimulationState

    circuit = _load_circuit(args.circuit)
    backend = args.backend.upper()

    if getattr(args, "device", None):
        from cqhecs.backends.noisy_density_matrix import NoisyDensityMatrixBackend
        from cqhecs.circuit_parsing import parse_circuit
        from cqhecs.device_profiles import UnknownDeviceProfileError, noise_model

        instructions, num_qubits = parse_circuit(circuit)
        if num_qubits > 10:
            raise ValueError(
                f"--device uses the exact density-matrix path (<= 10 qubits); this circuit has {num_qubits}"
            )
        try:
            model = noise_model(args.device, instructions, num_qubits)
        except UnknownDeviceProfileError as exc:
            raise ValueError(exc.args[0]) from exc
        LOG.info("executing %s with measured device profile %s", args.circuit, args.device)
        result = NoisyDensityMatrixBackend(max_qubits=10).simulate(
            instructions, noise_model=model, shots=args.shots, seed=args.seed
        )
        result.backend_profile_id = f"device:{args.device}"
    elif getattr(args, "profile", None):
        from cqhecs.hardware_bridge import FakeHardwareProvider, ExecutionMode
        provider = FakeHardwareProvider()
        try:
            fake_backend = provider.get_backend(args.profile)
        except KeyError as exc:
            raise ValueError(exc.args[0]) from exc
        exec_mode = (
            ExecutionMode.NOISY_CLASSICAL
            if getattr(args, "noisy", True)
            else ExecutionMode.IDEAL_CLASSICAL
        )
        LOG.info(
            "executing %s via hardware profile %s (mode=%s, shots=%d, seed=%s)",
            args.circuit, args.profile, exec_mode.value, args.shots, args.seed,
        )
        result = fake_backend.run(
            circuit,
            shots=args.shots,
            seed=args.seed,
            execution_mode=exec_mode,
        )
    else:
        router = EntanglementAdaptiveRouter(
            error_tolerance=args.error_tolerance,
            max_pauli_terms=args.max_pauli_terms,
        )
        LOG.info(
            "executing %s via %s (shots=%d, seed=%s)",
            args.circuit, backend, args.shots, args.seed,
        )
        result = router.route_and_execute(
            circuit,
            shots=args.shots,
            seed=args.seed,
            preferred_path=None if backend == "AUTO" else backend,
            error_tolerance=args.error_tolerance,
        )

    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "version": __version__,
        "result": result.to_dict(),
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"Path        : {result.path}")
        if result.execution_mode:
            print(f"Mode        : {result.execution_mode.value if hasattr(result.execution_mode, 'value') else result.execution_mode}")
        if result.backend_profile_id:
            print(f"Profile     : {result.backend_profile_id}")
        print(f"State       : {result.state.value if result.state else 'UNKNOWN'}")
        print(f"Exact       : {result.exact}")
        print(f"Error bound : {result.error_bound:.3e}")
        if result.sampling_error_bound is not None:
            print(f"Sampling TV : {result.sampling_error_bound:.3e}")
        print(f"Time (ms)   : {result.execution_time_ms:.2f}")
        if result.expectation_values:
            print("Expectations:")
            for key, value in sorted(result.expectation_values.items()):
                print(f"  {key:<12} {value:+.6f}")
        if result.counts:
            print("Counts:")
            for key, value in sorted(result.counts.items(), key=lambda kv: -kv[1])[:20]:
                print(f"  {key}  {value}")
        elif not result.expectation_values:
            print("Counts      : (none produced)")
        if result.unresolved:
            print(f"Unresolved  : {result.metadata.get('reason', 'see metadata')}")

    return EXIT_UNRESOLVED if result.state == SimulationState.UNRESOLVED else EXIT_OK


def cmd_expect(args: argparse.Namespace) -> int:
    """Evaluates Pauli expectation values (exact where possible)."""
    from cqhecs.expectation import expectation_values

    circuit = _load_circuit(args.circuit)
    result = expectation_values(
        circuit,
        args.observable,
        method=args.method,
        error_tolerance=args.error_tolerance,
        max_pauli_terms=args.max_pauli_terms,
    )
    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "version": __version__,
        "result": result.to_dict(),
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"Method      : {result.method}")
        print(f"Exact       : {result.exact}")
        print(f"Error bound : {result.error_bound:.3e}")
        print(f"Time (ms)   : {result.execution_time_ms:.2f}")
        print("Expectations:")
        for key, value in result.values.items():
            shown = "UNRESOLVED" if value is None else f"{value:+.6f}"
            print(f"  {key:<24} {shown}")
        if result.unresolved:
            print(f"Unresolved  : {result.metadata.get('reason', 'see metadata')}")
    return EXIT_UNRESOLVED if result.unresolved else EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    """Compares CQ-HECS against a trusted reference implementation."""
    from cqhecs.router import EntanglementAdaptiveRouter

    circuit = _load_circuit(args.circuit)
    backend = args.backend.upper()
    router = EntanglementAdaptiveRouter()
    result = router.route_and_execute(
        circuit,
        shots=args.shots,
        seed=args.seed,
        preferred_path=None if backend == "AUTO" else backend,
    )

    if result.counts and args.reference == "aer":
        try:
            from qiskit_aer import AerSimulator
        except ImportError:
            payload = {
                "schema_version": JSON_SCHEMA_VERSION,
                "verified": False,
                "reason": "qiskit-aer is not installed; install the 'dev' extra",
            }
            _emit_json(payload)
            return EXIT_ENVIRONMENT

        try:
            import copy as _copy

            ref_circuit = _copy.deepcopy(circuit)
            if not any(getattr(i.operation, "name", "") == "measure"
                       for i in ref_circuit.data):
                ref_circuit.measure_all()
            reference = AerSimulator().run(
                ref_circuit, shots=args.shots, seed_simulator=args.seed
            ).result().get_counts()
        except Exception as exc:
            payload = {
                "schema_version": JSON_SCHEMA_VERSION,
                "verified": False,
                "reason": f"reference execution failed: {exc}",
            }
            _emit_json(payload)
            return EXIT_ENVIRONMENT

        keys = set(result.counts) | set(reference)
        total = max(sum(result.counts.values()), 1)
        ref_total = max(sum(reference.values()), 1)
        deltas = {
            k: abs(result.counts.get(k, 0) / total - reference.get(k, 0) / ref_total)
            for k in keys
        }
        worst_key = max(deltas, key=deltas.get)
        worst = deltas[worst_key]
        # Compare at 3 sigma of a binomial proportion at the given shot count.
        tolerance = 6.0 * (0.25 / args.shots) ** 0.5 + 0.01
        passed = worst <= tolerance
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "verified": bool(passed),
            "reference": "aer",
            "path": result.path,
            "shots": args.shots,
            "max_abs_probability_delta": worst,
            "max_delta_outcome": worst_key,
            "tolerance": tolerance,
        }
        _emit_json(payload)
        return EXIT_OK if passed else EXIT_UNRESOLVED

    # No joint counts: verify the certified expectation values instead.
    if result.expectation_values and args.reference == "aer":
        try:
            from qiskit_aer import AerSimulator
        except ImportError:
            _emit_json({
                "schema_version": JSON_SCHEMA_VERSION,
                "verified": False,
                "reason": "qiskit-aer is not installed; install the 'dev' extra",
            })
            return EXIT_ENVIRONMENT

        from qiskit.quantum_info import SparsePauliOp, Statevector
        import re

        state = Statevector(circuit)
        worst, worst_key = 0.0, None
        for key, value in result.expectation_values.items():
            qubits = [int(x) for x in re.findall(r"Z\[(\d+)\]", key)]
            label = ["I"] * state.num_qubits
            for q in qubits:
                label[state.num_qubits - 1 - q] = "Z"
            expected = float(
                state.expectation_value(SparsePauliOp("".join(label))).real
            )
            delta = abs(expected - value)
            if delta > worst:
                worst, worst_key = delta, key

        # The certified bound must dominate the observed deviation.
        passed = worst <= result.error_bound + 1e-9
        payload = {
            "schema_version": JSON_SCHEMA_VERSION,
            "verified": bool(passed),
            "reference": "aer",
            "path": result.path,
            "compared": "expectation_values",
            "max_abs_deviation": worst,
            "max_deviation_observable": worst_key,
            "certified_error_bound": result.error_bound,
        }
        _emit_json(payload)
        return EXIT_OK if passed else EXIT_UNRESOLVED

    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "verified": False,
        "reason": (
            "No comparable output was produced. Path D reports expectation "
            "values; verify those with --reference aer, or use --backend A/B/C "
            "for exact counts."
        ),
        "path": result.path,
    }
    _emit_json(payload)
    return EXIT_UNRESOLVED


def cmd_benchmark(args: argparse.Namespace) -> int:
    if args.benchmark_command != "smoke":
        print(f"Unknown benchmark subcommand: {args.benchmark_command}", file=sys.stderr)
        return EXIT_USAGE

    from cqhecs.router import EntanglementAdaptiveRouter
    from qiskit import QuantumCircuit

    router = EntanglementAdaptiveRouter()
    cases = []
    ghz = QuantumCircuit(8)
    ghz.h(0)
    for i in range(7):
        ghz.cx(i, i + 1)
    cases.append(("ghz8", ghz))

    mixed = QuantumCircuit(4)
    mixed.h(0)
    mixed.cx(0, 1)
    mixed.t(1)
    mixed.rz(0.4, 2)
    cases.append(("mixed4", mixed))

    rows = []
    for name, circuit in cases:
        import time as _time
        start = _time.perf_counter()
        result = router.route_and_execute(circuit, shots=1024, seed=42)
        elapsed = (_time.perf_counter() - start) * 1000.0
        rows.append({
            "case": name,
            "path": result.path,
            "state": result.state.value if result.state else None,
            "wall_ms": elapsed,
        })

    payload = {
        "schema_version": JSON_SCHEMA_VERSION,
        "version": __version__,
        "note": (
            "Timings are single-run wall clock on the local CPU and are not a "
            "performance claim."
        ),
        "cases": rows,
    }
    if args.format == "json":
        _emit_json(payload)
    else:
        print(f"{'case':<10} {'path':<5} {'state':<12} {'wall_ms':>9}")
        for row in rows:
            print(f"{row['case']:<10} {row['path']:<5} {str(row['state']):<12} "
                  f"{row['wall_ms']:>9.2f}")
    return EXIT_OK


# ------------------------------------------------------------------ parser
def _csv_ints(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def _csv_floats(value: str) -> list[float]:
    return [float(part) for part in value.split(",") if part.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cq-hecs",
        description=(
            "CQ-HECS: deterministic classical four-path quantum circuit "
            "simulation engine."
        ),
        epilog=(
            "Examples:\n"
            "  cq-hecs doctor\n"
            "  cq-hecs analyze name:ghz8\n"
            "  cq-hecs run name:ghz8 --backend auto --shots 1000 --seed 42\n"
            "  cq-hecs run name:ghz8 --format json\n"
            "  cq-hecs verify name:bell --reference aer\n"
            "  cq-hecs benchmark smoke\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format. 'json' emits one JSON document on stdout.",
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase stderr verbosity (repeatable).",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="Suppress stderr diagnostics.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print version information")
    sub.add_parser("doctor", help="Report the execution environment")
    p_prof = sub.add_parser("profile", help="Inspect hardware calibration profiles")
    prof_sub = p_prof.add_subparsers(dest="profile_command", required=True)
    prof_sub.add_parser("list", help="List available hardware calibration profiles")
    p_show = prof_sub.add_parser("show", help="Show details of a hardware profile")
    p_show.add_argument("name", help="Profile name (e.g. fake_manila, linear_5q)")
    p_mig = prof_sub.add_parser("migrate", help="Rewrite a schema 1.0 profile JSON as schema 2.0")
    p_mig.add_argument("input", help="Profile JSON (bare, or the output of 'profile show --format json')")
    p_mig.add_argument("output", help="Where to write the schema 2.0 profile JSON")

    p_ref = sub.add_parser(
        "reference",
        help="Evaluate a noise model against real measured bitstrings",
    )
    ref_sub = p_ref.add_subparsers(dest="reference_command", required=True)
    ref_sub.add_parser("list", help="List registered real-input/output datasets")
    p_ref_run = ref_sub.add_parser("run", help="Run the preregistered reference evaluation")
    p_ref_run.add_argument(
        "--dataset", default="r-io-5",
        help="Registered dataset ID: r-io-5 (default) or r-io-7 (Open Quantum suite results)",
    )
    p_ref_run.add_argument(
        "--data-dir", default="tests/data/quantum_noise_transfer",
        help="Directory containing the verified dataset files",
    )
    p_ref_run.add_argument(
        "--bootstrap", type=int, default=1000,
        help="Bootstrap resamples for the median-delta interval",
    )
    p_ref_run.add_argument("--seed", type=int, default=20261030, help="Bootstrap seed")
    p_ref_run.add_argument("--json-out", default=None, help="Write the full result JSON here")

    p_fit = sub.add_parser(
        "noise-fit",
        help="Fit a per-qubit noise profile (M-FIT-2, exploratory) from measured counts",
    )
    p_fit.add_argument("--dataset", default="r-io-7", help="Dataset ID (only r-io-7)")
    p_fit.add_argument(
        "--data-dir", default="research/v3/evidence/openquantum/rigetti_cepheus-1-108q",
        help="Directory with OQ-xx result folders",
    )
    p_fit.add_argument("--out", default=None, help="Write the profile JSON here")
    p_fit.add_argument(
        "--evaluate", action="store_true",
        help="Also score M-FIT-2 against ideal and M-FIT on the EVAL split (post-hoc)",
    )
    p_fit.add_argument("--bootstrap", type=int, default=5000, help="Bootstrap resamples")

    p_selftest = sub.add_parser(
        "selftest",
        help="Run metamorphic and property-based installation checks",
    )
    p_selftest.add_argument("--cases", type=int, default=8, help="Random circuits per property")
    p_selftest.add_argument("--seed", type=int, default=20261030, help="Deterministic seed")

    p_backend = sub.add_parser("backend", help="Inspect backend capabilities")
    backend_sub = p_backend.add_subparsers(dest="backend_command", required=True)
    backend_sub.add_parser("list", help="List backends and their supported gates")

    p_analyze = sub.add_parser("analyze", help="Statically analyze a circuit")
    p_analyze.add_argument("circuit", help=".qasm file, 'name:<builtin>' or 'mod.py:NAME'")

    p_run = sub.add_parser("run", help="Execute a circuit")
    p_run.add_argument("circuit", help=".qasm file, 'name:<builtin>' or 'mod.py:NAME'")
    p_run.add_argument(
        "--backend", default="auto",
        help="auto (default) or a forced path A/B/C/D",
    )
    p_run.add_argument("--shots", type=int, default=1024, help="Measurement shots (> 0)")
    p_run.add_argument("--seed", type=int, default=42, help="RNG seed")
    p_run.add_argument(
        "--error-tolerance", type=float, default=0.05,
        help="Accepted error bound for certified paths",
    )
    p_run.add_argument(
        "--max-pauli-terms", type=int, default=1024,
        help="Pauli term budget for Path D",
    )
    p_run.add_argument(
        "--profile", default=None,
        help="Hardware profile to emulate (e.g. fake_manila, linear_5q)",
    )
    p_run.add_argument(
        "--device", default=None,
        help="Measured QPU noise profile (see `cq-hecs devices`), e.g. ibm_kingston",
    )
    p_run.add_argument(
        "--noisy", action=argparse.BooleanOptionalAction, default=True,
        help="Enable/disable noise model when running with --profile",
    )

    p_verify = sub.add_parser("verify", help="Compare against a reference backend")
    p_verify.add_argument("circuit", help=".qasm file, 'name:<builtin>' or 'mod.py:NAME'")
    p_verify.add_argument(
        "--reference", default="aer", choices=["aer"],
        help="Reference implementation to compare against",
    )
    p_verify.add_argument("--shots", type=int, default=8192, help="Measurement shots")
    p_verify.add_argument("--seed", type=int, default=42, help="RNG seed")
    p_verify.add_argument("--backend", default="auto", help="auto or A/B/C/D")

    p_expect = sub.add_parser(
        "expect", help="Evaluate Pauli expectation values",
        description=(
            "Exact for Clifford circuits (stabilizer) and up to 22 qubits "
            "(dense); certified Heisenberg propagation (sparse_pauli) beyond. "
            "Pauli strings: dense Qiskit label such as 'IZX' (rightmost = "
            "qubit 0) or sparse 'X0 Z2'."
        ),
    )
    p_expect.add_argument("circuit", help=".qasm file, 'name:<builtin>' or 'mod.py:NAME'")
    p_expect.add_argument(
        "-o", "--observable", action="append", required=True, metavar="PAULI",
        help="Pauli string; repeat for several observables",
    )
    p_expect.add_argument(
        "--method", default="auto",
        choices=["auto", "stabilizer", "dense", "sparse_pauli"],
        help="Evaluation engine (default: auto)",
    )
    p_expect.add_argument(
        "--error-tolerance", type=float, default=0.05,
        help="Accepted bound for the sparse_pauli engine",
    )
    p_expect.add_argument(
        "--max-pauli-terms", type=int, default=1024,
        help="Pauli term budget for the sparse_pauli engine",
    )

    p_bench = sub.add_parser("benchmark", help="Run benchmarks")
    bench_sub = p_bench.add_subparsers(dest="benchmark_command", required=True)
    bench_sub.add_parser("smoke", help="Fast end-to-end smoke benchmark")

    p_sat = sub.add_parser("sat", help="Sound DIMACS SAT solving and sweeps")
    sat_sub = p_sat.add_subparsers(dest="sat_command", required=True)
    p_sat_solve = sat_sub.add_parser("solve", help="Solve one CNF formula")
    p_sat_solve.add_argument("file", nargs="?", help="DIMACS .cnf file")
    p_sat_solve.add_argument("--cnf", default=None, help="DIMACS text")
    p_sat_solve.add_argument("--random", type=int, default=None, metavar="N", help="Generate random 3-SAT with N variables")
    p_sat_solve.add_argument("--ratio", type=float, default=None, help="Clause/variable ratio for --random")
    p_sat_solve.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds")
    p_sat_solve.add_argument("--seed", type=int, default=20261030, help="Random seed")
    p_sat_solve.add_argument("--json-out", default=None, help="Write the full result JSON here")
    p_sat_solve.add_argument("--show-model", action="store_true", help="Print the satisfying assignment")
    p_sat_solve.add_argument(
        "--engine", choices=["dpll", "watched", "cadical", "omniwave"], default="dpll",
        help="dpll (built-in reference), watched (same search with two-watched-literal propagation), "
        "cadical (optional extra: pip install cqhecs[sat]) "
        "or omniwave (experimental multi-front search; UNSAT only with a checked DRAT proof)",
    )
    p_sat_solve.add_argument("--waves", type=int, default=4, help="OMNIWAVE: number of waves")
    p_sat_solve.add_argument("--workers", type=int, default=2, help="OMNIWAVE: worker threads")
    p_sat_solve.add_argument("--bcp", choices=["scalar", "batch", "vulkan"], default="scalar",
                             help="OMNIWAVE: propagation backend (vulkan is verified against the CPU)")
    p_sat_solve.add_argument("--branch", choices=["auto", "jw", "bfs"], default="auto",
                             help="OMNIWAVE: branching order (auto uses BFS on parity-heavy formulas, JW elsewhere)")
    p_sat_solve.add_argument("--batch-size", type=int, default=64, help="OMNIWAVE: fronts per batch")
    p_sat_solve.add_argument("--proof-out", default=None, help="OMNIWAVE: write the checked DRAT proof here")
    p_sat_count = sat_sub.add_parser("count", help="Exact model count (#SAT)")
    p_sat_count.add_argument("file", nargs="?", help="DIMACS .cnf file")
    p_sat_count.add_argument("--cnf", default=None, help="DIMACS text")
    p_sat_count.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds")

    p_sat_models = sat_sub.add_parser("models", help="Enumerate up to N models")
    p_sat_models.add_argument("file", nargs="?", help="DIMACS .cnf file")
    p_sat_models.add_argument("--cnf", default=None, help="DIMACS text")
    p_sat_models.add_argument("--random", type=int, default=None, metavar="N")
    p_sat_models.add_argument("--ratio", type=float, default=None)
    p_sat_models.add_argument("--limit", type=int, default=10)
    p_sat_models.add_argument("--timeout", type=float, default=10.0)
    p_sat_models.add_argument("--seed", type=int, default=20261030)
    p_sat_models.add_argument("--json-out", default=None)

    p_sat_max = sat_sub.add_parser("maxsat", help="Exact weighted MaxSAT for <=20 variables")
    p_sat_max.add_argument("file", nargs="?", help="DIMACS .cnf file")
    p_sat_max.add_argument("--cnf", default=None, help="DIMACS text")
    p_sat_max.add_argument("--random", type=int, default=None, metavar="N")
    p_sat_max.add_argument("--ratio", type=float, default=None)
    p_sat_max.add_argument("--weights", default=None, help="Comma-separated clause weights")
    p_sat_max.add_argument("--timeout", type=float, default=10.0)
    p_sat_max.add_argument("--seed", type=int, default=20261030)
    p_sat_max.add_argument("--json-out", default=None)

    p_sat_sweep = sat_sub.add_parser("sweep", help="Empirical random-3-SAT phase-transition sweep")
    p_sat_sweep.add_argument("--sizes", type=_csv_ints, default=[10, 15, 20, 25], help="Comma-separated variable counts")
    p_sat_sweep.add_argument("--ratios", type=_csv_floats, default=[3.0, 3.5, 4.0, 4.26, 4.5, 5.0], help="Comma-separated clause ratios")
    p_sat_sweep.add_argument("--trials", type=int, default=5, help="Instances per cell")
    p_sat_sweep.add_argument("--timeout", type=float, default=2.0, help="Per-instance timeout in seconds")
    p_sat_sweep.add_argument("--seed", type=int, default=20261030, help="Random seed")
    p_sat_sweep.add_argument("--json-out", default=None, help="Write the full result JSON here")

    sub.add_parser("devices", help="List measured QPU noise profiles")
    sub.add_parser("mcp", help="Start the stdio MCP server")

    p_studio = sub.add_parser("studio", help="Start the local CQ-HECS experiment UI")
    p_studio.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p_studio.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    p_studio.add_argument("--root", default=None, help="Repository root for evidence discovery")
    p_studio.add_argument("--no-browser", action="store_true", help="Do not open a browser")

    return parser


def _configure_logging(args: argparse.Namespace) -> None:
    if args.quiet:
        level = logging.ERROR
    elif args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING
    logging.basicConfig(
        level=level, stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args)

    handlers = {
        "version": cmd_version,
        "doctor": cmd_doctor,
        "backend": cmd_backend,
        "profile": cmd_profile,
        "reference": cmd_reference,
        "noise-fit": cmd_noise_fit,
        "sat": cmd_sat,
        "devices": cmd_devices,
        "mcp": cmd_mcp,
        "studio": cmd_studio,
        "selftest": cmd_selftest,
        "analyze": cmd_analyze,
        "run": cmd_run,
        "verify": cmd_verify,
        "expect": cmd_expect,
        "benchmark": cmd_benchmark,
    }
    handler = handlers[args.command]
    try:
        return handler(args)
    except FileNotFoundError as exc:
        LOG.error("%s", exc)
        if args.format == "json":
            _emit_json({"schema_version": JSON_SCHEMA_VERSION, "error": str(exc)})
        return EXIT_USAGE
    except (ValueError, TypeError, HardwareBridgeError) as exc:
        LOG.error("%s", exc)
        if args.format == "json":
            _emit_json({"schema_version": JSON_SCHEMA_VERSION, "error": str(exc)})
        return EXIT_USAGE
    except Exception as exc:  # pragma: no cover - last-resort diagnostics
        LOG.exception("unexpected failure: %s", exc)
        if args.format == "json":
            _emit_json({
                "schema_version": JSON_SCHEMA_VERSION,
                "error": f"{type(exc).__name__}: {exc}",
            })
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())