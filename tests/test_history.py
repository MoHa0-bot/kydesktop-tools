# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import json
import tempfile
import unittest
from pathlib import Path

from kylinpkg import history as history_mod
from kylinpkg.config import State
from kylinpkg.resolver import PlanEntry, ResolvePlan
from kylinpkg.util import KylinPkgError


def _make_plan(
    profile: str = "p1",
    archs=("amd64",),
    baseline: str = "",
    requested=("hello",),
    recommends: bool = True,
    with_deps: bool = True,
) -> ResolvePlan:
    return ResolvePlan(
        requested=list(requested),
        entries=[
            PlanEntry(
                uri="http://example.com/hello.deb",
                filename="hello.deb",
                size=10,
                package="hello",
                version="1.0",
                architecture="amd64",
            )
        ],
        baseline={"name": baseline} if baseline else {},
        root={"profile": profile, "architectures": list(archs)},
        recommends=recommends,
        with_dependencies=with_deps,
    )


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-history-test-")
        self.state = State(Path(self.tmp.name) / "state").ensure()

    def tearDown(self):
        self.tmp.cleanup()

    def test_record_and_list(self):
        plan = _make_plan()
        entry = history_mod.build_entry(
            [plan],
            Path("/tmp/out"),
            force=False,
            make_repo=True,
            status=history_mod.STATUS_OK,
            result={"total": 1, "total_bytes": 10, "reused": False},
        )
        history_mod.record_task(self.state, entry)

        entries = history_mod.list_tasks(self.state)
        self.assertEqual(len(entries), 1)
        stored = entries[0]
        self.assertEqual(stored["profile"], "p1")
        self.assertEqual(stored["architectures"], ["amd64"])
        self.assertIsNone(stored["baseline"])  # 空 dict 表示全量
        self.assertEqual(stored["requested"], ["hello"])
        self.assertTrue(stored["make_repo"])
        self.assertEqual(stored["package_count"], 1)

        # 记录文件存在且是合法 JSON
        raw = json.loads(self.state.history_file.read_text(encoding="utf-8"))
        self.assertEqual(len(raw), 1)

    def test_baseline_name_preserved(self):
        plan = _make_plan(baseline="b1")
        entry = history_mod.build_entry(
            [plan], Path("/tmp/out"), False, False, history_mod.STATUS_OK
        )
        self.assertEqual(entry["baseline"], "b1")

    def test_newest_first_and_cap(self):
        for index in range(history_mod.MAX_ENTRIES + 10):
            plan = _make_plan(requested=("pkg%d" % index,))
            entry = history_mod.build_entry(
                [plan], Path("/tmp/out-%d" % index), False, False, history_mod.STATUS_OK
            )
            history_mod.record_task(self.state, entry)
        entries = history_mod.list_tasks(self.state)
        self.assertEqual(len(entries), history_mod.MAX_ENTRIES)
        # 最新记录在最前
        self.assertEqual(entries[0]["requested"], ["pkg%d" % (history_mod.MAX_ENTRIES + 9)])

    def test_find_by_id_and_prefix(self):
        plan = _make_plan()
        entry = history_mod.build_entry(
            [plan], Path("/tmp/out"), False, False, history_mod.STATUS_FAILED, error="boom"
        )
        history_mod.record_task(self.state, entry)
        task_id = str(entry["id"])

        self.assertEqual(history_mod.find_task(self.state, task_id)["id"], entry["id"])
        # 唯一前缀
        self.assertEqual(
            history_mod.find_task(self.state, task_id[:12])["id"], entry["id"]
        )
        with self.assertRaises(KylinPkgError):
            history_mod.find_task(self.state, "no-such-task")

    def test_remove_and_clear(self):
        plan = _make_plan()
        entry = history_mod.build_entry(
            [plan], Path("/tmp/out"), False, False, history_mod.STATUS_CANCELLED
        )
        history_mod.record_task(self.state, entry)
        removed = history_mod.remove_task(self.state, str(entry["id"]))
        self.assertEqual(removed["id"], entry["id"])
        self.assertEqual(history_mod.list_tasks(self.state), [])

        history_mod.record_task(self.state, entry)
        count = history_mod.clear_tasks(self.state)
        self.assertEqual(count, 1)
        self.assertEqual(history_mod.list_tasks(self.state), [])

    def test_equivalent_command(self):
        plan = _make_plan(
            archs=("amd64", "i386"),
            baseline="b1",
            requested=("hello=1.0",),
            recommends=False,
            with_deps=False,
        )
        entry = history_mod.build_entry(
            [plan],
            Path("/tmp/out dir"),
            force=False,
            make_repo=True,
            status=history_mod.STATUS_OK,
        )
        command = history_mod.equivalent_command(entry)
        self.assertIn("download -p p1", command)
        self.assertIn("-a amd64,i386", command)
        self.assertIn("--baseline b1", command)
        self.assertIn("--no-recommends", command)
        self.assertIn("--no-deps", command)
        self.assertIn("--repo", command)
        self.assertIn("hello=1.0", command)
        self.assertIn("/tmp/out dir", command)

    def test_equivalent_command_full_closure(self):
        plan = _make_plan(baseline=history_mod_baseline_empty())
        entry = history_mod.build_entry(
            [plan], Path("/tmp/out"), False, False, history_mod.STATUS_OK
        )
        self.assertIn("--full", history_mod.equivalent_command(entry))

    def test_redo_requires_profile_and_packages(self):
        entry = {"id": "x", "profile": "", "requested": []}
        with self.assertRaises(KylinPkgError):
            history_mod.redo_task(self.state, entry)
        entry = {"id": "x", "profile": "p1", "requested": [], "output": "/tmp/out"}
        with self.assertRaises(KylinPkgError):
            history_mod.redo_task(self.state, entry)


def history_mod_baseline_empty() -> str:
    from kylinpkg import baseline as baseline_mod

    return baseline_mod.RESERVED_EMPTY


if __name__ == "__main__":
    unittest.main()
