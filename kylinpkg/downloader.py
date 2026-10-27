# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""执行下载计划：apt 下载、file:// 复制、哈希校验、生成 manifest。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit

from . import manifest as manifest_mod
from . import repo as repo_mod
from .aptroot import AptRoot
from .config import State
from .resolver import PlanEntry, ResolvePlan
from .util import (
    CancelToken,
    KylinPkgError,
    atomic_write_text,
    ensure_dir,
    hash_file,
    human_size,
    sha256_file,
)

_PARTIAL_MARKER = ".kylinpkg-partial"


def _plan_fingerprint(plan: ResolvePlan) -> Dict[str, object]:
    return {
        "profile": plan.root.get("profile"),
        "architectures": list(plan.root.get("architectures") or []),
        "baseline": (plan.baseline or {}).get("name"),
        "requested": sorted(plan.requested),
        "recommends": plan.recommends if plan.with_dependencies else None,
        "with_dependencies": plan.with_dependencies,
    }


def _plans_fingerprint(plans: Sequence[ResolvePlan]) -> Dict[str, object]:
    first = plans[0]
    requested = sorted({spec for plan in plans for spec in plan.requested})
    return {
        "profile": first.root.get("profile"),
        "architectures": list(first.root.get("architectures") or []),
        "baseline": (first.baseline or {}).get("name"),
        "requested": requested,
        "recommends": first.recommends if first.with_dependencies else None,
        "with_dependencies": first.with_dependencies,
        "version_plans": sorted(sorted(plan.requested) for plan in plans),
    }


def _existing_fingerprint(manifest: Dict[str, object]) -> Dict[str, object]:
    baseline = manifest.get("baseline") or {}
    result = {
        "profile": manifest.get("profile"),
        "architectures": list(manifest.get("architectures") or []),
        "baseline": baseline.get("name") if isinstance(baseline, dict) else None,
        "requested": sorted(manifest.get("requested") or []),
        "recommends": (
            manifest.get("recommends")
            if manifest.get("with_dependencies", True)
            else None
        ),
        "with_dependencies": manifest.get("with_dependencies", True),
    }
    if manifest.get("version_plans"):
        result["version_plans"] = sorted(
            sorted((item or {}).get("requested") or [])
            for item in manifest.get("version_plans") or []
        )
    return result


def _prepare_output(
    out_dir: Path, fingerprint: Dict[str, object], force: bool
) -> Optional[Dict[str, object]]:
    """返回已有且校验通过的 manifest 表示可复用；否则返回 None 继续下载。"""
    if not out_dir.exists():
        return None
    if force:
        shutil.rmtree(str(out_dir))
        return None
    if not any(out_dir.iterdir()):
        return None
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        # 上次下载被中断/失败留下的目录：允许继续，而不是强制 --force
        if (out_dir / _PARTIAL_MARKER).is_file():
            return None
        raise KylinPkgError("输出目录非空且不是 kylinpkg 结果：%s（加 --force 覆盖）" % out_dir)
    existing = manifest_mod.read_manifest(out_dir)
    if _existing_fingerprint(existing) != fingerprint:
        raise KylinPkgError("输出目录已有不同任务的结果：%s（换目录或加 --force）" % out_dir)
    errors, _warnings = manifest_mod.verify_manifest(out_dir)
    if not errors:
        return existing
    return None


def _file_uri_path(uri: str) -> Path:
    parts = urlsplit(uri)
    if parts.scheme != "file":
        raise KylinPkgError("不是 file: URI：%s" % uri)
    if parts.netloc and parts.netloc not in ("", "localhost"):
        raise KylinPkgError("不支持远端 file: URI：%s" % uri)
    return Path(unquote(parts.path))


def _verify_entry(path: Path, entry: PlanEntry) -> None:
    if not entry.hash_type or not entry.hash_value:
        return
    try:
        actual = hash_file(path, entry.hash_type)
    except (ValueError, OSError) as exc:
        raise KylinPkgError("无法校验 %s：%s" % (path, exc)) from exc
    if actual.lower() != entry.hash_value.lower():
        raise KylinPkgError(
            "%s 哈希校验失败：实际 %s:%s，期望 %s:%s"
            % (path.name, entry.hash_type, actual, entry.hash_type, entry.hash_value)
        )


