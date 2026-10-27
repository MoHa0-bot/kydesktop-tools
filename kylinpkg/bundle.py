# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""原始主机收集包（kylinpkg-collect 生成）的检查与一键导入。"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import baseline as baseline_mod
from . import deb822
from . import profile as profile_mod
from .arch import detect_system_archs, normalize_arch_set
from .config import State
from .util import KylinPkgError, sha256_file, validate_name


def _safe_extract(archive: Path, dest: Path) -> List[str]:
    warnings: List[str] = []
    try:
        bundle = tarfile.open(str(archive), mode="r:*")
    except (OSError, tarfile.TarError) as exc:
        raise KylinPkgError("无法打开收集包 %s：%s" % (archive, exc)) from exc
    dest_root = dest.resolve()
    with bundle:
        for member in bundle.getmembers():
            name = member.name
            parts = Path(name).parts
            if not parts or name.startswith("/") or ".." in parts:
                raise KylinPkgError("收集包包含不安全路径：%s" % name)
            target = (dest / name).resolve()
            if target != dest_root and dest_root not in target.parents:
                raise KylinPkgError("收集包路径越界：%s" % name)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                warnings.append("跳过非普通文件：%s" % name)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise KylinPkgError("无法读取收集包成员：%s" % name)
            with source, open(target, "wb") as out:
                shutil.copyfileobj(source, out)
    return warnings


def _find_bundle_root(extracted: Path) -> Path:
    candidates = [
        path.parent
        for path in extracted.rglob("bundle.json")
        if (path.parent / "rootfs").is_dir()
    ]
    if not candidates:
        if (extracted / "bundle.json").is_file() and (extracted / "rootfs").is_dir():
            return extracted
        raise KylinPkgError("收集包中找不到 bundle.json + rootfs/")
    candidates.sort(key=lambda item: len(item.parts))
    return candidates[0]


def _read_meta(root: Path) -> Dict[str, object]:
    path = root / "bundle.json"
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KylinPkgError("bundle.json 损坏：%s" % exc) from exc
    if not isinstance(meta, dict):
        raise KylinPkgError("bundle.json 格式不正确")
    return meta


