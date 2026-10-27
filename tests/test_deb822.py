# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
import unittest

from kylinpkg import deb822


STATUS = """Package: libc6
Status: install ok installed
Priority: optional
Section: libs
Installed-Size: 100
Maintainer: Kylin <kylin@example.com>
Architecture: amd64
Multi-Arch: same
Source: glibc
Version: 2.31-1
Description: GNU C Library
 continuation line one
 continuation line two

Package: libc6
Status: install ok installed
Architecture: i386
Version: 2.31-1
Description: GNU C Library (i386)

Package: removed-pkg
Status: deinstall ok config-files
Architecture: amd64
Version: 1.0
Description: removed
"""

SOURCES_ONE_LINE = """# comment
deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kylin main restricted universe multiverse
deb [arch=arm64 signed-by=/usr/share/keyrings/foo.gpg trusted=yes] http://example/repo stable main contrib
"""

SOURCES_DEB822 = """Types: deb
URIs: https://packages.microsoft.com/repos/code
Suites: stable
Components: main
Architectures: amd64
Signed-By: /usr/share/keyrings/microsoft.gpg
Enabled: yes

Types: deb
URIs: http://disabled.example/repo
Suites: stable
Components: main
Enabled: no
"""


class Deb822Test(unittest.TestCase):
    def test_parse_status_and_summary(self):
        paragraphs = deb822.parse_status_text(STATUS)
        self.assertEqual(len(paragraphs), 3)
        self.assertEqual(paragraphs[0]["Description"], "GNU C Library\ncontinuation line one\ncontinuation line two")
        summary = deb822.status_summary(paragraphs)
        self.assertEqual(summary["package_count"], 3)
        self.assertEqual(summary["installed_count"], 2)
        self.assertEqual(summary["architectures"], ["amd64", "i386"])
        installed = deb822.installed_version_map(paragraphs)
        self.assertEqual(installed[("libc6", "amd64")], "2.31-1")
        self.assertNotIn(("removed-pkg", "amd64"), installed)

    def test_one_line_sources(self):
        entries = deb822.parse_sources_text(SOURCES_ONE_LINE, "test.list")
        self.assertEqual(len(entries), 2)
        first = entries[0]
        self.assertEqual(first.types, ["deb"])
        self.assertEqual(first.suites, ["10.1-kylin"])
        self.assertEqual(first.components, ["main", "restricted", "universe", "multiverse"])
        self.assertEqual(first.architectures, [])
        second = entries[1]
        self.assertEqual(second.architectures, ["arm64"])
        self.assertEqual(second.signed_by, ["/usr/share/keyrings/foo.gpg"])
        self.assertEqual(second.options.get("trusted"), "yes")

    def test_deb822_sources(self):
        entries = deb822.parse_sources_text(SOURCES_DEB822, "test.sources")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].uri, "https://packages.microsoft.com/repos/code")
        self.assertEqual(entries[0].architectures, ["amd64"])
        self.assertTrue(entries[0].enabled)
        self.assertFalse(entries[1].enabled)
        enabled = [item for item in entries if item.enabled]
        self.assertEqual(len(enabled), 1)

    def test_validate_sources(self):
        entries = deb822.parse_sources_text(SOURCES_ONE_LINE, "test.list")
        entries += deb822.parse_sources_text(SOURCES_ONE_LINE, "test.list")
        warnings = deb822.validate_sources(entries)
        self.assertTrue(any("重复的源" in item for item in warnings))
        self.assertTrue(any("keyring 不存在" in item for item in warnings))

    def test_deb822_with_x_field(self):
        text = "X-Repolib-Name: Example\n" + SOURCES_DEB822
        self.assertTrue(deb822.looks_like_deb822(text))
        entries = deb822.parse_sources_text(text, "x.sources")
        self.assertEqual(len(entries), 2)

    def test_file_uri_missing(self):
        entries = deb822.parse_sources_text("deb [trusted=yes] file:/no/such/dir ./", "x.list")
        warnings = deb822.validate_sources(entries)
        self.assertTrue(any("file: 源路径不存在" in item for item in warnings))


if __name__ == "__main__":
    unittest.main()