def _identity(entry: PlanEntry) -> Tuple[str, str, str]:
    return (entry.package, entry.version, entry.architecture)


def download(
    state: State,
    plan: ResolvePlan,
    output_dir: Path,
    force: bool = False,
    make_repo: bool = False,
    cancel: Optional[CancelToken] = None,
) -> Dict[str, object]:
    if cancel is not None:
        cancel.check()
    out_dir = Path(output_dir).expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise KylinPkgError("输出路径已存在且不是目录：%s" % out_dir)
    ensure_dir(out_dir, 0o755)
    existing = _prepare_output(out_dir, _plan_fingerprint(plan), force)
    if existing is not None:
        try:
            (out_dir / _PARTIAL_MARKER).unlink()
        except OSError:
            pass
        return {
            "manifest": existing,
            "reused": True,
            "downloaded": 0,
            "total": len(existing.get("packages") or []),
            "warnings": [],
        }

    debs_dir = out_dir / "debs"
    ensure_dir(debs_dir, 0o755)
    ensure_dir(debs_dir / "partial", 0o755)
    marker = out_dir / _PARTIAL_MARKER
    atomic_write_text(marker, "partial\n", 0o600)

    plan_by_name: Dict[str, PlanEntry] = {}
    plan_by_identity: Dict[Tuple[str, str, str], PlanEntry] = {}
    for entry in plan.entries:
        plan_by_name[entry.filename] = entry
        plan_by_name[unquote(entry.filename)] = entry
        if entry.package:
            plan_by_identity[_identity(entry)] = entry
    before = {path.name for path in debs_dir.glob("*.deb")}

    warnings: List[str] = []
    if plan.entries:
        root = AptRoot(
            state,
            str(plan.root.get("profile")),
            plan.root.get("architectures"),
            (plan.baseline or {}).get("name"),
            cancel=cancel,
        )
        if plan.with_dependencies:
            args: List[str] = ["--download-only", "-y"]
            if not plan.recommends:
                args.append("--no-install-recommends")
            args.append("install")
            args.extend(plan.requested)
            root.run_apt(
                args,
                timeout=1800,
                extra_options=["-o", "Dir::Cache::archives=%s/" % debs_dir],
            )
        else:
            root.run_apt(
                ["download"] + list(plan.requested),
                timeout=1800,
                cwd=debs_dir,
            )

    # file:// 源 apt 不会复制进 archives；远程源理论上已由 apt 校验，这里统一复核。
    for entry in plan.entries:
        if cancel is not None:
            cancel.check()
        path = debs_dir / entry.filename
        if not path.is_file():
            decoded = debs_dir / unquote(entry.filename)
            if decoded.is_file():
                path = decoded
        if not path.is_file():
            scheme = urlsplit(entry.uri).scheme
            if scheme == "file":
                src = _file_uri_path(entry.uri)
                if not src.is_file():
                    raise KylinPkgError("本地源文件不存在：%s" % src)
                path = debs_dir / entry.filename
                shutil.copyfile(str(src), str(path))
            else:
                raise KylinPkgError(
                    "apt 未下载到 %s（%s）；可重试或检查源" % (entry.filename, entry.uri)
                )
        _verify_entry(path, entry)

    actual: List[Tuple[Path, PlanEntry]] = []
    matched = set()
    for path in sorted(debs_dir.glob("*.deb")):
        if cancel is not None:
            cancel.check()
        entry = plan_by_name.get(path.name) or plan_by_name.get(unquote(path.name))
        if entry is None:
            try:
                control = manifest_mod.deb_control(path)
                key = (
                    control.get("Package", ""),
                    control.get("Version", ""),
                    control.get("Architecture", ""),
                )
                entry = plan_by_identity.get(key)
            except KylinPkgError:
                entry = None
        if entry is None:
            warnings.append("下载到计划外的包：%s" % path.name)
            entry = PlanEntry(uri="", filename=path.name, size=path.stat().st_size)
        else:
            matched.add(entry.filename)
            _verify_entry(path, entry)
        actual.append((path, entry))

    missing = [entry.filename for entry in plan.entries if entry.filename not in matched]
    if missing:
        raise KylinPkgError("以下计划中的包未落盘：%s" % ", ".join(missing))

    if cancel is not None:
        cancel.check()
    do_repo = make_repo and bool(actual)
    if make_repo and not do_repo:
        warnings.append("没有可用的 .deb，跳过离线源生成")
    manifest = manifest_mod.build_manifest(out_dir, plan, actual)
    manifest["warnings"] = list(manifest.get("warnings") or []) + warnings
    manifest_mod.write_manifest(out_dir, manifest)
    try:
        marker.unlink()
    except OSError:
        pass

    if do_repo:
        repo_mod.build_repo(out_dir)

    after = {path.name for path in debs_dir.glob("*.deb")}
    return {
        "manifest": manifest,
        "reused": False,
        "downloaded": len(after - before),
        "total": len(after),
        "total_bytes": sum(
            path.stat().st_size for path in debs_dir.glob("*.deb")
        ),
        "warnings": warnings,
    }


