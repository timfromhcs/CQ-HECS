"""Schema 1.0 -> 2.0 profile migration and v3 CLI JSON contracts (gate V3-E)."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cqhecs.cli import EXIT_OK, EXIT_USAGE, JSON_SCHEMA_VERSION, main
from cqhecs.hardware_bridge import BackendProfile, InvalidProfileError, create_fake_manila_profile

REPO_ROOT = Path(__file__).resolve().parents[1]
RIGETTI = REPO_ROOT / "research" / "v3" / "evidence" / "openquantum" / "rigetti_cepheus-1-108q"


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def v1_profile_dict():
    """A schema 1.0 document as v2.x wrote it (no 2.0 keys at all)."""
    data = create_fake_manila_profile().to_dict()
    data["schema_version"] = "1.0"
    data.pop("calibration_flags", None)
    data.pop("source_sha256", None)
    return data


class MigrationTests(unittest.TestCase):
    def test_v1_documents_still_load(self):
        profile = BackendProfile.from_dict(v1_profile_dict())
        self.assertEqual(profile.schema_version, "1.0")
        self.assertEqual(profile.calibration_flags, {})
        self.assertIsNone(profile.source_sha256)

    def test_migration_keeps_every_physics_field(self):
        original = BackendProfile.from_dict(v1_profile_dict())
        migrated = original.migrated_to_v2()
        self.assertEqual(migrated.schema_version, "2.0")
        before, after = original.to_dict(), migrated.to_dict()
        before.pop("schema_version")
        after.pop("schema_version")
        self.assertEqual(before, after)
        self.assertEqual(migrated.calibration_flags, {})
        self.assertIsNone(migrated.source_sha256)

    def test_migration_does_not_change_the_noise_model(self):
        original = BackendProfile.from_dict(v1_profile_dict())
        a = original.to_noise_model().to_dict()
        b = original.migrated_to_v2().to_noise_model().to_dict()
        self.assertEqual(a, b)

    def test_v2_is_a_fixed_point_and_round_trips(self):
        migrated = BackendProfile.from_dict(v1_profile_dict()).migrated_to_v2()
        self.assertEqual(migrated.migrated_to_v2().to_dict(), migrated.to_dict())
        self.assertEqual(BackendProfile.from_dict(json.loads(json.dumps(migrated.to_dict()))).to_dict(),
                         migrated.to_dict())

    def test_v1_cannot_carry_v2_fields_and_unknown_versions_are_refused(self):
        data = v1_profile_dict()
        data["source_sha256"] = "0" * 64
        with self.assertRaises(InvalidProfileError):
            BackendProfile.from_dict(data)
        data = v1_profile_dict()
        data["schema_version"] = "3.0"
        with self.assertRaises(InvalidProfileError):
            BackendProfile.from_dict(data)


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_profile_migrate_json_contract(self):
        source = self.tmp / "v1.json"
        source.write_text(json.dumps(v1_profile_dict()), "utf-8")
        target = self.tmp / "v2.json"
        code, out, _err = run_cli("--format", "json", "profile", "migrate", str(source), str(target))
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["schema_version"], JSON_SCHEMA_VERSION)
        self.assertEqual((payload["from_schema"], payload["to_schema"]), ("1.0", "2.0"))
        self.assertEqual(json.loads(target.read_text("utf-8"))["schema_version"], "2.0")

    def test_profile_migrate_accepts_profile_show_output(self):
        code, out, _err = run_cli("--format", "json", "profile", "show", "fake_manila")
        self.assertEqual(code, EXIT_OK)
        source = self.tmp / "show.json"
        source.write_text(out, "utf-8")
        code, _out, _err = run_cli("profile", "migrate", str(source), str(self.tmp / "out.json"))
        self.assertEqual(code, EXIT_OK)

    def test_profile_migrate_refuses_bad_input(self):
        source = self.tmp / "bad.json"
        source.write_text("{\"name\": \"x\"}", "utf-8")
        code, _out, err = run_cli("profile", "migrate", str(source), str(self.tmp / "out.json"))
        self.assertEqual(code, EXIT_USAGE)
        self.assertFalse((self.tmp / "out.json").exists())

    def test_reference_r_io_7_json_contract(self):
        code, out, _err = run_cli("--format", "json", "reference", "run", "--dataset", "r-io-7",
                                  "--data-dir", str(RIGETTI), "--bootstrap", "200")
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        for key in ("dataset_id", "backend", "dataset_sha256", "model", "aggregate", "circuits",
                    "calibration_status", "bit_order"):
            self.assertIn(key, payload)
        self.assertEqual(payload["aggregate"]["n_eval"], 20)
        self.assertEqual(payload["calibration_status"], "absent")

    def test_reference_r_io_7_missing_data_is_a_usage_error(self):
        code, _out, _err = run_cli("reference", "run", "--dataset", "r-io-7", "--data-dir", str(self.tmp / "none"))
        self.assertEqual(code, EXIT_USAGE)

    def test_noise_fit_json_contract(self):
        target = self.tmp / "profile.json"
        code, out, _err = run_cli("--format", "json", "noise-fit", "--data-dir", str(RIGETTI), "--out", str(target))
        self.assertEqual(code, EXIT_OK)
        payload = json.loads(out)
        self.assertEqual(payload["model"], "M-FIT-2")
        self.assertEqual(payload["status"], "EXPLORATORY_POST_HOC")
        self.assertEqual(len(payload["readout"]), 5)
        self.assertEqual(json.loads(target.read_text("utf-8")), payload)
        self.assertTrue(np.isfinite(payload["cx_depolarizing"]["uncorrected"]))

    def test_noise_fit_unknown_dataset_is_refused(self):
        code, _out, _err = run_cli("noise-fit", "--dataset", "r-io-5")
        self.assertEqual(code, EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
