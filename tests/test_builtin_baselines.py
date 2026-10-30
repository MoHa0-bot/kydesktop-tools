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
    "sp1-2303-arm64",
    "sp1-2303-x86",
    "sp1-2403-arm64",
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
            # 内核元包版本列：内置基线必须能给出 linux-generic 版本
            self.assertRegex(str(item.get("kernel_version", "")), r"^5\.", item["name"])

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
            self.assertEqual(len(baseline_mod.list_baselines(state)), 7)
            # 幂等：再次调用不重复导入
            self.assertEqual(baseline_mod.ensure_builtin_baselines(state), [])
            self.assertEqual(len(baseline_mod.list_baselines(state)), 7)
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


class KernelVersionTest(unittest.TestCase):
    STATUS = (
        "Package: linux-generic\n"
        "Status: install ok installed\n"
        "Version: 5.4.18.142.131\n"
        "\n"
        "Package: linux-image-5.4.0-1-generic\n"
        "Status: install ok installed\n"
        "Version: 5.4.0-1\n"
        "\n"
        "Package: ukui-kwin\n"
        "Status: install ok installed\n"
        "Version: 1.0.2\n"
        "\n"
    )

    def test_extract_installed_kernel_metapackage(self):
        kv = baseline_mod.kernel_versions_from_status(self.STATUS.encode("utf-8"))
        self.assertEqual(kv, {"linux-generic": "5.4.18.142.131"})
        self.assertEqual(baseline_mod.kernel_display(kv), "5.4.18.142.131")

    def test_not_installed_or_non_metapackage_ignored(self):
        text = self.STATUS.replace("install ok installed\nVersion: 5.4.18.142.131", "deinstall ok config-files\nVersion: 5.4.18.142.131")
        self.assertEqual(baseline_mod.kernel_versions_from_status(text.encode("utf-8")), {})
        self.assertEqual(baseline_mod.kernel_display({}), "-")

    def test_hwe_variant_shown_with_name(self):
        kv = {"linux-generic": "5.4.0.1", "linux-generic-hwe-20.04": "5.10.0.2"}
        display = baseline_mod.kernel_display(kv)
        self.assertTrue(display.startswith("5.4.0.1;"))
        self.assertIn("linux-generic-hwe-20.04 5.10.0.2", display)

    def test_empty_status(self):
        self.assertEqual(baseline_mod.kernel_versions_from_status(b""), {})

    def test_ensure_kernel_info_backfills_old_meta(self):
        # 老版本导入的 baseline（meta 无 kernel_version）在列表时回填
        with tempfile.TemporaryDirectory(prefix="kylinpkg-kernel-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            meta = baseline_mod.import_baseline(
                state, "k1", from_builtin="sp1-2503-x86"
            )
            self.assertTrue(meta.get("kernel_version"))
            stale = json.loads(
                (state.baseline_dir("k1") / "meta.json").read_text(encoding="utf-8")
            )
            stale.pop("kernel_version", None)
            stale.pop("kernel_versions", None)
            (state.baseline_dir("k1") / "meta.json").write_text(
                json.dumps(stale, ensure_ascii=False), encoding="utf-8"
            )
            refreshed = baseline_mod.ensure_kernel_info(state, stale)
            self.assertEqual(refreshed["kernel_version"], meta["kernel_version"])
            persisted = json.loads(
                (state.baseline_dir("k1") / "meta.json").read_text(encoding="utf-8")
            )
            self.assertEqual(persisted["kernel_version"], meta["kernel_version"])


if __name__ == "__main__":
    unittest.main()