def _ensure_plan_files(
    state: State,
    plan: ResolvePlan,
    debs_dir: Path,
    cancel: Optional[CancelToken],
) -> None:
    if not plan.entries:
        return
    root = AptRoot(
        state,
        str(plan.root.get("profile")),
        plan.root.get("architectures"),
        (plan.baseline or {}).get("name"),
        cancel=cancel,
    )
    if plan.with_dependencies:
        args: List[str] = ["--download-only", "-y"]
        if not plan.recommends:
            args.append("--no-install-recommends")
        args.append("install")
        args.extend(plan.requested)
        root.run_apt(
            args,
            timeout=1800,
            extra_options=["-o", "Dir::Cache::archives=%s/" % debs_dir],
        )
    else:
        root.run_apt(
            ["download"] + list(plan.requested),
            timeout=1800,
            cwd=debs_dir,
        )
    for entry in plan.entries:
        if cancel is not None:
            cancel.check()
        path = debs_dir / entry.filename
        if not path.is_file():
            decoded = debs_dir / unquote(entry.filename)
            if decoded.is_file():
                path = decoded
        if not path.is_file():
            if urlsplit(entry.uri).scheme == "file":
                src = _file_uri_path(entry.uri)
                if not src.is_file():
                    raise KylinPkgError("本地源文件不存在：%s" % src)
                path = debs_dir / entry.filename
                shutil.copyfile(str(src), str(path))
            else:
                raise KylinPkgError(
                    "apt 未下载到 %s（%s）；可重试或检查源"
                    % (entry.filename, entry.uri)
                )
        _verify_entry(path, entry)


