"""Configuration diagnostics shared by CLI and source upload."""

from pathlib import Path

import yaml


def validate(path):
    path = Path(path).resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("services"), list)
        or not 1 <= len(data["services"]) <= 20
    ):
        raise ValueError("project.yml: services 必须包含 1–20 个服务")
    seen = set()
    for i, service in enumerate(data["services"]):
        where = f"project.yml: services[{i}]"
        if (
            not isinstance(service, dict)
            or not isinstance(service.get("name"), str)
            or not isinstance(service.get("path"), str)
        ):
            raise ValueError(where + " 需要字符串 name 和 path")
        if service["name"] in seen:
            raise ValueError(where + " name 重复")
        seen.add(service["name"])
        folder = (path.parent / service["path"]).resolve()
        if (
            Path(service["path"]).is_absolute()
            or path.parent != folder
            and path.parent not in folder.parents
            or not folder.is_dir()
        ):
            raise ValueError(where + ".path 必须是 project.yml 目录内已存在的相对目录")
        if "exposed" in service and not isinstance(service["exposed"], bool):
            raise ValueError(where + ".exposed 使用 true 或 false，不要加引号")
        if "include_classes" in service and (
            not isinstance(service["include_classes"], list)
            or not all(isinstance(x, str) for x in service["include_classes"])
        ):
            raise ValueError(where + ".include_classes 需要完整类名列表")
    for field in ["policies", "trusted_identity", "repair", "analysis"]:
        if not isinstance(data.get(field, {}), dict):
            raise ValueError("project.yml: " + field + " 需要键值映射")
    for method, kind in data.get("trusted_identity", {}).items():
        if kind not in {"user", "tenant", "role"}:
            raise ValueError("trusted_identity." + method + " 只能为 user、tenant 或 role")
    for key, maximum, default in [("max_depth", 30, 30), ("max_states", 128, 128)]:
        value = data.get("analysis", {}).get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("analysis." + key + " 必须为正整数")
    return data


def diagnose(path):
    data = validate(path)
    from .frontend import Project

    project = Project(Path(path))
    names = {m.cls + "." + m.name for m in project.methods.values()}
    warnings = []
    for method in data.get("trusted_identity", {}):
        if method not in names:
            warnings.append("可信身份方法未在已加载源码中找到：" + method)
    if not project.entries():
        warnings.append("未识别到对外接口，请检查 services.path、exposed 和路由注解")
    if not data.get("policies"):
        warnings.append("尚未配置业务授权规则，请核对 DDL 推断的归属列和租户列是否符合业务要求")
    return {
        "valid": True,
        "manifest": str(Path(path).resolve()),
        "services": [s["name"] for s in data["services"]],
        "entries": len(project.entries()),
        "java_files": project.stats["java_files"],
        "warnings": warnings,
        "parser_issues": project.issues,
    }
