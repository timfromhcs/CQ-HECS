"""Packaging tooling contracts (W14 / T6-07).

Fast, offline tests of the scripts that inspect, archive, hash and inventory release artifacts,
plus static checks of the packaging metadata and workflow. They do NOT build a wheel, a
PyInstaller folder or a native binary; the real builds are run by scripts/package_*.py|ps1 and
.github/workflows/package.yml and recorded in research/v7/evidence/waveC_C2.md.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


archive = _load("package_archive")
inspect_mod = _load("package_inspect")
manifest = _load("make_manifest")
sbom = _load("sbom_cyclonedx")


# --------------------------------------------------------------------------- archive

def _tree(tmp: Path) -> Path:
    src = tmp / "app"
    (src / "sub").mkdir(parents=True)
    (src / "b.txt").write_text("b")
    (src / "a.txt").write_text("a")
    (src / "sub" / "c.bin").write_bytes(b"\x00\x01")
    return src


def test_zip_is_deterministic_sorted_and_forward_slashed(tmp_path):
    src = _tree(tmp_path)
    z1, z2 = tmp_path / "1.zip", tmp_path / "2.zip"
    archive.make_zip(src, z1, "app")
    # touch mtimes: a different build time must not change the archive
    for p in src.rglob("*"):
        if p.is_file():
            p.touch()
    archive.make_zip(src, z2, "app")
    assert z1.read_bytes() == z2.read_bytes()
    names = zipfile.ZipFile(z1).namelist()
    assert names == sorted(names) == ["app/a.txt", "app/b.txt", "app/sub/c.bin"]
    assert all("\\" not in n for n in names)
    assert {zi.date_time for zi in zipfile.ZipFile(z1).infolist()} == {archive.FIXED_TIME}


def _sdist(path: Path, mtime: float) -> None:
    with tarfile.open(path, "w:gz") as t:
        for name, data in (("pkg-1/z.txt", b"z"), ("pkg-1/a.txt", b"a")):
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime, ti.uid, ti.uname = len(data), mtime, 1000, "someone"
            t.addfile(ti, io.BytesIO(data))


def test_targz_normalization_removes_build_time_and_owner(tmp_path):
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    _sdist(a, 1_700_000_000)
    _sdist(b, 1_800_000_000)
    assert a.read_bytes() != b.read_bytes()
    archive.normalize_targz(a)
    archive.normalize_targz(b)
    assert a.read_bytes() == b.read_bytes()
    with tarfile.open(a) as t:
        assert [m.name for m in t.getmembers()] == ["pkg-1/a.txt", "pkg-1/z.txt"]
        assert all(m.uid == 0 and m.uname == "" for m in t.getmembers())


# --------------------------------------------------------------------------- manifest

def test_manifest_roundtrip_and_tamper_detection(tmp_path):
    (tmp_path / "x.whl").write_bytes(b"wheel")
    (tmp_path / "y.zip").write_bytes(b"zip")
    entries = manifest.collect(tmp_path)
    text = manifest.render(entries)
    assert text == "".join(f"{hashlib.sha256(d).hexdigest()}  {n}\n" for n, d in (("x.whl", b"wheel"), ("y.zip", b"zip")))
    mf = tmp_path / "SHA256SUMS"
    mf.write_text(text, encoding="ascii")
    assert manifest.verify(tmp_path, mf) == []
    (tmp_path / "y.zip").write_bytes(b"tampered")
    assert manifest.verify(tmp_path, mf) == ["MISMATCH: y.zip"]
    (tmp_path / "z.txt").write_text("late")
    assert "unlisted file: z.txt" in manifest.verify(tmp_path, mf)
    (tmp_path / "x.whl").unlink()
    assert "missing: x.whl" in manifest.verify(tmp_path, mf)


def test_manifest_rejects_malformed_lines():
    with pytest.raises(ValueError):
        manifest.parse("not-a-hash  file\n")


# --------------------------------------------------------------------------- inspect

def _wheel(path: Path, extra: dict | None = None, drop: tuple[str, ...] = ()) -> Path:
    members = {n: b"x = 1\n" for n in inspect_mod.REQUIRED_WHEEL}
    members.update({
        "cqhecs-9.0.0.dist-info/METADATA": b"Name: cqhecs\n",
        "cqhecs-9.0.0.dist-info/entry_points.txt": b"[console_scripts]\n",
        "cqhecs-9.0.0.dist-info/RECORD": b"",
        "cqhecs-9.0.0.dist-info/licenses/LICENSE": b"Apache",
    })
    members.update(extra or {})
    for d in drop:
        members.pop(d, None)
    with zipfile.ZipFile(path, "w") as z:
        for n, d in members.items():
            z.writestr(n, d)
    return path


def test_inspect_accepts_a_complete_clean_wheel(tmp_path):
    assert inspect_mod.inspect(_wheel(tmp_path / "ok.whl"))["status"] == "PASS"


@pytest.mark.parametrize("extra,needle", [
    ({"cqhecs/.env": b"X=1"}, "dotenv"),
    ({"cqhecs/provider_credentials.json": b"{}"}, "credential"),
    ({"research/v7/evidence/raw.json": b"{}"}, "research"),
    ({"cqhecs/__pycache__/a.pyc": b""}, "bytecode"),
    ({"tests/test_x.py": b""}, "non-runtime"),
    ({"cqhecs/note.txt": rb"saved at C:\Users\someone\proj\out.json"}, "developer-machine path"),
    ({"cqhecs/note2.txt": b"-----BEGIN RSA PRIVATE KEY-----\nabc"}, "credential-shaped"),
    ({"cqhecs/note3.txt": b"token ghp_" + b"A" * 36}, "credential-shaped"),
])
def test_inspect_flags_forbidden_content(tmp_path, extra, needle):
    rep = inspect_mod.inspect(_wheel(tmp_path / "bad.whl", extra=extra))
    assert rep["status"] == "FAIL"
    assert any(needle in f["what"] for f in rep["findings"]), rep["findings"]


@pytest.mark.parametrize("missing", ["cqhecs/studio/static/qg.js", "cqhecs/studio/data/dataset.json"])
def test_inspect_requires_studio_assets(tmp_path, missing):
    rep = inspect_mod.inspect(_wheel(tmp_path / "w.whl", drop=(missing,)))
    assert rep["status"] == "FAIL"
    assert any(f["where"] == missing for f in rep["findings"])


def test_inspect_unreadable_archive_is_a_fail_not_a_skip(tmp_path):
    bad = tmp_path / "broken.whl"
    bad.write_bytes(b"not a zip")
    assert inspect_mod.inspect(bad)["status"] == "FAIL"


# --------------------------------------------------------------------------- sbom

def _dist(root: Path, name: str, version: str, lic_lines: str, top: str | None = None) -> None:
    d = root / f"{name}-{version}.dist-info"
    d.mkdir(parents=True)
    (d / "METADATA").write_text(f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n{lic_lines}", encoding="utf-8")
    if top:
        (d / "top_level.txt").write_text(top + "\n")


def test_sbom_never_guesses_a_licence(tmp_path):
    sp = tmp_path / "sp"
    _dist(sp, "alpha", "1.0", "License-Expression: MIT\n")
    _dist(sp, "beta", "2.0", "")
    _dist(sp, "gamma", "3.0", "Classifier: License :: OSI Approved :: BSD License\n")
    comps = sbom.collect([sp], exclude=[])
    by = {c["name"]: c for c in comps}
    assert by["alpha"]["licence"] == "MIT" and by["alpha"]["licence_basis"] == "metadata License-Expression"
    assert by["beta"]["licence"] == "UNVERIFIED"
    assert by["gamma"]["licence_basis"] == "metadata Trove classifier"
    bom = sbom.build("t", "1", comps, [], "Apache-2.0", None)
    lic = {c["name"]: c["licenses"][0] for c in bom["components"]}
    assert lic["alpha"] == {"expression": "MIT"}
    assert lic["beta"] == {"license": {"name": "UNVERIFIED"}}  # a name, never promoted to an SPDX id


def test_sbom_is_deterministic_and_has_no_clock(tmp_path):
    sp = tmp_path / "sp"
    _dist(sp, "alpha", "1.0", "License-Expression: MIT\n")
    a = sbom.build("t", "1", sbom.collect([sp], []), [], "Apache-2.0", None)
    b = sbom.build("t", "1", sbom.collect([sp], []), [], "Apache-2.0", None)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert "timestamp" not in a["metadata"]
    assert a["bomFormat"] == "CycloneDX" and a["specVersion"] == "1.5"
    assert re.fullmatch(r"urn:uuid:[0-9a-f-]{36}", a["serialNumber"])


def test_sbom_bundle_filter_lists_only_bundled_distributions(tmp_path):
    sp, bundle = tmp_path / "sp", tmp_path / "bundle"
    _dist(sp, "inside", "1.0", "License-Expression: MIT\n", top="inside_mod")
    _dist(sp, "outside", "1.0", "License-Expression: MIT\n", top="outside_mod")
    bundle.mkdir()
    (bundle / "inside_mod").mkdir()
    present = sbom.bundled_names(bundle, None)
    assert [c["name"] for c in sbom.collect([sp], [], present)] == ["inside"]


def test_sbom_records_artifact_hash(tmp_path):
    art = tmp_path / "a.whl"
    art.write_bytes(b"abc")
    bom = sbom.build("t", "1", [], [art], "Apache-2.0", "2026-01-01T00:00:00Z")
    assert bom["metadata"]["component"]["hashes"] == [{"alg": "SHA-256", "content": hashlib.sha256(b"abc").hexdigest()}]
    assert bom["metadata"]["timestamp"] == "2026-01-01T00:00:00Z"


# --------------------------------------------------------------------------- static metadata

def test_package_data_and_manifest_cover_studio_assets():
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"cqhecs.studio" = ["static/*", "data/*"]' in py
    man = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert "recursive-include cqhecs/studio/static" in man and "include schemas/*.json" in man
    for p in ("prune research", "prune web"):
        assert p in man
    assert (ROOT / "cqhecs" / "studio" / "static" / "qg.js").is_file()
    assert (ROOT / "schemas" / "studio.openapi.json").is_file()


def test_pyproject_version_is_not_touched_by_packaging_metadata():
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "\d+\.\d+\.\d+"$', py, re.M)
    assert 'license-files = ["LICENSE"]' in py


def test_package_workflow_is_pinned_least_privilege_and_does_not_publish():
    text = (ROOT / ".github" / "workflows" / "package.yml").read_text(encoding="utf-8")
    uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", text, re.M)
    assert uses, "no actions found"
    for u in uses:
        assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", u), f"action not pinned to a commit SHA: {u}"
    assert re.search(r"^permissions:\n\s+contents: read\s*$", text, re.M)
    assert "contents: write" not in text and "id-token" not in text and "secrets." not in text
    for forbidden in ("action-gh-release", "gh release", "git push", "git tag", "twine", "pypi-publish"):
        assert forbidden not in text, forbidden
    assert "pull_request_target" not in text


def test_release_workflow_is_unchanged_in_trigger_semantics():
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "tags:" in text and "contents: read" in text


def test_build_exe_is_onedir_and_uses_the_smoke_driver():
    ps = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8")
    assert "--onedir" in ps and "--onefile" not in ps
    assert "package_smoke.py" in ps and "package_archive.py" in ps
    assert "single-file" not in ps.replace("One-file mode is intentionally not used", "").lower().replace("not a single-file app", "")


def test_native_packaging_names_are_exact():
    ps = (ROOT / "scripts" / "package_native.ps1").read_text(encoding="utf-8")
    assert '"cq-hecs-cpu"' in ps and '"cq-hecs-vulkan"' in ps
    assert "CQ_ENABLE_VULKAN=$VulkanFlag" in ps
    assert 'Build-Lane "cpu" "OFF"' in ps and 'Build-Lane "vulkan" "ON"' in ps


def test_native_package_script_discovers_the_visual_studio_generator():
    """Regression: windows-latest moved to Visual Studio 2026 and a fixed "17 2022" could not configure."""
    ps = (ROOT / "scripts" / "package_native.ps1").read_text(encoding="utf-8")
    assert '[string]$Generator = ""' in ps  # no hard-coded default
    assert "function Resolve-CMakeGenerator" in ps and "$Generator = Resolve-CMakeGenerator $Generator" in ps
    assert "CQ_CMAKE_GENERATOR" in ps  # explicit override
    assert "vswhere.exe" in ps and "Visual Studio 18 2026" in ps and "Visual Studio 17 2022" in ps
    assert "-G $Generator" in ps


def test_smoke_driver_scrubs_import_path_and_credentials(monkeypatch):
    smoke = _load("package_smoke")
    monkeypatch.setenv("PYTHONPATH", "/some/repo")
    monkeypatch.setenv("CQ_HECS_STUDIO_TOKEN", "x")
    monkeypatch.setenv("OPENQUANTUM_API_KEY", "x")
    env = smoke.clean_env()
    assert "PYTHONPATH" not in env and "CQ_HECS_STUDIO_TOKEN" not in env and "OPENQUANTUM_API_KEY" not in env
    assert smoke.studio_env(env)["CQ_HECS_STUDIO_TOKEN"] == smoke.STUDIO_TOKEN
    assert smoke.REPO_ROOT == ROOT


def test_port_is_free_after_a_stopped_server_leaves_time_wait_but_not_while_listening():
    """Regression: studio_health_and_stop failed on Linux with Errno 98 after the tree kill."""
    import socket

    smoke = _load("package_smoke")
    srv = socket.socket()
    if os.name != "nt":
        # Like http.server (allow_reuse_address): on Linux the TIME_WAIT sockets inherit the creating
        # listener's SO_REUSEADDR, which is what lets the fresh bind in port_is_free succeed.
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    assert smoke.port_is_free(port) is False  # a live listener must still be detected
    cli = socket.create_connection(("127.0.0.1", port))
    conn, _ = srv.accept()
    conn.close()  # server side closes first: its connection sits in TIME_WAIT on `port`
    cli.close()
    srv.close()
    assert smoke.port_is_free(port) is True


def test_inspect_flags_this_machines_path_even_in_a_binary(tmp_path):
    home = str(Path.home()).encode()
    rep = inspect_mod.inspect(_wheel(tmp_path / "leak.whl", extra={"cqhecs/x.pyd": b"\x00build at " + home + b"\x00"}))
    assert rep["status"] == "FAIL"
    assert any("build machine" in f["what"] for f in rep["findings"])


def test_inspect_bundle_dir_ignores_upstream_paths_in_third_party_files_only(tmp_path):
    root = tmp_path / "cq-hecs"
    (root / "_internal" / "numpy-2.dist-info").mkdir(parents=True)
    (root / "_internal" / "numpy-2.dist-info" / "DELVEWHEEL").write_text(r"built in C:\Users\runneradmin\x")
    (root / "_internal" / "cqhecs").mkdir()
    (root / "_internal" / "cqhecs" / "ok.txt").write_text("fine")
    assert inspect_mod.inspect(root)["status"] == "PASS"
    (root / "_internal" / "cqhecs" / "bad.txt").write_text(r"C:\Users\someone\proj")
    assert inspect_mod.inspect(root)["status"] == "FAIL"


def test_notices_copy_licence_files_only_for_bundled_distributions(tmp_path):
    notices = _load("package_notices")
    sp, app = tmp_path / "sp", tmp_path / "app"
    _dist(sp, "inside", "1.0", "License-Expression: MIT\n", top="inside_mod")
    (sp / "inside-1.0.dist-info" / "licenses").mkdir()
    (sp / "inside-1.0.dist-info" / "licenses" / "LICENSE").write_text("MIT text")
    _dist(sp, "bare", "2.0", "License-Expression: MIT\n", top="bare_mod")
    _dist(sp, "outside", "3.0", "License-Expression: MIT\n", top="outside_mod")
    (app / "_internal" / "inside_mod").mkdir(parents=True)
    (app / "_internal" / "bare_mod").mkdir()
    lic = tmp_path / "LICENSE"
    lic.write_text("Apache")
    assert notices.main(["--app-dir", str(app), "--metadata-root", str(sp), "--licence-file", str(lic)]) == 0
    text = (app / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
    assert "inside 1.0" in text and "outside" not in text
    assert (app / "licences" / "inside-1.0" / "LICENSE").read_text() == "MIT text"
    # a distribution that ships no licence file is reported as such, never given an invented one
    assert "bare 2.0" in text and "NO LICENCE FILE" in text
    assert (app / "LICENSE").read_text() == "Apache"


# --------------------------------------------------------------------------- E4: build identity, SBOM closure

SHA = "a" * 40


def test_build_info_is_deterministic_and_uses_source_date_epoch():
    a = archive.build_info_bytes("7.0.0", SHA, "github-actions:r:w", "1767225600")
    assert a == archive.build_info_bytes("7.0.0", SHA, "github-actions:r:w", "1767225600")
    doc = json.loads(a)
    assert doc["build_date"] == "2026-01-01T00:00:00Z" and doc["source_sha"] == SHA
    assert doc["version"] == "7.0.0" and doc["builder"] == "github-actions:r:w"
    with pytest.raises(ValueError):
        archive.build_info_bytes("7.0.0", "abc", "x")


def test_zip_with_build_info_is_reproducible_and_sorted(tmp_path):
    src = _tree(tmp_path)
    info = {"BUILD-INFO.json": archive.build_info_bytes("7.0.0", SHA, "local", "1767225600")}
    z1, z2 = tmp_path / "1.zip", tmp_path / "2.zip"
    archive.make_zip(src, z1, "app", info)
    archive.make_zip(src, z2, "app", info)
    assert z1.read_bytes() == z2.read_bytes()
    names = zipfile.ZipFile(z1).namelist()
    assert names == sorted(names) and "app/BUILD-INFO.json" in names
    assert json.loads(zipfile.ZipFile(z1).read("app/BUILD-INFO.json"))["source_sha"] == SHA
    # default call is unchanged: no BUILD-INFO unless asked
    archive.make_zip(src, tmp_path / "3.zip", "app")
    assert "app/BUILD-INFO.json" not in zipfile.ZipFile(tmp_path / "3.zip").namelist()


def test_build_info_refuses_to_overwrite_a_source_file(tmp_path):
    src = _tree(tmp_path)
    (src / "BUILD-INFO.json").write_text("{}")
    with pytest.raises(ValueError):
        archive.make_zip(src, tmp_path / "x.zip", "app", {"BUILD-INFO.json": b"{}"})


def test_cli_embeds_build_info_from_env_but_never_touches_targz(tmp_path, monkeypatch):
    src = _tree(tmp_path)
    monkeypatch.setenv("CQHECS_SOURCE_SHA", SHA)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    out = tmp_path / "o.zip"
    assert archive.main(["--src", str(src), "--out", str(out), "--root-name", "app", "--build-version", "7.0.0"]) == 0
    assert "app/BUILD-INFO.json" in zipfile.ZipFile(out).namelist()
    out2 = tmp_path / "o2.zip"
    assert archive.main(["--src", str(src), "--out", str(out2), "--root-name", "app", "--no-build-info"]) == 0
    assert "app/BUILD-INFO.json" not in zipfile.ZipFile(out2).namelist()
    # sdist normalisation is independent of build identity (wheel/sdist stay reproducible)
    a, b = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    _sdist(a, 1.0)
    _sdist(b, 2.0)
    archive.normalize_targz(a)
    archive.normalize_targz(b)
    assert a.read_bytes() == b.read_bytes()


def _fixture_venv(sp: Path) -> None:
    """A fake build venv: the wheel's real closure plus venv tooling that must not be listed."""
    _dist(sp, "cqhecs", "7.0.0", "License-Expression: Apache-2.0\nRequires-Dist: numpy>=1.24\nRequires-Dist: qiskit>=0.45\n"
                                 "Requires-Dist: python-sat>=1.8; extra == 'sat'\n")
    _dist(sp, "numpy", "2.0", "License-Expression: BSD-3-Clause\n")
    _dist(sp, "qiskit", "2.0", "License-Expression: Apache-2.0\nRequires-Dist: rustworkx>=0.15\n"
                               "Requires-Dist: numpy>=1.17\nRequires-Dist: symengine>=0.11; platform_system != 'Windows'\n")
    _dist(sp, "rustworkx", "0.16", "License-Expression: Apache-2.0\nRequires-Dist: numpy<3,>=1.16\n")
    _dist(sp, "setuptools", "70", "License-Expression: MIT\nRequires-Dist: jaraco.text>=3.7; extra == 'core'\n")
    _dist(sp, "jaraco.text", "3.12", "License-Expression: MIT\nRequires-Dist: autocommand\n")
    _dist(sp, "autocommand", "2.2", "License: LGPL-3.0-only\n")
    _dist(sp, "wheel", "0.43", "License-Expression: MIT\n")
    _dist(sp, "zipp", "3.19", "License-Expression: MIT\n")
    _dist(sp, "python-sat", "1.8", "License-Expression: MIT\n")  # extra only: not a runtime dependency


