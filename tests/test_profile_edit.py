import tempfile
import unittest
from pathlib import Path

from kylinpkg import profile
from kylinpkg.config import State
from kylinpkg.util import KylinPkgError


class ProfileEditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kylinpkg-edit-test-")
        self.root = Path(self.tmp.name)
        self.state = State(self.root / "state").ensure()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "dummy.deb").write_bytes(b"x")
        self.sources = self.root / "sources.list"
        self.sources.write_text(
            "deb [trusted=yes] file:%s ./\n" % self.repo, encoding="utf-8"
        )
        profile.import_profile(
            self.state, "p1", sources_files=[self.sources], architectures=["amd64"]
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_view_and_edit_sources(self):
        files = profile.profile_files(self.state, "p1")
        by_path = {item["path"]: item for item in files}
        self.assertTrue(by_path["sources.list"]["editable"])
        self.assertFalse(by_path["keyrings/trusted.gpg"]["editable"])
        content = profile.read_profile_file(self.state, "p1", "sources.list")
        self.assertIn("file:", content)
        before = profile.fingerprint(self.state, "p1")

        new_content = content + "\n# edited\n"
        meta = profile.write_profile_file(self.state, "p1", "sources.list", new_content)
        self.assertNotEqual(before, profile.fingerprint(self.state, "p1"))
        self.assertIn("# edited", profile.read_profile_file(self.state, "p1", "sources.list"))

        # 追加第二条源，验证 meta 的源条数
        extra = self.root / "extra"
        extra.mkdir()
        new_content += "deb [trusted=yes] file:%s ./\n" % extra
        meta = profile.write_profile_file(self.state, "p1", "sources.list", new_content)
        self.assertEqual(len(meta["sources_summary"]), 2)

    def test_invalid_source_reverts(self):
        original = profile.read_profile_file(self.state, "p1", "sources.list")
        with self.assertRaises(KylinPkgError):
            profile.write_profile_file(self.state, "p1", "sources.list", "garbage line\n")
        self.assertEqual(
            profile.read_profile_file(self.state, "p1", "sources.list"), original
        )

    def test_delete_rules(self):
        with self.assertRaises(KylinPkgError):
            profile.delete_profile_file(self.state, "p1", "sources.list")

        extra = self.root / "extra2"
        extra.mkdir()
        extra_content = "deb [trusted=yes] file:%s ./\n" % extra
        profile.write_profile_file(
            self.state, "p1", "sources.list.d/extra.list", extra_content
        )
        meta = profile.delete_profile_file(self.state, "p1", "sources.list")
        self.assertEqual(
            profile.read_profile_file(self.state, "p1", "sources.list"), ""
        )
        with self.assertRaises(KylinPkgError):
            profile.delete_profile_file(self.state, "p1", "sources.list.d/extra.list")

    def test_preferences_and_auth(self):
        profile.write_profile_file(
            self.state, "p1", "preferences", "Package: *\nPin: release a=stable\nPin-Priority: 500\n"
        )
        self.assertIn(
            "Pin-Priority",
            profile.read_profile_file(self.state, "p1", "preferences"),
        )
        meta = profile.write_profile_file(
            self.state,
            "p1",
            "auth.conf",
            "machine example.com login demo password secret\n",
        )
        self.assertTrue(meta["with_auth"])
        self.assertTrue(meta["warnings"])
        meta = profile.delete_profile_file(self.state, "p1", "auth.conf")
        self.assertFalse(meta["with_auth"])

    def test_path_traversal_and_keyring_rejected(self):
        with self.assertRaises(KylinPkgError):
            profile.write_profile_file(self.state, "p1", "../evil.list", "x")
        with self.assertRaises(KylinPkgError):
            profile.read_profile_file(self.state, "p1", "keyrings/trusted.gpg")
        with self.assertRaises(KylinPkgError):
            profile.read_profile_file(self.state, "p1", "profile.json")


if __name__ == "__main__":
    unittest.main()
