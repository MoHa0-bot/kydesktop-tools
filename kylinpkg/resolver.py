# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""依赖解析：调用 apt-get --print-uris，把结果转成可执行的下载计划。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlsplit

from . import baseline as baseline_mod
from . import deb822
from .aptroot import AptRoot
from .config import State
from .util import CancelToken, CommandError, KylinPkgError, human_size

_URI_LINE_RE = re.compile(
    r"^'(?P<uri>.+)'\s+(?P<filename>\S+)\s+(?P<size>\d+)"
    r"(?:\s+(?P<hash>[A-Za-z0-9]+:[0-9a-fA-F]+))?\s*$"
)


@dataclass
class AvailableVersion:
    version: str
    priority: int
    sources: List[str] = field(default_factory=list)
    architectures: List[str] = field(default_factory=list)
    downloadable: bool = False
    installed: bool = False
    candidate: bool = False


@dataclass
class PlanEntry:
    uri: str
    filename: str
    size: int
    hash_type: str = ""
    hash_value: str = ""
    package: str = ""
    version: str = ""
    architecture: str = ""
    baseline_state: str = "new"
    source: str = ""

    @property
    def identity(self) -> Tuple[str, str, str]:
        return (self.package, self.version, self.architecture)


@dataclass
class ResolvePlan:
    requested: List[str]
    entries: List[PlanEntry] = field(default_factory=list)
    requested_satisfied: List[str] = field(default_factory=list)
    baseline: Dict[str, object] = field(default_factory=dict)
    root: Dict[str, object] = field(default_factory=dict)
    recommends: bool = True
    with_dependencies: bool = True
    warnings: List[str] = field(default_factory=list)

    @property
    def total_size(self) -> int:
        return sum(entry.size for entry in self.entries)


def parse_print_uris(output: str) -> List[PlanEntry]:
    entries: List[PlanEntry] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line.startswith("'"):
            continue
        match = _URI_LINE_RE.match(line)
        if not match:
            continue
        filename = match.group("filename")
        decoded = unquote(filename)
        package = version = arch = ""
        if decoded.endswith(".deb"):
            parts = decoded[:-4].split("_")
            if len(parts) >= 3:
                package = parts[0]
                version = "_".join(parts[1:-1])
                arch = parts[-1]
        hash_type = hash_value = ""
        hash_token = match.group("hash")
        if hash_token and ":" in hash_token:
            hash_type, hash_value = hash_token.split(":", 1)
        source = ""
        try:
            parts_uri = urlsplit(match.group("uri"))
            source = parts_uri.netloc or parts_uri.scheme
        except ValueError:
            pass
        entries.append(
            PlanEntry(
                uri=match.group("uri"),
                filename=filename,
                size=int(match.group("size")),
                hash_type=hash_type,
                hash_value=hash_value,
                package=package,
                version=version,
                architecture=arch,
                source=source,
            )
        )
    return entries


_POLICY_VERSION_RE = re.compile(r"^(?:\*\*\*\s+)?(\S+)\s+(-?\d+)\s*$")
_POLICY_SOURCE_RE = re.compile(r"^(-?\d+)\s+(\S+)(?:\s+(.*))?$")