def _verify_sums(root: Path) -> List[str]:
    sums = root / "SHA256SUMS"
    if not sums.is_file():
        return ["收集包没有 SHA256SUMS，跳过整体校验"]
    errors: List[str] = []
    for lineno, raw in enumerate(sums.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append("SHA256SUMS 第 %d 行格式错误" % lineno)
            continue
        digest, rel = parts[0], parts[1].lstrip("*")
        if rel.startswith("/") or ".." in Path(rel).parts:
            errors.append("SHA256SUMS 第 %d 行路径不安全：%s" % (lineno, rel))
            continue
        path = root / rel
        if not path.is_file():
            errors.append("收集包缺少文件：%s" % rel)
            continue
        actual = sha256_file(path)
        if actual != digest:
            errors.append("文件校验失败：%s" % rel)
    return errors


def _bundle_context(extracted: Path) -> Dict[str, object]:
    root = _find_bundle_root(extracted)
    meta = _read_meta(root)
    rootfs = root / "rootfs"
    status = rootfs / "var" / "lib" / "dpkg" / "status"
    apt_dir = rootfs / "etc" / "apt"
    if not status.is_file():
        raise KylinPkgError("收集包缺少 rootfs/var/lib/dpkg/status")
    if not apt_dir.is_dir():
        raise KylinPkgError("收集包缺少 rootfs/etc/apt")
    sum_errors = _verify_sums(root)
    hard_errors = [item for item in sum_errors if "跳过整体校验" not in item]
    if hard_errors:
        raise KylinPkgError("收集包校验失败：\n%s" % "\n".join(hard_errors))
    return {
        "root": root,
        "meta": meta,
        "rootfs": rootfs,
        "status": status,
        "apt_dir": apt_dir,
        "warnings": [item for item in sum_errors if "跳过整体校验" in item],
    }


def inspect_bundle(archive: Path) -> Dict[str, object]:
    archive = Path(archive).expanduser()
    if not archive.is_file():
        raise KylinPkgError("收集包不存在：%s" % archive)
    with tempfile.TemporaryDirectory(prefix="kylinpkg-bundle-") as tmp:
        extracted = Path(tmp)
        extract_warnings = _safe_extract(archive, extracted)
        ctx = _bundle_context(extracted)
        meta = ctx["meta"]
        status_path = ctx["status"]
        paragraphs = deb822.parse_status_text(
            status_path.read_text(encoding="utf-8", errors="replace")
        )
        summary = deb822.status_summary(paragraphs)
        sources = deb822.collect_sources(ctx["apt_dir"])
        archs = [arch for arch in (meta.get("architectures") or []) if arch and arch != "all"]
        if not archs:
            archs = list(summary["architectures"])
        return {
            "archive": str(archive.resolve()),
            "bundle": meta,
            "architectures": archs,
            "baseline": {
                "installed_count": summary["installed_count"],
                "package_count": summary["package_count"],
                "architectures": summary["architectures"],
            },
            "sources": len(sources),
            "warnings": list(extract_warnings) + list(ctx["warnings"]),
        }


def _safe_import_name(value: str, fallback: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip(".-_")
    if not name:
        name = fallback
    if not re.match(r"^[A-Za-z0-9]", name):
        name = "host-" + name
    return name[:60]


def import_bundle(
    state: State,
    archive: Path,
    profile_name: Optional[str] = None,
    baseline_name: Optional[str] = None,
    architectures: Optional[Sequence[str]] = None,
    bind_baseline: bool = True,
    force: bool = False,
) -> Dict[str, object]:
    archive = Path(archive).expanduser()
    if not archive.is_file():
        raise KylinPkgError("收集包不存在：%s" % archive)

    with tempfile.TemporaryDirectory(prefix="kylinpkg-bundle-") as tmp:
        extracted = Path(tmp)
        extract_warnings = _safe_extract(archive, extracted)
        ctx = _bundle_context(extracted)
        meta = ctx["meta"]
        rootfs = Path(ctx["rootfs"])
        status_path = Path(ctx["status"])

        host = str(meta.get("hostname") or archive.stem)
        profile_name = validate_name(
            profile_name or _safe_import_name(host, "imported-host"), "profile 名称"
        )
        baseline_name = validate_name(
            baseline_name
            or _safe_import_name("%s-baseline" % profile_name, "imported-baseline"),
            "baseline 名称",
        )

        if architectures:
            target_archs = normalize_arch_set(architectures)
        else:
            archs = [
                arch
                for arch in (meta.get("architectures") or [])
                if arch and arch != "all"
            ]
            if not archs:
                paragraphs = deb822.parse_status_text(
                    status_path.read_text(encoding="utf-8", errors="replace")
                )
                archs = list(deb822.status_summary(paragraphs)["architectures"])
            if not archs:
                archs = detect_system_archs()
                extract_warnings.append("收集包未声明架构，已使用本机架构")
            target_archs = normalize_arch_set(archs)

        pdir = state.profile_dir(profile_name)
        bdir = state.baseline_dir(baseline_name)
        profile_existed = pdir.exists()
        baseline_existed = bdir.exists()
        if profile_existed and not force:
            raise KylinPkgError("profile 已存在：%s（加 --force 覆盖）" % profile_name)
        if baseline_existed and not force:
            raise KylinPkgError("baseline 已存在：%s（加 --force 覆盖）" % baseline_name)

        try:
            bmeta = baseline_mod.import_baseline(
                state,
                baseline_name,
                status_file=status_path,
                note="imported from bundle %s" % archive.name,
                force=force,
            )
            pmeta = profile_mod.import_profile(
                state,
                profile_name,
                from_rootfs=rootfs,
                architectures=target_archs,
                baseline=None,
                note="imported from bundle %s" % archive.name,
                force=force,
                include_auth=bool(meta.get("with_auth")),
            )
            warnings: List[str] = list(extract_warnings)
            warnings.extend(bmeta.get("warnings") or [])
            warnings.extend(pmeta.get("warnings") or [])
            bound = False
            if bind_baseline:
                problem = baseline_mod.check_compatible(pmeta, bmeta)
                if problem:
                    warnings.append(problem + "；已保留 profile 未绑定 baseline")
                else:
                    profile_mod.bind_baseline(state, profile_name, baseline_name)
                    pmeta = profile_mod.load_profile(state, profile_name)
                    bound = True
            return {
                "profile": profile_name,
                "baseline": baseline_name,
                "architectures": list(target_archs),
                "installed_count": bmeta.get("installed_count", 0),
                "sources": len(pmeta.get("sources_summary") or []),
                "bound": bound,
                "warnings": warnings,
            }
        except Exception:
            if (not profile_existed or force) and pdir.exists():
                shutil.rmtree(str(pdir), ignore_errors=True)
            if (not baseline_existed or force) and bdir.exists():
                shutil.rmtree(str(bdir), ignore_errors=True)
            raise
