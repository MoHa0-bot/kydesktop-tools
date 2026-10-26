import gzip
import shutil
import tempfile
import unittest
from pathlib import Path

from kylinpkg import downloader, manifest, profile, resolver
from kylinpkg.config import State
from kylinpkg.util import run


class PolicyParseTest(unittest.TestCase):
    def test_parse_policy_output(self):
        output = """pkg:
  Installed: 1.0
  Candidate: 2.0
  Version table:
 *** 1.0 100
        100 /var/lib/dpkg/status
     2.0 600
        600 http://example.invalid/repo suite/main amd64 Packages
     1.0 500
        500 http://example.invalid/repo suite/main amd64 Packages
"""
        data = resolver.parse_policy_output(output, "pkg")
        self.assertEqual(data["installed"], "1.0")
        self.assertEqual(data["candidate"], "2.0")
        versions = {item["version"]: item for item in data["versions"]}
        self.assertTrue(versions["1.0"]["installed"])
        self.assertFalse(versions["1.0"]["candidate"])
        self.assertTrue(versions["1.0"]["downloadable"])
        self.assertEqual(versions["1.0"]["architectures"], ["amd64"])
        self.assertTrue(versions["2.0"]["candidate"])
        self.assertFalse(versions["2.0"]["installed"])


@unittest.skipUnless(
    shutil.which("dpkg-deb") and shutil.which("apt-ftparchive"),
    "需要 dpkg-deb/apt-ftparchive",
)
class MultiVersionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-versions-test-")
        self.root = Path(self.tmp.name)
        self.repo_dir = self.root / "repo"
        self.debs = self.repo_dir / "debs"
        self.debs.mkdir(parents=True)
        for version in ("1.0", "2.0"):
            pkg = self.root / ("pkg-" + version)
            (pkg / "DEBIAN").mkdir(parents=True)
            (pkg / "DEBIAN" / "control").write_text(
                "Package: hello-versions\n"
                "Version: %s\n"
                "Architecture: all\n"
                "Maintainer: Test <test@example.com>\n"
                "Description: version test %s\n" % (version, version),
                encoding="utf-8",
            )
            run(
                [
                    "dpkg-deb",
                    "--build",
                    str(pkg),
                    str(self.debs / ("hello-versions_%s_all.deb" % version)),
                ]
            )
        proc = run(["apt-ftparchive", "packages", "debs"], cwd=self.repo_dir)
        packages_text = proc.stdout
        (self.repo_dir / "Packages").write_text(packages_text, encoding="utf-8")
        with gzip.open(self.repo_dir / "Packages.gz", "wb") as fh:
            fh.write(packages_text.encode("utf-8"))
        sources = self.repo_dir / "sources.list"
        sources.write_text("deb [trusted=yes] file:%s ./\n" % self.repo_dir, encoding="utf-8")
        self.sources = sources
        self.state = State(self.root / "state").ensure()
        profile.import_profile(
            self.state, "p", sources_files=[sources], architectures=["amd64"]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_and_multi_download(self):
        data = resolver.list_versions(self.state, "p", "hello-versions")
        versions = [item["version"] for item in data["versions"]]
        self.assertEqual(set(versions), {"1.0", "2.0"})
        self.assertEqual(data["candidate"], "2.0")
        self.assertTrue(all(item["downloadable"] for item in data["versions"]))

        plans = resolver.resolve_specs(
            self.state, "p", ["hello-versions=1.0", "hello-versions=2.0"]
        )
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].requested, ["hello-versions=1.0"])
        self.assertEqual(plans[1].requested, ["hello-versions=2.0"])

        out = self.root / "out"
        result = downloader.download_plans(
            self.state, plans, out, make_repo=True
        )
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["plans"], 2)
        packages = {
            (item["package"], item["version"])
            for item in result["manifest"]["packages"]
        }
        self.assertEqual(
            packages, {("hello-versions", "1.0"), ("hello-versions", "2.0")}
        )
        self.assertEqual(len(result["manifest"]["version_plans"]), 2)
        errors, warnings = manifest.verify_manifest(out)
        self.assertEqual(errors, [], "\n".join(warnings))
        packages_text = (out / "Packages").read_text(encoding="utf-8")
        self.assertIn("hello-versions_1.0_all.deb", packages_text)
        self.assertIn("hello-versions_2.0_all.deb", packages_text)

        # 从生成的离线源再读一次，确认两个版本都可被 apt 看到
        local_state = State(self.root / "state-local").ensure()
        profile.import_profile(
            local_state,
            "local",
            sources_files=[out / "sources.list"],
            architectures=["amd64"],
        )
        local_data = resolver.list_versions(local_state, "local", "hello-versions")
        self.assertEqual(
            {item["version"] for item in local_data["versions"]}, {"1.0", "2.0"}
        )

        reused = downloader.download_plans(self.state, plans, out, make_repo=True)
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["total"], 2)

    def test_single_spec_uses_one_plan(self):
        plans = resolver.resolve_specs(self.state, "p", ["hello-versions=1.0"])
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].requested, ["hello-versions=1.0"])


if __name__ == "__main__":
    unittest.main()
