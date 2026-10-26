"""Small, evidence-directed patches. Originals are never modified by default."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
from pathlib import Path

import javalang as jl

from .frontend import Project
from .model import equivalent, term_text


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def argument_span(text, node, index):
    """Token positions avoid replacing a similar expression elsewhere in the file."""
    offsets = Project.line_offsets(text)
    start = offsets[node.position.line - 1] + node.position.column - 1
    tokens = [
        (t, offsets[t.position.line - 1] + t.position.column - 1)
        for t in jl.tokenizer.tokenize(text)
    ]
    tokens = [(t, p) for t, p in tokens if p >= start]
    opening = next(i for i, (t, p) in enumerate(tokens) if t.value == "(")
    depth, arg, begin = 0, 0, tokens[opening][1] + 1
    for t, pos in tokens[opening + 1 :]:
        if t.value in ("(", "[", "{"):
            depth += 1
        elif t.value in (")", "]", "}"):
            if t.value == ")" and depth == 0:
                if arg == index:
                    return begin, pos
                break
            depth -= 1
        if t.value == "," and depth == 0:
            if arg == index:
                return begin, pos
            arg, begin = arg + 1, pos + 1
    raise ValueError("Cannot locate argument")


def build_repairs(project: Project, report: dict, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    config = project.config.get("repair", {})
    patches = []
    for finding in report["results"]:
        if finding["status"] != "suspected":
            continue
        entry = project.methods[finding["entry"]]
        op = finding["operation"]
        text = project.texts[entry.file]
        file, start, end, new, strategy, reason = entry.file, None, None, None, None, None
        missing = [x["kind"] for x in finding["missing"]]
        # A repair candidate must have exactly one unmet requirement.
        if len(missing) != 1:
            continue
        obj = op["object"]
        direct = next(
            (p["name"] for p in entry.params if obj == ("input", entry.id, p["kind"], p["wire"])),
            None,
        )
        calls = [n for _, n in entry.node.filter(jl.tree.MethodInvocation)]
        if missing[0] == "object_mismatch":
            owner_field = finding["required"].get("owner")
            checked = set()
            for f in finding["facts"]:
                if f["op"] != "==":
                    continue
                for left, right in [(f["left"], f["right"]), (f["right"], f["left"])]:
                    if (
                        left[0] == "column"
                        and left[1] == op["table"]
                        and left[3] == owner_field
                        and equivalent(right, ("trusted", "user"), finding["facts"])
                    ):
                        for p in entry.params:
                            if left[2] == ("input", entry.id, p["kind"], p["wire"]):
                                checked.add(p["name"])
            site = next(
                (
                    t
                    for t in reversed(op["trace"])
                    if t["kind"] == "callsite"
                    and t["method"] == entry.id
                    and term_text(obj) in t["arguments"]
                ),
                None,
            )
            if len(checked) == 1 and site:
                candidates = [
                    n
                    for n in calls
                    if n.position.line == site["line"]
                    and len(n.arguments) == len(site["arguments"])
                ]
                if len(candidates) == 1:
                    start, end = argument_span(
                        text, candidates[0], site["arguments"].index(term_text(obj))
                    )
                    new, strategy = next(iter(checked)), "bind_checked_object"
                    reason = "将跨服务实参绑定到已有授权覆盖的路径对象；本接口约定以路径 ID 为准。"
        elif (
            missing[0] == "untrusted_subject"
            and config.get("owner_guard")
            and config.get("current_user")
        ):
            matches = [
                n
                for n in calls
                if f"{n.qualifier}.{n.member}" == config["owner_guard"] and len(n.arguments) == 2
            ]
            if len(matches) == 1:
                start, end = argument_span(text, matches[0], 1)
                new, strategy = " " + config["current_user"], "trusted_subject"
                reason = "复用当前服务的可信身份来源，替换请求者可控的用户 ID。"
        elif missing[0] in ("missing_owner", "missing_role"):
            role = missing[0] == "missing_role"
            guard = config.get("role_guard" if role else "owner_guard")
            if guard and (role or direct) and "." in guard:
                qualifier, member = guard.rsplit(".", 1)
                method = project.resolve(entry, qualifier, member, 0 if role else 2, {})
                if method and (role or config.get("current_user")):
                    start = end = entry.body_offset
                    statement = (
                        f"{guard}();" if role else f"{guard}({direct}, {config['current_user']});"
                    )
                    new, strategy = "\n        " + statement, "reuse_existing_guard"
                    reason = "入口处已有所需对象和可信身份；复用当前类可调用的鉴权方法，使检查先于敏感效果。"
        elif missing[0] == "missing_tenant":
            sql = op["sql"]
            candidates = [k for k, v in op["parameters"].items() if v == "trusted:tenant"]
            if (
                sql["supported"]
                and sql["file"].endswith(".xml")
                and len(candidates) == 1
                and not re.search(r"\b(group|order|limit|union)\b", sql["raw"], re.I)
            ):
                file, text = sql["file"], project.texts[sql["file"]]
                raw = sql["raw"]
                method = project.methods[op["method"]]
                element = re.search(
                    r"<select\b[^>]*\bid=[\"\']"
                    + re.escape(method.name)
                    + r"[\"\'][^>]*>([\s\S]*?)</select>",
                    text,
                )
                # Bind the edit to the Mapper statement, not a SQL substring in another query.
                if element and element.group(1).count(raw) == 1:
                    start = element.start(1) + element.group(1).index(raw)
                    end = start + len(raw)
                    join = " AND " if re.search(r"\bWHERE\b", raw, re.I) else " WHERE "
                    new = raw + join + finding["required"]["tenant"] + " = #{" + candidates[0] + "}"
                    strategy, reason = (
                        "sql_scope",
                        "可信租户已传递到 Mapper；在查询处补充约束，不改变跨服务接口。",
                    )
        if start is None:
            patches.append(
                {
                    "finding_id": finding["id"],
                    "status": "manual_review",
                    "reason": "当前模板缺少明确的修改位置或可用变量。",
                }
            )
            continue
        old = text[start:end]
        changed = text[:start] + new + text[end:]
        patch = {
            "finding_id": finding["id"],
            "endpoint": finding["endpoint"],
            "status": "candidate",
            "strategy": strategy,
            "reason": reason,
            "file": file,
            "sha256_before": digest(text),
            "start": start,
            "end": end,
            "old": old,
            "new": new,
            "verification": "not_run",
            "affected_entries": sorted(
                {r["entry"] for r in report["results"] if r["operation"]["method"] == op["method"]}
            ),
        }
        diff = "".join(
            difflib.unified_diff(
                text.splitlines(True),
                changed.splitlines(True),
                fromfile="a/" + file,
                tofile="b/" + file,
            )
        )
        name = finding["id"] + ".diff"
        (outdir / name).write_text(diff, encoding="utf-8")
        patch["diff"] = name
        patches.append(patch)
    plan = {"schema_version": "1.0", "patches": patches}
    (outdir / "repair_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return plan


def apply_repairs(root: Path, plan: dict, destination: Path):
    root, destination = root.resolve(), destination.resolve()
    if destination.exists():
        raise ValueError("Repair destination already exists; choose an empty new path")
    if destination == root or root in destination.parents:
        raise ValueError("Repair destination must be outside the source project")
    by_file = {}
    for patch in plan["patches"]:
        if patch["status"] == "candidate":
            by_file.setdefault(patch["file"], []).append(patch)
    changed = {}
    for file, patches in by_file.items():
        path = (root / file).resolve()
        if root not in path.parents:
            raise ValueError("Patch file escapes project root")
        text = path.read_text(encoding="utf-8")
        last = len(text) + 1
        for p in sorted(patches, key=lambda x: x["start"], reverse=True):
            if (
                digest(path.read_text(encoding="utf-8")) != p["sha256_before"]
                or text[p["start"] : p["end"]] != p["old"]
            ):
                raise ValueError(f"Stale patch preimage: {file}")
            if not 0 <= p["start"] <= p["end"] < last:
                raise ValueError(f"Overlapping or invalid patch range: {file}")
            last = p["start"]
            text = text[: p["start"]] + p["new"] + text[p["end"] :]
        changed[file] = text
    shutil.copytree(
        root,
        destination,
        ignore=shutil.ignore_patterns("target", ".git", "__pycache__", "out", ".env"),
    )
    for file, text in changed.items():
        (destination / file).write_text(text, encoding="utf-8")
    return {
        "destination": str(destination),
        "modified_files": sorted(changed),
        "patch_count": sum(len(x) for x in by_file.values()),
    }
