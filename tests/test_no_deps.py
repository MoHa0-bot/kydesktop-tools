# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import gzip
import shutil
import tempfile
import unittest
from pathlib import Path

from kylinpkg import downloader, manifest, profile, resolver
from kylinpkg.config import State
from kylinpkg.util import run


@unittest.skipUnless(
    shutil.which("dpkg-deb") and shutil.which("apt-ftparchive"),
    "需要 dpkg-deb/apt-ftparchive",
)
class NoDepsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-nodeps-test-")
        self.root = Path(self.tmp.name)
        self.repo_dir = self.root / "repo"
        self.debs = self.repo_dir / "debs"
        self.debs.mkdir(parents=True)

        dep = self.root / "dep-pkg"
        (dep / "DEBIAN").mkdir(parents=True)
        (dep / "DEBIAN" / "control").write_text(
            "Package: dep-pkg\n"
            "Version: 1.0\n"
            "Architecture: all\n"
            "Maintainer: Test <test@example.com>\n"
            "Description: dependency package\n",
            encoding="utf-8",
        )
        run(["dpkg-deb", "--build", str(dep), str(self.debs / "dep-pkg_1.0_all.deb")])

        main = self.root / "hello-with-dep"
        (main / "DEBIAN").mkdir(parents=True)
        (main / "DEBIAN" / "control").write_text(
            "Package: hello-with-dep\n"
            "Version: 1.0\n"
            "Architecture: all\n"
            "Depends: dep-pkg\n"
            "Maintainer: Test <test@example.com>\n"
            "Description: package with a dependency\n",
            encoding="utf-8",
        )
        run(
            [
                "dpkg-deb",
                "--build",
                str(main),
                str(self.debs / "hello-with-dep_1.0_all.deb"),
            ]
        )

        proc = run(["apt-ftparchive", "packages", "debs"], cwd=self.repo_dir)
        text = proc.stdout
        (self.repo_dir / "Packages").write_text(text, encoding="utf-8")
        with gzip.open(self.repo_dir / "Packages.gz", "wb") as fh:
            fh.write(text.encode("utf-8"))
        sources = self.repo_dir / "sources.list"
        sources.write_text("deb [trusted=yes] file:%s ./\n" % self.repo_dir, encoding="utf-8")
        self.state = State(self.root / "state").ensure()
        profile.import_profile(
            self.state, "p", sources_files=[sources], architectures=["amd64"]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_dependency_toggle(self):
        with_deps = resolver.resolve_specs(
            self.state, "p", ["hello-with-dep"], with_dependencies=True
        )[0]
        only = resolver.resolve_specs(
            self.state, "p", ["hello-with-dep"], with_dependencies=False
        )[0]
        self.assertTrue(with_deps.with_dependencies)
        self.assertFalse(only.with_dependencies)
        self.assertEqual(
            {entry.package for entry in with_deps.entries},
            {"hello-with-dep", "dep-pkg"},
        )
        self.assertEqual({entry.package for entry in only.entries}, {"hello-with-dep"})

        out_only = self.root / "out-only"
        result = downloader.download(self.state, only, out_only, make_repo=True)
        self.assertEqual(result["total"], 1)
        self.assertEqual(
            [path.name for path in (out_only / "debs").glob("*.deb")],
            ["hello-with-dep_1.0_all.deb"],
        )
        self.assertFalse(result["manifest"]["with_dependencies"])
        errors, warnings = manifest.verify_manifest(out_only)
        self.assertEqual(errors, [], "\n".join(warnings))
        packages_text = (out_only / "Packages").read_text(encoding="utf-8")
        self.assertIn("Package: hello-with-dep\n", packages_text)
        self.assertNotIn("Package: dep-pkg\n", packages_text)

        out_full = self.root / "out-full"
        result = downloader.download(self.state, with_deps, out_full)
        self.assertEqual(result["total"], 2)
        self.assertTrue(result["manifest"]["with_dependencies"])


if __name__ == "__main__":
    unittest.main()
