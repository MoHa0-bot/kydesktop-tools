# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""baseline 打开查询：包记录解析、过滤、内置回退与 CLI 输出。"""
import argparse
import contextlib
import gzip
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from kylinpkg import baseline, cli
from kylinpkg.config import State
from kylinpkg.util import KylinPkgError


STATUS = """Package: bash
Status: install ok installed
Priority: required
Architecture: amd64
Version: 5.0-6kylin1
Depends: libc6 (>= 2.25), libtinfo6 (>= 6)
Description: GNU Bourne Again SHell
 Bash is the GNU Project's shell.
 .
 Bourne Again SHell
Conffiles:
 /etc/bash.bashrc 47b92b3a04f9d0a6a63a6cf4de00f8d1f1

Package: bash
Status: install ok installed
Architecture: i386
Version: 5.0-6kylin1
Depends: libc6 (>= 2.25)

Package: libfoo
Status: deinstall ok config-files
Architecture: all
Version: 1.2-3
Conffiles:
 /etc/libfoo.conf 47b92b3a04f9d0a6a63a6cf4de00f8d1f1
Description: a library used by bash-tools

Package: bash-doc
Status: install ok installed
Architecture: all
Version: 5.0-6kylin1
Description: documentation for bash
"""


class BaselineQueryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-query-test-")
        self.root = Path(self.tmp.name)
        self.state = State(self.root / "state").ensure()
        self.status_path = self.root / "status"
        self.status_path.write_text(STATUS, encoding="utf-8")
        baseline.import_baseline(self.state, "b1", status_file=self.status_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_open_keeps_raw_paragraph_and_fields(self):
        data = baseline.open_baseline(self.state, "b1")
        self.assertEqual(data["source"], "state")
        self.assertEqual(len(data["records"]), 4)
        records = data["records"]
        first = records[0]
        self.assertEqual(first["package"], "bash")
        self.assertEqual(first["architecture"], "amd64")
        self.assertTrue(first["installed"])
        self.assertIn("libtinfo6 (>= 6)", first["fields"]["Depends"])
        self.assertIn(" .", first["raw"])
        self.assertIn("/etc/bash.bashrc", first["raw"])
        self.assertIn("Conffiles:", first["raw"])
        # 原始段落逐字保留（不含段落间空行）
        self.assertEqual(first["raw"], STATUS.split("\n\n")[0])
        self.assertFalse(records[2]["installed"])
        self.assertEqual(records[2]["status"], "deinstall ok config-files")

    def test_filter_keyword_exact_installed_arch(self):
        records = baseline.open_baseline(self.state, "b1")["records"]
        self.assertEqual(len(baseline.filter_records(records)), 4)
        self.assertEqual(
            [rec["package"] for rec in baseline.filter_records(records, "BASH")],
            ["bash", "bash", "bash-doc"],
        )
        self.assertEqual(
            [rec["architecture"] for rec in baseline.filter_records(records, "bash", exact=True)],
            ["amd64", "i386"],
        )
        self.assertEqual(
            [rec["package"] for rec in baseline.filter_records(records, installed_only=True)],
            ["bash", "bash", "bash-doc"],
        )
        self.assertEqual(
            [rec["architecture"] for rec in baseline.filter_records(records, arch="i386")],
            ["i386"],
        )
        # 默认只搜包名/版本/架构/状态，搜不到 Depends 与 Description 里的文本
        self.assertEqual(baseline.filter_records(records, "libtinfo6"), [])
        self.assertEqual(
            [rec["package"] for rec in baseline.filter_records(records, "libtinfo6", all_fields=True)],
            ["bash"],
        )
        self.assertEqual(
            [rec["package"] for rec in baseline.filter_records(records, "a library used", all_fields=True)],
            ["libfoo"],
        )

    def test_query_result_counters(self):
        result = baseline.query_baseline(self.state, "b1", keyword="bash", exact=True)
        self.assertEqual((result["total"], result["matched"]), (4, 2))
        self.assertEqual([rec["architecture"] for rec in result["records"]], ["amd64", "i386"])
        empty = baseline.query_baseline(self.state, "empty")
        self.assertEqual((empty["source"], empty["total"], empty["matched"]), ("empty", 0, 0))

    def test_builtin_fallback_and_missing(self):
        builtin_root = self.root / "builtins"
        entry = builtin_root / "builtin-b1"
        entry.mkdir(parents=True)
        with gzip.open(entry / "status.gz", "wb") as fh:
            fh.write(STATUS.encode("utf-8"))
        (entry / "meta.json").write_text(
            json.dumps(
                {
                    "name": "builtin-b1",
                    "installed_count": 3,
                    "architectures": ["amd64", "i386"],
                    "kernel_version": "5.4.18",
                    "status_sha256": "abc",
                }
            ),
            encoding="utf-8",
        )
        with unittest.mock.patch.object(baseline, "BUILTIN_BASELINES_DIR", builtin_root):
            result = baseline.query_baseline(self.state, "builtin-b1", keyword="libfoo")
            self.assertEqual(result["source"], "builtin")
            self.assertEqual(result["matched"], 1)
            self.assertEqual(result["records"][0]["fields"]["Version"], "1.2-3")
            # state 中出现同名基线时优先 state；--builtin 强制读内置数据
            other = self.root / "status-other"
            other.write_text(
                "Package: only-in-state\nStatus: install ok installed\n"
                "Architecture: amd64\nVersion: 9\n",
                encoding="utf-8",
            )
            baseline.import_baseline(self.state, "builtin-b1", status_file=other)
            state_result = baseline.query_baseline(
                self.state, "builtin-b1", keyword="libfoo"
            )
            self.assertEqual((state_result["source"], state_result["matched"]), ("state", 0))
            forced = baseline.query_baseline(
                self.state, "builtin-b1", keyword="libfoo", use_builtin=True
            )
            self.assertEqual((forced["source"], forced["matched"]), ("builtin", 1))
        with self.assertRaises(KylinPkgError) as ctx:
            baseline.query_baseline(self.state, "not-exist")
        self.assertIn("baseline 不存在", str(ctx.exception))

    def _args(self, **overrides):
        values = dict(
            name="b1", keyword="", installed=False, arch="", exact=False,
            all_fields=False, raw=False, json=False, limit=None, use_builtin=False,
        )
        values.update(overrides)
        return argparse.Namespace(**values)

    def _run(self, **overrides):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.cmd_baseline_query(self._args(**overrides), self.state)
        self.assertEqual(code, 0)
        return out.getvalue()

    def test_cli_table_raw_limit_and_json(self):
        table = self._run(keyword="bash", exact=True, limit=1)
        self.assertIn("基线：b1", table)
        self.assertIn("5.0-6kylin1", table)
        self.assertNotIn("libfoo", table)
        self.assertIn("匹配 2 条，已显示 1 条", table)
        self.assertIn("用 --limit 0 显示全部", table)
        raw = self._run(keyword="libfoo", raw=True)
        self.assertIn("Conffiles:", raw)
        self.assertIn("/etc/libfoo.conf", raw)
        payload = json.loads(self._run(keyword="bash", exact=True, json=True))
        self.assertEqual(payload["total"], 4)
        self.assertEqual(payload["matched"], 2)
        self.assertEqual(payload["shown"], 2)
        self.assertEqual(payload["records"][0]["fields"]["Depends"], "libc6 (>= 2.25), libtinfo6 (>= 6)")
        self.assertEqual(payload["source"], "state")

    def test_cli_installed_arch_all_fields(self):
        out = self._run(installed=True, arch="all", limit=0)
        self.assertIn("bash-doc", out)
        self.assertNotIn("libfoo", out)
        out = self._run(keyword="libtinfo6", all_fields=True, limit=0)
        self.assertIn("bash", out)
        with self.assertRaises(KylinPkgError):
            self._run(limit=-1)

    def test_parser_wiring(self):
        args = cli.build_parser().parse_args(
            ["baseline", "query", "b1", "libfoo", "--exact", "--raw", "--limit", "0"]
        )
        self.assertIs(args.func, cli.cmd_baseline_query)
        self.assertEqual((args.name, args.keyword, args.limit), ("b1", "libfoo", 0))
        self.assertTrue(args.exact)
        self.assertTrue(args.raw)


if __name__ == "__main__":
    unittest.main()
