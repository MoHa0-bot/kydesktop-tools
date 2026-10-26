import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from kylinpkg import baseline, bundle, profile
from kylinpkg.config import State

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = PROJECT_ROOT / "collector" / "kylinpkg-collect.sh"


def _collector_available() -> bool:
    if not COLLECTOR.is_file() or shutil.which("bash") is None:
        return False
    if not Path("/var/lib/dpkg/status").is_file():
        return False
    if not Path("/etc/apt").is_dir():
        return False
    sources = list(Path("/etc/apt/sources.list.d").glob("*.list")) if Path("/etc/apt/sources.list.d").is_dir() else []
    return Path("/etc/apt/sources.list").is_file() or bool(sources) or bool(
        list(Path("/etc/apt/sources.list.d").glob("*.sources"))
    )


@unittest.skipUnless(_collector_available(), "需要 bash、dpkg 和 apt 源文件")
class BundleTest(unittest.TestCase):
    def test_collect_inspect_import(self):
        with tempfile.TemporaryDirectory(prefix="kylinpkg-bundle-test-") as tmp:
            tmp_path = Path(tmp)
            out = tmp_path / "out"
            out.mkdir()
            proc = subprocess.run(
                ["bash", str(COLLECTOR), "-o", str(out), "-n", "test-bundle"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            archives = list(out.glob("*.tar.gz"))
            self.assertEqual(len(archives), 1)
            archive = archives[0]
            self.assertGreater(archive.stat().st_size, 0)

            info = bundle.inspect_bundle(archive)
            self.assertGreater(info["baseline"]["installed_count"], 0)
            self.assertGreater(info["sources"], 0)
            self.assertTrue(info["architectures"])

            state = State(tmp_path / "state").ensure()
            result = bundle.import_bundle(
                state,
                archive,
                profile_name="imported-test",
                baseline_name="imported-test-base",
            )
            self.assertEqual(result["profile"], "imported-test")
            self.assertTrue(result["bound"])
            meta = profile.load_profile(state, "imported-test")
            self.assertTrue(meta["architectures"])
            self.assertTrue((state.profile_dir("imported-test") / "profile.json").is_file())
            self.assertTrue((state.baseline_dir("imported-test-base") / "status").is_file())
            bmeta = baseline.load_meta(state, "imported-test-base")
            self.assertGreater(bmeta["installed_count"], 0)

            # 跨架构导入：基线保留但不绑定
            cross = bundle.import_bundle(
                state,
                archive,
                profile_name="imported-arm",
                baseline_name="imported-arm-base",
                architectures=["arm64"],
                bind_baseline=True,
            )
            self.assertFalse(cross["bound"])
            arm_meta = profile.load_profile(state, "imported-arm")
            self.assertEqual(arm_meta["architectures"], ["arm64"])


if __name__ == "__main__":
    unittest.main()