def download_plans(
    state: State,
    plans: Sequence[ResolvePlan],
    output_dir: Path,
    force: bool = False,
    make_repo: bool = False,
    cancel: Optional[CancelToken] = None,
) -> Dict[str, object]:
    """多个版本（多个 apt 事务）下载到同一个目录/离线源。"""
    if not plans:
        raise KylinPkgError("没有可下载的版本计划")
    if len(plans) == 1:
        return download(state, plans[0], output_dir, force, make_repo, cancel)
    first = plans[0]
    for plan in plans[1:]:
        if (
            plan.root != first.root
            or plan.baseline != first.baseline
            or plan.recommends != first.recommends
            or plan.with_dependencies != first.with_dependencies
        ):
            raise KylinPkgError(
                "多版本下载要求使用同一个 profile/架构/基线/Recommends/依赖设置"
            )
    if cancel is not None:
        cancel.check()

    out_dir = Path(output_dir).expanduser()
    if out_dir.exists() and not out_dir.is_dir():
        raise KylinPkgError("输出路径已存在且不是目录：%s" % out_dir)
    ensure_dir(out_dir, 0o755)
    existing = _prepare_output(out_dir, _plans_fingerprint(plans), force)
    if existing is not None:
        try:
            (out_dir / _PARTIAL_MARKER).unlink()
        except OSError:
            pass
        return {
            "manifest": existing,
            "reused": True,
            "downloaded": 0,
            "total": len(existing.get("packages") or []),
            "warnings": [],
            "plans": len(plans),
        }

    debs_dir = out_dir / "debs"
    ensure_dir(debs_dir, 0o755)
    ensure_dir(debs_dir / "partial", 0o755)
    marker = out_dir / _PARTIAL_MARKER
    atomic_write_text(marker, "partial\n", 0o600)
    before = {path.name for path in debs_dir.glob("*.deb")}

    for plan in plans:
        if cancel is not None:
            cancel.check()
        _ensure_plan_files(state, plan, debs_dir, cancel)

    unique: Dict[str, PlanEntry] = {}
    for plan in plans:
        for entry in plan.entries:
            previous = unique.get(entry.filename)
            if previous is not None:
                if (
                    previous.hash_value
                    and entry.hash_value
                    and previous.hash_value != entry.hash_value
                ):
                    raise KylinPkgError(
                        "不同版本计划产生了同名但哈希不同的文件：%s" % entry.filename
                    )
                continue
            unique[entry.filename] = entry

    plan_by_name: Dict[str, PlanEntry] = {}
    plan_by_identity: Dict[Tuple[str, str, str], PlanEntry] = {}
    for entry in unique.values():
        plan_by_name[entry.filename] = entry
        plan_by_name[unquote(entry.filename)] = entry
        if entry.package:
            plan_by_identity[_identity(entry)] = entry

    warnings: List[str] = []
    actual: List[Tuple[Path, PlanEntry]] = []
    matched = set()
    for path in sorted(debs_dir.glob("*.deb")):
        if cancel is not None:
            cancel.check()
        entry = plan_by_name.get(path.name) or plan_by_name.get(unquote(path.name))
        if entry is None:
            try:
                control = manifest_mod.deb_control(path)
                key = (
                    control.get("Package", ""),
                    control.get("Version", ""),
                    control.get("Architecture", ""),
                )
                entry = plan_by_identity.get(key)
            except KylinPkgError:
                entry = None
        if entry is None:
            warnings.append("下载到计划外的包：%s" % path.name)
            entry = PlanEntry(uri="", filename=path.name, size=path.stat().st_size)
        else:
            matched.add(entry.filename)
            _verify_entry(path, entry)
        actual.append((path, entry))

    missing = [name for name in unique if name not in matched]
    if missing:
        raise KylinPkgError("以下计划中的包未落盘：%s" % ", ".join(missing))

    requested: List[str] = []
    satisfied: List[str] = []
    for plan in plans:
        for spec in plan.requested:
            if spec not in requested:
                requested.append(spec)
        for spec in plan.requested_satisfied:
            if spec not in satisfied:
                satisfied.append(spec)
    combined_warnings: List[str] = []
    for plan in plans:
        for warning in plan.warnings:
            if warning not in combined_warnings:
                combined_warnings.append(warning)
    combined = ResolvePlan(
        requested=requested,
        entries=list(unique.values()),
        requested_satisfied=satisfied,
        baseline=first.baseline,
        root=first.root,
        recommends=first.recommends,
        with_dependencies=first.with_dependencies,
        warnings=combined_warnings,
    )

    if cancel is not None:
        cancel.check()
    do_repo = make_repo and bool(actual)
    if make_repo and not do_repo:
        warnings.append("没有可用的 .deb，跳过离线源生成")
    manifest = manifest_mod.build_manifest(out_dir, combined, actual)
    manifest["warnings"] = list(manifest.get("warnings") or []) + warnings
    manifest["version_plans"] = [
        {
            "requested": list(plan.requested),
            "files": sorted({entry.filename for entry in plan.entries}),
        }
        for plan in plans
    ]
    manifest_mod.write_manifest(out_dir, manifest)
    try:
        marker.unlink()
    except OSError:
        pass
    if do_repo:
        repo_mod.build_repo(out_dir)

    after = {path.name for path in debs_dir.glob("*.deb")}
    return {
        "manifest": manifest,
        "reused": False,
        "downloaded": len(after - before),
        "total": len(after),
        "total_bytes": sum(path.stat().st_size for path in debs_dir.glob("*.deb")),
        "warnings": warnings,
        "plans": len(plans),
    }
