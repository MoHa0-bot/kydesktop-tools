# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""kylinpkg 命令行入口。"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import __version__
from . import baseline as baseline_mod
from . import bundle as bundle_mod
from . import downloader, history as history_mod, presets as presets_mod, profile as profile_mod, repo as repo_mod, resolver
from .arch import arch_key, detect_system_archs, parse_arch_list
from .aptroot import AptRoot
from .config import State, default_output_dir
from .manifest import read_manifest, verify_manifest
from .util import KylinPkgError, human_size, run


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(str(h)) for h in headers]
    for row in rows:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))
    fmt = "  ".join("{:<%d}" % width for width in widths)
    lines = [fmt.format(*headers), fmt.format(*["-" * width for width in widths])]
    lines.extend(fmt.format(*row) for row in rows)
    return "\n".join(lines)


def _print_warnings(warnings: Sequence[str]) -> None:
    for warning in warnings:
        print("警告：%s" % warning, file=sys.stderr)


def _archs_for(state: State, args, profile_meta: Dict[str, object]) -> List[str]:
    if getattr(args, "arch", None):
        return parse_arch_list(args.arch)
    return list(profile_meta.get("architectures") or [])


def cmd_profile_import(args, state: State) -> int:
    if state.profile_dir(args.name).exists() and not args.force:
        raise KylinPkgError("profile 已存在：%s（加 --force 覆盖）" % args.name)
    capture_meta: Optional[Dict[str, object]] = None
    baseline_name = args.baseline
    architectures = parse_arch_list(args.arch) if args.arch else []
    if args.capture_baseline:
        if not (args.from_system or args.from_ssh or args.from_rootfs):
            raise KylinPkgError("--capture-baseline 需与 --from-system/--from-ssh/--from-rootfs 一起使用")
        if (
            baseline_name
            and baseline_name != args.capture_baseline
            and baseline_name != baseline_mod.RESERVED_EMPTY
        ):
            raise KylinPkgError("--baseline 与 --capture-baseline 名字不一致")
        capture_meta = baseline_mod.import_baseline(
            state,
            args.capture_baseline,
            from_system=args.from_system,
            from_ssh=args.from_ssh,
            from_rootfs=args.from_rootfs,
            note="captured by profile import",
            force=args.force,
        )
        if baseline_name != baseline_mod.RESERVED_EMPTY:
            baseline_name = baseline_name or args.capture_baseline
        if not architectures:
            architectures = list(capture_meta.get("architectures") or [])

    meta = profile_mod.import_profile(
        state,
        args.name,
        from_system=args.from_system,
        from_ssh=args.from_ssh,
        from_rootfs=args.from_rootfs,
        sources_files=args.sources_file,
        sources_dirs=args.sources_dir,
        preferences_files=args.preferences_file,
        preferences_dirs=args.preferences_dir,
        keyrings=args.keyring,
        architectures=architectures,
        baseline=baseline_name,
        note=args.note,
        force=args.force,
        copy_system_keys=not args.no_system_keyrings,
        include_auth=args.with_auth,
        auth_files=args.auth_file,
        auth_dirs=args.auth_dir,
    )
    print("已导入 profile：%s" % meta["name"])
    print("  架构：%s" % ", ".join(meta.get("architectures") or []))
    print("  基线：%s" % (meta.get("baseline") or "（无，默认全量闭包）"))
    print("  源配置：%d 条" % len(meta.get("sources_summary") or []))
    if capture_meta is not None:
        print(
            "  已抓取 baseline：%s（已安装 %s 个包）"
            % (capture_meta["name"], capture_meta.get("installed_count", 0))
        )
    _print_warnings(meta.get("warnings") or [])
    return 0


def cmd_profile_add(args, state: State) -> int:
    components = [item for item in args.components.replace(",", " ").split() if item]
    meta = profile_mod.add_kylin_profile(
        state,
        args.name,
        suites=args.kylin_suite or [],
        base_suite=args.kylin_base,
        uri=args.uri,
        components=components,
        architectures=parse_arch_list(args.arch) if args.arch else [],
        partner=args.partner,
        baseline=args.baseline,
        note=args.note,
        force=args.force,
    )
    print("已创建 profile：%s" % meta["name"])
    print("  架构：%s" % ", ".join(meta.get("architectures") or []))
    print("  基线：%s" % (meta.get("baseline") or "（无，默认全量闭包）"))
    for line in meta.get("sources_summary") or []:
        print("  %s" % line)
    _print_warnings(meta.get("warnings") or [])
    return 0


def cmd_profile_bind(args, state: State) -> int:
    baseline = None if args.baseline == baseline_mod.RESERVED_EMPTY else args.baseline
    meta = profile_mod.bind_baseline(state, args.name, baseline)
    print(
        "profile %s 的默认 baseline：%s"
        % (args.name, meta.get("baseline") or "空（全量闭包）")
    )
    return 0


def cmd_profile_list(args, state: State) -> int:
    items = profile_mod.list_profiles(state)
    if not items:
        print("还没有 profile。用 kylinpkg profile import 导入源配置。")
        return 0
    rows = []
    for meta in items:
        rows.append(
            [
                meta.get("name", "?"),
                ",".join(meta.get("architectures") or []),
                meta.get("baseline") or "-",
                len(meta.get("sources_summary") or []),
                meta.get("created_at", "-"),
            ]
        )
    print(_table(["名称", "架构", "默认基线", "源条数", "创建时间"], rows))
    return 0


