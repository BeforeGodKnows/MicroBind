"""Build a deterministic source archive from explicitly allowed repository paths."""

import argparse
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "README.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "compose.yml",
    "compose.lab.yml",
    "pyproject.toml",
}
SOURCE_DIRS = {
    ".github",
    "config",
    "demo",
    "deploy",
    "docs",
    "frontend",
    "samples",
    "scripts",
    "src",
    "tests",
    "tools",
}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-neo",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "target",
    "out",
    "artifacts",
    "dist",
    "node_modules",
    "secrets",
    "test-results",
    "playwright-report",
}
SOURCE_SUFFIXES = {
    ".conf",
    ".py",
    ".java",
    ".xml",
    ".sql",
    ".properties",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".md",
    ".txt",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".sh",
    ".lock",
}
SOURCE_NAMES = {"LICENSE", "NOTICE", "Dockerfile", ".gitignore", ".dockerignore"}


def source_files(root: Path, output: Path):
    """Yield release inputs, rejecting symlinks inside the selected source tree."""
    output = output.resolve()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if EXCLUDED_DIRS.intersection(relative.parts) or any(
            part.endswith((".egg-info", ".dist-info")) for part in relative.parts
        ):
            continue
        if path == output or output in path.parents:
            continue
        if len(relative.parts) == 1:
            selected = relative.name in ROOT_FILES
        else:
            selected = relative.parts[0] in SOURCE_DIRS and (
                path.suffix in SOURCE_SUFFIXES
                or path.name in SOURCE_NAMES
                or (relative.parts[0] == "deploy" and path.name.startswith("Dockerfile."))
            )
        if not selected or path.name == ".env" or path.name.startswith(".env."):
            if relative.as_posix() != ".env.example":
                continue
        if path.is_symlink():
            raise ValueError(f"Release inputs must not be symlinks: {relative}")
        if path.is_file():
            yield path, relative.as_posix()


def repository_revision(root: Path):
    if not (root / ".git").exists():
        return None, None
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = bool(
        subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()
    )
    return revision, dirty


def build_archive(root: Path, output: Path):
    root = root.resolve()
    output = output.resolve()
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    output.mkdir(parents=True, exist_ok=True)
    files = [(relative, path.read_bytes()) for path, relative in source_files(root, output)]
    revision, dirty = repository_revision(root)
    manifest = {
        "schema_version": "1.0",
        "version": version,
        "git_commit": revision,
        "git_dirty": dirty,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in files},
    }
    files.append(
        (
            "release-manifest.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
        )
    )
    archive = output / f"MicroBind_v{version}.zip"
    temporary = archive.with_suffix(".zip.tmp")
    with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=9) as package:
        for name, data in files:
            entry = ZipInfo("microbind/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (0o100755 if name.endswith(".sh") else 0o100644) << 16
            entry.compress_type = ZIP_DEFLATED
            package.writestr(entry, data, compresslevel=9)
    temporary.replace(archive)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / f"MicroBind_v{version}_SHA256.txt").write_text(f"{checksum}  {archive.name}\n")
    return {
        "archive": str(archive),
        "source_files": len(manifest["files"]),
        "size_bytes": archive.stat().st_size,
        "sha256": checksum,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_archive(ROOT, args.out), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
