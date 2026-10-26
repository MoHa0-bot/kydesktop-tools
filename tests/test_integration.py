"""联网集成测试：默认跳过，KYLINPKG_NET_TESTS=1 时运行。

验证：
1) arm64 全量依赖闭包解析；
2) 下载 + manifest + 离线源；
3) 从本地源二次解析（回灌）；
4) amd64 增量模式可复用目标基线；
5) 全程不修改宿主 /etc/apt 与 /var/lib/dpkg。
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
_WATCHED = ["/etc/apt/sources.list", "/var/lib/dpkg/status"]


def _run(state: Path, *args, check: bool = True) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "kylinpkg.cli", "--state", str(state)] + list(args)
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=1800,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            "命令失败：%s\nstdout:\n%s\nstderr:\n%s"
            % (" ".join(cmd), proc.stdout, proc.stderr)
        )
    return proc


def _snapshot():
    data = {}
    for path in _WATCHED:
        p = Path(path)
        data[path] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
    lists = Path("/var/lib/apt/lists")
    data["lists"] = sorted(p.name for p in lists.iterdir()) if lists.is_dir() else []
    return data


def _up_to_date_package():
    """找一个宿主上已安装且没有可升级版本的包，用于验证增量零下载。"""
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    for name in ("coreutils", "bash", "grep", "sed", "tar", "gzip"):
        try:
            proc = subprocess.run(
                ["apt-cache", "policy", name],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                env=env,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        installed = candidate = ""
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("Installed:"):
                installed = line.split(":", 1)[1].strip()
            elif line.startswith("Candidate:"):
                candidate = line.split(":", 1)[1].strip()
        if installed and installed == candidate and installed != "(none)":
            return name
    return None


@unittest.skipUnless(
    os.environ.get("KYLINPKG_NET_TESTS") == "1",
    "联网集成测试未启用（设置 KYLINPKG_NET_TESTS=1）",
)
class NetworkIntegrationTest(unittest.TestCase):
    def test_full_closure_repo_roundtrip_and_delta(self):
        before = _snapshot()
        with tempfile.TemporaryDirectory(prefix="kylinpkg-net-test-") as tmp:
            tmp_path = Path(tmp)
            state = tmp_path / "state"
            out = tmp_path / "out"

            _run(state, "baseline", "import", "host", "--from-system")
            _run(
                state,
                "profile",
                "import",
                "sp1-arm64",
                "--from-system",
                "--arch",
                "arm64",
            )

            proc = _run(
                state, "resolve", "-p", "sp1-arm64", "-a", "arm64", "--full", "--json", "zlib1g"
            )
            plan = json.loads(proc.stdout)
            names = {item["package"] for item in plan["packages"]}
            self.assertIn("zlib1g", names)
            self.assertIn("libc6", names)
            self.assertGreaterEqual(len(names), 5)
            for item in plan["packages"]:
                self.assertIn(item["architecture"], ("arm64", "all"))
            self.assertEqual(plan["baseline"]["mode"], "full")

            _run(
                state,
                "download",
                "-p",
                "sp1-arm64",
                "-a",
                "arm64",
                "--full",
                "-o",
                str(out),
                "--repo",
                "--quiet",
                "zlib1g",
            )
            debs = list((out / "debs").glob("*.deb"))
            self.assertEqual(len(debs), len(names))
            self.assertTrue((out / "manifest.json").is_file())
            self.assertTrue((out / "Packages").is_file())
            _run(state, "verify", str(out))

            # 把本地源当普通源导入，验证回灌
            _run(
                state,
                "profile",
                "import",
                "local-arm64",
                "--sources-file",
                str(out / "sources.list"),
                "--arch",
                "arm64",
            )
            proc = _run(
                state, "resolve", "-p", "local-arm64", "-a", "arm64", "--full", "--json", "zlib1g"
            )
            local_plan = json.loads(proc.stdout)
            local_names = {item["package"] for item in local_plan["packages"]}
            self.assertEqual(local_names, names)

            # 增量模式：已安装且无升级的包不应出现在下载计划里
            _run(
                state,
                "profile",
                "import",
                "sp1-x86",
                "--from-system",
                "--arch",
                "amd64,i386",
                "--baseline",
                "host",
            )
            installed_pkg = _up_to_date_package()
            if installed_pkg:
                proc = _run(state, "resolve", "-p", "sp1-x86", "--json", installed_pkg)
                delta_plan = json.loads(proc.stdout)
                self.assertEqual(delta_plan["baseline"]["mode"], "delta")
                self.assertNotIn(
                    installed_pkg, {item["package"] for item in delta_plan["packages"]}
                )

        self.assertEqual(_snapshot(), before, "宿主 apt/dpkg 状态被修改")


if __name__ == "__main__":
    unittest.main()
