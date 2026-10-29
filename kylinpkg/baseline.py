# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""dpkg status 基线：导入、校验、存放。"""

from __future__ import annotations

import gzip
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from . import deb822
from .config import State
from .util import (
    KylinPkgError,
    atomic_write_bytes,
    atomic_write_text,
    copy_file,
    ensure_dir,
    iso_now,
    run,
    sha256_file,
    validate_name,
)

RESERVED_EMPTY = "empty"

# 随包分发的内置现场基线（来自 kylinpkg-collect 收集包，status 以 gzip 存储）
BUILTIN_BASELINES_DIR = Path(__file__).resolve().parent / "resources" / "baselines"


def _status_bytes_from_system() -> bytes:
    path = Path("/var/lib/dpkg/status")
    if not path.is_file():
        raise KylinPkgError("本机不存在 %s" % path)
    return path.read_bytes()


def _status_bytes_from_rootfs(rootfs: Path) -> bytes:
    path = Path(rootfs) / "var" / "lib" / "dpkg" / "status"
    if not path.is_file():
        raise KylinPkgError("rootfs 中不存在 %s" % path)
    return path.read_bytes()


def _status_bytes_from_ssh(host: str) -> bytes:
    if not host or host.startswith("-"):
        raise KylinPkgError("SSH 目标不合法：%r" % host)
    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        host,
        "cat /var/lib/dpkg/status",
    ]
    proc = run(cmd, check=False)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise KylinPkgError("从 %s 读取 /var/lib/dpkg/status 失败：%s" % (host, detail))
    return proc.stdout.encode("utf-8")


def _write_baseline(
    state: State,
    name: str,
    status_bytes: bytes,
    origin_kind: str,
    origin_detail: str,
    note: str = "",
    force: bool = False,
) -> Dict[str, object]:
    name = validate_name(name, "baseline 名称")
    if name == RESERVED_EMPTY:
        raise KylinPkgError("baseline 名称 %r 为保留字，请换一个名字" % RESERVED_EMPTY)

    warnings: List[str] = []
    summary: Dict[str, object] = {
        "package_count": 0,
        "installed_count": 0,
        "architectures": [],
        "duplicates": [],
    }
    if status_bytes.strip():
        try:
            text = status_bytes.decode("utf-8", errors="replace")
            paragraphs = deb822.parse_status_text(text)
            summary = deb822.status_summary(paragraphs)
        except KylinPkgError as exc:
            raise KylinPkgError("status 文件不是合法的 Deb822 文本：%s" % exc) from exc
    else:
        warnings.append("空基线：将按全量依赖闭包解析")
    if status_bytes.strip():
        if int(summary["package_count"]) == 0:
            warnings.append(
                "未从 status 中解析到任何包记录；baseline 必须是完整的 /var/lib/dpkg/status"
            )
        elif int(summary["installed_count"]) == 0:
            warnings.append(
                "未识别到任何已安装包；确认导入的是完整 /var/lib/dpkg/status，"
                "而不是 dpkg --get-selections 之类的精简列表"
            )
    if summary["duplicates"]:
        warnings.append("status 中存在重复的包/架构条目：%s" % summary["duplicates"][:10])

    bdir = state.baseline_dir(name)
    if bdir.exists() and not force:
        raise KylinPkgError("baseline 已存在：%s（加 --force 覆盖）" % name)
    try:
        if bdir.exists():
            shutil.rmtree(str(bdir))
        ensure_dir(bdir, 0o700)

        status_path = bdir / "status"
        atomic_write_bytes(status_path, status_bytes, 0o600)
        meta = {
            "schema": 1,
            "name": name,
            "created_at": iso_now(),
            "origin": {"kind": origin_kind, "detail": origin_detail},
            "note": note,
            "status_sha256": sha256_file(status_path),
            "status_size": status_path.stat().st_size,
            "package_count": summary["package_count"],
            "installed_count": summary["installed_count"],
            "architectures": summary["architectures"],
            "warnings": warnings,
        }
        atomic_write_text(
            bdir / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
        )
        return meta
    except Exception:
        shutil.rmtree(str(bdir), ignore_errors=True)
        raise