def parse_policy_output(output: str, package: str) -> Dict[str, object]:
    installed: Optional[str] = None
    candidate: Optional[str] = None
    versions: Dict[str, AvailableVersion] = {}
    current: Optional[AvailableVersion] = None
    in_table = False
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Installed:"):
            value = line.split(":", 1)[1].strip()
            installed = None if value in ("(none)", "") else value
            current = None
            continue
        if line.startswith("Candidate:"):
            value = line.split(":", 1)[1].strip()
            candidate = None if value in ("(none)", "") else value
            current = None
            continue
        if line == "Version table:":
            in_table = True
            continue
        if not in_table:
            continue

        version_match = _POLICY_VERSION_RE.match(line)
        if version_match:
            version, priority = version_match.group(1), int(version_match.group(2))
            existing = versions.get(version)
            if existing is None:
                existing = AvailableVersion(version=version, priority=priority)
                versions[version] = existing
            else:
                existing.priority = max(existing.priority, priority)
            current = existing
            continue

        source_match = _POLICY_SOURCE_RE.match(line)
        if source_match and current is not None:
            priority = int(source_match.group(1))
            uri = source_match.group(2)
            rest = (source_match.group(3) or "").strip()
            current.sources.append(
                ("%d %s%s" % (priority, uri, (" " + rest) if rest else "")).strip()
            )
            current.priority = max(current.priority, priority)
            if uri and not uri.startswith("/"):
                current.downloadable = True
            if uri == "/var/lib/dpkg/status":
                current.installed = True
            tokens = rest.split()
            if len(tokens) >= 2 and tokens[-1] == "Packages":
                arch = tokens[-2]
                if arch not in ("./", ".", "/") and arch not in current.architectures:
                    current.architectures.append(arch)
            continue

    for version in versions.values():
        if installed and version.version == installed:
            version.installed = True
        if candidate and version.version == candidate:
            version.candidate = True
    return {
        "package": package,
        "installed": installed,
        "candidate": candidate,
        "versions": [
            {
                "version": item.version,
                "priority": item.priority,
                "sources": list(item.sources),
                "architectures": list(item.architectures),
                "downloadable": item.downloadable,
                "installed": item.installed,
                "candidate": item.candidate,
            }
            for item in versions.values()
        ],
    }


def list_versions(
    state: State,
    profile_name: str,
    package: str,
    architectures: Optional[Sequence[str]] = None,
    baseline_name: Optional[str] = None,
    cancel: Optional[CancelToken] = None,
) -> Dict[str, object]:
    package = package.strip()
    if not package:
        raise KylinPkgError("软件包名为空")
    package = package.split("=", 1)[0]
    root = AptRoot(state, profile_name, architectures, baseline_name, cancel=cancel)
    root.update(force=False, no_update=False)
    if cancel is not None:
        cancel.check()
    output = root.run_tool(
        "apt-cache",
        ["policy", package],
        timeout=180,
        env_extra={"LC_ALL": "C"},
    )
    data = parse_policy_output(output, package)
    data["root"] = root.root_info()
    data["baseline"] = root.baseline_info()
    if not data["versions"]:
        raise KylinPkgError(
            "没有找到 %s 的可用版本；请检查包名、架构和源配置（可用 profile show 查看）" % package
        )
    return data


def _requested_name(spec: str) -> str:
    name = spec.split("=", 1)[0]
    if ":" in name:
        head, tail = name.rsplit(":", 1)
        if tail in ("all", "any") or re.match(r"^[a-z0-9][a-z0-9-]*$", tail):
            name = head
    return name


def _annotate_baseline(
    entries: List[PlanEntry], installed: Dict[Tuple[str, str], str]
) -> None:
    for entry in entries:
        version = ""
        if entry.package:
            version = installed.get((entry.package, entry.architecture), "")
            if not version:
                version = installed.get((entry.package, "all"), "")
        if not version:
            entry.baseline_state = "new"
        elif version == entry.version:
            entry.baseline_state = "assumed"
        else:
            entry.baseline_state = "upgrade"


def _satisfied_requests(
    requested: Sequence[str],
    entries: Sequence[PlanEntry],
    installed: Dict[Tuple[str, str], str],
) -> List[str]:
    have_names = {entry.package for entry in entries}
    installed_names = {name for (name, _arch) in installed}
    satisfied: List[str] = []
    for spec in requested:
        name = _requested_name(spec)
        # 计划里有的包会被下载；只有不在计划里、但基线已装的才算“无需下载”。
        if name not in have_names and name in installed_names:
            satisfied.append(spec)
    return satisfied


