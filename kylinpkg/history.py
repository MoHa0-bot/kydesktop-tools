# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""下载任务历史：记录每次下载任务的配置与结果，支持查询、重做、套用。

历史保存在状态目录的 ``history.json``（新条目在前，最多保留 MAX_ENTRIES 条）。
CLI（cmd_download）与 GUI 共用同一个入口：downloader.download/download_plans
执行结束时无论成功、失败还是中断都会写入一条记录。
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from . import baseline as baseline_mod
from . import resolver
from .config import State
from .resolver import ResolvePlan
from .util import CancelToken, KylinPkgError, atomic_write_text, human_size, iso_now

HISTORY_FILENAME = "history.json"
MAX_ENTRIES = 200

STATUS_OK = "ok"
STATUS_REUSED = "reused"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

_STATUS_LABELS = {
    STATUS_OK: "成功",
    STATUS_REUSED: "复用",
    STATUS_FAILED: "失败",
    STATUS_CANCELLED: "中断",
}


def _history_file(state: State) -> Path:
    return state.root / HISTORY_FILENAME


def _load(state: State) -> List[Dict[str, object]]:
    path = _history_file(state)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _save(state: State, entries: List[Dict[str, object]]) -> None:
    state.ensure()
    atomic_write_text(
        _history_file(state),
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        0o600,
    )


def record_task(state: State, entry: Dict[str, object]) -> Dict[str, object]:
    """写入一条任务记录（新条目放最前，超出上限的丢弃）。"""
    entries = _load(state)
    entries.insert(0, entry)
    del entries[MAX_ENTRIES:]
    _save(state, entries)
    return entry


def build_entry(
    plans: Sequence[ResolvePlan],
    output_dir: Path,
    force: bool,
    make_repo: bool,
    status: str,
    result: Optional[Dict[str, object]] = None,
    error: Optional[str] = None,
) -> Dict[str, object]:
    """根据解析计划与下载结果构造一条历史记录。"""
    first = plans[0]
    baseline = (first.baseline or {}).get("name")
    entry: Dict[str, object] = {
        "id": "%s-%s"
        % (datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), uuid.uuid4().hex[:6]),
        "created_at": iso_now(),
        "kind": "download",
        "status": status,
        "profile": first.root.get("profile"),
        "architectures": list(first.root.get("architectures") or []),
        "baseline": baseline,
        "requested": sorted({spec for plan in plans for spec in plan.requested}),
        "recommends": bool(first.recommends),
        "with_dependencies": bool(first.with_dependencies),
        "force": bool(force),
        "make_repo": bool(make_repo),
        "output": str(output_dir),
    }
    if len(plans) > 1:
        entry["plans"] = len(plans)
    if result is not None:
        entry["package_count"] = int(result.get("total", 0) or 0)
        entry["total_bytes"] = int(result.get("total_bytes", 0) or 0)
        entry["reused"] = bool(result.get("reused"))
    if error:
        entry["error"] = str(error)
    return entry


def list_tasks(state: State, limit: Optional[int] = None) -> List[Dict[str, object]]:
    entries = _load(state)
    if limit is not None:
        entries = entries[: max(0, limit)]
    return entries


def find_task(state: State, task_id: str) -> Dict[str, object]:
    """按 id 精确匹配；否则按唯一前缀匹配。"""
    if not task_id:
        raise KylinPkgError("请指定任务 ID（kylinpkg history list 查看）")
    entries = _load(state)
    for entry in entries:
        if str(entry.get("id")) == task_id:
            return entry
    prefix_matches = [e for e in entries if str(e.get("id", "")).startswith(task_id)]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        raise KylinPkgError("任务 ID 前缀不唯一：%s" % task_id)
    raise KylinPkgError("没有找到任务：%s" % task_id)


def remove_task(state: State, task_id: str) -> Dict[str, object]:
    entry = find_task(state, task_id)
    entries = [e for e in _load(state) if str(e.get("id")) != entry.get("id")]
    _save(state, entries)
    return entry