def test_sbom_closure_lists_only_the_wheels_runtime_dependencies(tmp_path):
    sp = tmp_path / "sp"
    _fixture_venv(sp)
    everything = sbom.collect([sp], [])
    clo = sbom.dependency_closure(everything, ["cqhecs"])
    names = [c["name"] for c in clo["components"]]
    assert names == ["numpy", "qiskit", "rustworkx"]
    assert "cqhecs" not in names  # root itself is never a component
    assert clo["not_installed"] == ["symengine"]  # conditional dep absent from the venv is recorded, not invented
    for tooling in ("setuptools", "wheel", "jaraco.text", "autocommand", "zipp", "python-sat"):
        assert tooling not in names


def test_sbom_closure_cli_and_missing_root_fails_closed(tmp_path, monkeypatch):
    sp = tmp_path / "sp"
    _fixture_venv(sp)
    out = tmp_path / "w.cdx.json"
    monkeypatch.setenv("CQHECS_SOURCE_SHA", SHA)
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    assert sbom.main(["--name", "cqhecs", "--version", "7.0.0", "--metadata-root", str(sp),
                      "--closure-of", "cqhecs", "--out", str(out)]) == 0
    bom = json.loads(out.read_text(encoding="utf-8"))
    assert [c["name"] for c in bom["components"]] == ["numpy", "qiskit", "rustworkx"]
    root = bom["metadata"]["component"]
    props = {p["name"]: p["value"] for p in root["properties"]}
    assert props["cqhecs:source-revision"] == SHA
    assert props["cqhecs:closure-not-installed"] == "symengine"
    assert root["externalReferences"] == [{"type": "vcs", "url": f"https://github.com/owner/repo/commit/{SHA}"}]
    with pytest.raises(SystemExit):
        sbom.main(["--name", "x", "--version", "1", "--metadata-root", str(sp), "--closure-of", "nope",
                   "--out", str(tmp_path / "n.json")])


