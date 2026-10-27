# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""内置 apt 源预设。

数据来自用户提供的《银河麒麟桌面版软件源地址汇总.md》修正版：
26 个版本配置、88 条 `deb` 源行（2026-10-27 按修正版重新解析并逐行核对）。
预设只是模板：创建成 profile 后可以自由查看、编辑。
`docs/kylin-desktop-sources.md` 保存修正版原文，`tests/test_presets.py`
会校验预设源行与文档一致。

文档中几处需要归一/说明的地方：
- V10SP1-2107/0521 HWE 的 KY 桌面源含 `$(ARCH)`，创建 profile 时替换为主架构；
- 最新修正版将 Kirin partner/feature 路径更新为 `10_1-`/`PART-10_1-`；
  第 12 条按文档保留 `10.1-kirin9a0` 的 partner suite；
- V10SP1-2303 通用版文档重复写了 universe，这里去重；
- 16/17 条与 14/15 条在文档中完全相同，update2 的差异未体现；
- 盘古（Pangwu）是华为海思的芯片产品线，ARM64 架构，预设按 arm64 处理；
- 部分 Kirin/Pangwu 的 partner/suite 在当前公网镜像未验证到，源文件可随时编辑。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .util import KylinPkgError

SOURCE_DOC = "银河麒麟桌面版软件源地址汇总.md"
_ARCH_BASE = "http://archive.kylinos.cn/kylin/KYLIN-ALL"
_ARCH_PARTNER = "http://archive.kylinos.cn/kylin/partner"
_A2 = "http://archive2.kylinos.cn/deb/kylin/production"
_PARTNER_SP1 = "http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1"
_KY_DESKTOP = (
    "http://archive2.kylinos.cn/deb/kylin/production/"
    "KY-V10-SP1-$(ARCH)/custom/kylin-desktop/V10-SP1-$(ARCH)"
)

_KIRIN_NOTE = (
    "Kirin/Pangwu 专用 partner/suite 未在当前公网镜像全部验证到；"
    "若解析报 404，请用目标机实际源地址覆盖。"
)
_PANGWU_NOTE = "盘古（Pangwu）是华为海思的另一款芯片产品线，ARM64 架构，预设按 arm64 处理。"
_DUP_NOTE = "文档中该条与相邻条目相同，update2 的 suite 差异未体现；请以目标机实际源为准。"
_2503_NOTE = (
    "文档使用 10.1-2503-bugfix；部分镜像/机器上实际是 10.1-2503-bugfix-limit。"
    "如果 apt 提示 suite 不存在，请编辑源文件改成实际 suite。"
)


@dataclass(frozen=True)
class SourcePreset:
    id: str
    name: str
    group: str
    description: str
    sources: Tuple[str, ...]
    architectures: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()


def _p(
    preset_id: str,
    name: str,
    group: str,
    description: str,
    sources: Sequence[str],
    architectures: Sequence[str] = (),
    notes: Sequence[str] = (),
) -> SourcePreset:
    return SourcePreset(
        id=preset_id,
        name=name,
        group=group,
        description=description,
        sources=tuple(sources),
        architectures=tuple(architectures),
        notes=tuple(notes),
    )


