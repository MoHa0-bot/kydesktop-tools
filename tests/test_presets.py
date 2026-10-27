# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from kylinpkg import deb822, presets, profile
from kylinpkg.config import State
from kylinpkg.util import KylinPkgError


class PresetsTest(unittest.TestCase):
    def test_catalog_is_parseable_and_unique(self):
        self.assertEqual(len(presets.PRESETS), 42)
        ids = [item.id for item in presets.PRESETS]
        self.assertEqual(len(ids), len(set(ids)))
        for item in presets.PRESETS:
            self.assertTrue(item.sources, item.id)
            for line in item.sources:
                self.assertNotIn(" ", line.split()[1], "URI 中有空格：%s" % line)
                entries = deb822.parse_sources_text(line + "\n", item.id)
                self.assertEqual(len(entries), 1)
                self.assertFalse(" " in entries[0].uri)

    def test_presets_match_source_document(self):
        doc = Path(__file__).resolve().parents[1] / "docs" / "kylin-desktop-sources.md"
        if not doc.is_file():
            self.skipTest("docs/kylin-desktop-sources.md 不存在")
        text = doc.read_text(encoding="utf-8", errors="replace")
        md_lines = [
            line.strip() for line in text.splitlines() if line.strip().startswith("deb ")
        ]
        preset_lines = [line for item in presets.PRESETS for line in item.sources]
        self.assertEqual(len(md_lines), 208)
        self.assertEqual(len(preset_lines), 208)

        def normalize(line):
            return " ".join(line.split())

        self.assertEqual(
            Counter(normalize(line) for line in md_lines),
            Counter(normalize(line) for line in preset_lines),
        )

    def test_groups_are_xc_hwe_wayland_legacy(self):
        groups = []
        for item in presets.PRESETS:
            if item.group not in groups:
                groups.append(item.group)
        self.assertEqual(
            groups,
            [
                "XC 产线（通用版）",
                "HWE 硬件启用栈",
                "Wayland · 麒麟 990",
                "Wayland · 麒麟 9006C",
                "Wayland · 盘古 M900（Pangwu）",
                "Wayland · 麒麟 9000C",
                "Wayland · 华为其他平台",
                "V10 基础版（非 SP1，历史）",
            ],
        )
        self.assertEqual(len(presets.list_presets("XC 产线（通用版）")), 6)
        self.assertEqual(len(presets.list_presets("HWE 硬件启用栈")), 10)
        self.assertEqual(
            sum(1 for item in presets.PRESETS if item.group.startswith("Wayland")), 24
        )

    def test_specific_presets(self):
        # 2503 使用带 -limit 的 bugfix suite（旧文档写的是 10.1-2503-bugfix，已过时）
        p2503 = presets.get_preset("xc-2503")
        text = "\n".join(p2503.sources)
        self.assertIn("10.1-kylin", text)
        self.assertIn("10.1-kylin-2503", text)
        self.assertIn("10.1-2503-bugfix-limit", text)
        # 全目录不应再出现过时的 10.1-2503-bugfix（非 -limit）写法
        for item in presets.PRESETS:
            for line in item.sources:
                parts = line.split()
                self.assertNotIn(
                    "10.1-2503-bugfix", parts[2:3], "过时的 suite：%s" % line
                )

        # Kirin partner 路径统一为 10_1-
        kirin = presets.get_preset("wl-2107-990")
        text = "\n".join(kirin.sources)
        self.assertIn("PART-10_1-kirin990", text)
        self.assertNotIn("PART-10.1-kirin990", text)
        self.assertEqual(kirin.architectures, ("arm64",))

        # 盘古 M900 归入独立分组
        self.assertEqual(
            presets.get_preset("wl-2503-m900").group, "Wayland · 盘古 M900（Pangwu）"
        )

        # V10 非 SP1 历史预设保留
        legacy = presets.get_preset("v10-2107")
        self.assertIn("10.0", "\n".join(legacy.sources))
        self.assertTrue(any("旧版" in note for note in legacy.notes))

    def test_preferences_are_recorded(self):
        with_pin = [item.id for item in presets.PRESETS if item.preferences]
        self.assertEqual(len(with_pin), 11)
        for preset_id in (
            "xc-2503",
            "hwe-2503",
            "hwe-pp-2503",
            "wl-2503-990",
            "wl-2503-9006c",
            "wl-2503-m900",
            "wl-2503-9000c",
            "wl-pangux-a-2403",
            "wl-pangux-b",
            "wl-flemingx",
            "wl-panguy",
        ):
            self.assertIn(preset_id, with_pin)
        # 每条优先级配置都必须是合法的 Pin 段落
        for item in presets.PRESETS:
            if not item.preferences:
                continue
            blocks = [blk for blk in "\n".join(item.preferences).split("\n\n") if blk.strip()]
            for block in blocks:
                lines = [ln for ln in block.splitlines() if ln.strip()]
                self.assertTrue(lines[0].startswith("Package:"), item.id)
                self.assertTrue(
                    any(ln.startswith("Pin-Priority:") for ln in lines), item.id
                )

    def test_create_from_preset(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-preset-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            meta = profile.create_from_preset(
                state, "xc-2503-test", "xc-2503", architectures=["amd64"]
            )
            self.assertEqual(meta["architectures"], ["amd64"])
            self.assertEqual(len(meta["sources_summary"]), 4)
            self.assertTrue(meta["notices"])
            entries = profile.profile_sources(state, "xc-2503-test")
            self.assertEqual(len(entries), 4)
            with self.assertRaises(KylinPkgError):
                profile.create_from_preset(
                    state, "xc-2503-test", "xc-2503", architectures=["amd64"]
                )
            meta = profile.create_from_preset(
                state,
                "xc-2503-test",
                "xc-2503",
                architectures=["amd64"],
                force=True,
            )
            self.assertEqual(meta["name"], "xc-2503-test")

            # 带优先级的预设会写入 preferences.d/kylin.pref
            pdir = state.profile_dir("xc-2503-test")
            pref = pdir / "preferences.d" / "kylin.pref"
            self.assertTrue(pref.is_file())
            content = pref.read_text(encoding="utf-8")
            self.assertIn("Pin-Priority: 600", content)
            self.assertIn("10.1-2503-bugfix-limit", content)
            self.assertTrue(
                any("kylin.pref" in str(f["path"]) for f in meta["files"])
            )

            # 不带优先级的预设不应生成 preferences 文件
            profile.create_from_preset(state, "xc-2303-test", "xc-2303")
            pdir2 = state.profile_dir("xc-2303-test")
            self.assertFalse((pdir2 / "preferences.d" / "kylin.pref").exists())

            arm = profile.create_from_preset(state, "kirin-test", "wl-2503-990")
            self.assertEqual(arm["architectures"], ["arm64"])

    def test_unknown_preset(self):
        with self.assertRaises(KylinPkgError):
            presets.get_preset("sp1-2503")


if __name__ == "__main__":
    unittest.main()