def test_sbom_without_revision_is_unchanged(tmp_path):
    sp = tmp_path / "sp"
    _dist(sp, "alpha", "1.0", "License-Expression: MIT\n")
    bom = sbom.build("t", "1", sbom.collect([sp], []), [], "Apache-2.0", None)
    assert "externalReferences" not in bom["metadata"]["component"]
    assert all(p["name"] != "cqhecs:source-revision" for p in bom["metadata"]["component"]["properties"])
    with_rev = sbom.build("t", "1", sbom.collect([sp], []), [], "Apache-2.0", None, SHA)
    assert with_rev["serialNumber"] != bom["serialNumber"]


def test_sbom_rejects_malformed_revision(tmp_path):
    sp = tmp_path / "sp"
    _dist(sp, "alpha", "1.0", "License-Expression: MIT\n")
    with pytest.raises(SystemExit):
        sbom.main(["--name", "t", "--version", "1", "--metadata-root", str(sp), "--source-revision", "main",
                   "--out", str(tmp_path / "o.json")])


def test_sbom_closure_versions_match_metadata_and_unstated_licence_stays_unverified(tmp_path):
    sp = tmp_path / "sp"
    _dist(sp, "cqhecs", "7.0.0", "License-Expression: Apache-2.0\nRequires-Dist: numpy>=1.24\nRequires-Dist: qiskit>=0.45\n")
    _dist(sp, "numpy", "2.0", "License-Expression: BSD-3-Clause\n")
    _dist(sp, "qiskit", "2.0", "License-Expression: Apache-2.0\nRequires-Dist: rustworkx>=0.15\n")
    _dist(sp, "rustworkx", "0.16", "Requires-Dist: numpy<3,>=1.16\n")  # metadata states no licence
    out = tmp_path / "w.cdx.json"
    assert sbom.main(["--name", "cqhecs", "--version", "7.0.0", "--metadata-root", str(sp),
                      "--closure-of", "cqhecs", "--out", str(out)]) == 0
    bom = json.loads(out.read_text(encoding="utf-8"))
    got = {c["name"]: (c["version"], c["licenses"]) for c in bom["components"]}
    assert {k: v[0] for k, v in got.items()} == {"numpy": "2.0", "qiskit": "2.0", "rustworkx": "0.16"}
    assert got["rustworkx"][1] == [{"license": {"name": "UNVERIFIED"}}]  # never guessed, never an SPDX id
    assert got["numpy"][1] == [{"expression": "BSD-3-Clause"}]
