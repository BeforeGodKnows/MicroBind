"""Publication boundaries: credentials and generated files stay outside source ZIPs."""

import hashlib
import importlib.util
import json
import shlex
from pathlib import Path
from zipfile import ZipFile

import pytest

spec = importlib.util.spec_from_file_location(
    "package_release", Path(__file__).parents[1] / "tools/package_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "0.3.4"\n')
    (root / "README.md").write_text("Example project\n")
    return root


def test_package_excludes_local_state_and_preserves_license(tmp_path):
    root = project(tmp_path)
    excluded = [
        ".env",
        ".env.local",
        "secrets/api_token.txt",
        "out/report.json",
        "frontend/node_modules/lib/index.ts",
        "src/.env.production",
        "src/private.key",
        "src/package.egg-info/requires.txt",
        "src/package.dist-info/direct_url.json",
        "src/__pycache__/state.pyc",
        "notes.txt",
    ]
    included = [
        ".env.example",
        "src/app.py",
        "samples/fixture/upstream/LICENSE",
        "samples/fixture/provenance.json",
        "deploy/Dockerfile.backend",
    ]
    for name in excluded + included:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name + "\n")
    result = release.build_archive(root, root / "out/release")
    with ZipFile(result["archive"]) as package:
        names = set(package.namelist())
        assert not names.intersection("microbind/" + name for name in excluded)
        assert all("microbind/" + name in names for name in included)
        manifest = json.loads(package.read("microbind/release-manifest.json"))
        assert manifest["git_commit"] is None
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(package.read("microbind/" + name)).hexdigest() == digest


def test_package_is_repeatable_and_does_not_include_itself(tmp_path):
    root = project(tmp_path)
    first = release.build_archive(root, root / "out/release")
    second = release.build_archive(root, root / "out/release")
    assert first["sha256"] == second["sha256"]


def test_package_rejects_symlink_to_external_file(tmp_path):
    root = project(tmp_path)
    secret = tmp_path / "external.py"
    secret.write_text("private data")
    (root / "src").mkdir()
    (root / "src/link.py").symlink_to(secret)
    with pytest.raises(ValueError, match="symlink"):
        release.build_archive(root, root / "out/release")


def test_release_contains_local_docker_build_inputs(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = release.build_archive(root, tmp_path / "release")
    with ZipFile(result["archive"]) as package:
        names = {name.removeprefix("microbind/") for name in package.namelist()}
    for dockerfile in (root / "deploy").glob("Dockerfile.*"):
        for line in dockerfile.read_text().splitlines():
            if not line.startswith("COPY "):
                continue
            fields = shlex.split(line)
            if fields[1].startswith("--from="):
                continue
            for source in fields[1:-1]:
                source = source.rstrip("/")
                assert source in names or any(name.startswith(source + "/") for name in names), (
                    f"{dockerfile.name}: COPY input missing from release: {source}"
                )
