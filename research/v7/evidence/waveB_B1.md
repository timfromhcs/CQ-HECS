# Wave B / B1: Paths B and C numerical assurance

Date: 2026-11-21. No QPU, credentials, or git mutations.

Commands (from worktree root):
- `python -m pytest tests/test_path_b_numerics.py tests/test_path_c_numerics.py tests/test_path_b_hygiene.py tests/test_path_c_operand_order.py tests/test_path_c_resources.py tests/test_mps_300qbits.py -q` -> 44 passed
- `python -m pytest tests/test_correctness_contracts.py tests/test_reference.py -q` -> 94 passed, 1 skipped
- `python -m pytest tests/test_schema_contracts.py tests/test_schema_migration.py -q` -> see handoff result

TDD note: the first run of the new tests failed (QFT block gate not decomposed; Path B drop
reachable only via product of small weights; observed error exceeded dropped mass due to
round-off). Tests and the written claim were corrected to match observed behaviour rather
than loosening any existing test.

NOT RUN: full pytest suite, native/CTest, web, benchmarks, n > 7 dense Path C comparison.

Details and proven-vs-tested split: research/v7/NUMERICS_B_C.md.
