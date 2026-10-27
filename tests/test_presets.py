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
        self.assertEqual(len(presets.PRESETS), 26)
        self.assertFalse(
            any("普通版" in item.name or "普通版" in item.description for item in presets.PRESETS)
        )
        ids = [item.id for item in presets.PRESETS]
        self.assertEqual(len(ids), len(set(ids)))
        for item in presets.PRESETS:
            self.assertTrue(item.sources, item.id)
            for line in item.sources:
                self.assertNotIn(" ", line.split()[1], "URI 中有空格：%s" % line)
                entries = deb822.parse_sources_text(line + "\n", item.id)
                self.assertEqual(len(entries), 1)
                self.assertFalse(" " in entries[0].uri)

    def test_presets_match_corrected_document(self):
        doc = Path(__file__).resolve().parents[1] / "docs" / "kylin-desktop-sources.md"
        if not doc.is_file():
            self.skipTest("docs/kylin-desktop-sources.md 不存在")
        text = doc.read_text(encoding="utf-8", errors="replace")
        md_lines = [
            line.strip() for line in text.splitlines() if line.strip().startswith("deb ")
        ]
        preset_lines = [line for item in presets.PRESETS for line in item.sources]
        self.assertEqual(len(md_lines), 88)
        self.assertEqual(len(preset_lines), 88)

        def normalize(line):
            line = " ".join(line.split())
            line = line.replace("universe universe", "universe")
            return line

        self.assertEqual(
            Counter(normalize(line) for line in md_lines),
            Counter(normalize(line) for line in preset_lines),
        )

    def test_specific_presets(self):
        p2503 = presets.get_preset("sp1-2503")
        text = "\n".join(p2503.sources)
        self.assertIn("10.1-kylin", text)
        self.assertIn("10.1-kylin-2503", text)
        self.assertIn("10.1-2503-bugfix", text)
        self.assertTrue(any("bugfix-limit" in note for note in p2503.notes))

        kirin = presets.get_preset("sp1-kirin990-old")
        text = "\n".join(kirin.sources)
        self.assertIn("PART-10_1-kirin990", text)
        self.assertNotIn("PART-10.1-kirin990", text)
        self.assertNotIn("PART-10 1-", text)
        self.assertEqual(kirin.architectures, ("arm64",))
        self.assertIn("2107版", presets.get_preset("sp1-kirin990-new").name)
        self.assertIn("通用版", presets.get_preset("sp1-2403").name)
        self.assertEqual(
            presets.get_preset("sp1-2203-pangwu-m900").group,
            "海思麒麟 · 盘古（Pangwu）",
        )

        # 第 12 条按文档保留 partner suite 的 10.1 路径
        kirin2203 = presets.get_preset("sp1-2203-kirin990")
        text = "\n".join(kirin2203.sources)
        self.assertIn("PART-10_1-kirin9a0", text)
        self.assertIn("partner/10.1-kirin9a0", text)
        self.assertIn("10_1-kirin990-feature", text)

    def test_create_from_preset(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-preset-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            meta = profile.create_from_preset(
                state, "sp1-2503-test", "sp1-2503", architectures=["amd64"]
            )
            self.assertEqual(meta["architectures"], ["amd64"])
            self.assertEqual(len(meta["sources_summary"]), 4)
            self.assertTrue(meta["notices"])
            entries = profile.profile_sources(state, "sp1-2503-test")
            self.assertEqual(len(entries), 4)
            with self.assertRaises(KylinPkgError):
                profile.create_from_preset(
                    state, "sp1-2503-test", "sp1-2503", architectures=["amd64"]
                )
            meta = profile.create_from_preset(
                state,
                "sp1-2503-test",
                "sp1-2503",
                architectures=["amd64"],
                force=True,
            )
            self.assertEqual(meta["name"], "sp1-2503-test")

            arm = profile.create_from_preset(state, "kirin-test", "sp1-kirin990-new")
            self.assertEqual(arm["architectures"], ["arm64"])

            hwe = profile.create_from_preset(
                state, "hwe-arm64", "sp1-2107-hwe", architectures=["arm64"]
            )
            self.assertEqual(hwe["architectures"], ["arm64"])
            hwe_entries = profile.profile_sources(state, "hwe-arm64")
            self.assertEqual(len(hwe_entries), 4)
            self.assertTrue(
                any("KY-V10-SP1-arm64" in entry.uri for entry in hwe_entries)
            )
            self.assertFalse(any("$(ARCH)" in entry.uri for entry in hwe_entries))


if __name__ == "__main__":
    unittest.main()
