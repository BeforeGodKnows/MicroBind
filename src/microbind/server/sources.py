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
            raise ValueError("ZIP 文件数超过 5000 个的上限")
        for item in z.infolist():
            p = PurePosixPath(item.filename)
            if (
                p.is_absolute()
                or ".." in p.parts
                or "\\" in item.filename
                or ":" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise ValueError("ZIP 包含不允许的路径或符号链接")
            if item.is_dir():
                continue
            if p in seen:
                raise ValueError("ZIP 包含重复文件")
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
                raise ValueError("解压后的源码大小或压缩比超过限制")
            target = destination.joinpath(*p.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(z.read(item))
    manifests = list(destination.rglob("project.yml"))
    if len(manifests) != 1:
        raise ValueError("ZIP 中必须包含且只包含一份 project.yml，格式请参照内置示例")
    manifest = manifests[0]
    config = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("services"), list)
        or not 1 <= len(config["services"]) <= 20
    ):
        raise ValueError("project.yml 的 services 必须包含 1–20 个服务")
    names = set()
    for service in config["services"]:
        if (
            not isinstance(service, dict)
            or not isinstance(service.get("name"), str)
            or not isinstance(service.get("path"), str)
        ):
            raise ValueError("每个服务必须填写 name 和 path")
        if service["name"] in names:
            raise ValueError("服务名称不能重复")
        names.add(service["name"])
        folder = (manifest.parent / service["path"]).resolve()
        if (
            folder != manifest.parent
            and manifest.parent not in folder.parents
            or not folder.is_dir()
        ):
            raise ValueError("服务路径必须指向项目目录内已存在的目录")
        if Path(service["path"]).is_absolute():
            raise ValueError("服务 path 必须使用相对路径")
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