def apt_error_hint(output: str) -> str:
    text = output or ""
    hints: List[str] = []
    if "NO_PUBKEY" in text or "没有公钥" in text:
        hints.append("源签名密钥缺失：把对应 keyring 导入 profile（--keyring 或 --from-system）")
    if "无法定位软件包" in text or "Unable to locate package" in text:
        hints.append("包名或架构不对，或该组件/架构没有这个包；确认 -a 与源里的 components")
    if "没有可安装候选" in text or "no installation candidate" in text:
        hints.append("目标架构没有候选版本：检查是否只挂了叠加 suite、漏了基础 suite 或组件")
    if "但无法安装它" in text or "but it is not installable" in text:
        hints.append("依赖链断在另一个包：常见原因是漏挂基础 suite（如 10.1-kylin）或漏组件（libc6 在 universe）")
    if "Release file" in text and "not found" in text:
        hints.append("suite 名称或 URI 不对：检查 sources 是否与目标小版本匹配")
    if not hints:
        hints.append("查看上方 apt 原始错误；可用 kylinpkg profile show 核对源与 pin")
    return "\n".join("提示：" + hint for hint in hints)


def resolve(
    state: State,
    profile_name: str,
    packages: Sequence[str],
    architectures: Optional[Sequence[str]] = None,
    baseline_name: Optional[str] = None,
    recommends: bool = True,
    no_update: bool = False,
    force_update: bool = False,
    with_dependencies: bool = True,
    cancel: Optional[CancelToken] = None,
) -> ResolvePlan:
    if not packages:
        raise KylinPkgError("至少指定一个软件包")
    root = AptRoot(state, profile_name, architectures, baseline_name, cancel=cancel)
    root.update(force=force_update, no_update=no_update)
    if cancel is not None:
        cancel.check()

    installed: Dict[Tuple[str, str], str] = {}
    if with_dependencies and root.baseline_name != baseline_mod.RESERVED_EMPTY:
        paragraphs = baseline_mod.read_status_paragraphs(state, root.baseline_name)
        installed = deb822.installed_version_map(paragraphs)

    if with_dependencies:
        args: List[str] = ["--print-uris", "-y", "--download-only"]
        if not recommends:
            args.append("--no-install-recommends")
        args.append("install")
    else:
        # apt-get download 只取请求的包本身，不解析依赖
        args = ["--print-uris", "download"]
    args.extend(packages)

    try:
        output = root.run_apt(args, timeout=600)
    except KylinPkgError as exc:
        detail = str(exc)
        raise KylinPkgError("%s\n%s" % (detail, apt_error_hint(detail))) from exc

    entries = parse_print_uris(output)
    _annotate_baseline(entries, installed)
    warnings: List[str] = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith(("W:", "警告：")):
            if line not in warnings:
                warnings.append(line)
    satisfied = _satisfied_requests(packages, entries, installed)
    if not entries and not satisfied:
        warnings.append("apt 未返回任何下载项；请用 apt-cache policy 核对请求与源")
    plan = ResolvePlan(
        requested=list(packages),
        entries=entries,
        requested_satisfied=satisfied,
        baseline=root.baseline_info(),
        root=root.root_info(),
        recommends=recommends,
        with_dependencies=with_dependencies,
        warnings=warnings,
    )
    return plan


def resolve_specs(
    state: State,
    profile_name: str,
    specs: Sequence[str],
    architectures: Optional[Sequence[str]] = None,
    baseline_name: Optional[str] = None,
    recommends: bool = True,
    no_update: bool = False,
    force_update: bool = False,
    with_dependencies: bool = True,
    cancel: Optional[CancelToken] = None,
) -> List[ResolvePlan]:
    """支持同一软件包的多个版本：同一包的多个版本拆成独立 apt 事务。

    不同的包如果各自只选了一个版本，仍然放在同一个事务里，保证依赖一次解析完。
    """
    unique: List[str] = []
    seen = set()
    for spec in specs:
        spec = (spec or "").strip()
        if spec and spec not in seen:
            seen.add(spec)
            unique.append(spec)
    if not unique:
        raise KylinPkgError("至少指定一个软件包")

    native_arch = architectures[0] if architectures else None

    def group_key(spec: str) -> str:
        base = spec.split("=", 1)[0]
        if native_arch and ":" in base:
            name, arch = base.rsplit(":", 1)
            if arch == native_arch:
                return name
        return base

    groups: Dict[str, List[str]] = {}
    for spec in unique:
        groups.setdefault(group_key(spec), []).append(spec)

    shared = [spec for spec in unique if len(groups[group_key(spec)]) == 1]
    separate = [spec for spec in unique if len(groups[group_key(spec)]) > 1]

    plans: List[ResolvePlan] = []
    first = True

    def add_plan(group_specs: Sequence[str]) -> None:
        nonlocal first
        plans.append(
            resolve(
                state,
                profile_name,
                group_specs,
                architectures=architectures,
                baseline_name=baseline_name,
                recommends=recommends,
                no_update=no_update,
                force_update=(force_update and first),
                with_dependencies=with_dependencies,
                cancel=cancel,
            )
        )
        first = False

    if shared:
        add_plan(shared)
    for spec in separate:
        add_plan([spec])
    return plans