def clear_tasks(state: State) -> int:
    entries = _load(state)
    _save(state, [])
    return len(entries)


def status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status or "?")


def describe_task(entry: Dict[str, object]) -> str:
    """单行摘要，用于 CLI 列表和 GUI 树。"""
    baseline = entry.get("baseline")
    return "%s  %s  %s  %s  %s  %s  %s" % (
        str(entry.get("created_at", "?")).replace("T", " "),
        status_label(str(entry.get("status", ""))),
        entry.get("profile", "?"),
        ",".join(entry.get("architectures") or []) or "-",
        baseline if baseline else "全量",
        " ".join(entry.get("requested") or []) or "-",
        entry.get("output", "-"),
    )


def equivalent_command(entry: Dict[str, object]) -> str:
    """给出与该历史任务等价的 download 命令行（用于套用到当前）。"""
    parts = ["kylinpkg", "download", "-p", str(entry.get("profile", "?"))]
    archs = entry.get("architectures") or []
    if archs:
        parts.extend(["-a", ",".join(str(a) for a in archs)])
    baseline = entry.get("baseline")
    if baseline == baseline_mod.RESERVED_EMPTY:
        parts.append("--full")
    elif baseline:
        parts.extend(["--baseline", str(baseline)])
    if not entry.get("recommends", True):
        parts.append("--no-recommends")
    if not entry.get("with_dependencies", True):
        parts.append("--no-deps")
    if entry.get("make_repo"):
        parts.append("--repo")
    parts.extend(["-o", str(entry.get("output", "."))])
    parts.extend(str(spec) for spec in entry.get("requested") or [])
    return " ".join(parts)


def redo_task(
    state: State,
    entry: Dict[str, object],
    output: Optional[Path] = None,
    force: Optional[bool] = None,
    make_repo: Optional[bool] = None,
    cancel: Optional[CancelToken] = None,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, object]:
    """按历史记录的配置重新解析并下载（会生成一条新的任务记录）。"""

    def say(text: str) -> None:
        if log is not None:
            log(text)

    profile = str(entry.get("profile") or "")
    if not profile:
        raise KylinPkgError("任务记录缺少 profile，无法重做")
    requested = [str(spec) for spec in entry.get("requested") or []]
    if not requested:
        raise KylinPkgError("任务记录没有软件包列表，无法重做")
    out_dir = Path(output) if output else Path(str(entry.get("output") or "")).expanduser()
    if not str(out_dir):
        raise KylinPkgError("任务记录没有输出目录，无法重做；请用 -o 指定")

    baseline_name = entry.get("baseline")
    if baseline_name == baseline_mod.RESERVED_EMPTY:
        baseline_name = baseline_mod.RESERVED_EMPTY
    elif baseline_name:
        try:
            baseline_mod.load_meta(state, str(baseline_name))
        except KylinPkgError:
            say("警告：baseline %s 已不存在，改用 profile 默认基线" % baseline_name)
            baseline_name = None

    say("重新下载任务 %s：%s" % (entry.get("id"), " ".join(requested)))
    try:
        plans = resolver.resolve_specs(
            state,
            profile,
            requested,
            architectures=[str(a) for a in entry.get("architectures") or []] or None,
            baseline_name=baseline_name if baseline_name else None,
            recommends=bool(entry.get("recommends", True)),
            with_dependencies=bool(entry.get("with_dependencies", True)),
            cancel=cancel,
        )
    except KylinPkgError as exc:
        raise KylinPkgError("重新解析失败：%s" % exc) from exc
    say(
        "解析完成：%d 个请求组，%d 个包，%s"
        % (
            len(plans),
            sum(len(p.entries) for p in plans),
            human_size(sum(p.total_size for p in plans)),
        )
    )
    from . import downloader  # 延迟导入：downloader 顶层会导入本模块

    return downloader.download_plans(
        state,
        plans,
        out_dir,
        force=bool(force) if force is not None else bool(entry.get("force")),
        make_repo=bool(make_repo) if make_repo is not None else bool(entry.get("make_repo")),
        cancel=cancel,
    )