def cmd_profile_show(args, state: State) -> int:
    meta = profile_mod.load_profile(state, args.name)
    if args.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
        return 0
    print("profile：%s" % meta.get("name"))
    print("  创建时间：%s" % meta.get("created_at"))
    print("  来源：%s %s" % ((meta.get("origin") or {}).get("kind"), (meta.get("origin") or {}).get("detail")))
    print("  架构：%s" % ", ".join(meta.get("architectures") or []))
    print("  默认基线：%s" % (meta.get("baseline") or "（无，默认全量闭包）"))
    if meta.get("note"):
        print("  备注：%s" % meta.get("note"))
    print("\n源：")
    for line in meta.get("sources_summary") or []:
        print("  %s" % line)
    print("\n文件：")
    for item in meta.get("files") or []:
        print("  %-42s %s  %s" % (item.get("path"), human_size(int(item.get("size", 0))), item.get("sha256", "")[:16]))
    _print_warnings(meta.get("warnings") or [])
    if args.raw:
        print("\n===== 原始文件 =====")
        pdir = state.profile_dir(args.name)
        for item in meta.get("files") or []:
            rel = item.get("path")
            path = pdir / str(rel)
            print("\n--- %s ---" % rel)
            if item.get("role") == "keyring":
                print("（二进制 keyring，已省略；请直接查看文件 %s）" % path)
                continue
            print(path.read_text(encoding="utf-8", errors="replace").rstrip())
    return 0


def cmd_profile_remove(args, state: State) -> int:
    profile_mod.remove_profile(state, args.name, purge_roots=args.purge_roots)
    print("已删除 profile：%s" % args.name)
    return 0


def cmd_profile_files(args, state: State) -> int:
    items = profile_mod.profile_files(state, args.name)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return 0
    rows = [
        [
            item.get("path", "?"),
            item.get("role", "?"),
            human_size(int(item.get("size", 0))),
            "是" if item.get("editable") else "否",
        ]
        for item in items
    ]
    print(_table(["文件", "类型", "大小", "可编辑"], rows))
    return 0


def cmd_profile_cat(args, state: State) -> int:
    if args.file:
        sys.stdout.write(profile_mod.read_profile_file(state, args.name, args.file))
        return 0
    if not args.all:
        raise KylinPkgError("请指定文件，或加 --all 打印全部可编辑文件")
    items = profile_mod.profile_files(state, args.name)
    for item in items:
        if not item.get("editable"):
            continue
        print("\n===== %s =====" % item.get("path"))
        text = profile_mod.read_profile_file(state, args.name, str(item["path"]))
        sys.stdout.write(text)
        if not text.endswith("\n"):
            print()
    return 0


def cmd_profile_set(args, state: State) -> int:
    if args.source:
        content = Path(args.source).expanduser().read_text(encoding="utf-8", errors="replace")
    else:
        if sys.stdin.isatty():
            raise KylinPkgError("请用 --from 指定内容文件，或通过管道传入内容")
        content = sys.stdin.read()
    meta = profile_mod.write_profile_file(state, args.name, args.file, content)
    print("已保存：%s" % args.file)
    _print_warnings(meta.get("warnings") or [])
    return 0


def cmd_profile_edit(args, state: State) -> int:
    content = profile_mod.read_profile_file(state, args.name, args.file)
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    tmp_path = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="kylinpkg-edit-", suffix=".txt")
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        try:
            rc = subprocess.call(shlex.split(editor) + [str(tmp_path)])
        except OSError as exc:
            raise KylinPkgError("无法启动编辑器 %r：%s" % (editor, exc)) from exc
        if rc != 0:
            raise KylinPkgError("编辑器退出码 %d，未保存" % rc)
        new_content = tmp_path.read_text(encoding="utf-8", errors="replace")
        if new_content == content:
            print("内容未变化")
            return 0
        meta = profile_mod.write_profile_file(state, args.name, args.file, new_content)
        print("已保存：%s" % args.file)
        _print_warnings(meta.get("warnings") or [])
        return 0
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def cmd_profile_rm_file(args, state: State) -> int:
    meta = profile_mod.delete_profile_file(state, args.name, args.file)
    print("已删除/清空：%s" % args.file)
    _print_warnings(meta.get("warnings") or [])
    return 0


def cmd_preset_list(args, state: State) -> int:
    items = presets_mod.list_presets(args.group)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": item.id,
                        "name": item.name,
                        "group": item.group,
                        "description": item.description,
                        "architectures": list(item.architectures),
                        "sources": list(item.sources),
                        "notes": list(item.notes),
                    }
                    for item in items
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    rows = [
        [item.group, item.id, item.name, ",".join(item.architectures) or "自动"]
        for item in items
    ]
    print(_table(["分组", "ID", "名称", "架构"], rows))
    print("\n共 %d 个预设；查看详情：kylinpkg preset show <ID>" % len(items))
    return 0


def cmd_preset_show(args, state: State) -> int:
    item = presets_mod.get_preset(args.preset_id)
    print("ID：%s" % item.id)
    print("名称：%s" % item.name)
    print("分组：%s" % item.group)
    print("说明：%s" % item.description)
    print("架构：%s" % (", ".join(item.architectures) or "自动/按机器"))
    print("\n源：")
    for line in item.sources:
        print("  " + line)
    if item.notes:
        print("\n注意：")
        for note in item.notes:
            print("  - " + note)
    return 0


def cmd_preset_create(args, state: State) -> int:
    meta = profile_mod.create_from_preset(
        state,
        args.profile,
        args.preset_id,
        architectures=parse_arch_list(args.arch) if args.arch else (),
        baseline=args.baseline,
        note=args.note,
        force=args.force,
    )
    print("已从预设创建 profile：%s" % meta["name"])
    print("  预设：%s" % args.preset_id)
    print("  架构：%s" % ", ".join(meta.get("architectures") or []))
    print("  基线：%s" % (meta.get("baseline") or "（无，默认全量闭包）"))
    print("  源：%d 条" % len(meta.get("sources_summary") or []))
    _print_warnings(meta.get("warnings") or [])
    print("查看/编辑：kylinpkg profile files %s；kylinpkg profile edit %s sources.list"
          % (meta["name"], meta["name"]))
    return 0


