"""dpkg 架构名归一化与检测。"""

from __future__ import annotations

import re
from typing import Iterable, List

from .util import KylinPkgError, run

_ALIASES = {
    "x86_64": "amd64",
    "x86-64": "amd64",
    "x64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "armv7l": "armhf",
    "armhf": "armhf",
    "i386": "i386",
    "i486": "i386",
    "i586": "i386",
    "i686": "i386",
    "x86": "i386",
    "loongarch64": "loongarch64",
    "loong64": "loongarch64",
    "loongarch": "loongarch64",
    "mips64el": "mips64el",
    "mips64": "mips64el",
    "sw_64": "sw64",
    "sw64": "sw64",
    "ppc64el": "ppc64el",
    "s390x": "s390x",
    "riscv64": "riscv64",
}

_ARCH_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def normalize_arch(value: str) -> str:
    key = value.strip().lower()
    arch = _ALIASES.get(key, key)
    if not _ARCH_RE.match(arch):
        raise KylinPkgError("架构名不合法：%r" % value)
    return arch


def parse_arch_list(value: str) -> List[str]:
    if not value:
        return []
    parts = re.split(r"[,\s]+", value.strip())
    out: List[str] = []
    for part in parts:
        if not part:
            continue
        arch = normalize_arch(part)
        if arch not in out:
            out.append(arch)
    return out


def detect_system_archs() -> List[str]:
    native = run(["dpkg", "--print-architecture"]).stdout.strip()
    foreign = run(["dpkg", "--print-foreign-architectures"], check=False).stdout.split()
    out: List[str] = []
    for item in [native] + foreign:
        if not item:
            continue
        arch = normalize_arch(item)
        if arch not in out:
            out.append(arch)
    return out


def normalize_arch_set(archs: Iterable[str]) -> List[str]:
    out: List[str] = []
    for item in archs:
        if not item:
            continue
        arch = normalize_arch(item)
        if arch == "all":
            continue
        if arch not in out:
            out.append(arch)
    if not out:
        raise KylinPkgError("架构列表为空（all 不能作为目标架构）")
    return out


def arch_key(archs: Iterable[str]) -> str:
    return "_".join(normalize_arch_set(archs))


def real_archs(archs: Iterable[str]) -> List[str]:
    """去掉 dpkg 的 all 伪架构。"""
    out = []
    for item in archs:
        if item and item != "all" and item not in out:
            out.append(item)
    return out
