# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""下载结果清单：读取 .deb 元数据、写 manifest、校验。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import deb822
from .resolver import PlanEntry, ResolvePlan
from .util import KylinPkgError, atomic_write_text, iso_now, run, sha256_file


def deb_control(path: Path) -> Dict[str, str]:
    try:
        proc = run(["dpkg-deb", "-f", str(path)], timeout=60)
    except KylinPkgError as exc:
        raise KylinPkgError("读取 deb 控制信息失败：%s（%s）" % (path, exc)) from exc
    paragraphs = deb822.parse_paragraphs(proc.stdout)
    if not paragraphs:
        raise KylinPkgError("deb 控制信息为空：%s" % path)
    return paragraphs[0]


def build_manifest(
    output_dir: Path,
    plan: ResolvePlan,
    entries: Sequence[Tuple[Path, PlanEntry]],
) -> Dict[str, object]:
    packages: List[Dict[str, object]] = []
    seen = set()
    for path, plan_entry in entries:
        if path.name in seen:
            continue
        seen.add(path.name)
        control = deb_control(path)
        package = control.get("Package", plan_entry.package)
        version = control.get("Version", plan_entry.version)
        arch = control.get("Architecture", plan_entry.architecture)
        packages.append(
            {
                "package": package,
                "version": version,
                "architecture": arch,
                "filename": path.name,
                "path": str(path.relative_to(output_dir)),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "uri": plan_entry.uri,
                "source": plan_entry.source,
                "baseline_state": plan_entry.baseline_state,
            }
        )
    packages.sort(key=lambda item: (item["package"], item["architecture"], item["version"]))
    manifest: Dict[str, object] = {
        "schema": 1,
        "created_at": iso_now(),
        "profile": plan.root.get("profile"),
        "architectures": plan.root.get("architectures"),
        "baseline": plan.baseline,
        "root": plan.root,
        "recommends": plan.recommends,
        "with_dependencies": plan.with_dependencies,
        "requested": plan.requested,
        "requested_satisfied": plan.requested_satisfied,
        "totals": {
            "count": len(packages),
            "bytes": sum(int(item["size"]) for item in packages),
        },
        "packages": packages,
        "warnings": list(plan.warnings),
    }
    write_manifest(output_dir, manifest)
    return manifest


def write_manifest(output_dir: Path, manifest: Dict[str, object]) -> Path:
    path = Path(output_dir) / "manifest.json"
    atomic_write_text(path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", 0o644)
    return path


def read_manifest(output_dir: Path) -> Dict[str, object]:
    path = Path(output_dir) / "manifest.json"
    if not path.is_file():
        raise KylinPkgError("目录中没有 manifest.json：%s" % output_dir)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KylinPkgError("manifest.json 损坏：%s（%s）" % (path, exc)) from exc


def verify_manifest(output_dir: Path) -> Tuple[List[str], List[str]]:
    output_dir = Path(output_dir)
    manifest = read_manifest(output_dir)
    errors: List[str] = []
    warnings: List[str] = []
    known = set()
    for item in manifest.get("packages") or []:
        rel = item.get("path") or ("debs/%s" % item.get("filename", ""))
        path = output_dir / rel
        name = item.get("package", "?")
        if not path.is_file():
            errors.append("缺少文件：%s" % rel)
            continue
        if path.name in known:
            errors.append("manifest 中文件名重复：%s" % path.name)
        known.add(path.name)
        size = path.stat().st_size
        if size != int(item.get("size", -1)):
            errors.append("%s 大小不符：实际 %d，期望 %s" % (rel, size, item.get("size")))
        digest = sha256_file(path)
        if digest != item.get("sha256"):
            errors.append("%s SHA256 不符：实际 %s，期望 %s" % (rel, digest, item.get("sha256")))
        try:
            control = deb_control(path)
            for field, key in (("Package", "package"), ("Version", "version"), ("Architecture", "architecture")):
                actual = control.get(field, "")
                expected = item.get(key, "")
                if expected and actual != expected:
                    errors.append("%s 的 %s 不符：实际 %s，期望 %s" % (rel, field, actual, expected))
        except KylinPkgError as exc:
            errors.append("无法读取 %s 的控制信息：%s" % (rel, exc))
    debs_dir = output_dir / "debs"
    if debs_dir.is_dir():
        for path in sorted(debs_dir.glob("*.deb")):
            if path.name not in known:
                warnings.append("目录中存在 manifest 未记录的 deb：%s" % path.name)
    return errors, warnings