def cmd_baseline_import(args, state: State) -> int:
    name = args.name
    if getattr(args, "from_builtin", None) and not name:
        name = args.from_builtin
    if not name:
        raise KylinPkgError("请提供 baseline 名称，或用 --builtin 时省略名称以内置名命名")
    meta = baseline_mod.import_baseline(
        state,
        name,
        status_file=args.status_file,
        from_system=args.from_system,
        from_ssh=args.from_ssh,
        from_rootfs=args.from_rootfs,
        empty=args.empty,
        from_builtin=getattr(args, "from_builtin", None),
        note=args.note,
        force=args.force,
    )
    print("已导入 baseline：%s" % meta["name"])
    print("  来源：%s %s" % ((meta.get("origin") or {}).get("kind"), (meta.get("origin") or {}).get("detail")))
    print("  已安装包：%s / 记录 %s" % (meta.get("installed_count"), meta.get("package_count")))
    print("  架构：%s" % (", ".join(meta.get("architectures") or []) or "（空）"))
    print("  status sha256：%s" % meta.get("status_sha256"))
    _print_warnings(meta.get("warnings") or [])
    return 0


def cmd_baseline_list(args, state: State) -> int:
    items = baseline_mod.list_baselines(state)
    state_names = {meta.get("name") for meta in items}
    builtin_items = [
        meta
        for meta in baseline_mod.list_builtin_baselines()
        if meta.get("name") not in state_names
    ]
    if not items and not builtin_items:
        print("还没有 baseline。用 kylinpkg baseline import 导入 dpkg status，")
        print("或用 kylinpkg baseline import <名称> --builtin <内置名> 创建内置现场基线。")
        return 0
    rows = []
    for meta in items:
        rows.append(
            [
                meta.get("name", "?"),
                meta.get("installed_count", 0),
                meta.get("package_count", 0),
                ",".join(meta.get("architectures") or []) or "-",
                (meta.get("origin") or {}).get("kind", "-"),
                meta.get("created_at", "-"),
            ]
        )
    for meta in builtin_items:
        rows.append(
            [
                meta.get("name", "?") + " *",
                meta.get("installed_count", 0),
                meta.get("package_count", 0),
                ",".join(meta.get("architectures") or []) or "-",
                "内置（未导入）",
                (meta.get("created_at") or "-")[:10],
            ]
        )
    print(_table(["名称", "已安装", "记录数", "架构", "来源", "创建时间"], rows))
    if builtin_items:
        print("说明：带 * 的为随包分发的内置现场基线，尚未导入本机；")
        print("      用 kylinpkg baseline import <名称> --builtin <内置名> 创建可编辑副本。")
    return 0


def cmd_baseline_show(args, state: State) -> int:
    meta = baseline_mod.load_meta(state, args.name)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def cmd_baseline_remove(args, state: State) -> int:
    baseline_mod.remove_baseline(state, args.name)
    print("已删除 baseline：%s" % args.name)
    return 0


def cmd_update(args, state: State) -> int:
    meta = profile_mod.load_profile(state, args.profile)
    archs = _archs_for(state, args, meta)
    root = AptRoot(state, args.profile, archs)
    root.update(force=args.force)
    print("已更新隔离索引：%s" % root.root)
    print("  架构：%s" % ", ".join(root.architectures))
    print("  包索引文件数：%d" % len([p for p in root.lists_dir.iterdir() if p.is_file()]))
    return 0


def _make_plans(args, state: State):
    meta = profile_mod.load_profile(state, args.profile)
    baseline = _baseline_for_with_state(args, state, meta)
    archs = _archs_for(state, args, meta)
    if getattr(args, "no_update", False) and getattr(args, "force_update", False):
        raise KylinPkgError("--no-update 与 --force-update 不能同时使用")
    return resolver.resolve_specs(
        state,
        args.profile,
        args.packages,
        architectures=archs,
        baseline_name=baseline,
        recommends=not args.no_recommends,
        no_update=getattr(args, "no_update", False),
        force_update=getattr(args, "force_update", False),
        with_dependencies=not getattr(args, "no_deps", False),
    )


def _baseline_for_with_state(args, state: State, profile_meta: Dict[str, object]) -> str:
    if getattr(args, "full", False) and getattr(args, "baseline", None):
        raise KylinPkgError("--full 与 --baseline 不能同时使用")
    if getattr(args, "full", False):
        return baseline_mod.RESERVED_EMPTY
    if getattr(args, "baseline", None):
        name = args.baseline
    else:
        name = profile_meta.get("baseline") or baseline_mod.RESERVED_EMPTY
    if name != baseline_mod.RESERVED_EMPTY:
        baseline_mod.load_meta(state, name)
    return name


def _print_plans(plans) -> None:
    if len(plans) == 1:
        print(resolver.format_plan(plans[0]))
        return
    for index, plan in enumerate(plans, 1):
        print(
            "===== 请求组 %d：%s ====="
            % (index, " ".join(plan.requested))
        )
        print(resolver.format_plan(plan))
        print()
    totals = resolver.plan_totals(plans)
    print(
        "合并去重后：%d 个包，%s"
        % (totals["count"], human_size(totals["bytes"]))
    )