def import_baseline(
    state: State,
    name: str,
    status_file: Optional[Path] = None,
    from_system: bool = False,
    from_ssh: Optional[str] = None,
    from_rootfs: Optional[Path] = None,
    empty: bool = False,
    from_builtin: Optional[str] = None,
    note: str = "",
    force: bool = False,
) -> Dict[str, object]:
    selectors = [
        status_file is not None,
        from_system,
        bool(from_ssh),
        from_rootfs is not None,
        empty,
        from_builtin is not None,
    ]
    if sum(1 for item in selectors if item) != 1:
        raise KylinPkgError(
            "请且只指定一种来源：--status-file / --from-system / --from-ssh /"
            " --from-rootfs / --empty / --builtin"
        )
    if empty:
        return _write_baseline(state, name, b"", "empty", "空基线（全量闭包）", note, force)
    if from_builtin is not None:
        builtin_meta = get_builtin_baseline_meta(from_builtin)
        detail = "内置基线 %s（收集包 %s）" % (
            from_builtin,
            builtin_meta.get("source_bundle", "?"),
        )
        return _write_baseline(
            state,
            name,
            _builtin_status_bytes(from_builtin),
            "builtin",
            detail,
            note,
            force,
        )
    if status_file is not None:
        path = Path(status_file).expanduser()
        if not path.is_file():
            raise KylinPkgError("status 文件不存在：%s" % path)
        return _write_baseline(
            state, name, path.read_bytes(), "file", str(path.resolve()), note, force
        )
    if from_system:
        return _write_baseline(
            state, name, _status_bytes_from_system(), "system", "/var/lib/dpkg/status", note, force
        )
    if from_ssh:
        return _write_baseline(
            state,
            name,
            _status_bytes_from_ssh(from_ssh),
            "ssh",
            "%s:/var/lib/dpkg/status" % from_ssh,
            note,
            force,
        )
    if from_rootfs is not None:
        rootfs = Path(from_rootfs).expanduser()
        return _write_baseline(
            state,
            name,
            _status_bytes_from_rootfs(rootfs),
            "rootfs",
            str((rootfs / "var/lib/dpkg/status").resolve()),
            note,
            force,
        )
    raise KylinPkgError("没有可用的 baseline 来源")


def list_builtin_baselines() -> List[Dict[str, object]]:
    """列出随包分发的内置现场基线（按名称排序）。"""
    items: List[Dict[str, object]] = []
    if not BUILTIN_BASELINES_DIR.is_dir():
        return items
    for bdir in sorted(BUILTIN_BASELINES_DIR.iterdir()):
        meta_path = bdir / "meta.json"
        if not bdir.is_dir() or not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items.append(meta)
    return items


def get_builtin_baseline_meta(name: str) -> Dict[str, object]:
    for meta in list_builtin_baselines():
        if meta.get("name") == name:
            return meta
    known = ", ".join(item.get("name", "?") for item in list_builtin_baselines())
    raise KylinPkgError("未知内置 baseline：%s（可用：%s）" % (name, known or "（无）"))


def _builtin_status_bytes(name: str) -> bytes:
    get_builtin_baseline_meta(name)
    path = BUILTIN_BASELINES_DIR / name / "status.gz"
    if not path.is_file():
        raise KylinPkgError("内置 baseline 数据缺失：%s" % path)
    with gzip.open(path, "rb") as fh:
        return fh.read()


# 记录已自动同步过的内置基线（name -> status_sha256）；
# 用户手动删除的内置基线不会被再次导入，内置数据更新（sha 变化）后会重新导入
_BUILTIN_SYNC_MARKER = ".builtin-sync.json"


