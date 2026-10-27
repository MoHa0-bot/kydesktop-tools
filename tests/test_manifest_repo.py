# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import shutil
import tempfile
import unittest
from pathlib import Path

from kylinpkg import manifest, repo
from kylinpkg.resolver import PlanEntry, ResolvePlan
from kylinpkg.util import run


@unittest.skipUnless(shutil.which("dpkg-deb") and shutil.which("apt-ftparchive"), "需要 dpkg-deb/apt-ftparchive")
class ManifestRepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-repo-test-")
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        self.debs = self.out / "debs"
        self.debs.mkdir(parents=True)
        pkg = self.root / "pkg"
        (pkg / "DEBIAN").mkdir(parents=True)
        (pkg / "DEBIAN" / "control").write_text(
            "Package: hello-test\n"
            "Version: 1.0\n"
            "Architecture: all\n"
            "Maintainer: Test <test@example.com>\n"
            "Description: test package\n",
            encoding="utf-8",
        )
        run(["dpkg-deb", "--build", str(pkg), str(self.debs / "hello-test_1.0_all.deb")])
        self.deb = self.debs / "hello-test_1.0_all.deb"
        self.plan = ResolvePlan(
            requested=["hello-test"],
            entries=[
                PlanEntry(
                    uri="file:/tmp/hello-test_1.0_all.deb",
                    filename=self.deb.name,
                    size=self.deb.stat().st_size,
                    package="hello-test",
                    version="1.0",
                    architecture="all",
                )
            ],
            baseline={"name": "empty", "mode": "full"},
            root={"profile": "test", "architectures": ["amd64"]},
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_and_repo(self):
        data = manifest.build_manifest(self.out, self.plan, [(self.deb, self.plan.entries[0])])
        self.assertEqual(data["totals"]["count"], 1)
        errors, warnings = manifest.verify_manifest(self.out)
        self.assertEqual(errors, [])
        repo.build_repo(self.out)
        self.assertTrue((self.out / "Packages").is_file())
        self.assertTrue((self.out / "Packages.gz").is_file())
        self.assertTrue((self.out / "Release").is_file())
        errors, warnings = repo.verify_repo(self.out)
        self.assertEqual(errors, [], "\n".join(warnings))

    def test_verify_detects_tamper(self):
        manifest.build_manifest(self.out, self.plan, [(self.deb, self.plan.entries[0])])
        with open(self.deb, "ab") as fh:
            fh.write(b"tampered")
        errors, _warnings = manifest.verify_manifest(self.out)
        self.assertTrue(any("大小不符" in item or "SHA256 不符" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
