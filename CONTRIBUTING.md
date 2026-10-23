# Contributing to CQ-HECS

Thank you for considering a contribution. This project is a classical quantum
circuit simulator with an explicit correctness contract, so contributions are
reviewed for **truthfulness first** and performance second.

## Ways to contribute

- **Bug reports** with a minimal reproduction (a QASM circuit or a short Python
  snippet is ideal).
- **Correctness counterexamples**: a circuit where a path returns a wrong
  result, a bound is violated, or an invalid input is silently accepted.
- **Tests** that cover a documented boundary, a typed error, or a
  fail-closed path.
- **Documentation fixes** where a claim no longer matches the code.
- **Performance work** only with a reproducible benchmark and a clear
  methodology (hardware, commit, build type, raw output).

## Development setup

```bash
git clone https://github.com/timfromhcs/CQ-HECS.git
cd CQ-HECS
python -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
```

The Python paths run on the CPU and do not require Vulkan. The native core is
optional:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCQ_BUILD_TESTS=ON
cmake --build build --config Release
```

## Required checks

Run the checks that match your change before opening a pull request.

```bash
# Python
CQ_HECS_REQUIRE_NATIVE=1 pytest tests/ -q

# Native
ctest --test-dir build -C Release --output-on-failure

# Contracts and audits
python scripts/check_version.py
python scripts/verify_no_silent_truncation.py
python scripts/verify_vulkan_shaders.py
python scripts/run_mutation_tests.py
```

On Windows PowerShell, set the environment variable first:

```powershell
$env:CQ_HECS_REQUIRE_NATIVE = "1"
python -m pytest tests/ -q
```

If the native artifact is not built, native-only tests skip visibly. CI's
native jobs set `CQ_HECS_REQUIRE_NATIVE=1` so they cannot skip silently.

## Pull request guidelines

1. Keep changes focused; separate correctness fixes from refactors.
2. Add or update a regression test for every behaviour change.
3. Do not weaken a test to make it pass. If a test encodes a wrong claim, fix
   the claim and the test together, and explain why in the PR.
4. Do not add a benchmark or performance claim without raw output and a
   reproducible command.
5. Update `CHANGELOG.md` for user-visible changes.
6. Describe the exact commands and results you ran in the PR body.

## Correctness and honesty rules

- Invalid input must fail closed with a typed error; it must not be repaired
  silently.
- Unknown gates must be rejected unless a documented contract defines safe
  semantics.
- A bound must name its metric and must not be presented as a bound on a
  different quantity.
- `exact=True` means "no deliberate approximation", not "symbolic arithmetic".
- GPU acceleration must not be claimed without a physical-device measurement.

## Reporting security issues

Do **not** open a public issue for a security vulnerability. Follow the
responsible-disclosure process in [SECURITY.md](SECURITY.md).

## Code style

- Python: standard library style, type hints where they clarify a contract,
  `flake8` fatal-error checks (`E9,F63,F7,F82`).
- C++: C++20, RAII, no silent fallbacks; keep public headers in `include/`.
- Markdown: keep claims linked to evidence in `research/` or `docs/`.

## License

By contributing, you agree that your contribution is licensed under the
Apache License 2.0, the same license as this project.