def ensure_builtin_baselines(state: State) -> List[str]:
    """把随包分发的内置基线同步进 state（幂等，启动时调用）。

    返回本次新导入的 baseline 名称列表。规则：
    - state 中尚不存在的内置基线 → 自动导入（与手工 --builtin 导入一致）；
    - 用户删除过的（已记录在同步标记中）→ 不再导入；
    - 内置数据更新（status_sha256 变化）→ 用 --force 语义覆盖刷新。
    """
    synced: Dict[str, str] = {}
    marker_path = state.baselines_dir / _BUILTIN_SYNC_MARKER
    if marker_path.is_file():
        try:
            synced = json.loads(marker_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            synced = {}
    created: List[str] = []
    changed = False
    for meta in list_builtin_baselines():
        name = str(meta.get("name", ""))
        sha = str(meta.get("status_sha256", ""))
        if not name or synced.get(name) == sha:
            continue
        exists = (state.baseline_dir(name) / "meta.json").is_file()
        if exists and name not in synced:
            # 用户手工导入过同名基线：不覆盖，只记录同步标记
            synced[name] = sha
            changed = True
            continue
        if exists:
            # 内置数据更新（sha 变化）且之前是自动导入的：覆盖刷新
            import_baseline(
                state, name, from_builtin=name,
                note=str(meta.get("note") or ""), force=True,
            )
        else:
            import_baseline(
                state, name, from_builtin=name,
                note=str(meta.get("note") or ""),
            )
            created.append(name)
        synced[name] = sha
        changed = True
    if changed or not marker_path.is_file():
        atomic_write_text(
            marker_path, json.dumps(synced, ensure_ascii=False, indent=2) + "\n"
        )
    return created


def load_meta(state: State, name: str) -> Dict[str, object]:
    if name == RESERVED_EMPTY:
        return {
            "schema": 1,
            "name": RESERVED_EMPTY,
            "empty": True,
            "installed_count": 0,
            "architectures": [],
            "status_sha256": "",
        }
    meta_path = state.baseline_dir(name) / "meta.json"
    if not meta_path.is_file():
        raise KylinPkgError("baseline 不存在：%s" % name)
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KylinPkgError("baseline 元数据损坏：%s（%s）" % (meta_path, exc)) from exc


def status_path(state: State, name: str) -> Optional[Path]:
    if name == RESERVED_EMPTY:
        return None
    path = state.baseline_dir(name) / "status"
    if not path.is_file():
        raise KylinPkgError("baseline 状态文件不存在：%s" % path)
    return path


def read_status_paragraphs(state: State, name: str) -> List[Dict[str, str]]:
    path = status_path(state, name)
    if path is None:
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return deb822.parse_status_text(text)


def list_baselines(state: State) -> List[Dict[str, object]]:
    items = []
    if not state.baselines_dir.is_dir():
        return items
    for bdir in sorted(state.baselines_dir.iterdir()):
        meta_path = bdir / "meta.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        items.append(meta)
    return items


def remove_baseline(state: State, name: str) -> None:
    if name == RESERVED_EMPTY:
        raise KylinPkgError("不能删除保留的 empty 基线")
    bdir = state.baseline_dir(name)
    if not bdir.exists():
        raise KylinPkgError("baseline 不存在：%s" % name)
    shutil.rmtree(str(bdir))


def check_compatible(profile_meta: Dict[str, object], baseline_meta: Dict[str, object]) -> Optional[str]:
    """检查基线中已安装包的架构是否都被 profile 覆盖。"""
    baseline_archs = [
        arch for arch in (baseline_meta.get("architectures") or []) if arch and arch != "all"
    ]
    profile_archs = list(profile_meta.get("architectures") or [])
    missing = [arch for arch in baseline_archs if arch not in profile_archs]
    if missing:
        return (
            "baseline %s 中含有 profile 未启用的架构 %s；请用 -a 补齐（当前：%s），"
            "否则 apt 解析结果会与目标机不一致。"
            % (baseline_meta.get("name"), ", ".join(missing), ", ".join(profile_archs))
        )
    return None
