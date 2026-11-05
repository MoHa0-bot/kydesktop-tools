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


# ---------------------------------------------------------------------------
# 内核元包版本（linux-generic）——用于 baseline 列表展示
# ---------------------------------------------------------------------------
def kernel_versions_from_status(status_bytes: bytes) -> Dict[str, str]:
    """从 dpkg status 提取已安装内核的版本（列表「内核」列数据源）。

    优先取内核元包：`linux-generic` 及其 hwe 变体（SP1 通用机型）。
    没有元包时回退到带版本号的内核镜像包（包名内含内核 release）：
    `linux-image-4.19.71-46-kr990`（麒麟 990 平台）与
    `kylin-image-4.4.131-20200710-generic`（V10 基础版），
    取包名中的内核 release（uname 风格）作为版本。

    返回 {包名: 版本}，只统计 Status 为 install ok installed 的记录；
    镜像包附件（linux-image-extra-…）不在此列。
    """
    if not status_bytes.strip():
        return {}
    try:
        paragraphs = deb822.parse_status_text(
            status_bytes.decode("utf-8", errors="replace")
        )
    except KylinPkgError:
        return {}
    metas: Dict[str, str] = {}
    images: Dict[str, str] = {}
    for p in paragraphs:
        name = p.get("Package", "")
        if p.get("Status") != "install ok installed":
            continue
        if name == "linux-generic" or name.startswith("linux-generic-hwe"):
            metas.setdefault(name, p.get("Version", ""))
            continue
        for prefix in ("linux-image-", "kylin-image-"):
            if not name.startswith(prefix):
                continue
            rest = name[len(prefix):]
            # 只要包名带内核版本的镜像包；跳过 extra 等附件与无版本号的平台元包
            if rest and rest[0].isdigit() and not rest.startswith("extra-"):
                images.setdefault(name, rest)
            break
    if metas:
        return metas
    return images


def kernel_display(version_map: Optional[Dict[str, str]]) -> str:
    """把内核版本映射格式化为列表里的一列文本。"""
    if not version_map:
        return "-"
    if set(version_map) == {"linux-generic"}:
        return version_map["linux-generic"] or "-"
    parts = []
    for name in sorted(version_map):
        ver = version_map[name]
        if name == "linux-generic" or (ver and name.endswith(ver)):
            # linux-generic 元包或镜像包（版本即包名尾部）只显示版本
            parts.append(ver)
        else:
            parts.append("%s %s" % (name, ver))
    return "; ".join(parts) or "-"


def ensure_kernel_info(state: State, meta: Dict[str, object]) -> Dict[str, object]:
    """列表展示用：旧 baseline 的 meta 缺 kernel_version 时，从 status 现算并回写。

    返回带 kernel_version / kernel_versions 字段的 meta（原对象或浅拷贝）。
    """
    if meta.get("kernel_version") or meta.get("empty"):
        return meta
    name = str(meta.get("name") or "")
    if not name or name == RESERVED_EMPTY:
        return meta
    path = state.baseline_dir(name) / "status"
    if not path.is_file():
        return meta
    try:
        version_map = kernel_versions_from_status(path.read_bytes())
    except OSError:
        return meta
    display = kernel_display(version_map)
    updated = dict(meta)
    updated["kernel_version"] = display
    if version_map:
        updated["kernel_versions"] = version_map
    try:
        atomic_write_text(
            state.baseline_dir(name) / "meta.json",
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        )
    except OSError:
        pass
    return updated


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
        kernel_map = kernel_versions_from_status(status_bytes)
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
            "kernel_version": kernel_display(kernel_map),
            "warnings": warnings,
        }
        if kernel_map:
            meta["kernel_versions"] = kernel_map
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


# ---------------------------------------------------------------------------
# 打开查询：读取基线里的包记录（CLI baseline query / GUI 查看器共用）
# ---------------------------------------------------------------------------
def _split_status_raw(text: str) -> List[str]:
    """按空行切分 status 原文，保留每个段落的续行格式（与 parse_status_text 顺序对齐）。"""
    blocks: List[str] = []
    current: List[str] = []
    for raw in text.splitlines():
        line = raw.rstrip("\r")
        if not line.strip():
            if current:
                blocks.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _render_paragraph(paragraph: Dict[str, str]) -> str:
    """把字段字典还原成 Deb822 段落（原文片段缺失时的兜底）。"""
    lines: List[str] = []
    for key, value in paragraph.items():
        parts = str(value).split("\n")
        lines.append("%s: %s" % (key, parts[0]))
        for line in parts[1:]:
            lines.append(" " + line if line else " .")
    return "\n".join(lines)


