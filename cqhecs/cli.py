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

    if getattr(args, "profile", None):
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