# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import tempfile
import unittest
from pathlib import Path

from kylinpkg import baseline, profile
from kylinpkg.config import State
from kylinpkg.util import KylinPkgError


STATUS = """Package: libc6
Status: install ok installed
Architecture: amd64
Version: 2.31-1
Description: libc

Package: libc6
Status: install ok installed
Architecture: i386
Version: 2.31-1
Description: libc i386
"""


class ProfileBaselineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-test-")
        self.root = Path(self.tmp.name)
        self.state = State(self.root / "state").ensure()
        self.repo_dir = self.root / "repo"
        self.repo_dir.mkdir()
        (self.repo_dir / "dummy.deb").write_bytes(b"not a real deb")

    def tearDown(self):
        self.tmp.cleanup()

    def _sources(self, name="test.list", suite="./"):
        path = self.root / name
        path.write_text(
            "deb [trusted=yes] file:%s %s\n" % (self.repo_dir, suite), encoding="utf-8"
        )
        return path

    def test_import_profile_and_fingerprint(self):
        sources = self._sources()
        meta = profile.import_profile(
            self.state,
            "p1",
            sources_files=[sources],
            architectures=["amd64"],
        )
        self.assertEqual(meta["architectures"], ["amd64"])
        self.assertIsNone(meta["baseline"])
        self.assertTrue((self.state.profile_dir("p1") / "sources.list").is_file())
        first = profile.fingerprint(self.state, "p1")
        (self.state.profile_dir("p1") / "sources.list").write_text(
            "deb [trusted=yes] file:%s ./\n# changed\n" % self.repo_dir, encoding="utf-8"
        )
        self.assertNotEqual(first, profile.fingerprint(self.state, "p1"))

    def test_duplicate_profile_requires_force(self):
        sources = self._sources()
        profile.import_profile(self.state, "p1", sources_files=[sources], architectures=["amd64"])
        with self.assertRaises(KylinPkgError):
            profile.import_profile(self.state, "p1", sources_files=[sources], architectures=["amd64"])
        meta = profile.import_profile(
            self.state, "p1", sources_files=[sources], architectures=["amd64"], force=True
        )
        self.assertEqual(meta["name"], "p1")

    def test_failed_import_cleans_up(self):
        with self.assertRaises(KylinPkgError):
            profile.import_profile(
                self.state,
                "broken",
                sources_files=[self.root / "missing.list"],
                architectures=["amd64"],
            )
        self.assertFalse(self.state.profile_dir("broken").exists())

    def test_baseline_import_and_compat(self):
        status_path = self.root / "status"
        status_path.write_text(STATUS, encoding="utf-8")
        meta = baseline.import_baseline(self.state, "b1", status_file=status_path)
        self.assertEqual(meta["installed_count"], 2)
        self.assertEqual(meta["architectures"], ["amd64", "i386"])
        problem = baseline.check_compatible({"architectures": ["amd64"]}, meta)
        self.assertIn("i386", problem)
        self.assertIsNone(baseline.check_compatible({"architectures": ["amd64", "i386"]}, meta))

    def test_reserved_empty_name(self):
        with self.assertRaises(KylinPkgError):
            baseline.import_baseline(self.state, "empty", empty=True)

    def test_duplicate_baseline_refusal_keeps_existing(self):
        status_path = self.root / "status"
        status_path.write_text(STATUS, encoding="utf-8")
        baseline.import_baseline(self.state, "b1", status_file=status_path)
        with self.assertRaises(KylinPkgError):
            baseline.import_baseline(self.state, "b1", status_file=status_path)
        self.assertTrue((self.state.baseline_dir("b1") / "meta.json").is_file())
        self.assertTrue((self.state.baseline_dir("b1") / "status").is_file())

    def test_source_declared_arch_is_used(self):
        sources = self.root / "arch.sources"
        sources.write_text(
            "Types: deb\n"
            "URIs: file:%s\n"
            "Suites: ./\n"
            "Components: \n"
            "Architectures: arm64\n"
            "Trusted: yes\n" % self.repo_dir,
            encoding="utf-8",
        )
        meta = profile.import_profile(self.state, "p-arm", sources_files=[sources])
        self.assertEqual(meta["architectures"], ["arm64"])

    def test_no_system_keyrings_marker(self):
        sources = self._sources()
        profile.import_profile(
            self.state,
            "p-nokeys",
            sources_files=[sources],
            architectures=["amd64"],
            copy_system_keys=False,
        )
        self.assertTrue(
            (self.state.profile_dir("p-nokeys") / "keyrings" / ".no-system-keys").is_file()
        )

    def test_auth_import_and_apt_options(self):
        from kylinpkg.aptroot import AptRoot

        sources = self._sources()
        auth = self.root / "auth.conf"
        auth.write_text("machine example.com login demo password secret\n", encoding="utf-8")
        meta = profile.import_profile(
            self.state,
            "p-auth",
            sources_files=[sources],
            architectures=["amd64"],
            auth_files=[auth],
        )
        self.assertTrue(meta["with_auth"])
        self.assertTrue((self.state.profile_dir("p-auth") / "auth.conf").is_file())
        root = AptRoot(self.state, "p-auth", ["amd64"])
        opts = root.apt_options()
        self.assertTrue(any("Dir::Etc::netrc=" in item for item in opts))

    def test_materialize_signed_by_from_rootfs(self):
        rootfs = self.root / "rootfs"
        (rootfs / "etc/apt/sources.list.d").mkdir(parents=True)
        (rootfs / "etc/apt/sources.list").write_text("", encoding="utf-8")
        (rootfs / "usr/share/keyrings").mkdir(parents=True)
        (rootfs / "usr/share/keyrings/fake.gpg").write_bytes(b"fake-key")
        (rootfs / "etc/apt/sources.list.d/fake.sources").write_text(
            "Types: deb\n"
            "URIs: http://example.invalid/repo\n"
            "Suites: stable\n"
            "Components: main\n"
            "Architectures: amd64\n"
            "Signed-By: /usr/share/keyrings/fake.gpg\n",
            encoding="utf-8",
        )
        meta = profile.import_profile(
            self.state,
            "p-signed",
            from_rootfs=rootfs,
            architectures=["amd64"],
        )
        self.assertTrue(meta["sources_summary"])
        key = self.state.profile_dir("p-signed") / "keyrings" / "signed-by" / "fake.gpg"
        self.assertTrue(key.is_file())
        source_text = (
            self.state.profile_dir("p-signed") / "sources.list.d" / "fake.sources"
        ).read_text(encoding="utf-8")
        self.assertIn(str(key), source_text)
        self.assertNotIn("/usr/share/keyrings/fake.gpg", source_text)

    def test_bind_baseline(self):
        status_path = self.root / "status"
        status_path.write_text(STATUS, encoding="utf-8")
        baseline.import_baseline(self.state, "b1", status_file=status_path)
        sources = self._sources()
        profile.import_profile(
            self.state, "p1", sources_files=[sources], architectures=["amd64", "i386"]
        )
        meta = profile.bind_baseline(self.state, "p1", "b1")
        self.assertEqual(meta["baseline"], "b1")
        meta = profile.bind_baseline(self.state, "p1", None)
        self.assertIsNone(meta["baseline"])


if __name__ == "__main__":
    unittest.main()