def open_baseline(
    state: State, name: str, use_builtin: bool = False
) -> Dict[str, object]:
    """打开一份 baseline，返回元数据和全部包记录（只读，不修改基线）。

    默认读 state 里的基线；state 中不存在时自动回退到随包分发的内置基线，
    因此删除过或尚未导入的内置基线也能直接查询。`use_builtin=True` 强制读内置
    数据（与 state 中的同名基线区分）。记录含包摘要、`fields`（完整 Deb822
    字段）和 `raw`（原始 status 段落，可直接查看/复制/导出）。
    """
    name = validate_name(name, "baseline 名称")
    if name == RESERVED_EMPTY:
        return {
            "name": name,
            "source": "empty",
            "meta": load_meta(state, name),
            "records": [],
        }

    source = "state"
    meta: Dict[str, object]
    status_bytes: bytes
    use_state = not use_builtin and (state.baseline_dir(name) / "meta.json").is_file()
    if use_state:
        meta = load_meta(state, name)
        path = status_path(state, name)
        try:
            status_bytes = path.read_bytes() if path else b""
        except OSError as exc:
            raise KylinPkgError("无法读取 baseline %s 的 status：%s" % (name, exc)) from exc
    else:
        try:
            meta = get_builtin_baseline_meta(name)
            status_bytes = _builtin_status_bytes(name)
        except KylinPkgError as exc:
            if use_builtin:
                raise
            raise KylinPkgError(
                "baseline 不存在：%s（也不是随包分发的内置基线）" % name
            ) from exc
        source = "builtin"

    text = status_bytes.decode("utf-8", errors="replace")
    try:
        paragraphs = deb822.parse_status_text(text)
    except KylinPkgError as exc:
        raise KylinPkgError("baseline %s 的 status 不是合法的 Deb822 文本：%s" % (name, exc)) from exc
    raws = _split_status_raw(text)
    records: List[Dict[str, object]] = []
    for index, paragraph in enumerate(paragraphs):
        status = paragraph.get("Status", "").strip()
        raw = raws[index] if index < len(raws) else _render_paragraph(paragraph)
        records.append(
            {
                "package": paragraph.get("Package", "").strip(),
                "version": paragraph.get("Version", "").strip(),
                "architecture": paragraph.get("Architecture", "").strip() or "all",
                "status": status,
                "installed": bool(status) and status.split()[-1] == "installed",
                "fields": dict(paragraph),
                "raw": raw,
            }
        )
    return {"name": name, "source": source, "meta": meta, "records": records}


def filter_records(
    records: List[Dict[str, object]],
    keyword: str = "",
    installed_only: bool = False,
    arch: str = "",
    exact: bool = False,
    all_fields: bool = False,
) -> List[Dict[str, object]]:
    """在内存中过滤包记录：CLI 与 GUI 共用同一套匹配规则。

    - keyword 为空时返回全部（受 installed_only / arch 约束）；
    - exact 按包名精确匹配（不区分大小写），否则做子串匹配；
    - all_fields=False 只搜包名/版本/架构/状态，True 时同时搜 Depends、
      Description 等全部 Deb822 字段值。
    """
    needle = (keyword or "").strip().lower()
    result: List[Dict[str, object]] = []
    for record in records:
        if installed_only and not record.get("installed"):
            continue
        if arch and str(record.get("architecture", "")) != arch:
            continue
        if needle:
            if exact:
                if str(record.get("package", "")).lower() != needle:
                    continue
            elif all_fields:
                haystack = " ".join(
                    [str(record.get("package", ""))]
                    + [str(value) for value in (record.get("fields") or {}).values()]
                ).lower()
                if needle not in haystack:
                    continue
            else:
                haystack = " ".join(
                    str(record.get(field, ""))
                    for field in ("package", "version", "architecture", "status")
                ).lower()
                if needle not in haystack:
                    continue
        result.append(record)
    return result


def query_baseline(
    state: State,
    name: str,
    keyword: str = "",
    installed_only: bool = False,
    arch: str = "",
    exact: bool = False,
    all_fields: bool = False,
    use_builtin: bool = False,
) -> Dict[str, object]:
    """查询某个 baseline 里的包信息，返回元数据、总数与匹配记录。"""
    data = open_baseline(state, name, use_builtin=use_builtin)
    records = list(data["records"] or [])
    matched = filter_records(
        records,
        keyword=keyword,
        installed_only=installed_only,
        arch=arch,
        exact=exact,
        all_fields=all_fields,
    )
    data["total"] = len(records)
    data["matched"] = len(matched)
    data["records"] = matched
    return data


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