def cmd_resolve(args, state: State) -> int:
    plans = _make_plans(args, state)
    if args.json:
        if len(plans) == 1:
            print(json.dumps(resolver.plan_as_dict(plans[0]), ensure_ascii=False, indent=2))
        else:
            print(
                json.dumps(
                    {
                        "plans": [resolver.plan_as_dict(plan) for plan in plans],
                        "totals": resolver.plan_totals(plans),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    else:
        _print_plans(plans)
    return 0


def cmd_versions(args, state: State) -> int:
    meta = profile_mod.load_profile(state, args.profile)
    baseline = _baseline_for_with_state(args, state, meta)
    archs = _archs_for(state, args, meta)
    data = resolver.list_versions(
        state,
        args.profile,
        args.package,
        architectures=archs,
        baseline_name=baseline,
    )
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("软件包：%s" % data["package"])
    print("  已安装：%s" % (data.get("installed") or "无"))
    print("  候选：%s" % (data.get("candidate") or "无"))
    rows = []
    for item in data["versions"]:
        status = []
        if item.get("installed"):
            status.append("已安装")
        if item.get("candidate"):
            status.append("候选")
        rows.append(
            [
                item["version"],
                item["priority"],
                "/".join(status) or "-",
                ",".join(item.get("architectures") or []) or "-",
                "是" if item.get("downloadable") else "否",
                "; ".join(item.get("sources") or []) or "-",
            ]
        )
    print(_table(["版本", "优先级", "状态", "架构", "可下载", "来源"], rows))
    print("\n下载指定版本：kylinpkg download -p %s <包名>=<版本>" % args.profile)
    return 0


def _print_download_summary(out_dir: Path, result: Dict[str, object], make_repo: bool) -> None:
    if result.get("reused"):
        print("输出目录已有完整结果，校验通过，未重复下载：%s" % out_dir)
    else:
        print("下载完成：%s" % out_dir)
        print("  包数：%s" % result.get("total", 0))
        print("  本次新下载：%s" % result.get("downloaded", 0))
        print("  总大小：%s" % human_size(int(result.get("total_bytes", 0))))
        if int(result.get("plans", 1)) > 1:
            print("  版本/请求组：%s" % result.get("plans"))
    print("  manifest：%s" % (out_dir / "manifest.json"))
    if make_repo:
        if (out_dir / "sources.list").is_file():
            print("  离线源：%s" % out_dir)
            print("  目标机 sources：%s" % (out_dir / "sources.list"))
        else:
            print("  未生成离线源（没有可用的 .deb）")
    _print_warnings(list(result.get("warnings") or []))


def cmd_download(args, state: State) -> int:
    plans = _make_plans(args, state)
    if not args.quiet:
        _print_plans(plans)
        print()
    if args.output:
        out_dir = Path(args.output).expanduser()
    else:
        out_dir = default_output_dir(
            args.profile, arch_key(plans[0].root.get("architectures") or [])
        )
    if len(plans) == 1:
        result = downloader.download(
            state, plans[0], out_dir, force=args.force, make_repo=args.repo
        )
    else:
        result = downloader.download_plans(
            state, plans, out_dir, force=args.force, make_repo=args.repo
        )
    if result.get("reused") and args.repo:
        repo_mod.build_repo(out_dir)
    _print_download_summary(out_dir, result, make_repo=args.repo)
    return 0


def cmd_history_list(args, state: State) -> int:
    entries = history_mod.list_tasks(state, limit=args.limit)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0
    if not entries:
        print("还没有下载任务记录。每次 kylinpkg download（CLI 或 GUI）都会自动记录。")
        return 0
    rows = []
    for entry in entries:
        packages = " ".join(entry.get("requested") or [])
        if len(packages) > 38:
            packages = packages[:37] + "…"
        rows.append(
            [
                entry.get("id", "?"),
                str(entry.get("created_at", "?")).replace("T", " "),
                history_mod.status_label(str(entry.get("status", ""))),
                entry.get("profile", "?"),
                packages or "-",
                entry.get("output", "-"),
            ]
        )
    print(_table(["ID", "时间", "状态", "profile", "软件包", "输出目录"], rows))
    print("\n详情：kylinpkg history show <ID>；重做：kylinpkg history redo <ID>")
    return 0


def cmd_history_show(args, state: State) -> int:
    entry = history_mod.find_task(state, args.id)
    if args.json:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0
    baseline = entry.get("baseline")
    print("任务：%s" % entry.get("id"))
    print("  时间：%s" % entry.get("created_at"))
    print("  状态：%s" % history_mod.status_label(str(entry.get("status", ""))))
    print("  profile：%s" % entry.get("profile"))
    print("  架构：%s" % (", ".join(entry.get("architectures") or []) or "-"))
    print("  基线：%s" % (baseline if baseline else "空（全量闭包）"))
    print("  软件包：%s" % (" ".join(entry.get("requested") or []) or "-"))
    print(
        "  选项：Recommends=%s，依赖=%s，离线源=%s，覆盖=%s"
        % (
            "是" if entry.get("recommends", True) else "否",
            "是" if entry.get("with_dependencies", True) else "否",
            "是" if entry.get("make_repo") else "否",
            "是" if entry.get("force") else "否",
        )
    )
    print("  输出目录：%s" % entry.get("output"))
    if entry.get("plans"):
        print("  版本/请求组：%s" % entry.get("plans"))
    if entry.get("package_count") is not None:
        print(
            "  结果：%s 个包，%s"
            % (entry.get("package_count"), human_size(int(entry.get("total_bytes", 0) or 0)))
        )
    if entry.get("error"):
        print("  错误：%s" % entry.get("error"))
    print("\n套用到当前（等价命令）：")
    print("  " + history_mod.equivalent_command(entry))
    print("直接重做：kylinpkg history redo %s" % args.id)
    return 0


def cmd_history_redo(args, state: State) -> int:
    entry = history_mod.find_task(state, args.id)
    if args.repo and args.no_repo:
        raise KylinPkgError("--repo 与 --no-repo 不能同时使用")
    make_repo = True if args.repo else (False if args.no_repo else None)
    out_dir = Path(args.output).expanduser() if args.output else None
    result = history_mod.redo_task(
        state,
        entry,
        output=out_dir,
        force=args.force,
        make_repo=make_repo,
        log=None if args.quiet else print,
    )
    final_dir = (
        Path(args.output).expanduser()
        if args.output
        else Path(str(entry.get("output"))).expanduser()
    )
    make_repo_effective = bool(
        make_repo if make_repo is not None else entry.get("make_repo")
    )
    if result.get("reused") and make_repo_effective:
        repo_mod.build_repo(final_dir)
    _print_download_summary(final_dir, result, make_repo=make_repo_effective)
    return 0


def cmd_history_remove(args, state: State) -> int:
    entry = history_mod.remove_task(state, args.id)
    print("已删除任务记录：%s" % entry.get("id"))
    return 0


def cmd_history_clear(args, state: State) -> int:
    if not args.yes:
        raise KylinPkgError("将清空全部下载任务记录；确认请加 --yes")
    count = history_mod.clear_tasks(state)
    print("已清空 %d 条任务记录（已下载的结果文件不受影响）" % count)
    return 0


def cmd_repo(args, state: State) -> int:
    out_dir = Path(args.dir).expanduser()
    repo_mod.build_repo(out_dir, suite=args.suite, origin=args.origin, label=args.label)
    errors, warnings = repo_mod.verify_repo(out_dir)
    print("已生成离线源：%s" % out_dir.resolve())
    print("  Packages / Packages.gz / Release / sources.list 已写入")
    _print_warnings(warnings)
    if errors:
        for error in errors:
            print("错误：%s" % error, file=sys.stderr)
        return 1
    print("校验通过")
    return 0


def cmd_verify(args, state: State) -> int:
    out_dir = Path(args.dir).expanduser()
    if (out_dir / "Packages").is_file():
        errors, warnings = repo_mod.verify_repo(out_dir)
    else:
        errors, warnings = verify_manifest(out_dir)
    _print_warnings(warnings)
    if errors:
        for error in errors:
            print("错误：%s" % error, file=sys.stderr)
        print("校验失败：%d 个问题" % len(errors), file=sys.stderr)
        return 1
    print("校验通过：%s" % out_dir.resolve())
    return 0


def cmd_list_output(args, state: State) -> int:
    print(repo_mod.list_repo(Path(args.dir).expanduser()))
    return 0


def cmd_bundle_inspect(args, state: State) -> int:
    info = bundle_mod.inspect_bundle(Path(args.archive))
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    meta = info.get("bundle") or {}
    baseline = info.get("baseline") or {}
    print("收集包：%s" % info.get("archive"))
    print("  主机：%s" % meta.get("hostname", "-"))
    print("  系统：%s %s" % (meta.get("os_name", "-"), meta.get("os_version", "")))
    print("  架构：%s" % (", ".join(info.get("architectures") or []) or "-"))
    print("  已安装包：%s / 记录 %s" % (baseline.get("installed_count"), baseline.get("package_count")))
    print("  源：%s 条" % info.get("sources"))
    _print_warnings(info.get("warnings") or [])
    return 0


def cmd_bundle_import(args, state: State) -> int:
    result = bundle_mod.import_bundle(
        state,
        Path(args.archive),
        profile_name=args.profile,
        baseline_name=args.baseline,
        architectures=parse_arch_list(args.arch) if args.arch else None,
        bind_baseline=not args.no_bind,
        force=args.force,
    )
    print("已导入收集包")
    print("  profile：%s" % result["profile"])
    print("  baseline：%s（已安装 %s 个包）" % (result["baseline"], result.get("installed_count", 0)))
    print("  架构：%s" % ", ".join(result.get("architectures") or []))
    print("  源：%s 条" % result.get("sources", 0))
    print("  绑定为默认基线：%s" % ("是" if result.get("bound") else "否"))
    _print_warnings(result.get("warnings") or [])
    print("下一步：kylinpkg resolve -p %s <包名>" % result["profile"])
    return 0


def cmd_gui(args, state: State) -> int:
    try:
        from .gui import run_gui
    except ImportError as exc:
        raise KylinPkgError(
            "图形界面需要 tkinter；Debian/Ubuntu 系可安装 python3-tk（%s）" % exc
        ) from exc
    try:
        run_gui(state)
    except Exception as exc:  # tkinter 在没有 DISPLAY 时会抛 TclError
        raise KylinPkgError("图形界面启动失败：%s" % exc) from exc
    return 0


def cmd_doctor(args, state: State) -> int:
    print("kylinpkg %s" % __version__)
    print("状态目录：%s" % state.root)
    print("Python：%s" % sys.version.split()[0])
    commands = ["apt-get", "dpkg", "dpkg-deb", "apt-ftparchive", "dpkg-scanpackages", "gzip", "ssh", "tar"]
    rows = [[name, shutil.which(name) or "缺失"] for name in commands]
    print(_table(["命令", "路径"], rows))
    for name in ("apt-get", "dpkg"):
        path = shutil.which(name)
        if path:
            proc = run([path, "--version"], check=False)
            first = (proc.stdout or "").splitlines()[:1]
            print("%s：%s" % (name, first[0] if first else "?"))
    try:
        host_archs = detect_system_archs()
    except KylinPkgError as exc:
        host_archs = ["?（%s）" % exc]
    print("本机架构：%s" % ", ".join(host_archs))
    try:
        import tkinter

        tk_status = "可用（Tk %s）" % tkinter.TkVersion
    except Exception as exc:  # noqa: BLE001 - 只用于报告可选依赖
        tk_status = "不可用：%s" % exc
    print("tkinter：%s" % tk_status)
    print("profiles：%d    baselines：%d" % (len(profile_mod.list_profiles(state)), len(baseline_mod.list_baselines(state))))
    missing = [name for name in commands if not shutil.which(name)]
    if missing:
        print("缺失命令：%s（部分功能不可用）" % ", ".join(missing))
    return 0


def cmd_gc(args, state: State) -> int:
    if not args.roots:
        raise KylinPkgError("当前仅支持 --roots/--cache（清理可重建的隔离索引）")
    freed = state.clear_cache(args.profile)
    if args.profile:
        print(
            "已清理 profile %s 的隔离缓存，释放 %s"
            % (args.profile, human_size(freed))
        )
    else:
        print("已清理全部隔离缓存，释放 %s" % human_size(freed))
    return 0


def _add_plan_args(parser: argparse.ArgumentParser, with_output: bool = False) -> None:
    parser.add_argument("-p", "--profile", required=True, help="profile 名称")
    parser.add_argument("-a", "--arch", help="目标架构，逗号分隔；默认用 profile 记录的架构")
    parser.add_argument("--full", action="store_true", help="使用空基线（全量依赖闭包）")
    parser.add_argument("--baseline", help="临时指定 baseline 名称（empty 表示全量）")
    parser.add_argument("--no-recommends", action="store_true", help="不安装 Recommends")
    parser.add_argument(
        "--no-deps",
        action="store_true",
        help="只下载请求的包本身，不解析/下载依赖",
    )
    parser.add_argument("--no-update", action="store_true", help="不刷新索引")
    parser.add_argument("--force-update", action="store_true", help="强制清空并刷新索引")
    if with_output:
        parser.add_argument("-o", "--output", help="输出目录")
        parser.add_argument("--repo", action="store_true", help="同时生成离线 apt 源")
        parser.add_argument("--force", action="store_true", help="覆盖已有输出目录")
        parser.add_argument("--quiet", action="store_true", help="不打印下载计划")
    parser.add_argument("packages", nargs="+", help="软件包名（可带 :arch）")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kylinpkg",
        description="多源、多架构 deb 包与依赖离线下载器（隔离 apt root，不改动本机）",
    )
    parser.add_argument("--state", type=Path, help="状态目录（默认 ~/.local/share/kylinpkg）")
    parser.add_argument("--debug", action="store_true", help="显示异常堆栈")
    parser.add_argument("--version", action="version", version="kylinpkg %s" % __version__)

    sub = parser.add_subparsers(dest="command", required=True)

    p_profile = sub.add_parser("profile", help="管理 apt 源配置")
    p_profile_sub = p_profile.add_subparsers(dest="profile_cmd", required=True)

    p_import = p_profile_sub.add_parser("import", help="导入一套 apt sources（文件/本机/SSH/rootfs）")
    p_import.add_argument("name")
    p_import.add_argument("--from-system", action="store_true", help="抓取本机 /etc/apt")
    p_import.add_argument("--from-ssh", metavar="[USER@]HOST", help="抓取远端 /etc/apt（需免密）")
    p_import.add_argument("--from-rootfs", type=Path, metavar="DIR", help="从解开的 rootfs 抓取")
    p_import.add_argument("--sources-file", type=Path, action="append", default=[], help="导入 .list/.sources 文件")
    p_import.add_argument("--sources-dir", type=Path, action="append", default=[], help="导入源文件目录")
    p_import.add_argument("--preferences-file", type=Path, action="append", default=[])
    p_import.add_argument("--preferences-dir", type=Path, action="append", default=[])
    p_import.add_argument("--keyring", type=Path, action="append", default=[], help="额外 keyring")
    p_import.add_argument("--no-system-keyrings", action="store_true", help="不复制本机 keyring")
    p_import.add_argument("--with-auth", action="store_true", help="同时收集/使用 auth.conf 凭据")
    p_import.add_argument("--auth-file", type=Path, action="append", default=[], help="auth.conf 文件")
    p_import.add_argument("--auth-dir", type=Path, action="append", default=[], help="auth.conf.d 目录")
    p_import.add_argument("--arch", help="目标架构，逗号分隔（缺省按来源检测）")
    p_import.add_argument("--baseline", help="绑定默认 baseline 名称")
    p_import.add_argument("--capture-baseline", metavar="NAME", help="同时从同一来源抓取 dpkg status")
    p_import.add_argument("--note", default="")
    p_import.add_argument("--force", action="store_true")
    p_import.set_defaults(func=cmd_profile_import)

    p_add = p_profile_sub.add_parser("add", help="按 Kylin suite 快捷生成源配置")
    p_add.add_argument("name")
    p_add.add_argument("--kylin-suite", action="append", default=[], help="叠加 suite，可重复")
    p_add.add_argument("--kylin-base", default="10.1-kylin", help="基础 suite（默认 10.1-kylin）")
    p_add.add_argument("--uri", default="http://archive.kylinos.cn/kylin/KYLIN-ALL")
    p_add.add_argument("--components", default="main,restricted,universe,multiverse")
    p_add.add_argument("--partner", action="store_true", help="附加 partner 源")
    p_add.add_argument("--arch", help="目标架构，逗号分隔")
    p_add.add_argument("--baseline")
    p_add.add_argument("--note", default="")
    p_add.add_argument("--force", action="store_true")
    p_add.set_defaults(func=cmd_profile_add)

    p_bind = p_profile_sub.add_parser("bind", help="绑定/解绑默认 baseline")
    p_bind.add_argument("name")
    p_bind.add_argument("--baseline", required=True, help="baseline 名称；empty 表示全量闭包")
    p_bind.set_defaults(func=cmd_profile_bind)

    p_plist = p_profile_sub.add_parser("list", help="列出 profile")
    p_plist.set_defaults(func=cmd_profile_list)

    p_show = p_profile_sub.add_parser("show", help="查看 profile")
    p_show.add_argument("name")
    p_show.add_argument("--json", action="store_true")
    p_show.add_argument("--raw", action="store_true", help="打印原始 sources/preferences 文件")
    p_show.set_defaults(func=cmd_profile_show)

    p_prem = p_profile_sub.add_parser("remove", help="删除 profile")
    p_prem.add_argument("name")
    p_prem.add_argument("--purge-roots", action="store_true", help="同时删除它的隔离 root")
    p_prem.set_defaults(func=cmd_profile_remove)

    p_pfiles = p_profile_sub.add_parser("files", help="列出 profile 中的源配置/keyring 文件")
    p_pfiles.add_argument("name")
    p_pfiles.add_argument("--json", action="store_true")
    p_pfiles.set_defaults(func=cmd_profile_files)

    p_pcat = p_profile_sub.add_parser("cat", help="查看源配置文件内容")
    p_pcat.add_argument("name")
    p_pcat.add_argument("file", nargs="?")
    p_pcat.add_argument("--all", action="store_true", help="打印全部可编辑文件")
    p_pcat.set_defaults(func=cmd_profile_cat)

    p_pset = p_profile_sub.add_parser("set", help="用文件或 stdin 覆盖某个源配置文件")
    p_pset.add_argument("name")
    p_pset.add_argument("file", help="例如 sources.list 或 sources.list.d/kylin.list")
    p_pset.add_argument("--from", dest="source", type=Path, help="内容来源文件；缺省读 stdin")
    p_pset.set_defaults(func=cmd_profile_set)

    p_pedit = p_profile_sub.add_parser("edit", help="用 $EDITOR 编辑源配置文件")
    p_pedit.add_argument("name")
    p_pedit.add_argument("file")
    p_pedit.set_defaults(func=cmd_profile_edit)

    p_prm = p_profile_sub.add_parser("rm-file", help="删除/清空某个源配置文件")
    p_prm.add_argument("name")
    p_prm.add_argument("file")
    p_prm.set_defaults(func=cmd_profile_rm_file)

    p_preset = sub.add_parser("preset", help="内置麒麟源预设")
    p_preset_sub = p_preset.add_subparsers(dest="preset_cmd", required=True)
    p_prlist = p_preset_sub.add_parser("list", help="列出预设")
    p_prlist.add_argument("--group", help="只显示某个分组")
    p_prlist.add_argument("--json", action="store_true")
    p_prlist.set_defaults(func=cmd_preset_list)
    p_prshow = p_preset_sub.add_parser("show", help="查看预设的源地址")
    p_prshow.add_argument("preset_id")
    p_prshow.set_defaults(func=cmd_preset_show)
    p_prcreate = p_preset_sub.add_parser("create", help="从预设创建可编辑 profile")
    p_prcreate.add_argument("preset_id")
    p_prcreate.add_argument("--profile", required=True, help="新 profile 名称")
    p_prcreate.add_argument("--arch", help="目标架构；缺省用预设架构或本机架构")
    p_prcreate.add_argument("--baseline", help="绑定默认 baseline")
    p_prcreate.add_argument("--note", default="")
    p_prcreate.add_argument("--force", action="store_true")
    p_prcreate.set_defaults(func=cmd_preset_create)

    p_base = sub.add_parser("baseline", help="管理 dpkg status 基线")
    p_base_sub = p_base.add_subparsers(dest="baseline_cmd", required=True)

    p_bimp = p_base_sub.add_parser(
        "import", help="导入 dpkg status（内置/文件/本机/SSH/rootfs/空）"
    )
    p_bimp.add_argument("name", nargs="?", default="", help="baseline 名称（--builtin 时可省略）")
    p_bimp.add_argument(
        "--builtin", metavar="NAME", dest="from_builtin",
        help="从随包分发的内置现场基线创建（kylinpkg baseline list 中带 * 的条目）",
    )
    p_bimp.add_argument("--status-file", type=Path, help="dpkg status 文件")
    p_bimp.add_argument("--from-system", action="store_true", help="使用本机 /var/lib/dpkg/status")
    p_bimp.add_argument("--from-ssh", metavar="[USER@]HOST", help="读取远端 /var/lib/dpkg/status")
    p_bimp.add_argument("--from-rootfs", type=Path, metavar="DIR", help="读取 rootfs 内的 status")
    p_bimp.add_argument("--empty", action="store_true", help="空基线（全量闭包）")
    p_bimp.add_argument("--note", default="")
    p_bimp.add_argument("--force", action="store_true")
    p_bimp.set_defaults(func=cmd_baseline_import)

    p_blist = p_base_sub.add_parser("list", help="列出 baseline")
    p_blist.set_defaults(func=cmd_baseline_list)

    p_bshow = p_base_sub.add_parser("show", help="查看 baseline 元数据")
    p_bshow.add_argument("name")
    p_bshow.set_defaults(func=cmd_baseline_show)

    p_brem = p_base_sub.add_parser("remove", help="删除 baseline")
    p_brem.add_argument("name")
    p_brem.set_defaults(func=cmd_baseline_remove)

    p_bundle = sub.add_parser("bundle", help="检查/导入原始主机收集包")
    p_bundle_sub = p_bundle.add_subparsers(dest="bundle_cmd", required=True)

    p_binspect = p_bundle_sub.add_parser("inspect", help="查看收集包内容，不导入")
    p_binspect.add_argument("archive")
    p_binspect.add_argument("--json", action="store_true")
    p_binspect.set_defaults(func=cmd_bundle_inspect)

    p_bimport = p_bundle_sub.add_parser("import", help="一键导入收集包中的 profile + baseline")
    p_bimport.add_argument("archive")
    p_bimport.add_argument("--profile", help="profile 名称（默认取主机名）")
    p_bimport.add_argument("--baseline", help="baseline 名称（默认 <profile>-baseline）")
    p_bimport.add_argument("--arch", help="覆盖目标架构，例如 arm64 或 amd64,i386")
    p_bimport.add_argument("--no-bind", action="store_true", help="导入 baseline 但不绑定为默认基线")
    p_bimport.add_argument("--force", action="store_true")
    p_bimport.set_defaults(func=cmd_bundle_import)

    p_update = sub.add_parser("update", help="刷新隔离 apt 索引")
    p_update.add_argument("-p", "--profile", required=True)
    p_update.add_argument("-a", "--arch")
    p_update.add_argument("--force", action="store_true", help="清空已有索引后重新下载")
    p_update.set_defaults(func=cmd_update)

    p_versions = sub.add_parser("versions", help="查看软件包所有可用版本（apt policy）")
    p_versions.add_argument("-p", "--profile", required=True)
    p_versions.add_argument("-a", "--arch")
    p_versions.add_argument("--full", action="store_true", help="使用空基线（全量闭包）")
    p_versions.add_argument("--baseline", help="临时指定 baseline")
    p_versions.add_argument("--json", action="store_true")
    p_versions.add_argument("package")
    p_versions.set_defaults(func=cmd_versions)

    p_resolve = sub.add_parser("resolve", help="只解析依赖，不下载")
    _add_plan_args(p_resolve)
    p_resolve.add_argument("--json", action="store_true")
    p_resolve.set_defaults(func=cmd_resolve)

    p_download = sub.add_parser("download", help="解析并下载 .deb + manifest（可生成离线源）")
    _add_plan_args(p_download, with_output=True)
    p_download.set_defaults(func=cmd_download)

    p_repo = sub.add_parser("repo", help="为已有下载目录生成离线 apt 源")
    p_repo.add_argument("dir")
    p_repo.add_argument("--suite", default="kylinpkg-offline")
    p_repo.add_argument("--origin", default="kylinpkg")
    p_repo.add_argument("--label", default="kylinpkg offline")
    p_repo.set_defaults(func=cmd_repo)

    p_verify = sub.add_parser("verify", help="校验下载目录/离线源")
    p_verify.add_argument("dir")
    p_verify.set_defaults(func=cmd_verify)

    p_list = sub.add_parser("list", help="列出下载目录中的包")
    p_list.add_argument("dir")
    p_list.set_defaults(func=cmd_list_output)

    p_gui = sub.add_parser("gui", help="启动图形界面")
    p_gui.set_defaults(func=cmd_gui)

    p_doctor = sub.add_parser("doctor", help="检查环境与依赖")
    p_doctor.set_defaults(func=cmd_doctor)

    p_gc = sub.add_parser("gc", help="清理可重建的隔离 root 缓存")
    p_gc.add_argument(
        "--roots",
        "--cache",
        dest="roots",
        action="store_true",
        help="清理隔离 apt 索引/包缓存（profile、baseline、下载结果不受影响）",
    )
    p_gc.add_argument("--profile", help="只清理某个 profile 的缓存")
    p_gc.set_defaults(func=cmd_gc)

    p_hist = sub.add_parser("history", help="查询下载任务记录（重新下载 / 套用配置）")
    p_hist_sub = p_hist.add_subparsers(dest="history_cmd", required=True)

    p_hlist = p_hist_sub.add_parser("list", help="列出最近的下载任务")
    p_hlist.add_argument("--limit", type=int, default=None, help="只显示最近 N 条")
    p_hlist.add_argument("--json", action="store_true")
    p_hlist.set_defaults(func=cmd_history_list)

    p_hshow = p_hist_sub.add_parser("show", help="查看任务详情与等价命令")
    p_hshow.add_argument("id", help="任务 ID（可唯一前缀）")
    p_hshow.add_argument("--json", action="store_true")
    p_hshow.set_defaults(func=cmd_history_show)

    p_hredo = p_hist_sub.add_parser("redo", help="按历史任务的配置重新下载")
    p_hredo.add_argument("id", help="任务 ID（可唯一前缀）")
    p_hredo.add_argument("-o", "--output", help="输出目录；缺省沿用原任务目录")
    p_hredo.add_argument("--force", action="store_true", help="覆盖已有输出目录")
    p_hredo.add_argument("--repo", action="store_true", help="强制生成离线 apt 源")
    p_hredo.add_argument("--no-repo", action="store_true", help="强制不生成离线 apt 源")
    p_hredo.add_argument("--quiet", action="store_true", help="不打印解析过程")
    p_hredo.set_defaults(func=cmd_history_redo)

    p_hrm = p_hist_sub.add_parser("remove", help="删除一条任务记录")
    p_hrm.add_argument("id", help="任务 ID（可唯一前缀）")
    p_hrm.set_defaults(func=cmd_history_remove)

    p_hclear = p_hist_sub.add_parser("clear", help="清空全部任务记录")
    p_hclear.add_argument("--yes", action="store_true", help="确认清空")
    p_hclear.set_defaults(func=cmd_history_clear)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    parser = build_parser()
    args = parser.parse_args(argv)
    state = State(args.state).ensure()
    try:
        return int(args.func(args, state))
    except KylinPkgError as exc:
        print("错误：%s" % exc, file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        print("已中断", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 - 顶层兜底，避免只看到半截堆栈
        print("内部错误：%s" % exc, file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
