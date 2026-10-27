# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import tempfile
import unittest
from pathlib import Path

from kylinpkg.config import State
from kylinpkg.util import ensure_dir


class CacheTest(unittest.TestCase):
    def test_clear_cache_keeps_profiles_and_baselines(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-cache-test-") as tmp:
            state = State(Path(tmp) / "state").ensure()
            ensure_dir(state.profile_dir("p1"))
            (state.profile_dir("p1") / "profile.json").write_text("{}", encoding="utf-8")
            ensure_dir(state.baseline_dir("b1"))
            (state.baseline_dir("b1") / "meta.json").write_text("{}", encoding="utf-8")

            root1 = state.roots_dir / "p1" / "amd64" / "var" / "lib" / "apt" / "lists"
            root2 = state.roots_dir / "p2" / "arm64" / "cache"
            ensure_dir(root1)
            ensure_dir(root2)
            (root1 / "Packages").write_bytes(b"x" * 100)
            (root2 / "pkg.deb").write_bytes(b"y" * 200)

            self.assertGreaterEqual(state.cache_size(), 300)
            self.assertGreaterEqual(state.cache_size("p1"), 100)

            freed = state.clear_cache("p1")
            self.assertGreaterEqual(freed, 100)
            self.assertFalse((state.roots_dir / "p1").exists())
            self.assertTrue((state.roots_dir / "p2").exists())
            self.assertTrue(state.profile_dir("p1").is_dir())
            self.assertTrue(state.baseline_dir("b1").is_dir())

            freed = state.clear_cache()
            self.assertGreaterEqual(freed, 200)
            self.assertTrue(state.roots_dir.is_dir())
            self.assertEqual(state.cache_size(), 0)
            self.assertTrue(state.profile_dir("p1").is_dir())
            self.assertTrue(state.baseline_dir("b1").is_dir())

            # 幂等
            self.assertEqual(state.clear_cache(), 0)


if __name__ == "__main__":
    unittest.main()
