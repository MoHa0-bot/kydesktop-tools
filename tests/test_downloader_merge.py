# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""downloader 追加合并（merge）与 _prepare_output 指纹放宽逻辑的单元测试。"""
import json
import tempfile
import unittest
from pathlib import Path

from kylinpkg.downloader import _prepare_output, _profile_fingerprint
from kylinpkg.util import KylinPkgError


def _manifest(profile="test", archs=("amd64",), baseline="empty", requested=("pkg-a",)):
    return {
        "schema": 1,
        "profile": profile,
        "architectures": list(archs),
        "baseline": {"name": baseline, "mode": "full"},
        "requested": list(requested),
        "requested_satisfied": [],
        "with_dependencies": True,
        "packages": [],
        "totals": {"count": 0, "bytes": 0},
    }


class ProfileFingerprintTest(unittest.TestCase):
    def test_ignores_requested(self):
        fp = {
            "profile": "test",
            "architectures": ["amd64"],
            "baseline": "empty",
            "requested": ["pkg-a"],
            "with_dependencies": True,
        }
        got = _profile_fingerprint(fp)
        self.assertNotIn("requested", got)
        self.assertNotIn("with_dependencies", got)
        self.assertEqual(got, {"profile": "test", "architectures": ["amd64"], "baseline": "empty"})


class PrepareOutputMergeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-merge-test-")
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _write_manifest(self, out: Path, manifest):
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_merge_allows_different_requested(self):
        out = self.root / "out"
        self._write_manifest(out, _manifest(requested=("pkg-a",)))
        new_fp = {
            "profile": "test",
            "architectures": ["amd64"],
            "baseline": "empty",
            "requested": ["pkg-b"],
        }
        # merge=True 且 profile/架构/基线一致 -> 返回 None（继续下载），不抛错。
        result = _prepare_output(out, new_fp, force=False, merge=True)
        self.assertIsNone(result)

    def test_merge_rejects_profile_mismatch(self):
        out = self.root / "out"
        self._write_manifest(out, _manifest(profile="test"))
        new_fp = {
            "profile": "other",
            "architectures": ["amd64"],
            "baseline": "empty",
            "requested": ["pkg-b"],
        }
        with self.assertRaises(KylinPkgError):
            _prepare_output(out, new_fp, force=False, merge=True)

    def test_merge_rejects_arch_mismatch(self):
        out = self.root / "out"
        self._write_manifest(out, _manifest(archs=("amd64",)))
        new_fp = {
            "profile": "test",
            "architectures": ["arm64"],
            "baseline": "empty",
            "requested": ["pkg-b"],
        }
        with self.assertRaises(KylinPkgError):
            _prepare_output(out, new_fp, force=False, merge=True)

    def test_merge_rejects_baseline_mismatch(self):
        out = self.root / "out"
        self._write_manifest(out, _manifest(baseline="empty"))
        new_fp = {
            "profile": "test",
            "architectures": ["amd64"],
            "baseline": "other",
            "requested": ["pkg-b"],
        }
        with self.assertRaises(KylinPkgError):
            _prepare_output(out, new_fp, force=False, merge=True)

    def test_non_merge_still_rejects_different_requested(self):
        out = self.root / "out"
        self._write_manifest(out, _manifest(requested=("pkg-a",)))
        new_fp = {
            "profile": "test",
            "architectures": ["amd64"],
            "baseline": "empty",
            "requested": ["pkg-b"],
        }
        with self.assertRaises(KylinPkgError):
            _prepare_output(out, new_fp, force=False, merge=False)


if __name__ == "__main__":
    unittest.main()
