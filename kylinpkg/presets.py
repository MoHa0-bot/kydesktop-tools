# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""内置 apt 源预设。

数据来自用户提供的《银河麒麟桌面外网源.xls》（在线推送使用的正式源，外网），
共 40 条产线配置：XC 通用版、HWE 硬件启用栈、Wayland（麒麟 990 / 9006C / 9000C /
盘古 M900 / 华为 Pangux·Flemingx·Panguy·Panguw）。其中 11 条附带的
`/etc/apt/preferences.d/kylin.pref` 优先级（Pin-Priority）也一并收入，`preferences`
字段会在创建 profile 时写进 `preferences.d/kylin.pref`。

另外保留 2 条 V10 非 SP1（10.0 系）历史预设——新的外网源清单不再收录它们，
仅用于老机器。

2026-10 起新增 3 条「现场实测」预设（`*`*-实机`），数据来自用
`collector/kylinpkg-collect.sh` 在 7 台现场主机（均为 XC 通用版）收集的配置包：
sp1-2203 / 2303 / 2403 / 2503 各 x86、arm64 一台。已去重：
2503 的 x86 / arm64、2303 的 x86 / arm64 配置一致各合并为一条；
2403 的 x86 / arm64 与官方清单 `xc-2403u2` 逐行一致不再单列。现场机器与官方清单的差异（如实收录）：
2203 / 2303 的 archive2 走 `DEB/KYLIN_DEB` 入口且无 bugfix-limit suite；
2503 实际使用 `10.1-2503-bugfix` suite、Pin-Priority 为 550 一档。

预设只是模板：创建成 profile 后可以自由查看、编辑。
`docs/kylin-desktop-sources.md` 保存原始清单，`tests/test_presets.py` 会校验
预设源行与清单一致。

总计：45 个预设 / 218 条 `deb` 源行 / 12 条带优先级配置。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .util import KylinPkgError

SOURCE_DOC = "银河麒麟桌面外网源.xls（docs/kylin-desktop-sources.md）"

_ARCH = "http://archive.kylinos.cn/kylin/KYLIN-ALL"
_ARCHS = "https://archive.kylinos.cn/kylin/KYLIN-ALL"
_PARTNER = "http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1"
_KIRIN9A0S = "https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0"
_KIRIN9A0 = "http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0"
_KIRIN990 = "http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin990/custom/partner/10_1-kirin990"
_DEB = "http://archive2.kylinos.cn/DEB/KYLIN_DEB"


@dataclass(frozen=True)
class SourcePreset:
    id: str
    name: str
    group: str
    description: str
    sources: Tuple[str, ...]
    preferences: Tuple[str, ...] = ()
    architectures: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()


def _p(
    preset_id: str,
    name: str,
    group: str,
    description: str,
    sources: Sequence[str],
    preferences: Sequence[str] = (),
    architectures: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> SourcePreset:
    return SourcePreset(
        id=preset_id,
        name=name,
        group=group,
        description=description,
        sources=tuple(sources),
        preferences=tuple(preferences),
        architectures=tuple(architectures),
        notes=tuple(notes),
    )


PRESETS: Tuple[SourcePreset, ...] = (
    # ------------------------------------------------------------
    # XC 产线（通用版）
    _p(
        "xc-2107",
        "V10 SP1 XC-2107",
        "XC 产线（通用版）",
        "XC 2107 通用版外网正式源",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2107-updates main" % _ARCH,
            "deb %s 10.1-2107-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
    ),
    _p(
        "xc-2203",
        "V10 SP1 XC-2203",
        "XC 产线（通用版）",
        "XC 2203 通用版外网正式源",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2203-updates-preview main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2203-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
    ),
    _p(
        "xc-2303",
        "V10 SP1 XC-2303",
        "XC 产线（通用版）",
        "XC 2303 通用版外网正式源",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
    ),
    _p(
        "xc-2303u2",
        "V10 SP1 XC-2303-update2",
        "XC 产线（通用版）",
        "XC 2303 update2 外网正式源",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update3 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update2-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
    ),
    _p(
        "xc-2403u2",
        "V10 SP1 XC-2403-update2",
        "XC 产线（通用版）",
        "XC 2403 update2 外网正式源",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-update2 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
        notes=(
            "2026-10 现场实测（sp1-2403-x86 与 sp1-2403-arm64 收集包）的源配置与本预设逐行一致。",
        )
    ),
    _p(
        "xc-2503",
        "V10 SP1 XC-2503",
        "XC 产线（通用版）",
        "XC 2503 外网正式源（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2503-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("amd64", "arm64", "loongarch64", "mips64el"),
        notes=("该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",)
    ),
    # ------------------------------------------------------------
    # XC 产线（通用版）· 现场实测（主机收集）
    _p(
        "xc-2203-实机",
        "V10 SP1 XC-2203（实机）",
        "XC 产线（通用版）",
        "XC 2203 现场主机实测源（源管理器标准配置）",
        [
            "deb %s V10-SP1 main all" % _DEB,
            "deb %s 10.1-2203-updates main restricted universe multiverse" % _ARCH,
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
        ],
        architectures=("amd64",),
        notes=(
            "数据来自 2026-10 现场主机收集包（sp1-2203-x86）。",
            "与官方清单 xc-2203 的差异：无 bugfix-limit / updates-preview suite；archive2 走 DEB/KYLIN_DEB 入口而非 PART partner 源。",
            "现场机器 preferences.d 中 archive2.pref 与 archive3.pref 内容完全重复（源管理器自动生成），未收录进预设。",
        )
    ),
    _p(
        "xc-2303-实机",
        "V10 SP1 XC-2303（实机）",
        "XC 产线（通用版）",
        "XC 2303 现场主机实测源（源管理器标准配置）",
        [
            "deb %s 10.1-2303-updates main universe multiverse restricted" % _ARCH,
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s V10-SP1 main all" % _DEB,
        ],
        architectures=("amd64", "arm64"),
        notes=(
            "数据来自 2026-10 现场主机收集包（sp1-2303-x86 与 sp1-2303-arm64），两台主机配置一致，合并为一条预设。",
            "与官方清单 xc-2303 的差异：无 bugfix-limit suite；archive2 走 DEB/KYLIN_DEB 入口而非 PART partner 源。",
            "现场机器另有单机本地源 /etc/apt/sources.list.d/kylin-apps-third.list（deb [trusted=yes] file:///opt/apps-third/ ./），未收录进预设。",
        )
    ),
    _p(
        "xc-2503-实机",
        "V10 SP1 XC-2503（实机）",
        "XC 产线（通用版）",
        "XC 2503 现场主机实测源（x86 / arm64 配置一致，含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2503-bugfix main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503",
            "Pin-Priority: 550",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-bugfix",
            "Pin-Priority: 550",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 550",
        ),
        architectures=("amd64", "arm64"),
        notes=(
            "数据来自 2026-10 现场主机收集包（sp1-2503-x86 与 sp1-2503-arm64），两台主机配置一致，合并为一条预设。",
            "现场机器实际使用 10.1-2503-bugfix suite（官方清单写 10.1-2503-bugfix-limit），Pin-Priority 为 550 一档（官方清单为 600），以现场实测为准。",
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
        )
    ),
    # ---------------------------------------------------------------
    # HWE 硬件启用栈
    _p(
        "hwe-2107",
        "V10 SP1 HWE-2107",
        "HWE 硬件启用栈",
        "HWE 2107 硬件启用栈",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-hwe main" % _ARCH,
            "deb %s 10.1-2107-hwe-updates main" % _ARCH,
            "deb %s 10.1-2107-hwe-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-2203",
        "V10 SP1 HWE-2203",
        "HWE 硬件启用栈",
        "HWE 2203 硬件启用栈",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2203-hwe-updates-preview main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2203-hwe-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-2303",
        "V10 SP1 HWE-2303",
        "HWE 硬件启用栈",
        "HWE 2303 硬件启用栈",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-hwe-updates main universe multiverse restricted" % _ARCH,
            "deb %s 10.1-2303-hwe-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-2303u2",
        "V10 SP1 HWE-2303-update2",
        "HWE 硬件启用栈",
        "HWE 2303 update2 硬件启用栈",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update3 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update2-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-hwe-update3 main" % _ARCH,
            "deb %s 10.1-2303-hwe-update2-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-2403u2",
        "V10 SP1 HWE-2403-update2",
        "HWE 硬件启用栈",
        "HWE 2403 update2 硬件启用栈",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-update2 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-hwe-update2 main universe multiverse restricted" % _ARCH,
            "deb %s 10.1-2403-hwe-bugfix-limit main" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-2503",
        "V10 SP1 HWE-2503",
        "HWE 硬件启用栈",
        "HWE 2503（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2503-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
            "deb %s 10.1-2503-hwe-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-hwe main" % _ARCH,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-hwe",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-hwe-bugfix-limit",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("amd64", "arm64"),
        notes=("该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",)
    ),
    _p(
        "hwe-pp-2303",
        "V10 SP1 HWE-PP-2303",
        "HWE 硬件启用栈",
        "HWE-PP 2303 分支",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-hwe-pp-updates main" % _ARCH,
            "deb %s 10.1-2303-hwe-pp-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-pp-2303u2",
        "V10 SP1 HWE-PP-2303-update2",
        "HWE 硬件启用栈",
        "HWE-PP 2303 update2 分支",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update3 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-update2-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-hwe-pp-update3 main" % _ARCH,
            "deb %s 10.1-2303-hwe-pp-update2-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-pp-2403u2",
        "V10 SP1 HWE-PP-2403-update2",
        "HWE 硬件启用栈",
        "HWE-PP 2403 update2 分支",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-update2 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2403-hwe-pp-update2 main" % _ARCH,
            "deb %s 10.1-2403-hwe-pp-bugfix-limit main" % _ARCH,
            "deb %s default all" % _PARTNER,
        ],
        architectures=("amd64", "arm64"),
    ),
    _p(
        "hwe-pp-2503",
        "V10 SP1 HWE-PP-2503",
        "HWE 硬件启用栈",
        "HWE-PP 2503（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2503-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _PARTNER,
            "deb %s 10.1-2503-hwe-pp-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-hwe-pp main" % _ARCH,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-hwe-pp",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-hwe-pp-bugfix-limit",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("amd64", "arm64"),
        notes=("该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",)
    ),
    # --------------------------------------------------------------
    # Wayland · 麒麟 990
    _p(
        "wl-2107-990",
        "Wayland 2107 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2107 Kirin 990",
        [
            "deb %s 10.1-pv main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2107-wayland-kirin990-bugfix-limit main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _KIRIN990,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2203-990",
        "Wayland 2203 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2203 Kirin 990",
        [
            "deb %s 10.1-wayland-2203-updates main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin990-feature main" % _ARCHS,
            "deb %s 10.1-2203-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2203-wayland-kirin990-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2303-990",
        "Wayland 2303 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2303 Kirin 990",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-wayland-2303-updates main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin990-2303-feature main" % _ARCHS,
            "deb %s 10.1-2303-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-kirin990-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2303u2-990",
        "Wayland 2303-update2 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2303 update2 Kirin 990",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update3 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update3-kirin990 main" % _ARCHS,
            "deb %s 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update2-kirin990-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2403u2-990",
        "Wayland 2403-update2 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2403 update2 Kirin 990",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirin990 main" % _ARCHS,
            "deb %s 10.1-2403-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-kirin990-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2503-990",
        "Wayland 2503 · 麒麟 990",
        "Wayland · 麒麟 990",
        "Wayland 2503 Kirin 990（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-2503-wayland-bugfix-limit main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin990 main" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin990-bugfix main universe restricted multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-wayland-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin990",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin990-bugfix",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    # -------------------------------------------------------------
    # Wayland · 麒麟 9006C
    _p(
        "wl-2107-9006c",
        "Wayland 2107 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2107 Kirin 9006C",
        [
            "deb %s default all" % _KIRIN9A0S,
            "deb %s 10.1-2107-wayland-kirin9006c-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-kv main restricted universe multiverse" % _ARCHS,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2203-9006c",
        "Wayland 2203 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2203 Kirin 9006C",
        [
            "deb %s 10.1-2203-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2203-wayland-kirin9006c-bugfix-limit main" % _ARCHS,
            "deb %s 10.1-kirin9006C-feature main" % _ARCHS,
            "deb %s 10.1-wayland-2203-updates main universe restricted multiverse" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2303-9006c",
        "Wayland 2303 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2303 Kirin 9006C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-wayland-2303-updates main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin9006C-2303-feature main" % _ARCHS,
            "deb %s 10.1-2303-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-kirin9006c-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2303u2-9006c",
        "Wayland 2303-update2 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2303 update2 Kirin 9006C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update3 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update3-kirin9006C main" % _ARCHS,
            "deb %s 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update2-kirin9006c-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2403u2-9006c",
        "Wayland 2403-update2 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2403 update2 Kirin 9006C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirin9006C main" % _ARCHS,
            "deb %s 10.1-2403-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-kirin9006c-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2503-9006c",
        "Wayland 2503 · 麒麟 9006C",
        "Wayland · 麒麟 9006C",
        "Wayland 2503 Kirin 9006C（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-2503-wayland-bugfix-limit main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin9006C main" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin9006C-bugfix main universe restricted multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-wayland-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin9006C",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin9006C-bugfix",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    # -------------------------------------------------------
    # Wayland · 盘古 M900（Pangwu）
    _p(
        "wl-2303u2-m900",
        "Wayland 2303-update2 · 盘古 M900",
        "Wayland · 盘古 M900（Pangwu）",
        "Wayland 2303 update2 盘古 M900",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-wayland-update3 main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-2303-wayland-update3-m900 main" % _ARCH,
            "deb %s 10.1-2303-wayland-update2-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2303-wayland-update2-kirinM900-bugfix-limit main" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        architectures=("arm64",),
        notes=(
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
            "源清单中 http / https 混用，按原始清单保留；若某条不通可单独改成另一种协议。",
        ),
    ),
    _p(
        "wl-2403u2-m900",
        "Wayland 2403-update2 · 盘古 M900",
        "Wayland · 盘古 M900（Pangwu）",
        "Wayland 2403 update2 盘古 M900",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirinM900 main" % _ARCHS,
            "deb %s 10.1-2403-wayland-bugfix-limit main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-kirinM900-bugfix-limit main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2503-m900",
        "Wayland 2503 · 盘古 M900",
        "Wayland · 盘古 M900（Pangwu）",
        "Wayland 2503 盘古 M900（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-2503-wayland-bugfix-limit main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirinM900 main" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirinM900-bugfix main universe restricted multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-wayland-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirinM900",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirinM900-bugfix",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    # -------------------------------------------------------------
    # Wayland · 麒麟 9000C
    _p(
        "wl-2403-9000c",
        "Wayland 2403 · 麒麟 9000C",
        "Wayland · 麒麟 9000C",
        "Wayland 2403 Kirin 9000C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-wayland-2403-updates main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin9000C-2403-feature main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2403u1-9000c",
        "Wayland 2403-update1 · 麒麟 9000C",
        "Wayland · 麒麟 9000C",
        "Wayland 2403 update1 Kirin 9000C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update1 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update1-kirin9000C main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2403u2-9000c",
        "Wayland 2403-update2 · 麒麟 9000C",
        "Wayland · 麒麟 9000C",
        "Wayland 2403 update2 Kirin 9000C",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirin9000C main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    _p(
        "wl-2503-9000c",
        "Wayland 2503 · 麒麟 9000C",
        "Wayland · 麒麟 9000C",
        "Wayland 2503 Kirin 9000C（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-2503-wayland-bugfix-limit main universe restricted multiverse" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin9000C main" % _ARCH,
            "deb %s 10.1-kylin-2503-wayland-kirin9000C-bugfix main universe restricted multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2503-wayland-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin9000C",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin-2503-wayland-kirin9000C-bugfix",
            "Pin-Priority: 700",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 600",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    _p(
        "wl-pangux-a-2403",
        "Wayland 2403 · 华为 Pangux-a",
        "Wayland · 麒麟 9000C",
        "华为 Pangux-a 2403（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kirin9000C-2403-feature-bugfix-limit main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin9000C-2403-feature main" % _ARCHS,
            "deb %s 10.1-wayland-2403-updates main universe restricted multiverse" % _ARCH,
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-wayland-2403-updates",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kirin9000C-2403-feature-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kirin9000C-2403-feature",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 500",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    _p(
        "wl-pangux-b",
        "Wayland · 华为 Pangux-b",
        "Wayland · 麒麟 9000C",
        "华为 Pangux-b（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-kirin9000C-2403-feature-bugfix-limit main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-kirin9000C-b-2403-feature main" % _ARCHS,
            "deb %s 10.1-wayland-2403-updates main universe restricted multiverse" % _ARCH,
            "deb %s 10.1 main restricted universe multiverse" % _ARCH,
            "deb %s default all" % _KIRIN9A0,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-wayland-2403-updates",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kirin9000C-2403-feature-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kirin9000C-b-2403-feature",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 500",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    # ----------------------------------------------------------
    # Wayland · 华为其他平台
    _p(
        "wl-flemingx",
        "Wayland · 华为 Flemingx",
        "Wayland · 华为其他平台",
        "华为 Flemingx（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-2403-wayland-update2-kirin9000C-pre-bugfix-limit main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirin9000C-pre main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2-kirin9000C-pre",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2-kirin9000C-pre-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 500",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    _p(
        "wl-panguy",
        "Wayland · 华为 Panguy（麒麟 9000X）",
        "Wayland · 华为其他平台",
        "华为 Panguy / Kirin 9000X（含 kylin.pref 优先级）",
        [
            "deb %s 10.1-2403-wayland-update2-kirin9000X-bugfix-limit main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1 main restricted universe multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2 main universe restricted multiverse" % _ARCHS,
            "deb %s 10.1-2403-wayland-update2-kirin9000X main" % _ARCHS,
            "deb %s default all" % _KIRIN9A0S,
        ],
        preferences=(
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-kylin",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2",
            "Pin-Priority: 500",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2-kirin9000X",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive.kylinos.cn\"",
            "Pin: release a=10.1-2403-wayland-update2-kirin9000X-bugfix-limit",
            "Pin-Priority: 600",
            "",
            "Package: *",
            "Pin: origin \"archive2.kylinos.cn\"",
            "Pin-Priority: 500",
        ),
        architectures=("arm64",),
        notes=(
            "该版本源配套 /etc/apt/preferences.d/kylin.pref 优先级配置，创建 profile 时会一并写入 profile 的 preferences.d/kylin.pref。",
            "feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",
        ),
    ),
    _p(
        "wl-2107-panguw",
        "Wayland 2107 · 华为 Panguw",
        "Wayland · 华为其他平台",
        "华为 Panguw 2107（10.1-pw）",
        [
            "deb %s 10.1-pw main restricted universe multiverse" % _ARCH,
        ],
        architectures=("arm64",),
        notes=("feature / bugfix-limit 均为芯片专属 suite，只适用于对应机型。",)
    ),
    # -------------------------------------------------------
    # V10 基础版（非 SP1，历史）
    _p(
        "v10-2107",
        "V10-2107 / 2101 / 0710 等（旧版，非 SP1）",
        "V10 基础版（非 SP1，历史）",
        "V10 非 SP1（10.0 系）历史源",
        [
            "deb %s 10.0 main restricted universe multiverse" % _ARCH,
            "deb http://archive.kylinos.cn/kylin/partner juniper main",
            "deb %s 10.0-fixs main" % _ARCH,
        ],
        notes=("来自旧版《银河麒麟桌面版软件源地址汇总》；新外网源清单（XC / HWE / Wayland）不再收录 V10 非 SP1（10.0 系），仅在老机器上参考。",)
    ),
    _p(
        "v10-2203",
        "V10-2203（X86_64 / ARM64 / MIPS64el，旧版，非 SP1）",
        "V10 基础版（非 SP1，历史）",
        "V10 非 SP1（10.0 系）历史源",
        [
            "deb %s 10.0 main restricted universe multiverse" % _ARCH,
            "deb http://archive.kylinos.cn/kylin/partner juniper main",
            "deb http://archive2.kylinos.cn/deb/kylin/production/PART-V10/custom/partner/V10 default all",
        ],
        architectures=("amd64", "arm64", "mips64el"),
        notes=("来自旧版《银河麒麟桌面版软件源地址汇总》；新外网源清单（XC / HWE / Wayland）不再收录 V10 非 SP1（10.0 系），仅在老机器上参考。",)
    ),
)


PRESET_MAP: Dict[str, SourcePreset] = {preset.id: preset for preset in PRESETS}


def get_preset(preset_id: str) -> SourcePreset:
    preset = PRESET_MAP.get(preset_id)
    if preset is None:
        raise KylinPkgError(
            "未知预设：%s（可用：%s）" % (preset_id, ", ".join(sorted(PRESET_MAP)))
        )
    return preset


def list_presets(group: Optional[str] = None) -> List[SourcePreset]:
    if group:
        return [preset for preset in PRESETS if preset.group == group]
    return list(PRESETS)


def preset_text(preset: SourcePreset, include_notes: bool = True) -> str:
    lines = list(preset.sources)
    if preset.preferences:
        lines.append("")
        lines.append("# /etc/apt/preferences.d/kylin.pref")
        lines.extend(preset.preferences)
    if include_notes and preset.notes:
        lines.append("")
        for note in preset.notes:
            lines.append("# 注意：" + note)
    return "\n".join(lines)

