import unittest

from kylinpkg.arch import arch_key, normalize_arch, normalize_arch_set, parse_arch_list
from kylinpkg.util import KylinPkgError


class ArchTest(unittest.TestCase):
    def test_aliases(self):
        self.assertEqual(normalize_arch("x86_64"), "amd64")
        self.assertEqual(normalize_arch("aarch64"), "arm64")
        self.assertEqual(normalize_arch("sw_64"), "sw64")
        self.assertEqual(normalize_arch("loong64"), "loongarch64")

    def test_parse_list_dedup(self):
        self.assertEqual(parse_arch_list("amd64, i386 amd64"), ["amd64", "i386"])

    def test_all_is_not_target(self):
        self.assertEqual(normalize_arch_set(["all", "amd64"]), ["amd64"])
        with self.assertRaises(KylinPkgError):
            normalize_arch_set(["all"])

    def test_arch_key(self):
        self.assertEqual(arch_key(["amd64", "i386"]), "amd64_i386")

    def test_invalid(self):
        with self.assertRaises(KylinPkgError):
            normalize_arch("../../etc/passwd")


if __name__ == "__main__":
    unittest.main()