def plan_totals(plans: Sequence[ResolvePlan]) -> Dict[str, int]:
    entries = {}
    for plan in plans:
        for entry in plan.entries:
            entries.setdefault(entry.filename, entry)
    return {
        "count": len(entries),
        "bytes": sum(entry.size for entry in entries.values()),
    }


def plan_as_dict(plan: ResolvePlan) -> Dict[str, object]:
    return {
        "requested": list(plan.requested),
        "requested_satisfied": list(plan.requested_satisfied),
        "baseline": plan.baseline,
        "root": plan.root,
        "recommends": plan.recommends,
        "with_dependencies": plan.with_dependencies,
        "totals": {"count": len(plan.entries), "bytes": plan.total_size},
        "packages": [
            {
                "package": entry.package,
                "version": entry.version,
                "architecture": entry.architecture,
                "filename": entry.filename,
                "size": entry.size,
                "uri": entry.uri,
                "source": entry.source,
                "hash": ("%s:%s" % (entry.hash_type, entry.hash_value))
                if entry.hash_type
                else "",
                "baseline_state": entry.baseline_state,
            }
            for entry in plan.entries
        ],
        "warnings": list(plan.warnings),
    }


def format_plan(plan: ResolvePlan) -> str:
    lines: List[str] = []
    baseline = plan.baseline or {}
    mode = "全量闭包" if baseline.get("mode") == "full" else "增量（相对基线 %s）" % baseline.get("name")
    deps = "完整依赖" if plan.with_dependencies else "仅当前包"
    lines.append(
        "profile: %s   架构: %s   模式: %s   依赖: %s"
        % (
            plan.root.get("profile", "?"),
            ",".join(plan.root.get("architectures") or []),
            mode,
            deps,
        )
    )
    if baseline.get("mode") != "full":
        lines.append("基线已安装包数：%s" % baseline.get("installed_count", 0))
    if not plan.entries:
        lines.append("无需下载：请求的包已由基线满足，或没有可下载的内容。")
    else:
        header = ("软件包", "版本", "架构", "大小", "状态", "来源")
        rows = [
            (
                entry.package or entry.filename,
                entry.version or "-",
                entry.architecture or "-",
                human_size(entry.size),
                {"new": "新增", "upgrade": "升级", "assumed": "基线已有"}.get(
                    entry.baseline_state, entry.baseline_state
                ),
                entry.source or "-",
            )
            for entry in plan.entries
        ]
        widths = [len(item) for item in header]
        for row in rows:
            widths = [max(widths[i], len(row[i])) for i in range(len(header))]
        fmt = "  ".join("{:<%d}" % width for width in widths)
        lines.append(fmt.format(*header))
        lines.append(fmt.format(*["-" * width for width in widths]))
        for row in rows:
            lines.append(fmt.format(*row))
        lines.append("")
        lines.append("共 %d 个包，%s" % (len(plan.entries), human_size(plan.total_size)))
    if plan.requested_satisfied:
        lines.append("已满足/无需下载的请求：%s" % ", ".join(plan.requested_satisfied))
    for warning in plan.warnings:
        lines.append("警告：" + warning)
    return "\n".join(lines)
