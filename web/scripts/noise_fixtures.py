"""Exact M-FIT-2 distributions (density matrix) for the web noise tests."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cqhecs.device_profiles import list_profiles, noise_model  # noqa: E402
from cqhecs.openquantum_suite import build_suite, simulate  # noqa: E402

OUT = ROOT / "web" / "tests" / "fixtures" / "device_noise.json"
SUITE = ROOT / "research" / "v3" / "openquantum_suite"


def only_cx_two_qubit(qasm: str) -> bool:
    two_qubit = re.findall(r"^\s*([a-z]\w*)(?:\([^)]*\))?\s+q\[\d+\]\s*,\s*q\[\d+\]", qasm, re.M)
    return all(name == "cx" for name in two_qubit)


def main() -> None:
    files = {p.name.split("_", 1)[0]: p for p in SUITE.glob("OQ-*.qasm")}
    cases = []
    for profile in list_profiles():
        for job in build_suite():
            qasm = files[job.job_id].read_text("utf-8")
            if job.job_id not in ("OQ-02", "OQ-03", "OQ-06", "OQ-09", "OQ-13", "OQ-21") or not only_cx_two_qubit(qasm):
                continue
            probs = simulate(job, noise_model(profile["id"], job.instructions(), job.num_qubits))
            cases.append({"profile": profile["id"], "job": job.job_id, "qasm": qasm,
                          "num_qubits": job.num_qubits, "probabilities": [float(p) for p in probs]})
    OUT.write_text(json.dumps({"generator": "cqhecs NoisyDensityMatrixBackend + device_profiles", "cases": cases}) + "\n", "utf-8")
    print(f"wrote {len(cases)} cases")


if __name__ == "__main__":
    main()
