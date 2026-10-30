# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""kylinpkg 图形界面（tkinter）。

界面只做三件事：
1. 导入/管理 apt 源配置 profile；
2. 导入/管理 dpkg status 基线 baseline；
3. 选择 profile + baseline，解析并下载软件包及其依赖。
"""

from __future__ import annotations

import argparse
import queue
import re
import shutil
import subprocess
import sys
import threading
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, simpledialog, ttk

from . import __version__
from . import baseline as baseline_mod
from . import bundle as bundle_mod
from . import downloader, history as history_mod, presets as presets_mod, profile as profile_mod, resolver
from . import deb822
from .arch import arch_key, detect_system_archs, parse_arch_list
from .config import State, default_output_dir
from .util import CancelToken, KylinPkgError, OperationCancelled, human_size

FULL_LABEL = "（全量闭包 / 不使用基线）"
NO_BIND_LABEL = "（不绑定）"

_UI_FONTS = (
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Micro Hei",
    "文泉驿微米黑",
    "微软雅黑",
    "Microsoft YaHei",
    "SimHei",
    "DejaVu Sans",
)
_MONO_FONTS = (
    "Noto Sans Mono CJK SC",
    "WenQuanYi Zen Hei Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
)

AUTO_ARCH_LABEL = "自动检测（按源/目标机）"

# 已确认的架构选项。GUI 直接显示 dpkg 架构名，内部仍使用 dpkg 架构名；
# 常见别名（x86_64/aarch64/mips64 等）在 arch.normalize_arch 中统一归一化。
# 已存在的 profile 若带其他架构（例如 sw64），会在选中时动态加入下拉框，
# 但不作为默认选项展示。
ARCH_OPTIONS = (
    ("amd64", "amd64"),
    ("arm64", "arm64"),
    ("mips64el", "mips64el"),
    ("loongarch64", "loongarch64"),
    ("i386", "i386（32 位 x86）"),
    ("amd64,i386", "amd64,i386（x86 + 32 位库）"),
)


def _arch_label(value: str) -> str:
    value = (value or "").strip()
    for arch, label in ARCH_OPTIONS:
        if arch == value:
            return label
    return value


def _arch_value(label: str) -> str:
    label = (label or "").strip()
    if label == AUTO_ARCH_LABEL:
        return ""
    for arch, text in ARCH_OPTIONS:
        if text == label:
            return arch
    return label


def _arch_labels(include_auto: bool = False, extra: Sequence[str] = ()) -> List[str]:
    labels = [label for _arch, label in ARCH_OPTIONS]
    for value in extra:
        value = (value or "").strip()
        if value and value not in {arch for arch, _label in ARCH_OPTIONS}:
            if value not in labels:
                labels.append(value)
    if include_auto:
        labels.insert(0, AUTO_ARCH_LABEL)
    return labels


def _setup_fonts(root: tk.Tk) -> None:
    try:
        families = set(tkfont.families(root))
    except Exception:
        families = set()
    ui = next((name for name in _UI_FONTS if name in families), None)
    mono = next((name for name in _MONO_FONTS if name in families), None)
    if ui:
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tkfont.nametofont(name).configure(family=ui, size=10)
            except Exception:
                pass
    if mono:
        try:
            tkfont.nametofont("TkFixedFont").configure(family=mono, size=10)
        except Exception:
            pass


_ICON_SIZES = (16, 32, 48, 64, 128, 256)
_ICON_DIR = Path(__file__).resolve().parent / "resources" / "icons"
# PhotoImage 对象必须保活，否则 Tk 侧图像会被回收导致图标消失
_icon_refs: List[tk.PhotoImage] = []


def _apply_window_icon(root: tk.Tk) -> None:
    """为窗口设置应用图标（标题栏 + 任务栏共用 _NET_WM_ICON）。

    tkinter 的 PhotoImage 不支持 SVG，因此加载随包分发的多尺寸 PNG；
    资源缺失或 Tcl 异常时静默跳过，不影响启动。
    """
    images: List[tk.PhotoImage] = []
    for size in _ICON_SIZES:
        path = _ICON_DIR / ("kylinpkg-%d.png" % size)
        if not path.is_file():
            continue
        try:
            img = tk.PhotoImage(file=str(path))
        except tk.TclError:
            continue
        images.append(img)
    if not images:
        return
    try:
        root.iconphoto(True, *images)
    except tk.TclError:
        return
    _icon_refs.extend(images)


class App:
    def __init__(self, root: tk.Tk, state: State):
        self.root = root
        self.state = state
        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.busy = False
        self._refreshing = False
        self._output_auto = True
        self._cancel_token: Optional[CancelToken] = None
        self._action_widgets: List[tk.Widget] = []

        self.root.title("kylinpkg - 麒麟 deb 离线下载器")
        self.root.geometry("1180x840")
        self.root.minsize(980, 700)
        _setup_fonts(self.root)
        self._try_theme()
        self._build_ui()
        self.refresh_all()
        self.root.after(100, self._poll)

    # ---------------------------------------------------------------- UI
    def _try_theme(self) -> None:
        try:
            style = ttk.Style(self.root)
            if "clam" in style.theme_names():
                style.theme_use("clam")
            # 主操作按钮（导入/下载等）使用强调色，视觉上与次要按钮区分。
            style.configure(
                "Accent.TButton",
                background="#2563eb",
                foreground="#ffffff",
                bordercolor="#1d4ed8",
                focuscolor="#ffffff",
                font=("TkDefaultFont", 10, "bold"),
                padding=(14, 4),
            )
            style.map(
                "Accent.TButton",
                background=[("pressed", "#1e40af"), ("active", "#1d4ed8"), ("disabled", "#93b4f5")],
                foreground=[("disabled", "#e5e7eb")],
            )
            style.configure("Hint.TLabel", foreground="#6b7280")
        except Exception:
            pass

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(3, weight=1)

        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew")
        # 先 pack 右侧按钮、再 pack 左侧标题：窗口变窄时标题先让位，
        # 按钮不会被挤出可视区域。
        history_button = ttk.Button(header, text="任务记录", command=self._history_dialog)
        history_button.pack(side="right", padx=(0, 0))
        self._action_widgets.append(history_button)
        cache_button = ttk.Button(header, text="清理缓存", command=self._clear_cache)
        cache_button.pack(side="right", padx=(6, 0))
        self._action_widgets.append(cache_button)
        bundle_button = ttk.Button(
            header, text="导入其他主机配置", command=self._bundle_import_dialog
        )
        bundle_button.pack(side="right", padx=(6, 0))
        self._action_widgets.append(bundle_button)
        refresh_button = ttk.Button(header, text="刷新列表", command=self._refresh_if_idle)
        refresh_button.pack(side="right", padx=(6, 0))
        self._action_widgets.append(refresh_button)
        ttk.Label(
            header,
            text="kylinpkg · 麒麟 deb 离线下载器",
            font=("TkDefaultFont", 13, "bold"),
        ).pack(side="left")
        self.root.bind("<F5>", lambda _event: self._refresh_if_idle())

        sources = ttk.Frame(main)
        sources.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        sources.columnconfigure(0, weight=1)
        sources.columnconfigure(1, weight=1)
        self._build_profile_panel(sources)
        self._build_baseline_panel(sources)

        self._build_params(main)
        self._build_log(main)
        self._build_status(main)
        self._build_menu()

    def _make_tree(
        self,
        parent: tk.Widget,
        columns: Sequence[str],
        headings: Sequence[str],
        widths: Sequence[int],
        height: int = 5,
    ) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame, columns=list(columns), show="headings", height=height, selectmode="browse"
        )
        for col, head, width in zip(columns, headings, widths):
            tree.heading(col, text=head)
            tree.column(col, width=width, minwidth=60, stretch=True)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        return tree

    def _build_profile_panel(self, parent: tk.Widget) -> None:
        frame = ttk.LabelFrame(parent, text="apt 源配置（profile）", padding=8)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.profile_tree = self._make_tree(
            frame,
            ("name", "arch", "baseline", "sources"),
            ("名称", "架构", "默认基线", "源条数"),
            (190, 110, 140, 70),
        )
        self.profile_tree.bind("<<TreeviewSelect>>", self._on_profile_select)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(6, 0))
        self._add_action_button(buttons, "从预设创建", self._preset_dialog)
        self._add_action_button(buttons, "从本机导入", self._quick_import_profile_system)
        self._add_action_button(buttons, "编辑源配置", self._profile_editor_dialog)
        more_button = ttk.Menubutton(buttons, text="更多")
        more_menu = tk.Menu(more_button, tearoff=0)
        more_menu.add_command(label="导入源配置", command=self._profile_import_dialog)
        more_menu.add_command(label="从 rootfs 导入", command=self._quick_import_profile_rootfs)
        more_button.configure(menu=more_menu)
        more_button.pack(side="left", padx=(0, 6))
        self._action_widgets.append(more_button)
        delete_button = ttk.Button(
            buttons, text="删除", width=6, command=self._delete_profile
        )
        delete_button.pack(side="left")
        self._action_widgets.append(delete_button)

    def _build_baseline_panel(self, parent: tk.Widget) -> None:
        frame = ttk.LabelFrame(parent, text="dpkg 初始状态（baseline）", padding=8)
        frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.baseline_tree = self._make_tree(
            frame,
            ("name", "installed", "arch", "kernel", "origin"),
            ("名称", "已安装包", "架构", "内核(linux-generic)", "来源"),
            (170, 70, 100, 130, 80),
        )
        self.baseline_tree.bind("<<TreeviewSelect>>", self._on_baseline_select)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(6, 0))
        self._add_action_button(buttons, "导入 status 文件", self._baseline_import_dialog)
        self._add_action_button(buttons, "从本机导入", self._quick_import_baseline_system)
        self._add_action_button(buttons, "删除", self._delete_baseline)

    def _add_action_button(self, parent: tk.Widget, text: str, command: Callable) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command)
        button.pack(side="left", padx=(0, 6))
        self._action_widgets.append(button)
        return button

    def _build_params(self, parent: tk.Widget) -> None:
        frame = ttk.LabelFrame(parent, text="下载参数", padding=8)
        frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self.profile_var = tk.StringVar()
        self.baseline_var = tk.StringVar(value=FULL_LABEL)
        self.arch_var = tk.StringVar()
        self.packages_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.recommends_var = tk.BooleanVar(value=True)
        self.with_dependencies_var = tk.BooleanVar(value=True)
        self.repo_var = tk.BooleanVar(value=True)
        self.force_var = tk.BooleanVar(value=False)
        self.force_update_var = tk.BooleanVar(value=False)

        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="apt 源配置：").pack(side="left")
        self.profile_combo = ttk.Combobox(
            row1, textvariable=self.profile_var, state="readonly", width=26
        )
        self.profile_combo.pack(side="left", padx=(0, 12))
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_combo)
        ttk.Label(row1, text="dpkg 基线：").pack(side="left")
        self.baseline_combo = ttk.Combobox(
            row1, textvariable=self.baseline_var, state="readonly", width=32, values=[FULL_LABEL]
        )
        self.baseline_combo.pack(side="left", padx=(0, 12))
        ttk.Label(row1, text="架构：").pack(side="left")
        self.arch_combo = ttk.Combobox(
            row1,
            textvariable=self.arch_var,
            state="readonly",
            width=28,
            values=_arch_labels(),
        )
        self.arch_combo.pack(side="left")

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="软件包：").pack(side="left")
        ttk.Entry(row2, textvariable=self.packages_var).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        self._add_action_button(row2, "选择版本", self._open_version_picker)
        self._add_action_button(row2, "解析计划", self._on_resolve)
        download_button = ttk.Button(
            row2, text="下载", style="Accent.TButton", command=self._on_download
        )
        download_button.pack(side="left")
        self._action_widgets.append(download_button)
        self.cancel_btn = ttk.Button(
            row2, text="中断", command=self._cancel_task, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=(6, 0))

        row3 = ttk.Frame(frame)
        row3.pack(fill="x", pady=2)
        ttk.Label(row3, text="输出目录：").pack(side="left")
        ttk.Entry(row3, textvariable=self.output_var).pack(
            side="left", fill="x", expand=True, padx=(0, 6)
        )
        ttk.Button(row3, text="浏览", command=self._browse_output).pack(side="left", padx=(0, 6))
        ttk.Button(row3, text="打开", command=self._open_output_dir).pack(side="left")

        row4 = ttk.Frame(frame)
        row4.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(
            row4, text="下载依赖（取消后仅当前包）", variable=self.with_dependencies_var
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(row4, text="包含 Recommends", variable=self.recommends_var).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(row4, text="下载后生成离线 apt 源", variable=self.repo_var).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(row4, text="覆盖已有输出", variable=self.force_var).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(row4, text="强制刷新索引", variable=self.force_update_var).pack(
            side="left"
        )

    def _build_log(self, parent: tk.Widget) -> None:
        frame = ttk.LabelFrame(parent, text="计划 / 日志", padding=8)
        frame.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(
            frame, wrap="none", font="TkFixedFont", height=14, state="disabled"
        )
        ysb = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        footer = ttk.Frame(frame)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(footer, text="清空日志", command=self._clear_log).pack(side="right")
        ttk.Button(footer, text="打开输出目录", command=self._open_output_dir).pack(
            side="right", padx=(0, 6)
        )

    def _build_status(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frame, textvariable=self.status_var, anchor="w").pack(
            side="left", fill="x", expand=True
        )
        self.progress = ttk.Progressbar(frame, mode="indeterminate", length=180)
        self.progress.pack(side="right")
        # 状态目录等长说明放到底部状态栏：窗口变窄时优先让位，不影响操作。
        ttk.Label(frame, text="隔离 apt root，不改本机；状态目录：%s" % self.state.root).pack(
            side="right", padx=(0, 8)
        )

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开状态目录", command=self._open_state_dir)
        file_menu.add_command(label="清理缓存", command=self._clear_cache)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.destroy)
        menubar.add_cascade(label="文件", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用手册", command=self._open_manual)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    # ------------------------------------------------------------ refresh
    def refresh_all(
        self, select_profile: Optional[str] = None, select_baseline: Optional[str] = None
    ) -> None:
        # 先刷新基线，再刷新 profile；profile 的默认 baseline 需要知道当前可选基线。
        self.refresh_baselines(select_baseline)
        self.refresh_profiles(select_profile)

    def refresh_profiles(self, select: Optional[str] = None) -> None:
        self._refreshing = True
        current = select or self.profile_var.get().strip()
        if not current:
            selection = self.profile_tree.selection()
            current = selection[0] if selection else ""
        self.profile_tree.delete(*self.profile_tree.get_children())
        names: List[str] = []
        for meta in profile_mod.list_profiles(self.state):
            name = str(meta.get("name") or "")
            if not name:
                continue
            names.append(name)
            self.profile_tree.insert(
                "",
                "end",
                iid=name,
                values=(
                    name,
                    ",".join(meta.get("architectures") or []),
                    meta.get("baseline") or "全量",
                    len(meta.get("sources_summary") or []),
                ),
            )
        self.profile_combo["values"] = names
        if names:
            chosen = current if current in names else names[0]
            self.profile_var.set(chosen)
            self.profile_tree.selection_set(chosen)
            self.profile_tree.see(chosen)
        else:
            self.profile_var.set("")
        self._refreshing = False
        if names:
            self._on_profile_select()
        else:
            self.status_var.set("还没有 apt 源配置，请先导入")

    def refresh_baselines(self, select: Optional[str] = None) -> None:
        self._refreshing = True
        current = select or self.baseline_var.get().strip()
        self.baseline_tree.delete(*self.baseline_tree.get_children())
        names: List[str] = []
        for meta in baseline_mod.list_baselines(self.state):
            name = str(meta.get("name") or "")
            if not name:
                continue
            names.append(name)
            origin = meta.get("origin") or {}
            meta = baseline_mod.ensure_kernel_info(self.state, meta)
            self.baseline_tree.insert(
                "",
                "end",
                iid=name,
                values=(
                    name,
                    meta.get("installed_count", 0),
                    ",".join(meta.get("architectures") or []),
                    meta.get("kernel_version", "-"),
                    origin.get("kind", "-"),
                ),
            )
        values = [FULL_LABEL] + names
        self.baseline_combo["values"] = values
        if select and select in names:
            self.baseline_tree.selection_set(select)
            self.baseline_tree.see(select)
            self.baseline_var.set(select)
        elif current not in values:
            self.baseline_var.set(FULL_LABEL)
        self._refreshing = False

    # ----------------------------------------------------------- selection
    def _set_arch_value(self, value: str) -> None:
        label = _arch_label(value)
        values = list(self.arch_combo["values"])
        if label and label not in values:
            values.append(label)
            self.arch_combo["values"] = values
        self.arch_var.set(label)

    def _current_arch_value(self) -> str:
        return _arch_value(self.arch_var.get())

    def _ask_arch(
        self, title: str, initial_value: str = "", allow_auto: bool = False
    ) -> Optional[str]:
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        extra = [initial_value] if initial_value else []
        values = _arch_labels(include_auto=allow_auto, extra=extra)
        if initial_value:
            default = _arch_label(initial_value)
        else:
            default = AUTO_ARCH_LABEL if allow_auto else values[0]
        if default not in values:
            values.append(default)
        var = tk.StringVar(value=default)
        ttk.Label(frame, text="目标架构：").grid(row=0, column=0, sticky="w")
        combo = ttk.Combobox(frame, textvariable=var, values=values, state="readonly", width=34)
        combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        result: Dict[str, Optional[str]] = {"value": None}

        def ok() -> None:
            result["value"] = _arch_value(var.get())
            self._release_grab(win)
            win.destroy()

        def cancel() -> None:
            self._release_grab(win)
            win.destroy()

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="确定", command=ok).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="取消", command=cancel).pack(side="right")
        win.bind("<Return>", lambda _event: ok())
        win.bind("<Escape>", lambda _event: cancel())
        self._center_dialog(win)
        self._make_modal(win)
        self.root.wait_window(win)
        return result["value"]

    def _refresh_if_idle(self) -> None:
        if not self.busy:
            self.refresh_all()

    def _on_profile_combo(self, _event=None) -> None:
        name = self.profile_var.get().strip()
        if name and name in self.profile_tree.get_children():
            self.profile_tree.selection_set(name)
            self.profile_tree.see(name)

    def _on_profile_select(self, _event=None) -> None:
        if self._refreshing:
            return
        selection = self.profile_tree.selection()
        name = selection[0] if selection else self.profile_var.get().strip()
        if not name:
            return
        self.profile_var.set(name)
        try:
            meta = profile_mod.load_profile(self.state, name)
        except KylinPkgError as exc:
            self.status_var.set(str(exc))
            return
        self._set_arch_value(",".join(meta.get("architectures") or []))
        baseline = meta.get("baseline") or FULL_LABEL
        values = self.baseline_combo["values"] or ()
        if baseline != FULL_LABEL and baseline not in values:
            baseline = FULL_LABEL
        self.baseline_var.set(str(baseline))
        if baseline != FULL_LABEL and baseline in self.baseline_tree.get_children():
            self.baseline_tree.selection_set(str(baseline))
            self.baseline_tree.see(str(baseline))
        elif self.baseline_tree.selection():
            self.baseline_tree.selection_remove(*self.baseline_tree.selection())
        if self._output_auto:
            self.output_var.set(self._default_output(name, meta))
        self.status_var.set(
            "已选择 profile %s（%s，%d 条源）"
            % (name, ",".join(meta.get("architectures") or []), len(meta.get("sources_summary") or []))
        )

    def _on_baseline_select(self, _event=None) -> None:
        if self._refreshing:
            return
        selection = self.baseline_tree.selection()
        if selection:
            self.baseline_var.set(selection[0])
            self.status_var.set("已选择 baseline %s" % selection[0])

    def _current_profile(self) -> str:
        selection = self.profile_tree.selection()
        if selection:
            return selection[0]
        return self.profile_var.get().strip()

    def _default_output(self, profile: str, meta: Optional[Dict[str, object]] = None) -> str:
        if meta is None:
            try:
                meta = profile_mod.load_profile(self.state, profile)
            except KylinPkgError:
                meta = {}
        try:
            archs = parse_arch_list(self._current_arch_value())
        except KylinPkgError:
            archs = []
        if not archs:
            archs = list(meta.get("architectures") or [])
        try:
            key = arch_key(archs) if archs else "arch"
        except KylinPkgError:
            key = "arch"
        return str(default_output_dir(profile, key))

    def _browse_output(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self.root, title="选择输出目录", initialdir=str(Path.cwd())
        )
        if chosen:
            self.output_var.set(chosen)
            self._output_auto = False

    # --------------------------------------------------------------- import
    def _pick_file(
        self, var: tk.StringVar, title: str, patterns, initialdir: Optional[Path] = None
    ) -> None:
        kwargs: Dict[str, object] = {}
        if initialdir is not None:
            kwargs["initialdir"] = str(initialdir)
        chosen = filedialog.askopenfilename(
            parent=self.root, title=title, filetypes=patterns, **kwargs
        )
        if chosen:
            var.set(chosen)

    @staticmethod
    def _user_pick_dir() -> Path:
        """文件选择框的默认目录：当前用户桌面，缺失时回退用户主目录。

        麒麟（UKUI）的桌面目录是 ~/桌面，通用环境是 ~/Desktop。
        """
        home = Path.home()
        for name in ("桌面", "Desktop"):
            candidate = home / name
            if candidate.is_dir():
                return candidate
        return home

    def _pick_dir(self, var: tk.StringVar, title: str) -> None:
        chosen = filedialog.askdirectory(parent=self.root, title=title)
        if chosen:
            var.set(chosen)

    def _dialog_row(
        self,
        parent: tk.Widget,
        row: int,
        label: str,
        var: tk.StringVar,
        button_text: str = "选择",
        button_command: Optional[Callable] = None,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(parent, textvariable=var, width=54).grid(
            row=row, column=1, sticky="ew", padx=4, pady=4
        )
        if button_text:
            ttk.Button(parent, text=button_text, command=button_command).grid(
                row=row, column=2, padx=8, pady=4
            )

    def _center_dialog(self, win: tk.Toplevel) -> None:
        win.update_idletasks()
        width = max(win.winfo_reqwidth(), 620)
        height = win.winfo_reqheight()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 3)
        win.geometry("+%d+%d" % (x, y))

    def _make_modal(self, win: tk.Toplevel) -> None:
        try:
            win.transient(self.root)
            win.update_idletasks()
            win.grab_set()
        except tk.TclError:
            pass

    def _release_grab(self, win: tk.Toplevel) -> None:
        try:
            win.grab_release()
        except tk.TclError:
            pass

    def _profile_import_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("导入 apt 源配置")
        win.transient(self.root)
        win.columnconfigure(1, weight=1)

        name_var = tk.StringVar(value="")
        sources_file_var = tk.StringVar()
        sources_dir_var = tk.StringVar()
        prefs_file_var = tk.StringVar()
        prefs_dir_var = tk.StringVar()
        keyring_var = tk.StringVar()
        auth_file_var = tk.StringVar()
        auth_dir_var = tk.StringVar()
        try:
            default_arch = ",".join(detect_system_archs())
        except KylinPkgError:
            default_arch = ""
        arch_var = tk.StringVar(
            value=_arch_label(default_arch) if default_arch else AUTO_ARCH_LABEL
        )
        note_var = tk.StringVar()
        bind_var = tk.StringVar(value=NO_BIND_LABEL)
        system_keys_var = tk.BooleanVar(value=True)
        auth_include_var = tk.BooleanVar(value=False)

        self._dialog_row(win, 0, "名称：", name_var, "")
        self._dialog_row(win, 1, "sources.list 文件：", sources_file_var, "选择",
                         lambda: self._pick_file(sources_file_var, "选择源文件",
                                                 (("apt 源文件", "*.list *.sources"), ("所有文件", "*"))))
        self._dialog_row(win, 2, "sources.list.d 目录：", sources_dir_var, "选择",
                         lambda: self._pick_dir(sources_dir_var, "选择源目录"))
        self._dialog_row(win, 3, "preferences 文件：", prefs_file_var, "选择",
                         lambda: self._pick_file(prefs_file_var, "选择 preferences 文件",
                                                 (("所有文件", "*"),)))
        self._dialog_row(win, 4, "preferences.d 目录：", prefs_dir_var, "选择",
                         lambda: self._pick_dir(prefs_dir_var, "选择 preferences 目录"))
        self._dialog_row(win, 5, "额外 keyring：", keyring_var, "选择",
                         lambda: self._pick_file(keyring_var, "选择 keyring",
                                                 (("keyring", "*.gpg *.asc *.key"), ("所有文件", "*"))))
        self._dialog_row(win, 6, "auth.conf 文件：", auth_file_var, "选择",
                         lambda: self._pick_file(auth_file_var, "选择 auth.conf", (("所有文件", "*"),)))
        self._dialog_row(win, 7, "auth.conf.d 目录：", auth_dir_var, "选择",
                         lambda: self._pick_dir(auth_dir_var, "选择 auth.conf.d 目录"))

        ttk.Label(win, text="目标架构：").grid(row=8, column=0, sticky="w", padx=8, pady=4)
        arch_values = _arch_labels(include_auto=True, extra=[default_arch])
        if arch_var.get() not in arch_values:
            arch_values.append(arch_var.get())
        ttk.Combobox(
            win, textvariable=arch_var, values=arch_values, state="readonly", width=38
        ).grid(row=8, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(win, text="自动检测：按源声明/本机", foreground="#777777").grid(
            row=8, column=2, sticky="w", padx=4
        )

        ttk.Label(win, text="绑定 baseline：").grid(row=9, column=0, sticky="w", padx=8, pady=4)
        bind_values = [NO_BIND_LABEL] + [m.get("name") for m in baseline_mod.list_baselines(self.state)]
        ttk.Combobox(
            win, textvariable=bind_var, values=bind_values, state="readonly", width=32
        ).grid(row=9, column=1, sticky="w", padx=4, pady=4)

        options = ttk.Frame(win)
        options.grid(row=10, column=1, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Checkbutton(options, text="复制本机 keyring", variable=system_keys_var).pack(
            side="left"
        )
        ttk.Checkbutton(options, text="包含 auth.conf 凭据", variable=auth_include_var).pack(
            side="left", padx=(14, 0)
        )
        self._dialog_row(win, 11, "备注：", note_var, "")

        buttons = ttk.Frame(win)
        buttons.grid(row=12, column=0, columnspan=3, sticky="e", padx=8, pady=(8, 10))

        def do_import() -> None:
            name = name_var.get().strip()
            file_path = sources_file_var.get().strip()
            dir_path = sources_dir_var.get().strip()
            if not file_path and not dir_path:
                messagebox.showerror("导入失败", "请至少选择一个源文件或源目录", parent=win)
                return
            try:
                arch_text = _arch_value(arch_var.get())
                archs = parse_arch_list(arch_text) if arch_text.strip() else []
                auth_file = auth_file_var.get().strip()
                auth_dir = auth_dir_var.get().strip()
                include_auth = bool(auth_include_var.get() or auth_file or auth_dir)
                meta = profile_mod.import_profile(
                    self.state,
                    name,
                    sources_files=[Path(file_path)] if file_path else [],
                    sources_dirs=[Path(dir_path)] if dir_path else [],
                    preferences_files=[Path(prefs_file_var.get())] if prefs_file_var.get().strip() else [],
                    preferences_dirs=[Path(prefs_dir_var.get())] if prefs_dir_var.get().strip() else [],
                    keyrings=[Path(keyring_var.get())] if keyring_var.get().strip() else [],
                    architectures=archs,
                    baseline=None if bind_var.get() == NO_BIND_LABEL else bind_var.get(),
                    note=note_var.get().strip(),
                    copy_system_keys=bool(system_keys_var.get()),
                    include_auth=include_auth,
                    auth_files=[Path(auth_file)] if auth_file else [],
                    auth_dirs=[Path(auth_dir)] if auth_dir else [],
                )
            except KylinPkgError as exc:
                messagebox.showerror("导入失败", str(exc), parent=win)
                return
            self._output_auto = True
            self.refresh_all(select_profile=meta["name"])
            self._append_log("已导入 profile：%s" % meta["name"])
            for warning in meta.get("warnings") or []:
                self._append_log("警告：%s" % warning)
            self._release_grab(win)
            win.destroy()

        ttk.Button(buttons, text="导入", command=do_import).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="取消", command=lambda: (self._release_grab(win), win.destroy())).pack(
            side="right"
        )
        self._center_dialog(win)
        self._make_modal(win)

    def _baseline_import_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("导入 dpkg status 基线")
        win.transient(self.root)
        win.columnconfigure(1, weight=1)

        name_var = tk.StringVar()
        mode_var = tk.StringVar(value="file")
        file_var = tk.StringVar()
        rootfs_var = tk.StringVar()
        note_var = tk.StringVar()

        self._dialog_row(win, 0, "名称：", name_var, "")
        row = ttk.Frame(win)
        row.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        ttk.Label(row, text="来源：").pack(side="left")
        for text, value in (
            ("status 文件", "file"),
            ("本机 /var/lib/dpkg/status", "system"),
            ("rootfs 目录", "rootfs"),
            ("空基线（全量闭包）", "empty"),
        ):
            ttk.Radiobutton(row, text=text, value=value, variable=mode_var).pack(
                side="left", padx=(0, 10)
            )
        self._dialog_row(win, 2, "status 文件：", file_var, "选择",
                         lambda: self._pick_file(file_var, "选择 dpkg status", (("所有文件", "*"),)))
        self._dialog_row(win, 3, "rootfs 目录：", rootfs_var, "选择",
                         lambda: self._pick_dir(rootfs_var, "选择 rootfs 根目录"))
        self._dialog_row(win, 4, "备注：", note_var, "")

        buttons = ttk.Frame(win)
        buttons.grid(row=5, column=0, columnspan=3, sticky="e", padx=8, pady=(8, 10))

        def do_import() -> None:
            name = name_var.get().strip()
            mode = mode_var.get()
            try:
                if mode == "file":
                    path = file_var.get().strip()
                    if not path:
                        messagebox.showerror("导入失败", "请选择 status 文件", parent=win)
                        return
                    meta = baseline_mod.import_baseline(
                        self.state, name, status_file=Path(path), note=note_var.get().strip()
                    )
                elif mode == "system":
                    meta = baseline_mod.import_baseline(
                        self.state, name, from_system=True, note=note_var.get().strip()
                    )
                elif mode == "rootfs":
                    path = rootfs_var.get().strip()
                    if not path:
                        messagebox.showerror("导入失败", "请选择 rootfs 目录", parent=win)
                        return
                    meta = baseline_mod.import_baseline(
                        self.state, name, from_rootfs=Path(path), note=note_var.get().strip()
                    )
                else:
                    meta = baseline_mod.import_baseline(
                        self.state, name, empty=True, note=note_var.get().strip()
                    )
            except KylinPkgError as exc:
                messagebox.showerror("导入失败", str(exc), parent=win)
                return
            self.refresh_baselines(select=meta["name"])
            self._append_log(
                "已导入 baseline：%s（已安装 %s 个包）"
                % (meta["name"], meta.get("installed_count", 0))
            )
            for warning in meta.get("warnings") or []:
                self._append_log("警告：%s" % warning)
            self._release_grab(win)
            win.destroy()

        ttk.Button(buttons, text="导入", command=do_import).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="取消", command=lambda: (self._release_grab(win), win.destroy())).pack(
            side="right"
        )
        self._center_dialog(win)
        self._make_modal(win)

    def _preset_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("从内置预设创建 apt 源配置")
        win.transient(self.root)
        win.geometry("1040x760")
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        win.rowconfigure(2, weight=1)

        ttk.Label(
            win,
            text="预设来源：%s（%d 条）。创建后可在“查看/编辑源配置”里修改。"
            % (presets_mod.SOURCE_DOC, len(presets_mod.PRESETS)),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))

        tree_frame = ttk.Frame(win)
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            tree_frame,
            columns=("group", "id", "name", "arch", "pin"),
            show="headings",
            height=9,
            selectmode="browse",
        )
        for col, head, width in (
            ("group", "分组", 165),
            ("id", "ID", 180),
            ("name", "名称", 380),
            ("arch", "预设架构", 165),
            ("pin", "优先级", 70),
        ):
            tree.heading(col, text=head)
            tree.column(col, width=width, minwidth=80, stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        for preset in presets_mod.PRESETS:
            tree.insert(
                "",
                "end",
                iid=preset.id,
                values=(
                    preset.group,
                    preset.id,
                    preset.name,
                    ",".join(preset.architectures) or "自动",
                    "有" if preset.preferences else "-",
                ),
            )

        preview_frame = ttk.LabelFrame(win, text="源预览", padding=6)
        preview_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(8, 4))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        preview = tk.Text(
            preview_frame, height=8, wrap="none", font="TkFixedFont", state="disabled"
        )
        pysb = ttk.Scrollbar(preview_frame, orient="vertical", command=preview.yview)
        pxsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=preview.xview)
        preview.configure(yscrollcommand=pysb.set, xscrollcommand=pxsb.set)
        preview.grid(row=0, column=0, sticky="nsew")
        pysb.grid(row=0, column=1, sticky="ns")
        pxsb.grid(row=1, column=0, sticky="ew")

        form = ttk.Frame(win)
        form.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
        name_var = tk.StringVar()
        arch_var = tk.StringVar(value=AUTO_ARCH_LABEL)
        baseline_var = tk.StringVar(value=NO_BIND_LABEL)
        force_var = tk.BooleanVar(value=False)
        ttk.Label(form, text="profile 名称：").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=name_var, width=32).grid(
            row=0, column=1, sticky="w", padx=(0, 14)
        )
        ttk.Label(form, text="目标架构：").grid(row=0, column=2, sticky="w")
        arch_combo = ttk.Combobox(
            form,
            textvariable=arch_var,
            values=_arch_labels(include_auto=True),
            state="readonly",
            width=28,
        )
        arch_combo.grid(row=0, column=3, sticky="w", padx=(0, 14))
        ttk.Label(form, text="绑定 baseline：").grid(row=1, column=0, sticky="w", pady=(6, 0))
        baseline_values = [NO_BIND_LABEL] + [
            str(item.get("name")) for item in baseline_mod.list_baselines(self.state)
        ]
        ttk.Combobox(
            form,
            textvariable=baseline_var,
            values=baseline_values,
            state="readonly",
            width=32,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))
        ttk.Checkbutton(form, text="覆盖同名 profile", variable=force_var).grid(
            row=1, column=3, sticky="w", pady=(6, 0)
        )

        def load_preview(_event=None) -> None:
            selection = tree.selection()
            if not selection:
                return
            preset = presets_mod.get_preset(selection[0])
            header = (
                "ID：%s\n名称：%s\n分组：%s\n说明：%s\n预设架构：%s\n优先级配置：%s\n\n"
                % (
                    preset.id,
                    preset.name,
                    preset.group,
                    preset.description,
                    ", ".join(preset.architectures) or "自动/按机器",
                    "有（preferences.d/kylin.pref）" if preset.preferences else "无",
                )
            )
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", header + presets_mod.preset_text(preset))
            preview.configure(state="disabled")
            name_var.set(preset.id)
            arch_var.set(AUTO_ARCH_LABEL)

        tree.bind("<<TreeviewSelect>>", load_preview)

        buttons = ttk.Frame(win)
        buttons.grid(row=4, column=0, sticky="e", padx=10, pady=(6, 10))

        def do_create() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("提示", "请先选择一个预设", parent=win)
                return
            preset_id = selection[0]
            name = name_var.get().strip() or preset_id
            arch_text = _arch_value(arch_var.get())
            baseline = None if baseline_var.get() == NO_BIND_LABEL else baseline_var.get()
            try:
                meta = profile_mod.create_from_preset(
                    self.state,
                    name,
                    preset_id,
                    architectures=parse_arch_list(arch_text) if arch_text else (),
                    baseline=baseline,
                    force=bool(force_var.get()),
                )
            except KylinPkgError as exc:
                messagebox.showerror("创建失败", str(exc), parent=win)
                return
            self._output_auto = True
            self.refresh_all(select_profile=meta["name"])
            self._append_log(
                "已从预设 %s 创建 profile：%s（%s）"
                % (preset_id, meta["name"], ",".join(meta.get("architectures") or []))
            )
            for warning in meta.get("warnings") or []:
                self._append_log("警告：%s" % warning)
            self.status_var.set("已从预设创建 profile：%s" % meta["name"])
            self._release_grab(win)
            win.destroy()

        ttk.Button(buttons, text="创建", command=do_create).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(
            buttons, text="取消", command=lambda: (self._release_grab(win), win.destroy())
        ).pack(side="right")
        self._center_dialog(win)
        self._make_modal(win)
        children = tree.get_children()
        if children:
            tree.selection_set(children[0])
            load_preview()

    def _profile_editor_dialog(self) -> None:
        profile_name = self._current_profile()
        if not profile_name:
            messagebox.showinfo("提示", "请先选择一个 apt 源配置", parent=self.root)
            return
        try:
            profile_mod.load_profile(self.state, profile_name)
        except KylinPkgError as exc:
            messagebox.showerror("无法打开", str(exc), parent=self.root)
            return

        win = tk.Toplevel(self.root)
        win.title("查看/编辑 apt 源配置 - %s" % profile_name)
        win.transient(self.root)
        win.geometry("1120x760")
        win.columnconfigure(1, weight=1)
        win.rowconfigure(1, weight=1)

        ttk.Label(
            win,
            text="profile：%s    保存后索引指纹会变化，下次解析自动刷新索引；keyring 文件只读。"
            % profile_name,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 4))

        left = ttk.Frame(win)
        left.grid(row=1, column=0, sticky="ns", padx=(10, 5), pady=4)
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            left,
            columns=("path", "role", "size", "edit"),
            show="headings",
            height=20,
            selectmode="browse",
        )
        for col, head, width in (
            ("path", "文件", 250),
            ("role", "类型", 120),
            ("size", "大小", 70),
            ("edit", "可编辑", 60),
        ):
            tree.heading(col, text=head)
            tree.column(col, width=width, minwidth=50, stretch=True)
        vsb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        right = ttk.Frame(win)
        right.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=4)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        text = tk.Text(right, wrap="none", font="TkFixedFont", undo=True)
        ysb = ttk.Scrollbar(right, orient="vertical", command=text.yview)
        xsb = ttk.Scrollbar(right, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        text.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")

        status_var = tk.StringVar(value="选择左侧文件进行查看/编辑")
        ttk.Label(
            win, textvariable=status_var, foreground="#555555", wraplength=1060, anchor="w"
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 2))

        buttons = ttk.Frame(win)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", padx=10, pady=(4, 10))
        save_btn = ttk.Button(buttons, text="保存")
        revert_btn = ttk.Button(buttons, text="还原")
        new_btn = ttk.Button(buttons, text="新建源文件")
        delete_btn = ttk.Button(buttons, text="删除")
        validate_btn = ttk.Button(buttons, text="验证")
        for widget in (save_btn, revert_btn, delete_btn):
            widget.pack(side="right", padx=(6, 0))
        new_btn.pack(side="left", padx=(0, 6))
        validate_btn.pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons, text="关闭", command=lambda: close_editor()
        ).pack(side="right", padx=(6, 0))

        items_by_rel: Dict[str, Dict[str, object]] = {}
        current: Dict[str, object] = {"rel": None, "dirty": False, "loading": False}
        suppress = {"selection": False}

        def find_item(rel: str) -> Optional[Dict[str, object]]:
            return items_by_rel.get(rel)

        def update_buttons() -> None:
            item = find_item(str(current["rel"])) if current["rel"] else None
            editable = bool(item and item.get("editable"))
            state = "normal" if editable else "disabled"
            for widget in (save_btn, revert_btn, delete_btn):
                widget.configure(state=state)
            text.configure(state="normal" if editable else "disabled")

        def load_file(rel: str, force: bool = False) -> None:
            if current["dirty"] and not force:
                if not messagebox.askyesno(
                    "未保存", "当前文件有未保存修改，切换将丢失，继续？", parent=win
                ):
                    if current["rel"]:
                        suppress["selection"] = True
                        tree.selection_set(str(current["rel"]))
                        win.after(80, lambda: suppress.__setitem__("selection", False))
                    return
            item = find_item(rel)
            if item is None:
                return
            current["loading"] = True
            text.configure(state="normal")
            text.delete("1.0", "end")
            if item.get("editable"):
                try:
                    content = profile_mod.read_profile_file(self.state, profile_name, rel)
                except KylinPkgError as exc:
                    text.insert("1.0", "读取失败：%s\n" % exc)
                    current["rel"] = rel
                    current["dirty"] = False
                    current["loading"] = False
                    update_buttons()
                    return
                text.insert("1.0", content)
            else:
                text.insert(
                    "1.0",
                    "该文件是二进制 keyring 或不允许编辑。\n"
                    "keyring 由导入源配置/收集包自动管理，不在此处编辑。\n",
                )
            text.edit_reset()
            text.edit_modified(False)
            current["rel"] = rel
            current["dirty"] = False
            current["loading"] = False
            update_buttons()
            status_var.set("当前文件：%s" % rel)

        def refresh_files(select: Optional[str] = None) -> None:
            items = profile_mod.profile_files(self.state, profile_name)
            items_by_rel.clear()
            items_by_rel.update({str(item["path"]): item for item in items})
            tree.delete(*tree.get_children())
            for item in items:
                tree.insert(
                    "",
                    "end",
                    iid=str(item["path"]),
                    values=(
                        item.get("path"),
                        item.get("role"),
                        human_size(int(item.get("size", 0))),
                        "是" if item.get("editable") else "否",
                    ),
                )
            target = select or current["rel"]
            if target not in items_by_rel:
                target = "sources.list" if "sources.list" in items_by_rel else (
                    items[0]["path"] if items else None
                )
            if target:
                suppress["selection"] = True
                tree.selection_set(str(target))
                tree.see(str(target))
                suppress["selection"] = False
                load_file(str(target), force=True)
            else:
                text.configure(state="normal")
                text.delete("1.0", "end")
                text.configure(state="disabled")
                current["rel"] = None
                update_buttons()

        def on_select(_event=None) -> None:
            if suppress["selection"]:
                return
            selection = tree.selection()
            if selection:
                load_file(selection[0])

        def on_modified(_event=None) -> None:
            if current["loading"]:
                return
            if text.edit_modified():
                text.edit_modified(False)
                current["dirty"] = True
                status_var.set("未保存修改：%s" % (current["rel"] or ""))

        def do_save() -> None:
            rel = current["rel"]
            item = find_item(str(rel)) if rel else None
            if not rel or not item or not item.get("editable"):
                return
            content = text.get("1.0", "end-1c")
            try:
                meta = profile_mod.write_profile_file(
                    self.state, profile_name, str(rel), content
                )
            except KylinPkgError as exc:
                messagebox.showerror("保存失败", str(exc), parent=win)
                return
            current["dirty"] = False
            refresh_files(select=str(rel))
            self.refresh_profiles(select=profile_name)
            warnings = meta.get("warnings") or []
            status_var.set(
                "已保存：%s%s"
                % (rel, ("；" + "；".join(warnings)) if warnings else "")
            )
            self._append_log("已保存 profile %s / %s" % (profile_name, rel))

        def do_revert() -> None:
            if current["rel"]:
                load_file(str(current["rel"]), force=True)

        def do_new() -> None:
            filename = simpledialog.askstring(
                "新建源文件",
                "文件名（.list 或 .sources；将放到 sources.list.d/）：",
                initialvalue="extra.list",
                parent=win,
            )
            if not filename:
                return
            filename = filename.strip()
            if not filename.endswith((".list", ".sources")):
                filename += ".list"
            rel = "sources.list.d/" + filename
            if rel in items_by_rel:
                messagebox.showerror("新建失败", "文件已存在：%s" % rel, parent=win)
                return
            try:
                profile_mod.write_profile_file(
                    self.state, profile_name, rel, "# new apt source\n"
                )
            except KylinPkgError as exc:
                messagebox.showerror("新建失败", str(exc), parent=win)
                return
            current["dirty"] = False
            refresh_files(select=rel)
            self.refresh_profiles(select=profile_name)
            self._append_log("已新建源文件：%s" % rel)

        def do_delete() -> None:
            rel = current["rel"]
            item = find_item(str(rel)) if rel else None
            if not rel or not item or not item.get("editable"):
                return
            if not messagebox.askyesno(
                "删除文件", "删除/清空 %s？\n该操作会立即修改 profile。" % rel, parent=win
            ):
                return
            try:
                meta = profile_mod.delete_profile_file(
                    self.state, profile_name, str(rel)
                )
            except KylinPkgError as exc:
                messagebox.showerror("删除失败", str(exc), parent=win)
                return
            current["rel"] = None
            current["dirty"] = False
            refresh_files()
            self.refresh_profiles(select=profile_name)
            warnings = meta.get("warnings") or []
            status_var.set(
                "已删除/清空：%s%s"
                % (rel, ("；" + "；".join(warnings)) if warnings else "")
            )
            self._append_log("已删除/清空 profile %s / %s" % (profile_name, rel))

        def do_validate() -> None:
            rel = current["rel"]
            if not rel:
                return
            content = text.get("1.0", "end-1c")
            if str(rel) == "sources.list" or str(rel).startswith("sources.list.d/"):
                try:
                    entries = deb822.parse_sources_text(content, str(rel))
                except KylinPkgError as exc:
                    status_var.set("解析失败：%s" % exc)
                    return
                warnings = deb822.validate_sources(entries)
                message = "解析到 %d 条源" % len(entries)
                if warnings:
                    message += "；" + "；".join(warnings)
                status_var.set(message)
            else:
                status_var.set("该文件不是 apt 源文件，保存后由 apt 解释")

        def close_editor() -> None:
            if current["dirty"]:
                if not messagebox.askyesno(
                    "未保存", "当前文件有未保存修改，确定关闭？", parent=win
                ):
                    return
            self._release_grab(win)
            win.destroy()

        save_btn.configure(command=do_save)
        revert_btn.configure(command=do_revert)
        new_btn.configure(command=do_new)
        delete_btn.configure(command=do_delete)
        validate_btn.configure(command=do_validate)
        tree.bind("<<TreeviewSelect>>", on_select)
        text.bind("<<Modified>>", on_modified)
        win.protocol("WM_DELETE_WINDOW", close_editor)
        refresh_files()
        self._center_dialog(win)
        self._make_modal(win)

    def _locate_collector_asset(self, name: str) -> Optional[Path]:
        """定位收集脚本/使用手册：deb 安装在 /opt/kylinpkg，源码运行在仓库根目录。"""
        candidates = [
            Path(__file__).resolve().parents[1] / "collector" / name,
            Path("/opt/kylinpkg/collector") / name,
        ]
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _save_collector_asset(
        self, asset_name: str, default_name: str, parent: tk.Widget
    ) -> None:
        """把内置的收集脚本/使用手册另存到用户选择的位置。"""
        source = self._locate_collector_asset(asset_name)
        if source is None:
            messagebox.showerror(
                "文件缺失",
                "未找到内置的 %s。\n请从安装目录 /opt/kylinpkg/collector 获取。" % asset_name,
                parent=parent,
            )
            return
        target = filedialog.asksaveasfilename(
            parent=parent,
            title="保存%s" % default_name,
            initialfile=default_name,
            defaultextension=source.suffix,
        )
        if not target:
            return
        try:
            shutil.copyfile(source, target)
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=parent)
            return
        if source.suffix == ".sh":
            try:
                Path(target).chmod(0o755)
            except OSError:
                pass
        self._append_log("已导出收集脚本资料：%s" % target)
        messagebox.showinfo("保存成功", "已保存到：\n%s" % target, parent=parent)

    def _bundle_import_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("导入其他主机配置")
        win.transient(self.root)
        win.columnconfigure(0, weight=1)

        container = ttk.Frame(win, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        # ── 顶部说明与资料下载 ──────────────────────────────────
        intro = ttk.Frame(container)
        intro.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            intro,
            text="先在原始主机上运行收集脚本生成收集包，再在此导入。",
            style="Hint.TLabel",
        ).pack(side="left")
        ttk.Button(
            intro,
            text="使用手册",
            command=lambda: self._save_collector_asset(
                "README.md", "kylinpkg-collect-使用手册.md", win
            ),
        ).pack(side="right")
        ttk.Button(
            intro,
            text="下载收集脚本",
            command=lambda: self._save_collector_asset(
                "kylinpkg-collect.sh", "kylinpkg-collect.sh", win
            ),
        ).pack(side="right", padx=(0, 6))

        # ── 第 1 步：选择收集包 ─────────────────────────────────
        step1 = ttk.LabelFrame(container, text=" 1 · 选择收集包 ", padding=10)
        step1.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        step1.columnconfigure(1, weight=1)
        archive_var = tk.StringVar()
        ttk.Label(step1, text="收集包文件：").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(step1, textvariable=archive_var).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Button(
            step1,
            text="选择",
            command=lambda: self._pick_file(
                archive_var,
                "选择收集包",
                (("kylinpkg 收集包", "*.tar.gz *.tgz"), ("所有文件", "*")),
                initialdir=self._user_pick_dir(),
            ),
        ).grid(row=0, column=2, padx=(4, 0), pady=4)
        ttk.Label(step1, text="文件选择窗口默认打开当前用户的桌面目录", style="Hint.TLabel").grid(
            row=1, column=1, sticky="w", padx=4
        )

        # ── 第 2 步：导入设置 ───────────────────────────────────
        step2 = ttk.LabelFrame(container, text=" 2 · 导入设置 ", padding=10)
        step2.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        step2.columnconfigure(1, weight=1)
        profile_var = tk.StringVar()
        baseline_var = tk.StringVar()
        arch_var = tk.StringVar(value=AUTO_ARCH_LABEL)
        bind_var = tk.BooleanVar(value=True)
        force_var = tk.BooleanVar(value=False)

        ttk.Label(step2, text="profile 名称：").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(step2, textvariable=profile_var).grid(
            row=0, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Label(
            step2, text="留空则用收集包中的主机名", style="Hint.TLabel"
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=(4, 0))
        ttk.Label(step2, text="baseline 名称：").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(step2, textvariable=baseline_var).grid(
            row=2, column=1, sticky="ew", padx=4, pady=4
        )
        ttk.Label(
            step2, text="留空则用 <profile>-baseline", style="Hint.TLabel"
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=(4, 0))
        ttk.Label(step2, text="目标架构：").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Combobox(
            step2,
            textvariable=arch_var,
            values=_arch_labels(include_auto=True),
            state="readonly",
        ).grid(row=4, column=1, sticky="ew", padx=4, pady=4)
        ttk.Label(
            step2, text="自动：使用包内 dpkg status 的架构", style="Hint.TLabel"
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=(4, 0))

        options = ttk.Frame(step2)
        options.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Checkbutton(
            options, text="绑定为 profile 默认基线", variable=bind_var
        ).pack(side="left")
        ttk.Checkbutton(
            options, text="覆盖同名 profile/baseline", variable=force_var
        ).pack(side="left", padx=(14, 0))

        # ── 底部操作按钮 ────────────────────────────────────────
        buttons = ttk.Frame(container)
        buttons.grid(row=3, column=0, sticky="ew", pady=(14, 0))

        def do_import() -> None:
            archive = archive_var.get().strip()
            if not archive:
                messagebox.showerror("导入失败", "请选择收集包文件", parent=win)
                return
            self.status_var.set("正在导入其他主机配置")
            self.root.update_idletasks()
            try:
                arch_text = _arch_value(arch_var.get())
                result = bundle_mod.import_bundle(
                    self.state,
                    Path(archive),
                    profile_name=profile_var.get().strip() or None,
                    baseline_name=baseline_var.get().strip() or None,
                    architectures=parse_arch_list(arch_text) if arch_text.strip() else None,
                    bind_baseline=bool(bind_var.get()),
                    force=bool(force_var.get()),
                )
            except KylinPkgError as exc:
                self.status_var.set("导入失败")
                messagebox.showerror("导入失败", str(exc), parent=win)
                return
            self._output_auto = True
            self.refresh_all(select_profile=result["profile"])
            if result["baseline"] in self.baseline_tree.get_children():
                self.baseline_tree.selection_set(result["baseline"])
                self.baseline_var.set(result["baseline"])
            self._append_log(
                "已导入其他主机配置：profile=%s，baseline=%s（已安装 %s 个包，%s 条源）"
                % (
                    result["profile"],
                    result["baseline"],
                    result.get("installed_count", 0),
                    result.get("sources", 0),
                )
            )
            for warning in result.get("warnings") or []:
                self._append_log("警告：%s" % warning)
            self.status_var.set("其他主机配置导入完成")
            self._release_grab(win)
            win.destroy()

        ttk.Button(buttons, text="导入", style="Accent.TButton", command=do_import).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(
            buttons, text="取消", command=lambda: (self._release_grab(win), win.destroy())
        ).pack(side="right")
        self._center_dialog(win)
        self._make_modal(win)

    def _quick_import_profile_system(self) -> None:
        name = simpledialog.askstring(
            "从本机导入源配置", "给这套 apt 源配置起个名字：", parent=self.root
        )
        if not name:
            return
        try:
            default_arch = ",".join(detect_system_archs())
        except KylinPkgError:
            default_arch = ""
        arch = self._ask_arch("目标架构", default_arch, allow_auto=False)
        if arch is None:
            return
        include_auth = messagebox.askyesno(
            "apt 凭据",
            "是否同时导入本机 /etc/apt/auth.conf 与 auth.conf.d？\n"
            "其中可能包含私有源的明文凭据。",
            parent=self.root,
        )
        try:
            meta = profile_mod.import_profile(
                self.state,
                name,
                from_system=True,
                architectures=parse_arch_list(arch) if arch.strip() else [],
                include_auth=include_auth,
            )
        except KylinPkgError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)
            return
        self._output_auto = True
        self.refresh_all(select_profile=meta["name"])
        self._append_log("已从本机导入 profile：%s" % meta["name"])
        for warning in meta.get("warnings") or []:
            self._append_log("警告：%s" % warning)

    def _quick_import_profile_rootfs(self) -> None:
        name = simpledialog.askstring(
            "从 rootfs 导入源配置", "给这套 apt 源配置起个名字：", parent=self.root
        )
        if not name:
            return
        rootfs = filedialog.askdirectory(
            parent=self.root, title="选择 rootfs 根目录（包含 etc/apt）"
        )
        if not rootfs:
            return
        arch = self._ask_arch("目标架构", "", allow_auto=True)
        if arch is None:
            return
        include_auth = messagebox.askyesno(
            "apt 凭据",
            "是否同时导入 rootfs 中的 /etc/apt/auth.conf 与 auth.conf.d？\n"
            "其中可能包含私有源的明文凭据。",
            parent=self.root,
        )
        try:
            meta = profile_mod.import_profile(
                self.state,
                name,
                from_rootfs=Path(rootfs),
                architectures=parse_arch_list(arch) if arch.strip() else [],
                include_auth=include_auth,
            )
        except KylinPkgError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)
            return
        self._output_auto = True
        self.refresh_all(select_profile=meta["name"])
        self._append_log("已从 rootfs 导入 profile：%s" % meta["name"])
        for warning in meta.get("warnings") or []:
            self._append_log("警告：%s" % warning)

    def _quick_import_baseline_system(self) -> None:
        name = simpledialog.askstring(
            "从本机导入 dpkg 状态", "给这个 baseline 起个名字：", parent=self.root
        )
        if not name:
            return
        try:
            meta = baseline_mod.import_baseline(self.state, name, from_system=True)
        except KylinPkgError as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.root)
            return
        self.refresh_baselines(select=meta["name"])
        self._append_log(
            "已从本机导入 baseline：%s（已安装 %s 个包）"
            % (meta["name"], meta.get("installed_count", 0))
        )

    # --------------------------------------------------------------- delete
    def _delete_profile(self) -> None:
        name = self._current_profile()
        if not name:
            messagebox.showinfo("提示", "请先选择一个 apt 源配置", parent=self.root)
            return
        if not messagebox.askyesno(
            "删除 profile", "删除 profile %s？\n它的隔离索引也会被清理。" % name, parent=self.root
        ):
            return
        try:
            profile_mod.remove_profile(self.state, name, purge_roots=True)
        except KylinPkgError as exc:
            messagebox.showerror("删除失败", str(exc), parent=self.root)
            return
        self.refresh_all()
        self._append_log("已删除 profile：%s" % name)

    def _delete_baseline(self) -> None:
        selection = self.baseline_tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先选择一个 baseline", parent=self.root)
            return
        name = selection[0]
        refs = [
            str(item.get("name"))
            for item in profile_mod.list_profiles(self.state)
            if item.get("baseline") == name
        ]
        message = "删除 baseline %s？" % name
        if refs:
            message += "\n以下 profile 正在引用它：%s\n删除后这些 profile 需要重新绑定。" % ", ".join(refs)
        if not messagebox.askyesno("删除 baseline", message, parent=self.root):
            return
        try:
            baseline_mod.remove_baseline(self.state, name)
        except KylinPkgError as exc:
            messagebox.showerror("删除失败", str(exc), parent=self.root)
            return
        if self.baseline_var.get() == name:
            self.baseline_var.set(FULL_LABEL)
        self.refresh_baselines()
        self._append_log("已删除 baseline：%s" % name)

    # ------------------------------------------------------------- download
    def _current_archs(self):
        text = self._current_arch_value()
        return parse_arch_list(text) if text else None

    def _current_baseline(self) -> str:
        label = self.baseline_var.get().strip()
        if not label or label == FULL_LABEL:
            return baseline_mod.RESERVED_EMPTY
        return label

    def _log_plans(self, plans) -> Dict[str, int]:
        if len(plans) == 1:
            self._log(resolver.format_plan(plans[0]))
        else:
            for index, plan in enumerate(plans, 1):
                self._log(
                    "===== 请求组 %d：%s ====="
                    % (index, " ".join(plan.requested))
                )
                self._log(resolver.format_plan(plan))
            totals = resolver.plan_totals(plans)
            self._log(
                "合并去重后：%d 个包，%s"
                % (totals["count"], human_size(totals["bytes"]))
            )
            return totals
        return resolver.plan_totals(plans)

    def _open_version_picker(self) -> None:
        profile_name = self._current_profile()
        if not profile_name:
            messagebox.showinfo("提示", "请先选择 apt 源配置", parent=self.root)
            return
        tokens = self.packages_var.get().split()
        if len(tokens) == 1 and "=" not in tokens[0]:
            package = tokens[0]
        else:
            initial = tokens[0].split("=", 1)[0] if tokens else ""
            package = simpledialog.askstring(
                "选择版本",
                "软件包名（不含版本，可带 :架构）：",
                initialvalue=initial,
                parent=self.root,
            )
            if not package:
                return
        package = package.strip()
        if not package:
            return
        try:
            archs = self._current_archs()
        except KylinPkgError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self.root)
            return
        baseline = self._current_baseline()
        token = CancelToken()

        def work():
            self._log(
                "查询版本：%s（%s）"
                % (package, ",".join(archs or []) or "按 profile")
            )
            return resolver.list_versions(
                self.state,
                profile_name,
                package,
                architectures=archs,
                baseline_name=baseline,
                cancel=token,
            )

        self._start_task(
            work, "查询版本", token=token, on_success=self._show_version_dialog
        )

    def _show_version_dialog(self, data: Dict[str, object]) -> None:
        package = str(data.get("package") or "")
        versions = list(data.get("versions") or [])
        if not versions:
            messagebox.showinfo("提示", "没有可用版本", parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title("选择版本 - %s" % package)
        win.transient(self.root)
        win.geometry("1040x560")
        win.columnconfigure(0, weight=1)
        win.rowconfigure(2, weight=1)

        ttk.Label(
            win,
            text="软件包：%s    已安装：%s    候选：%s"
            % (
                package,
                data.get("installed") or "无",
                data.get("candidate") or "无",
            ),
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        ttk.Label(
            win,
            text="按住 Ctrl/Shift 可多选。同一软件包的多个版本会分别解析，"
            "最终合并到同一个输出目录和离线源。",
            foreground="#777777",
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(0, 4))

        tree_frame = ttk.Frame(win)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=10)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(
            tree_frame,
            columns=("version", "priority", "status", "arch", "downloadable", "sources"),
            show="headings",
            height=12,
            selectmode="extended",
        )
        for col, head, width in (
            ("version", "版本", 190),
            ("priority", "优先级", 70),
            ("status", "状态", 110),
            ("arch", "架构", 110),
            ("downloadable", "可下载", 70),
            ("sources", "来源", 460),
        ):
            tree.heading(col, text=head)
            tree.column(col, width=width, minwidth=50, stretch=True)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        xsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=xsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")

        for index, item in enumerate(versions):
            status = []
            if item.get("installed"):
                status.append("已安装")
            if item.get("candidate"):
                status.append("候选")
            tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    item.get("version", ""),
                    item.get("priority", ""),
                    "/".join(status) or "-",
                    ",".join(item.get("architectures") or []) or "-",
                    "是" if item.get("downloadable") else "否",
                    "; ".join(item.get("sources") or []) or "-",
                ),
            )

        buttons = ttk.Frame(win)
        buttons.grid(row=3, column=0, sticky="e", padx=10, pady=(8, 10))

        def add_selected() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("提示", "请先选择版本", parent=win)
                return
            chosen = []
            skipped = []
            for iid in selection:
                item = versions[int(iid)]
                if not item.get("downloadable"):
                    skipped.append(str(item.get("version")))
                    continue
                spec = "%s=%s" % (package, item.get("version"))
                if spec not in chosen:
                    chosen.append(spec)
            if skipped:
                messagebox.showwarning(
                    "部分版本不可下载",
                    "以下版本没有可下载的源，已跳过：\n%s" % "\n".join(skipped),
                    parent=win,
                )
            if not chosen:
                return
            current = [
                token
                for token in self.packages_var.get().split()
                if not (token == package and "=" not in token)
            ]
            for spec in chosen:
                if spec not in current:
                    current.append(spec)
            self.packages_var.set(" ".join(current))
            self._append_log("已加入版本：" + " ".join(chosen))
            self._release_grab(win)
            win.destroy()

        ttk.Button(buttons, text="加入软件包列表", command=add_selected).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(
            buttons, text="取消", command=lambda: (self._release_grab(win), win.destroy())
        ).pack(side="right")
        self._center_dialog(win)
        self._make_modal(win)

    def _collect_params(self) -> Dict[str, object]:
        profile = self._current_profile()
        if not profile:
            raise KylinPkgError("请先选择 apt 源配置")
        packages = [item for item in re.split(r"[\s,，]+", self.packages_var.get().strip()) if item]
        if not packages:
            raise KylinPkgError("请输入要下载的软件包名")
        arch_text = self._current_arch_value()
        architectures = parse_arch_list(arch_text) if arch_text else None
        baseline_label = self.baseline_var.get().strip()
        if not baseline_label or baseline_label == FULL_LABEL:
            baseline = baseline_mod.RESERVED_EMPTY
        else:
            baseline = baseline_label
        output_text = self.output_var.get().strip()
        if not output_text:
            output_text = self._default_output(profile)
            self.output_var.set(output_text)
            self._output_auto = True
        return {
            "profile": profile,
            "packages": packages,
            "architectures": architectures,
            "baseline": baseline,
            "recommends": bool(self.recommends_var.get()),
            "with_dependencies": bool(self.with_dependencies_var.get()),
            "make_repo": bool(self.repo_var.get()),
            "force": bool(self.force_var.get()),
            "force_update": bool(self.force_update_var.get()),
            "output": Path(output_text).expanduser(),
        }

    def _on_resolve(self) -> None:
        try:
            params = self._collect_params()
        except KylinPkgError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self.root)
            return

        token = CancelToken()

        def work() -> str:
            self._log("开始解析：%s" % " ".join(params["packages"]))
            plans = resolver.resolve_specs(
                self.state,
                str(params["profile"]),
                params["packages"],
                architectures=params["architectures"],
                baseline_name=str(params["baseline"]),
                recommends=bool(params["recommends"]),
                force_update=bool(params["force_update"]),
                with_dependencies=bool(params["with_dependencies"]),
                cancel=token,
            )
            totals = self._log_plans(plans)
            return "解析完成：%d 个请求组，%d 个唯一包，%s" % (
                len(plans),
                totals["count"],
                human_size(totals["bytes"]),
            )

        self._start_task(work, "解析", token=token)

    def _on_download(self) -> None:
        try:
            params = self._collect_params()
        except KylinPkgError as exc:
            messagebox.showerror("参数错误", str(exc), parent=self.root)
            return

        token = CancelToken()

        def work() -> str:
            self._log("开始解析：%s" % " ".join(params["packages"]))
            plans = resolver.resolve_specs(
                self.state,
                str(params["profile"]),
                params["packages"],
                architectures=params["architectures"],
                baseline_name=str(params["baseline"]),
                recommends=bool(params["recommends"]),
                force_update=bool(params["force_update"]),
                with_dependencies=bool(params["with_dependencies"]),
                cancel=token,
            )
            totals = self._log_plans(plans)
            if totals["count"] == 0:
                return "无需下载：请求的包已由基线满足"
            output = Path(params["output"])
            self._log("输出目录：%s" % output)
            self._log(
                "正在下载 %d 个唯一包（约 %s），请稍候"
                % (totals["count"], human_size(totals["bytes"]))
            )
            if len(plans) == 1:
                result = downloader.download(
                    self.state,
                    plans[0],
                    output,
                    force=bool(params["force"]),
                    make_repo=bool(params["make_repo"]),
                    cancel=token,
                )
            else:
                result = downloader.download_plans(
                    self.state,
                    plans,
                    output,
                    force=bool(params["force"]),
                    make_repo=bool(params["make_repo"]),
                    cancel=token,
                )
            if result.get("reused"):
                text = "已有完整结果且校验通过：%s" % output
            else:
                text = "下载完成：%s 个包，%s" % (
                    result.get("total", 0),
                    human_size(int(result.get("total_bytes", 0))),
                )
            if int(result.get("plans", 1)) > 1:
                text += "（%d 个版本/请求组）" % int(result.get("plans", 1))
            self._log("manifest：%s" % (output / "manifest.json"))
            if params["make_repo"] and (output / "sources.list").is_file():
                self._log("离线源：%s" % output)
                self._log("目标机 sources：%s" % (output / "sources.list"))
            for warning in result.get("warnings") or []:
                self._log("警告：%s" % warning)
            return text

        self._start_task(work, "下载", token=token)

    def _start_task(
        self,
        work: Callable[[], object],
        label: str,
        token: Optional[CancelToken] = None,
        on_success: Optional[Callable[[object], None]] = None,
    ) -> None:
        if self.busy:
            return
        self._cancel_token = token
        self._set_busy(True, "%s中（可点中断）" % label)
        self._append_log("=" * 72)

        def runner() -> None:
            try:
                result = work()
            except OperationCancelled:
                self.queue.put(("cancelled", "操作已中断"))
            except KylinPkgError as exc:
                self.queue.put(("error", str(exc)))
            except Exception:
                self.queue.put(("error", traceback.format_exc()))
            else:
                if on_success is not None:
                    self.queue.put(("callback", (result, on_success)))
                else:
                    self.queue.put(("done", result))

        threading.Thread(target=runner, daemon=True).start()

    def _cancel_task(self) -> None:
        token = self._cancel_token
        if not self.busy or token is None:
            return
        token.cancel()
        self.status_var.set("正在中断")
        self._append_log("请求中断当前操作")
        try:
            self.cancel_btn.configure(state="disabled")
        except Exception:
            pass

    def _poll(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "log":
                    self._append_log(payload)
                elif kind == "done":
                    self._set_busy(False, payload)
                    self._append_log(payload)
                elif kind == "callback":
                    result, callback = payload
                    self._set_busy(False, "完成")
                    try:
                        callback(result)
                    except KylinPkgError as exc:
                        self._append_log("错误：%s" % exc)
                        messagebox.showerror("操作失败", str(exc), parent=self.root)
                    except Exception:
                        detail = traceback.format_exc()
                        self._append_log("错误：%s" % detail)
                        messagebox.showerror("操作失败", detail, parent=self.root)
                elif kind == "cancelled":
                    self._set_busy(False, "已中断")
                    self._append_log(payload)
                    self._append_log("已下载的部分文件会保留，可再次点击下载继续/重试。")
                elif kind == "error":
                    self._set_busy(False, "操作失败")
                    self._append_log("错误：%s" % payload)
                    messagebox.showerror("操作失败", payload, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    def _set_busy(self, busy: bool, text: str = "") -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for widget in self._action_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
        if busy:
            self.progress.start(12)
            self.status_var.set(text or "处理中")
            try:
                self.cancel_btn.configure(
                    state="normal" if self._cancel_token is not None else "disabled"
                )
            except Exception:
                pass
        else:
            self.progress.stop()
            self.status_var.set(text or "就绪")
            self._cancel_token = None
            try:
                self.cancel_btn.configure(state="disabled")
            except Exception:
                pass

    # ----------------------------------------------------------------- log
    def _log(self, text: str) -> None:
        self.queue.put(("log", text))

    def _append_log(self, text: str) -> None:
        if not text:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text.rstrip() + "\n")
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 4000:
            self.log_text.delete("1.0", "1000.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ------------------------------------------------------- 任务记录
    def _history_dialog(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("下载任务记录")
        win.geometry("1040x540")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        tree = ttk.Treeview(
            frame,
            columns=("time", "status", "profile", "arch", "baseline", "packages", "output"),
            show="headings",
            selectmode="browse",
        )
        for col, head, width in (
            ("time", "时间", 150),
            ("status", "状态", 60),
            ("profile", "profile", 120),
            ("arch", "架构", 100),
            ("baseline", "基线", 110),
            ("packages", "软件包", 230),
            ("output", "输出目录", 230),
        ):
            tree.heading(col, text=head)
            tree.column(col, width=width, minwidth=50, stretch=True)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        entries: Dict[str, Dict[str, object]] = {}

        def refresh() -> None:
            selected = tree.selection()
            tree.delete(*tree.get_children())
            entries.clear()
            for entry in history_mod.list_tasks(self.state):
                task_id = str(entry.get("id") or "")
                entries[task_id] = entry
                baseline = entry.get("baseline")
                tree.insert(
                    "",
                    "end",
                    iid=task_id,
                    values=(
                        str(entry.get("created_at", "")).replace("T", " "),
                        history_mod.status_label(str(entry.get("status", ""))),
                        entry.get("profile", ""),
                        ",".join(str(a) for a in entry.get("architectures") or []),
                        baseline if baseline else "全量",
                        " ".join(str(s) for s in entry.get("requested") or []),
                        entry.get("output", ""),
                    ),
                )
            if selected:
                try:
                    tree.selection_set(selected[0])
                    tree.see(selected[0])
                except tk.TclError:
                    pass

        def selected_entry() -> Optional[Dict[str, object]]:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("任务记录", "请先选择一条任务记录", parent=win)
                return None
            return entries.get(selection[0])

        def redo() -> None:
            entry = selected_entry()
            if entry is None:
                return
            if self.busy:
                messagebox.showinfo("任务记录", "当前有任务正在执行，请等它结束后再试", parent=win)
                return

            def work() -> str:
                result = history_mod.redo_task(self.state, entry, log=self._log)
                if result.get("reused"):
                    return "重新下载：结果已存在且校验通过，未重复下载"
                return "重新下载完成：%s 个包，%s" % (
                    result.get("total", 0),
                    human_size(int(result.get("total_bytes", 0))),
                )

            def done(text: object) -> None:
                refresh()
                self.status_var.set(str(text))

            self._start_task(work, "重新下载", on_success=done)

        def apply_to_current() -> None:
            entry = selected_entry()
            if entry is None:
                return
            try:
                self._apply_history_params(entry)
            except KylinPkgError as exc:
                messagebox.showerror("套用失败", str(exc), parent=win)
                return
            win.destroy()

        def remove_record() -> None:
            entry = selected_entry()
            if entry is None:
                return
            if not messagebox.askyesno(
                "删除记录",
                "删除任务 %s 的记录？\n已下载的文件不受影响。"
                % entry.get("id"),
                parent=win,
            ):
                return
            try:
                history_mod.remove_task(self.state, str(entry.get("id")))
            except KylinPkgError as exc:
                messagebox.showerror("删除失败", str(exc), parent=win)
                return
            refresh()

        buttons = ttk.Frame(frame)
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="重新下载", command=redo).pack(side="left")
        ttk.Button(buttons, text="应用到当前参数", command=apply_to_current).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(buttons, text="删除记录", command=remove_record).pack(
            side="left", padx=(6, 0)
        )
        ttk.Button(buttons, text="刷新", command=refresh).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="关闭", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", lambda _event: apply_to_current())

        refresh()
        self._center_dialog(win)

    def _apply_history_params(self, entry: Dict[str, object]) -> None:
        """把一条历史任务的配置套用到当前下载参数（表单）。"""
        profile = str(entry.get("profile") or "")
        if profile:
            names = list(self.profile_combo["values"] or ())
            if profile not in names:
                raise KylinPkgError(
                    "profile %s 已不存在，无法套用；请先重新导入源配置" % profile
                )
            self.refresh_profiles(select=profile)
        baseline = entry.get("baseline")
        values = list(self.baseline_combo["values"] or ())
        if baseline and baseline != baseline_mod.RESERVED_EMPTY and baseline in values:
            self.baseline_var.set(str(baseline))
        else:
            if baseline and baseline != baseline_mod.RESERVED_EMPTY:
                self._append_log("警告：baseline %s 已不存在，已改为全量闭包" % baseline)
            self.baseline_var.set(FULL_LABEL)
        archs = ",".join(str(a) for a in entry.get("architectures") or [])
        if archs:
            self._set_arch_value(archs)
        packages = " ".join(str(s) for s in entry.get("requested") or [])
        if packages:
            self.packages_var.set(packages)
        output = str(entry.get("output") or "")
        if output:
            self.output_var.set(output)
            self._output_auto = False
        self.recommends_var.set(bool(entry.get("recommends", True)))
        self.with_dependencies_var.set(bool(entry.get("with_dependencies", True)))
        self.repo_var.set(bool(entry.get("make_repo", False)))
        self.status_var.set("已套用任务 %s 的配置" % entry.get("id"))

    # --------------------------------------------------------------- misc
    def _open_output_dir(self) -> None:
        text = self.output_var.get().strip()
        if not text:
            profile = self._current_profile()
            if not profile:
                messagebox.showinfo("提示", "请先选择 apt 源配置", parent=self.root)
                return
            text = self._default_output(profile)
        path = Path(text).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("打开失败", str(exc), parent=self.root)
            return
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen(
                [opener, str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            messagebox.showinfo("输出目录", str(path), parent=self.root)

    def _clear_cache(self) -> None:
        size = self.state.cache_size()
        if size <= 0:
            messagebox.showinfo("清理缓存", "没有可清理的缓存。", parent=self.root)
            return
        if not messagebox.askyesno(
            "清理缓存",
            "将删除隔离 apt 索引和包缓存（%s）。\n"
            "不会删除 profile、baseline 和已下载结果。\n"
            "下次解析会自动重建索引。" % human_size(size),
            parent=self.root,
        ):
            return
        try:
            freed = self.state.clear_cache()
        except OSError as exc:
            messagebox.showerror("清理失败", str(exc), parent=self.root)
            return
        self._append_log("已清理缓存，释放 %s" % human_size(freed))
        self.status_var.set("缓存已清理：%s" % human_size(freed))

    def _open_state_dir(self) -> None:
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen(
                [opener, str(self.state.root)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            messagebox.showinfo("状态目录", str(self.state.root), parent=self.root)

    def _locate_manual(self) -> Optional[Path]:
        """定位使用手册 PDF：源码运行在仓库根 docs/，deb 安装在 /opt/kylinpkg/docs/。"""
        candidates = [
            Path(__file__).resolve().parents[1] / "docs" / "kylinpkg-manual.pdf",
            Path("/opt/kylinpkg/docs/kylinpkg-manual.pdf"),
        ]
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _open_manual(self) -> None:
        manual = self._locate_manual()
        if manual is None:
            messagebox.showerror(
                "未找到使用手册",
                "未找到内置的使用手册 PDF。\n"
                "请从安装目录 /opt/kylinpkg/docs 获取，或在源码目录执行：\n"
                "python3 packaging/build-doc-pdf.py",
                parent=self.root,
            )
            return
        opener = shutil.which("xdg-open")
        if opener:
            subprocess.Popen(
                [opener, str(manual)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            messagebox.showinfo("使用手册", str(manual), parent=self.root)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "关于 kylinpkg",
            "kylinpkg %s\n\n"
            "多源、多架构 deb 包与依赖离线下载器。\n"
            "所有 apt 操作在隔离 root 中进行，不修改本机 /etc/apt 与 /var/lib/dpkg。\n\n"
            "CLI: bin/kylinpkg\nGUI: bin/kylinpkg-gui\n\n"
            "许可：MIT，Copyright (c) 2026 mohao\n"
            "本项目是独立的第三方工具，不是麒麟软件有限公司的官方产品。\n"
            "“麒麟”“Kylin”商标归各自权利人所有，本项目仅作描述性使用。" % __version__,
            parent=self.root,
        )


def run_gui(state: State) -> None:
    # className 写入 WM_CLASS 的 class 分量，配合 .desktop 的
    # StartupWMClass 让启动器/任务栏能正确关联窗口
    root = tk.Tk(className="Kylinpkg")
    _apply_window_icon(root)
    App(root, state)
    root.mainloop()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kylinpkg-gui", description="kylinpkg 图形界面"
    )
    parser.add_argument("--state", type=Path, help="状态目录（与命令行共用）")
    args = parser.parse_args(argv)
    state = State(args.state).ensure()
    try:
        baseline_mod.ensure_builtin_baselines(state)  # 内置基线默认导入（幂等）
    except Exception:
        pass  # 自动导入失败不阻塞 GUI 启动
    try:
        run_gui(state)
    except tk.TclError as exc:
        print("无法启动图形界面：%s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
