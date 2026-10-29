# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from kylinpkg import baseline as baseline_mod
from kylinpkg import deb822
from kylinpkg.config import State
from kylinpkg.util import KylinPkgError

EXPECTED_NAMES = [
    "sp1-2203-x86",
    "sp1-2303-x86",
    "sp1-2403-x86",
    "sp1-2503-arm64",
    "sp1-2503-x86",
]


class BuiltinBaselinesTest(unittest.TestCase):
    def test_catalog(self):
        items = baseline_mod.list_builtin_baselines()
        names = [item.get("name") for item in items]
        self.assertEqual(names, EXPECTED_NAMES)
        for item in items:
            self.assertTrue(item.get("builtin"))
            self.assertGreater(int(item.get("installed_count", 0)), 1000, item["name"])
            self.assertTrue(item.get("architectures"), item["name"])
            self.assertTrue(item.get("source_bundle"), item["name"])
            self.assertTrue(item.get("status_sha256"), item["name"])
            self.assertTrue(item.get("note"), item["name"])

    def test_status_gz_matches_meta(self):
        items = baseline_mod.list_builtin_baselines()
        self.assertTrue(items)
        for item in items:
            data = baseline_mod._builtin_status_bytes(item["name"])
            self.assertEqual(
                hashlib.sha256(data).hexdigest(), item["status_sha256"], item["name"]
            )
            self.assertEqual(len(data), int(item["status_size"]), item["name"])
            summary = deb822.status_summary(
                deb822.parse_status_text(data.decode("utf-8", errors="replace"))
            )
            self.assertEqual(
                summary["installed_count"], int(item["installed_count"]), item["name"]
            )
            self.assertEqual(
                sorted(summary["architectures"]),
                sorted(item["architectures"]),
                item["name"],
            )
            self.assertEqual(summary["duplicates"], [], item["name"])

    def test_2503_x86_and_arm64_are_distinct(self):
        x86 = baseline_mod._builtin_status_bytes("sp1-2503-x86")
        arm64 = baseline_mod._builtin_status_bytes("sp1-2503-arm64")
        self.assertNotEqual(x86, arm64)
        self.assertIn("amd64", baseline_mod.get_builtin_baseline_meta("sp1-2503-x86")["architectures"])
        self.assertIn("arm64", baseline_mod.get_builtin_baseline_meta("sp1-2503-arm64")["architectures"])

    def test_unknown_builtin(self):
        with self.assertRaises(KylinPkgError):
            baseline_mod.get_builtin_baseline_meta("sp1-9999")

    def test_import_from_builtin(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-builtin-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            meta = baseline_mod.import_baseline(
                state, "sp1-2203-x86", from_builtin="sp1-2203-x86"
            )
            self.assertEqual(meta["origin"]["kind"], "builtin")
            self.assertIn("sp1-2203-x86", meta["origin"]["detail"])
            self.assertEqual(
                meta["installed_count"],
                baseline_mod.get_builtin_baseline_meta("sp1-2203-x86")["installed_count"],
            )
            # 再次导入同名需要 --force
            with self.assertRaises(KylinPkgError):
                baseline_mod.import_baseline(
                    state, "sp1-2203-x86", from_builtin="sp1-2203-x86"
                )
            meta = baseline_mod.import_baseline(
                state, "sp1-2203-x86", from_builtin="sp1-2203-x86", force=True
            )
            self.assertEqual(meta["name"], "sp1-2203-x86")
            # 来源互斥：--builtin 与 --empty 不能同时给
            with self.assertRaises(KylinPkgError):
                baseline_mod.import_baseline(
                    state, "x", from_builtin="sp1-2203-x86", empty=True
                )
            # state 里的 baseline 可被正常读取
            self.assertEqual(len(baseline_mod.list_baselines(state)), 1)

    def test_import_with_chinese_name(self):
        # 名称规则支持汉字（预设 ID 如 xc-2203-实机）
        with tempfile.TemporaryDirectory(prefix="kylinpkg-cjk-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            meta = baseline_mod.import_baseline(
                state, "基线-2203-实机", from_builtin="sp1-2203-x86"
            )
            self.assertEqual(meta["name"], "基线-2203-实机")
            self.assertTrue(
                (state.baseline_dir("基线-2203-实机") / "meta.json").is_file()
            )

    def test_ensure_builtin_auto_import(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-ensure-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            created = baseline_mod.ensure_builtin_baselines(state)
            self.assertEqual(sorted(created), sorted(EXPECTED_NAMES))
            self.assertEqual(len(baseline_mod.list_baselines(state)), 5)
            # 幂等：再次调用不重复导入
            self.assertEqual(baseline_mod.ensure_builtin_baselines(state), [])
            self.assertEqual(len(baseline_mod.list_baselines(state)), 5)
            # 用户删除后不再自动恢复（同步标记已记录）
            baseline_mod.remove_baseline(state, "sp1-2203-x86")
            self.assertEqual(baseline_mod.ensure_builtin_baselines(state), [])
            self.assertFalse(
                (state.baseline_dir("sp1-2203-x86") / "meta.json").is_file()
            )

    def test_ensure_respects_manual_import(self):
        # 用户手工导入过同名基线：自动同步不覆盖，只记录标记
        with tempfile.TemporaryDirectory(prefix="kylinpkg-ensure2-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            manual = baseline_mod.import_baseline(
                state, "sp1-2303-x86", from_system=True, note="手工"
            )
            created = baseline_mod.ensure_builtin_baselines(state)
            self.assertNotIn("sp1-2303-x86", created)
            current = baseline_mod.load_meta(state, "sp1-2303-x86")
            self.assertEqual(current["created_at"], manual["created_at"])


if __name__ == "__main__":
    unittest.main()