PRESETS: Tuple[SourcePreset, ...] = (
    # ---------------------------------------------------------- V10 基础版
    _p(
        "v10-2107",
        "V10-2107 / 2101.0710 等",
        "V10 基础版",
        "V10 非 SP1",
        [
            "deb %s 10.0 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s juniper main" % _ARCH_PARTNER,
            "deb %s 10.0-fixs main" % _ARCH_BASE,
        ],
    ),
    _p(
        "v10-2203",
        "V10-2203（X86_64 / ARM64 / MIPS64el）",
        "V10 基础版",
        "V10 非 SP1",
        [
            "deb %s 10.0 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s juniper main" % _ARCH_PARTNER,
            "deb %s/PART-V10/custom/partner/V10 default all" % _A2,
        ],
        ("amd64", "arm64", "mips64el"),
    ),
    # ------------------------------------------------- V10 SP1 2107 / 0521
    _p(
        "sp1-2107-hwe",
        "V10SP1-2107-HWE & V10SP1-0521-HWE",
        "V10 SP1 2107 / 0521",
        "2107/0521 HWE（KY desktop + partner）",
        [
            "deb %s default all" % _KY_DESKTOP,
            "deb %s default all" % _PARTNER_SP1,
            "deb %s 10.1-hwe main" % _ARCH_BASE,
            "deb %s 10.1 main" % _ARCH_PARTNER,
        ],
        ("amd64", "arm64"),
        notes=(
            "源地址中的 $(ARCH) 会在创建 profile 时替换为目标主架构；"
            "已在公网镜像验证 amd64/arm64。",
        ),
    ),
    _p(
        "sp1-2107-0521",
        "V10 SP1 2107 & 211217 & 0521（多架构）",
        "V10 SP1 2107 / 0521",
        "2107 / 211217 / 0521 系列",
        [
            "deb %s 10.1 main universe multiverse restricted" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
        ("amd64", "arm64", "mips64el"),
    ),
    # ------------------------------------------------------- V10 SP1 2203
    _p(
        "sp1-2203",
        "V10 SP1 2203（X86_64 / ARM64 / MIPS64el / LoongArch64）",
        "V10 SP1 2203",
        "2203 基础更新",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2203-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
        ("amd64", "arm64", "mips64el", "loongarch64"),
    ),
    _p(
        "sp1-2203-hwe",
        "V10 SP1 2203 HWE",
        "V10 SP1 2203",
        "2203 HWE 更新",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2203-hwe-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    # ------------------------------------------------------- V10 SP1 2303
    _p(
        "sp1-2303",
        "V10 SP1 2303 & update2（通用版）",
        "V10 SP1 2303",
        "2303 通用版",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
        notes=("文档中 components 重复写了 universe，此预设已去重。",),
    ),
    _p(
        "sp1-2303-hwe",
        "V10 SP1 2303 HWE & update2",
        "V10 SP1 2303",
        "2303 HWE",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2303-hwe-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    _p(
        "sp1-2303-hwe-pp",
        "V10 SP1 2303 HWE-PP",
        "V10 SP1 2303",
        "2303 HWE + PP 分支",
        [
            "deb %s 10.1 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2303-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2303-hwe-pp-updates main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    # --------------------------------------------------------- 海思麒麟
    _p(
        "sp1-kirin990-old",
        "V10 SP1 海思麒麟 990（早期版）",
        "海思麒麟（Kirin）",
        "Kirin 990 早期",
        [
            "deb http://archive1.kylinos.cn/kylin/KYLIN-ALL 10.1-pv main restricted universe multiverse",
            "deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin990/custom/partner/10_1-kirin990 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-kirin990-new",
        "V10 SP1 海思麒麟 990（2107版）",
        "海思麒麟（Kirin）",
        "Kirin 990 2107版",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kv main restricted universe multiverse",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-2203-kirin990",
        "V10 SP1 2203 海思麒麟 990",
        "海思麒麟（Kirin）",
        "2203 + Kirin 990 feature",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10_1-kirin990-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10.1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-2203-kirin9006c",
        "V10 SP1 2203 海思麒麟 9006C",
        "海思麒麟（Kirin）",
        "2203 + Kirin 9006C feature",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-kirin9006c-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-2303-kirin990",
        "V10 SP1 2303 海思麒麟 990",
        "海思麒麟（Kirin）",
        "2303 + Kirin 990 feature",
        [
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL/ 10_1-kirin990-2303-feature main",
            "deb http://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-2303-kirin9006c",
        "V10 SP1 2303 海思麒麟 9006C",
        "海思麒麟（Kirin）",
        "2303 + Kirin 9006C feature",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006c-2303-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    _p(
        "sp1-2303u2-kirin9006c",
        "V10 SP1 2303-update2 海思麒麟 9006C",
        "海思麒麟（Kirin）",
        "2303 update2 + Kirin 9006C（文档同 2303 条）",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9006c-2303-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE, _DUP_NOTE),
    ),
    _p(
        "sp1-2303u2-kirin990",
        "V10 SP1 2303-update2 海思麒麟 990",
        "海思麒麟（Kirin）",
        "2303 update2 + Kirin 990（文档同 2303 条）",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10_1-kirin990-2303-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE, _DUP_NOTE),
    ),
    _p(
        "sp1-2403-kirin9000c",
        "V10 SP1 2403 海思麒麟 9000C",
        "海思麒麟（Kirin）",
        "2403 Wayland + Kirin 9000C feature",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2403-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirin9000C-2403-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE,),
    ),
    # --------------------------------------------------------- 盘古
    _p(
        "sp1-2203-pangwu-m900",
        "V10 SP1 2203 盘古 M900",
        "海思麒麟 · 盘古（Pangwu）",
        "2203 Wayland + 盘古 M900",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL/ 10.1-wayland-2203-pangwu main universe restricted multiverse",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (_KIRIN_NOTE, _PANGWU_NOTE),
    ),
    _p(
        "sp1-2303-pangwu-m900",
        "V10 SP1 2303 盘古 M900",
        "海思麒麟 · 盘古（Pangwu）",
        "2303 Wayland + 盘古 M900",
        [
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-wayland-2303-updates main universe restricted multiverse",
            "deb https://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-kirinM900-2303-feature main",
            "deb https://archive2.kylinos.cn/deb/kylin/production/PART-10_1-kirin9a0/custom/partner/10_1-kirin9a0 default all",
        ],
        ("arm64",),
        (
            _KIRIN_NOTE,
            _PANGWU_NOTE,
            "10.1-kirinM900-2303-feature 在当前公网镜像返回 404；请以目标机实际 suite 为准。",
        ),
    ),
    # ------------------------------------------------------- V10 SP1 2403
    _p(
        "sp1-2403",
        "V10 SP1 2403（通用版）",
        "V10 SP1 2403",
        "2403 通用版",
        [
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb http://archive2.kylinos.cn/DEB/KYLIN_DEB V10-SP1 main all",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-updates main restricted universe multiverse",
        ],
    ),
    _p(
        "sp1-2403-u1",
        "V10 SP1 2403-update1",
        "V10 SP1 2403",
        "2403 update1",
        [
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update1 main restricted universe multiverse",
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    _p(
        "sp1-2403-hwe-u1",
        "V10 SP1 2403 HWE & update1",
        "V10 SP1 2403",
        "2403 HWE + update1",
        [
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update1 main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-hwe-update1 main",
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    _p(
        "sp1-2403-u2",
        "V10 SP1 2403-update2",
        "V10 SP1 2403",
        "2403 update2",
        [
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1 main restricted universe multiverse",
            "deb http://archive.kylinos.cn/kylin/KYLIN-ALL 10.1-2403-update2 main restricted universe multiverse",
            "deb %s default all" % _PARTNER_SP1,
        ],
    ),
    # ------------------------------------------------------- V10 SP1 2503
    _p(
        "sp1-2503-hwe",
        "V10 SP1 2503 HWE",
        "V10 SP1 2503",
        "2503 + HWE + bugfix",
        [
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-kylin-2503-hwe main" % _ARCH_BASE,
            "deb %s 10.1-2503-bugfix main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2503-hwe-bugfix main restricted universe multiverse" % _ARCH_BASE,
            "deb %s default all" % _PARTNER_SP1,
        ],
        notes=(_2503_NOTE,),
    ),
    _p(
        "sp1-2503",
        "V10 SP1 2503（通用版）",
        "V10 SP1 2503",
        "2503 通用版",
        [
            "deb %s default all" % _PARTNER_SP1,
            "deb %s 10.1-kylin main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-kylin-2503 main restricted universe multiverse" % _ARCH_BASE,
            "deb %s 10.1-2503-bugfix main restricted universe multiverse" % _ARCH_BASE,
        ],
        notes=(_2503_NOTE,),
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
    if include_notes and preset.notes:
        lines.append("")
        for note in preset.notes:
            lines.append("# 注意：" + note)
    return "\n".join(lines)
