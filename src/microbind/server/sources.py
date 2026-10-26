"""Source-only ZIP intake. Uploaded projects are never built or executed."""

import stat
import zipfile
from pathlib import Path, PurePosixPath

import yaml

ALLOWED = {
    ".java",
    ".xml",
    ".sql",
    ".yml",
    ".yaml",
    ".properties",
    ".md",
    ".txt",
    ".json",
    ".gradle",
    ".kts",
}


def unpack(archive: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=False)
    total = 0
    seen = set()
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) > 5000:
            raise ValueError("ZIP 最多 5000 个文件")
        for item in z.infolist():
            p = PurePosixPath(item.filename)
            if (
                p.is_absolute()
                or ".." in p.parts
                or "\\" in item.filename
                or ":" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise ValueError("ZIP 含非法路径或软链接")
            if item.is_dir():
                continue
            if p in seen:
                raise ValueError("ZIP 含重复文件")
            seen.add(p)
            if any(x.startswith(".") or x in {"target", "node_modules"} for x in p.parts):
                continue
            if p.suffix.lower() not in ALLOWED:
                continue
            total += item.file_size
            if (
                item.file_size > 2 * 1024 * 1024
                or total > 100 * 1024 * 1024
                or item.file_size > max(item.compress_size, 1) * 200
            ):
                raise ValueError("源码体积或压缩比例超过限制")
            target = destination.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
    manifests = list(destination.rglob("project.yml"))
    if len(manifests) != 1:
        raise ValueError("ZIP 必须含唯一 project.yml；格式参见内置示例")
    manifest = manifests[0]
    config = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("services"), list)
        or not 1 <= len(config["services"]) <= 20
    ):
        raise ValueError("project.yml 需要 1–20 个 services")
    names = set()
    for service in config["services"]:
        if (
            not isinstance(service, dict)
            or not isinstance(service.get("name"), str)
            or not isinstance(service.get("path"), str)
        ):
            raise ValueError("service 必须提供 name 和 path")
        if service["name"] in names:
            raise ValueError("service 名称重复")
        names.add(service["name"])
        folder = (manifest.parent / service["path"]).resolve()
        if (
            folder != manifest.parent
            and manifest.parent not in folder.parents
            or not folder.is_dir()
        ):
            raise ValueError("service path 必须在项目目录内且存在")
        if Path(service["path"]).is_absolute():
            raise ValueError("service path 需要相对路径")
    from ..project_config import validate

    validate(manifest)
    analysis = config.get("analysis", {})
    config["analysis"] = {
        "max_depth": min(30, analysis.get("max_depth", 30)),
        "max_states": min(128, analysis.get("max_states", 128)),
    }
    manifest.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return manifest
