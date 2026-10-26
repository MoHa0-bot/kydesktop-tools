import unittest

from kylinpkg.resolver import PlanEntry, _annotate_baseline, _requested_name, apt_error_hint, parse_print_uris


SAMPLE = """\
正在读取软件包列表...
需要下载 2,937 kB 的归档。
'http://archive.kylinos.cn/kylin/KYLIN-ALL/pool/main/z/zlib/zlib1g_1%3a1.2.11_arm64.deb' zlib1g_1%3a1.2.11_arm64.deb 91814 MD5Sum:964b4be5d16899c2074c7d2e342545bd
'file:/tmp/repo/./hello_1.0_all.deb' hello_1.0_all.deb 1234
"""


class ResolverTest(unittest.TestCase):
    def test_parse_print_uris(self):
        entries = parse_print_uris(SAMPLE)
        self.assertEqual(len(entries), 2)
        first = entries[0]
        self.assertEqual(first.package, "zlib1g")
        self.assertEqual(first.version, "1:1.2.11")
        self.assertEqual(first.architecture, "arm64")
        self.assertEqual(first.size, 91814)
        self.assertEqual(first.hash_type, "MD5Sum")
        self.assertEqual(first.source, "archive.kylinos.cn")
        second = entries[1]
        self.assertEqual(second.package, "hello")
        self.assertEqual(second.architecture, "all")
        self.assertEqual(second.source, "file")
        self.assertEqual(second.hash_type, "")

    def test_baseline_annotation(self):
        entries = [
            PlanEntry(uri="x", filename="zlib1g_1%3a1.2.11_arm64.deb", size=1,
                      package="zlib1g", version="1:1.2.11", architecture="arm64"),
            PlanEntry(uri="x", filename="hello_1.0_all.deb", size=1,
                      package="hello", version="1.0", architecture="all"),
        ]
        _annotate_baseline(entries, {("zlib1g", "arm64"): "1:1.2.11", ("hello", "all"): "0.9"})
        self.assertEqual(entries[0].baseline_state, "assumed")
        self.assertEqual(entries[1].baseline_state, "upgrade")

    def test_requested_name(self):
        self.assertEqual(_requested_name("zlib1g:arm64"), "zlib1g")
        self.assertEqual(_requested_name("zlib1g=1:1.2"), "zlib1g")
        self.assertEqual(_requested_name("zlib1g"), "zlib1g")

    def test_hint(self):
        self.assertIn("基础 suite", apt_error_hint("libc6 : 依赖: libgcc-s1 但无法安装它"))
        self.assertIn("签名密钥", apt_error_hint("NO_PUBKEY F49EC40DDCE76770"))


if __name__ == "__main__":
    unittest.main()
