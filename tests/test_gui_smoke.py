# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk

    _TK_IMPORT_ERROR = None
except Exception as exc:  # noqa: BLE001 - 可选依赖
    tk = None
    ttk = None
    _TK_IMPORT_ERROR = exc

_HAVE_DISPLAY = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@unittest.skipUnless(tk is not None and _HAVE_DISPLAY, "需要 tkinter 与图形显示")
class GuiSmokeTest(unittest.TestCase):
    def _walk_widgets(self, widget):
        yield widget
        for child in widget.winfo_children():
            yield from self._walk_widgets(child)

    def _assert_no_ellipsis(self, widget):
        for child in self._walk_widgets(widget):
            if isinstance(child, (tk.Button, ttk.Button)):
                self.assertNotIn("…", child.cget("text"))

    def test_create_and_select(self):
        from kylinpkg import baseline, profile
        from kylinpkg.config import State
        from kylinpkg.gui import FULL_LABEL, App
        import kylinpkg.gui as gui_module
        from kylinpkg.util import CancelToken, run

        with tempfile.TemporaryDirectory(prefix="kylinpkg-gui-test-") as tmp:
            root_dir = Path(tmp)
            state = State(root_dir / "state").ensure()
            repo_dir = root_dir / "repo"
            repo_dir.mkdir()
            (repo_dir / "dummy.deb").write_bytes(b"x")
            sources = root_dir / "sources.list"
            sources.write_text(
                "deb [trusted=yes] file:%s ./\n" % repo_dir, encoding="utf-8"
            )
            profile.import_profile(
                state, "p1", sources_files=[sources], architectures=["amd64"]
            )
            status = root_dir / "status"
            status.write_text(
                "Package: libc6\n"
                "Status: install ok installed\n"
                "Architecture: amd64\n"
                "Version: 2.31-1\n"
                "Description: libc\n",
                encoding="utf-8",
            )
            baseline.import_baseline(state, "b1", status_file=status)

            root = None
            try:
                root = tk.Tk()
                root.withdraw()
                app = App(root, state)
                root.update()
                self.assertEqual(list(app.profile_tree.get_children()), ["p1"])
                self.assertEqual(list(app.baseline_tree.get_children()), ["b1"])
                self.assertIn(FULL_LABEL, app.baseline_combo["values"])
                self.assertIn("b1", app.baseline_combo["values"])

                # baseline 面板不再显示"已安装包"列
                headings = [
                    app.baseline_tree.heading(col)["text"]
                    for col in app.baseline_tree["columns"]
                ]
                self.assertNotIn("已安装包", headings)

                # 两个面板的搜索栏：过滤列表显示，下拉框仍保留全部可选值
                app.baseline_search_var.set("b1")
                app.refresh_baselines()
                self.assertEqual(list(app.baseline_tree.get_children()), ["b1"])
                app.baseline_search_var.set("无匹配关键字")
                app.refresh_baselines()
                self.assertEqual(list(app.baseline_tree.get_children()), [])
                self.assertIn("b1", app.baseline_combo["values"])
                app.baseline_search_var.set("")
                app.refresh_baselines()
                self.assertEqual(list(app.baseline_tree.get_children()), ["b1"])
                app.profile_search_var.set("p1")
                app.refresh_profiles()
                self.assertEqual(list(app.profile_tree.get_children()), ["p1"])
                app.profile_search_var.set("无匹配关键字")
                app.refresh_profiles()
                self.assertEqual(list(app.profile_tree.get_children()), [])
                self.assertIn("p1", app.profile_combo["values"])
                app.profile_search_var.set("")
                app.refresh_profiles()
                self.assertEqual(list(app.profile_tree.get_children()), ["p1"])
                app.profile_tree.selection_set("p1")
                app.profile_var.set("p1")
                root.update()
                self.assertEqual(app._current_arch_value(), "amd64")
                app.packages_var.set("bash")
                self.assertTrue(app.with_dependencies_var.get())
                self.assertTrue(app._collect_params()["with_dependencies"])
                app.with_dependencies_var.set(False)
                self.assertFalse(app._collect_params()["with_dependencies"])
                app.with_dependencies_var.set(True)
                self._assert_no_ellipsis(root)

                # profile 按钮行：更多菜单收纳导入入口，删除按钮收窄，且保持同一行
                profile_frame = next(
                    child
                    for child in self._walk_widgets(root)
                    if isinstance(child, ttk.LabelFrame)
                    and "apt 源配置" in str(child.cget("text"))
                )
                controls = {
                    str(child.cget("text")): child
                    for child in self._walk_widgets(profile_frame)
                    if isinstance(child, (ttk.Button, ttk.Menubutton))
                }
                for text in ("从预设创建", "从本机导入", "编辑源配置", "更多", "删除"):
                    self.assertIn(text, controls)
                self.assertNotIn("导入源配置", controls)
                self.assertNotIn("从 rootfs 导入", controls)
                self.assertEqual(int(controls["删除"].cget("width")), 6)
                self.assertEqual(
                    len({str(controls[text].master) for text in (
                        "从预设创建", "从本机导入", "编辑源配置", "更多", "删除"
                    )}),
                    1,
                )
                more_menu = root.nametowidget(controls["更多"].cget("menu"))
                self.assertEqual(
                    [more_menu.entrycget(i, "label") for i in range(2)],
                    ["导入源配置", "从 rootfs 导入"],
                )

                # 中断按钮：用 sleep 模拟长时间任务，验证 GUI 中断链路
                token = CancelToken()

                def slow_work():
                    run(["sleep", "10"], timeout=20, cancel=token)
                    return "未中断"

                with unittest.mock.patch.object(
                    gui_module.messagebox, "showerror", lambda *a, **k: None
                ):
                    app._start_task(slow_work, "测试", token=token)
                    root.update()
                    self.assertTrue(app.busy)
                    app._cancel_task()
                    deadline = time.time() + 5
                    while app.busy and time.time() < deadline:
                        root.update()
                        time.sleep(0.05)
                    root.update()
                self.assertFalse(app.busy)
                self.assertEqual(app.status_var.get(), "已中断")
                self._assert_no_ellipsis(root)

                # 回调型后台任务（版本查询走这条路径）
                seen = {}
                app._start_task(
                    lambda: {"ok": True},
                    "查询",
                    token=CancelToken(),
                    on_success=lambda data: seen.update(data),
                )
                deadline = time.time() + 5
                while app.busy and time.time() < deadline:
                    root.update()
                    time.sleep(0.05)
                root.update()
                self.assertFalse(app.busy)
                self.assertTrue(seen.get("ok"))

                # 清理缓存按钮
                cache_file = state.roots_dir / "p1" / "amd64" / "cache.bin"
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_bytes(b"x" * 100)
                with unittest.mock.patch.object(
                    gui_module.messagebox, "askyesno", lambda *a, **k: True
                ):
                    app._clear_cache()
                self.assertEqual(state.cache_size(), 0)
                self.assertIn("缓存已清理", app.status_var.get())

                def close_dialogs():
                    for child in list(root.winfo_children()):
                        if isinstance(child, tk.Toplevel):
                            try:
                                child.grab_release()
                            except Exception:
                                pass
                            child.destroy()

                # 两个导入对话框也应能正常构建和销毁
                app._profile_import_dialog()
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
                app._baseline_import_dialog()
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
                app._bundle_import_dialog()
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
                app._preset_dialog()
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
                app._profile_editor_dialog()
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
                app._show_version_dialog(
                    {
                        "package": "p1",
                        "installed": None,
                        "candidate": "2.0",
                        "versions": [
                            {
                                "version": "2.0",
                                "priority": 500,
                                "sources": ["http://example.invalid stable/main"],
                                "architectures": ["amd64"],
                                "downloadable": True,
                                "installed": False,
                                "candidate": True,
                            },
                            {
                                "version": "1.0",
                                "priority": 500,
                                "sources": ["http://example.invalid stable/main"],
                                "architectures": ["amd64"],
                                "downloadable": True,
                                "installed": False,
                                "candidate": False,
                            },
                        ],
                    }
                )
                root.update()
                self._assert_no_ellipsis(root)
                close_dialogs()
            finally:
                if root is not None:
                    root.destroy()


if __name__ == "__main__":
    unittest.main()
