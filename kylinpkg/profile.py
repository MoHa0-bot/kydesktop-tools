# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""apt 源配置 profile：导入、校验、存放、与 baseline 绑定。"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from . import baseline as baseline_mod
from . import deb822
from .arch import detect_system_archs, normalize_arch_set
from .config import State
from .presets import SOURCE_DOC, get_preset
from .util import (
    CommandError,
    KylinPkgError,
    atomic_write_bytes,
    atomic_write_text,
    copy_file,
    ensure_dir,
    iso_now,
    redact_uri,
    run,
    sha256_file,
    validate_name,
)

_APT_TOP_NAMES = {
    "sources.list",
    "sources.list.d",
    "preferences",
    "preferences.d",
    "trusted.gpg",
    "trusted.gpg.d",
}

_DEFAULT_URI = "http://archive.kylinos.cn/kylin/KYLIN-ALL"
_PARTNER_URI = "http://archive2.kylinos.cn/deb/kylin/production/PART-V10-SP1/custom/partner/V10-SP1"


def _ensure_layout(pdir: Path) -> None:
    ensure_dir(pdir, 0o700)
    ensure_dir(pdir / "sources.list.d", 0o700)
    ensure_dir(pdir / "preferences.d", 0o700)
    ensure_dir(pdir / "keyrings" / "trusted.gpg.d", 0o700)
    ensure_dir(pdir / "keyrings" / "signed-by", 0o700)
    ensure_dir(pdir / "auth.conf.d", 0o700)
    for name in ("sources.list", "preferences", "auth.conf"):
        path = pdir / name
        if not path.exists():
            atomic_write_text(path, "", 0o600)


def _real_path(path: Path, rootfs: Optional[Path]) -> Path:
    """处理 rootfs 中的绝对符号链接，避免读到宿主的同名文件。"""
    if path.is_symlink():
        target = os.readlink(str(path))
        if rootfs is not None and target.startswith("/"):
            candidate = Path(rootfs) / target.lstrip("/")
            if candidate.exists():
                return candidate
    return path


def _copy_into(src: Path, dst: Path, rootfs: Optional[Path] = None) -> None:
    src = _real_path(Path(src), rootfs)
    if not src.is_file():
        return
    copy_file(src, dst, 0o600)


def _copy_keyrings_from_apt(apt_dir: Path, pdir: Path, rootfs: Optional[Path] = None) -> int:
    count = 0
    trusted = apt_dir / "trusted.gpg"
    if trusted.exists():
        real = _real_path(trusted, rootfs)
        copy_file(real, pdir / "keyrings" / "trusted.gpg", 0o600)
        count += 1
    trusted_parts = apt_dir / "trusted.gpg.d"
    if trusted_parts.is_dir():
        for path in sorted(trusted_parts.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            real = _real_path(path, rootfs)
            copy_file(real, pdir / "keyrings" / "trusted.gpg.d" / path.name, 0o600)
            count += 1
    return count


def _install_keys(
    apt_dir: Path,
    pdir: Path,
    rootfs: Optional[Path],
    enabled: bool,
) -> int:
    if enabled:
        return _copy_keyrings_from_apt(apt_dir, pdir, rootfs)
    atomic_write_text(pdir / "keyrings" / ".no-system-keys", "", 0o600)
    return 0


def _copy_sources_from_apt(apt_dir: Path, pdir: Path, rootfs: Optional[Path] = None) -> None:
    main = apt_dir / "sources.list"
    if main.exists() or main.is_symlink():
        _copy_into(main, pdir / "sources.list", rootfs)
    parts = apt_dir / "sources.list.d"
    if parts.is_dir():
        for path in sorted(parts.iterdir()):
            if not path.is_file() and not path.is_symlink():
                continue
            if path.name.startswith(".") or path.name.endswith((".bak", ".save", ".disabled", "~")):
                continue
            if not path.name.endswith((".list", ".sources")):
                continue
            real = _real_path(path, rootfs)
            copy_file(real, pdir / "sources.list.d" / path.name, 0o600)


def _copy_prefs_from_apt(apt_dir: Path, pdir: Path, rootfs: Optional[Path] = None) -> None:
    main = apt_dir / "preferences"
    if main.exists() or main.is_symlink():
        _copy_into(main, pdir / "preferences", rootfs)
    parts = apt_dir / "preferences.d"
    if parts.is_dir():
        for path in sorted(parts.iterdir()):
            if (not path.is_file() and not path.is_symlink()) or path.name.startswith("."):
                continue
            if path.name.endswith((".bak", ".save", ".disabled", "~")):
                continue
            real = _real_path(path, rootfs)
            copy_file(real, pdir / "preferences.d" / path.name, 0o600)


def _copy_auth_from_apt(
    apt_dir: Path, pdir: Path, rootfs: Optional[Path] = None
) -> int:
    count = 0
    main = apt_dir / "auth.conf"
    if main.exists() or main.is_symlink():
        real = _real_path(main, rootfs)
        if real.is_file():
            copy_file(real, pdir / "auth.conf", 0o600)
            count += 1
    parts = apt_dir / "auth.conf.d"
    if parts.is_dir():
        for path in sorted(parts.iterdir()):
            if not path.is_file() and not path.is_symlink():
                continue
            if path.name.startswith(".") or path.name.endswith(
                (".bak", ".save", ".disabled", "~")
            ):
                continue
            real = _real_path(path, rootfs)
            copy_file(real, pdir / "auth.conf.d" / path.name, 0o600)
            count += 1
    return count


def _copy_explicit_auth(files: Sequence[Path], dirs: Sequence[Path], pdir: Path) -> int:
    count = 0
    for item in files:
        path = Path(item).expanduser()
        if not path.is_file():
            raise KylinPkgError("auth.conf 文件不存在：%s" % path)
        copy_file(path, pdir / "auth.conf", 0o600)
        count += 1
    for directory in dirs:
        directory = Path(directory).expanduser()
        if not directory.is_dir():
            raise KylinPkgError("auth.conf.d 目录不存在：%s" % directory)
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                copy_file(path, pdir / "auth.conf.d" / path.name, 0o600)
                count += 1
    return count


def _copy_explicit_sources(files: Sequence[Path], dirs: Sequence[Path], pdir: Path) -> None:
    def place(path: Path) -> None:
        path = Path(path).expanduser()
        if not path.is_file():
            raise KylinPkgError("源文件不存在：%s" % path)
        if path.name == "sources.list":
            dst = pdir / "sources.list"
        else:
            if not path.name.endswith((".list", ".sources")):
                raise KylinPkgError("源文件扩展名必须是 .list 或 .sources：%s" % path)
            dst = pdir / "sources.list.d" / path.name
        if dst.exists() and dst.stat().st_size > 0 and sha256_file(dst) != sha256_file(path):
            raise KylinPkgError("源文件重名且内容不同：%s（请改名后导入）" % dst.name)
        copy_file(path, dst, 0o600)

    for item in files:
        place(Path(item))
    for directory in dirs:
        directory = Path(directory).expanduser()
        if not directory.is_dir():
            raise KylinPkgError("源目录不存在：%s" % directory)
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.name.endswith((".list", ".sources")):
                place(path)


def _copy_explicit_prefs(files: Sequence[Path], dirs: Sequence[Path], pdir: Path) -> None:
    for item in files:
        path = Path(item).expanduser()
        if not path.is_file():
            raise KylinPkgError("preferences 文件不存在：%s" % path)
        copy_file(path, pdir / "preferences", 0o600)
    for directory in dirs:
        directory = Path(directory).expanduser()
        if not directory.is_dir():
            raise KylinPkgError("preferences 目录不存在：%s" % directory)
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                copy_file(path, pdir / "preferences.d" / path.name, 0o600)


def _copy_explicit_keyrings(files: Sequence[Path], pdir: Path) -> None:
    for item in files:
        path = Path(item).expanduser()
        if not path.is_file():
            raise KylinPkgError("keyring 文件不存在：%s" % path)
        if path.name == "trusted.gpg":
            dst = pdir / "keyrings" / "trusted.gpg"
        else:
            dst = pdir / "keyrings" / "trusted.gpg.d" / path.name
        copy_file(path, dst, 0o600)


def _run_binary(cmd: Sequence[str], timeout: int = 60) -> bytes:
    try:
        proc = subprocess.run(
            [str(x) for x in cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise KylinPkgError("找不到命令：%s" % cmd[0]) from exc
    except subprocess.TimeoutExpired as exc:
        raise KylinPkgError("命令超时：%s" % " ".join(map(str, cmd))) from exc
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise CommandError(cmd, proc.returncode, "", stderr)
    return proc.stdout


def _extract_ssh_apt(host: str, dest: Path, include_auth: bool = False) -> None:
    if not host or host.startswith("-"):
        raise KylinPkgError("SSH 目标不合法：%r" % host)
    names = (
        "sources.list sources.list.d preferences preferences.d "
        "trusted.gpg trusted.gpg.d"
    )
    if include_auth:
        names += " auth.conf auth.conf.d"
    tar_cmd = (
        "tar -C /etc/apt -c -z -h -f - --ignore-failed-read " + names
    )
    data = _run_binary(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, tar_cmd],
        timeout=90,
    )
    if not data:
        raise KylinPkgError("从 %s 抓取 /etc/apt 失败：返回为空" % host)
    ensure_dir(dest, 0o700)
    try:
        archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise KylinPkgError("解析远端 tar 包失败：%s" % exc) from exc
    with archive:
        for member in archive.getmembers():
            name = member.name.lstrip("./")
            parts = Path(name).parts
            if not parts or parts[0] not in _APT_TOP_NAMES:
                continue
            if member.name.startswith("/") or ".." in parts:
                raise KylinPkgError("远端 tar 包含不安全路径：%s" % member.name)
            if not (member.isfile() or member.isdir()):
                continue
            archive.extract(member, path=str(dest))


def _ssh_archs(host: str) -> List[str]:
    cmd = "dpkg --print-architecture; dpkg --print-foreign-architectures"
    proc = run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", host, cmd],
        check=False,
    )
    if proc.returncode != 0:
        return []
    archs: List[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            arch = _normalize_single(line)
        except KylinPkgError:
            continue
        if arch not in archs:
            archs.append(arch)
    return archs


def _normalize_single(value: str) -> str:
    from .arch import normalize_arch

    return normalize_arch(value)


def _rootfs_archs(rootfs: Path) -> List[str]:
    status = Path(rootfs) / "var" / "lib" / "dpkg" / "status"
    if not status.is_file():
        return []
    paragraphs = deb822.parse_status_text(status.read_text(encoding="utf-8", errors="replace"))
    return list(deb822.status_summary(paragraphs)["architectures"])


def _file_role(rel: str) -> str:
    if rel == "sources.list":
        return "sources.main"
    if rel.startswith("sources.list.d/"):
        return "sources.part"
    if rel == "preferences":
        return "preferences.main"
    if rel.startswith("preferences.d/"):
        return "preferences.part"
    if rel == "auth.conf":
        return "auth.main"
    if rel.startswith("auth.conf.d/"):
        return "auth.part"
    if rel.startswith("keyrings/"):
        return "keyring"
    return "other"


def _scan_files(pdir: Path) -> List[Dict[str, object]]:
    paths: List[Path] = []
    for name in ("sources.list", "preferences", "auth.conf"):
        path = pdir / name
        if path.is_file():
            paths.append(path)
    for sub in (
        "sources.list.d",
        "preferences.d",
        "auth.conf.d",
        "keyrings",
        "keyrings/trusted.gpg.d",
        "keyrings/signed-by",
    ):
        directory = pdir / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                paths.append(path)
    result = []
    for path in sorted(set(paths)):
        rel = str(path.relative_to(pdir))
        result.append(
            {
                "path": rel,
                "role": _file_role(rel),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return result


def _redacted_summary(entry: deb822.SourceEntry) -> str:
    text = entry.describe()
    if entry.uri:
        text = text.replace(entry.uri, redact_uri(entry.uri), 1)
    return text


def _arch_hints(entries: Iterable[deb822.SourceEntry], target_archs: Sequence[str]) -> List[str]:
    warnings: List[str] = []
    for entry in entries:
        if entry.architectures and not set(entry.architectures) & set(target_archs):
            warnings.append(
                "源 %s 限定架构为 %s，与目标架构 %s 没有交集"
                % (redact_uri(entry.uri), ",".join(entry.architectures), ",".join(target_archs))
            )
    return warnings


def _write_meta(
    pdir: Path,
    state: State,
    name: str,
    origin_kind: str,
    origin_detail: str,
    architectures: Sequence[str],
    baseline: Optional[str],
    note: str,
    extra_warnings: Sequence[str],
    with_auth: bool = False,
    notices: Sequence[str] = (),
) -> Dict[str, object]:
    entries = deb822.collect_sources(pdir)
    if not entries:
        raise KylinPkgError("没有解析到任何 apt 源，请检查导入的 sources 文件")
    warnings = list(extra_warnings) + deb822.validate_sources(entries)
    warnings += _arch_hints(entries, architectures)
    warnings.extend(notices)
    if with_auth:
        warnings.append("profile 包含 apt 凭据（auth.conf），状态目录与备份请妥善保管")
    baseline_value = None if baseline in (None, baseline_mod.RESERVED_EMPTY) else baseline
    if baseline_value:
        meta = baseline_mod.load_meta(state, baseline_value)
        problem = baseline_mod.check_compatible(
            {"architectures": list(architectures)}, meta
        )
        if problem:
            raise KylinPkgError(problem)
        if int(meta.get("installed_count", 0)) == 0:
            warnings.append(
                "绑定的 baseline %s 未识别到已安装包，增量解析可能退化为全量" % baseline_value
            )
    meta = {
        "schema": 1,
        "name": name,
        "created_at": iso_now(),
        "origin": {"kind": origin_kind, "detail": origin_detail},
        "note": note,
        "architectures": list(architectures),
        "baseline": baseline_value,
        "with_auth": bool(with_auth),
        "notices": list(notices),
        "files": _scan_files(pdir),
        "sources_summary": [_redacted_summary(entry) for entry in entries],
        "warnings": warnings,
    }
    atomic_write_text(pdir / "profile.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def import_profile(
    state: State,
    name: str,
    from_system: bool = False,
    from_ssh: Optional[str] = None,
    from_rootfs: Optional[Path] = None,
    sources_files: Sequence[Path] = (),
    sources_dirs: Sequence[Path] = (),
    preferences_files: Sequence[Path] = (),
    preferences_dirs: Sequence[Path] = (),
    keyrings: Sequence[Path] = (),
    architectures: Sequence[str] = (),
    baseline: Optional[str] = None,
    note: str = "",
    force: bool = False,
    copy_system_keys: bool = True,
    include_auth: bool = False,
    auth_files: Sequence[Path] = (),
    auth_dirs: Sequence[Path] = (),
) -> Dict[str, object]:
    name = validate_name(name, "profile 名称")
    if (auth_files or auth_dirs) and not include_auth:
        include_auth = True
    selectors = [from_system, bool(from_ssh), from_rootfs is not None]
    if sum(1 for item in selectors if item) > 1:
        raise KylinPkgError("--from-system / --from-ssh / --from-rootfs 只能选一个")
    using_selector = any(selectors)
    if using_selector and (sources_files or sources_dirs or preferences_files or preferences_dirs):
        raise KylinPkgError("使用 --from-system/ssh/rootfs 时不要再传 --sources-*/--preferences-*")
    if not using_selector and not (sources_files or sources_dirs):
        raise KylinPkgError("请提供源：--sources-file/--sources-dir，或 --from-system/--from-ssh/--from-rootfs")

    pdir = state.profile_dir(name)
    if pdir.exists():
        if not force:
            raise KylinPkgError("profile 已存在：%s（加 --force 覆盖）" % name)
        shutil.rmtree(str(pdir))
    _ensure_layout(pdir)

    origin_kind = "files"
    origin_detail = ""
    derived_archs: List[str] = []
    key_count = 0
    auth_count = 0
    temp_dir: Optional[tempfile.TemporaryDirectory] = None
    try:
        if from_system:
            apt_dir = Path("/etc/apt")
            origin_kind = "system"
            origin_detail = str(apt_dir)
            _copy_sources_from_apt(apt_dir, pdir)
            _copy_prefs_from_apt(apt_dir, pdir)
            key_count = _install_keys(apt_dir, pdir, None, copy_system_keys)
            if include_auth:
                auth_count = _copy_auth_from_apt(apt_dir, pdir)
            try:
                derived_archs = detect_system_archs()
            except KylinPkgError:
                derived_archs = []
        elif from_ssh:
            temp_dir = tempfile.TemporaryDirectory(prefix="kylinpkg-ssh-")
            tmp = Path(temp_dir.name)
            _extract_ssh_apt(from_ssh, tmp, include_auth=include_auth)
            origin_kind = "ssh"
            origin_detail = "%s:/etc/apt" % from_ssh
            _copy_sources_from_apt(tmp, pdir)
            _copy_prefs_from_apt(tmp, pdir)
            key_count = _install_keys(tmp, pdir, None, copy_system_keys)
            if include_auth:
                auth_count = _copy_auth_from_apt(tmp, pdir)
            derived_archs = _ssh_archs(from_ssh)
        elif from_rootfs is not None:
            rootfs = Path(from_rootfs).expanduser()
            apt_dir = rootfs / "etc" / "apt"
            if not apt_dir.is_dir():
                raise KylinPkgError("rootfs 中不存在 /etc/apt：%s" % apt_dir)
            origin_kind = "rootfs"
            origin_detail = str(apt_dir)
            _copy_sources_from_apt(apt_dir, pdir, rootfs)
            _copy_prefs_from_apt(apt_dir, pdir, rootfs)
            key_count = _install_keys(apt_dir, pdir, rootfs, copy_system_keys)
            if include_auth:
                auth_count = _copy_auth_from_apt(apt_dir, pdir, rootfs)
            derived_archs = _rootfs_archs(rootfs)
        else:
            origin_kind = "files"
            origin_detail = ", ".join(
                [str(Path(p).expanduser()) for p in list(sources_files) + list(sources_dirs)]
            )
            _copy_explicit_sources(sources_files, sources_dirs, pdir)
            _copy_explicit_prefs(preferences_files, preferences_dirs, pdir)
            key_count += _install_keys(Path("/etc/apt"), pdir, None, copy_system_keys)

        if auth_files or auth_dirs:
            auth_count += _copy_explicit_auth(auth_files, auth_dirs, pdir)

        if keyrings:
            _copy_explicit_keyrings(keyrings, pdir)
            key_count += len(keyrings)

        extra_warnings: List[str] = []
        arch_source = ""
        if architectures:
            target_archs = normalize_arch_set(architectures)
        else:
            source_archs: List[str] = []
            if not using_selector:
                source_archs = deb822.source_architectures(deb822.collect_sources(pdir))
            if source_archs:
                target_archs = normalize_arch_set(source_archs)
                arch_source = "源中声明的 Architectures"
            else:
                target_archs = normalize_arch_set(derived_archs or detect_system_archs())
                arch_source = "本机/来源系统"
        if key_count == 0:
            extra_warnings.append("profile 中没有 keyring；若源未设置 trusted=yes，apt update 会因签名失败")
        if not architectures:
            extra_warnings.append("未指定 --arch，已使用%s架构：%s" % (arch_source, ",".join(target_archs)))
        if from_ssh and not derived_archs and arch_source == "本机/来源系统":
            extra_warnings.append("未能从远端检测架构，已退回本机架构；建议显式 --arch")
        if include_auth and auth_count == 0:
            extra_warnings.append(
                "请求包含 auth.conf，但来源中没有找到 /etc/apt/auth.conf 或 auth.conf.d"
            )

        meta = _write_meta(
            pdir,
            state,
            name,
            origin_kind,
            origin_detail,
            target_archs,
            baseline,
            note,
            extra_warnings,
            with_auth=include_auth,
        )
        extra_roots = [Path(from_rootfs).expanduser()] if from_rootfs is not None else []
        materialize_signed_by(state, name, extra_roots)
        return load_profile(state, name)
    except Exception:
        if temp_dir is not None:
            temp_dir.cleanup()
            temp_dir = None
        shutil.rmtree(str(pdir), ignore_errors=True)
        raise
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def add_kylin_profile(
    state: State,
    name: str,
    suites: Sequence[str],
    base_suite: str = "10.1-kylin",
    uri: str = _DEFAULT_URI,
    components: Sequence[str] = ("main", "restricted", "universe", "multiverse"),
    architectures: Sequence[str] = (),
    partner: bool = False,
    baseline: Optional[str] = None,
    note: str = "",
    force: bool = False,
) -> Dict[str, object]:
    name = validate_name(name, "profile 名称")
    all_suites: List[str] = []
    for suite in list([base_suite]) + list(suites):
        suite = (suite or "").strip()
        if suite and suite not in all_suites:
            all_suites.append(suite)
    if not all_suites:
        raise KylinPkgError("至少需要一个 Kylin suite")

    pdir = state.profile_dir(name)
    if pdir.exists():
        if not force:
            raise KylinPkgError("profile 已存在：%s（加 --force 覆盖）" % name)
        shutil.rmtree(str(pdir))
    _ensure_layout(pdir)
    lines = ["# generated by kylinpkg profile add"]
    for suite in all_suites:
        lines.append("deb %s %s %s" % (uri, suite, " ".join(components)))
    if partner:
        lines.append("deb %s default all" % _PARTNER_URI)
    try:
        atomic_write_text(pdir / "sources.list", "\n".join(lines) + "\n", 0o600)
        key_count = _copy_keyrings_from_apt(Path("/etc/apt"), pdir)
        target_archs = normalize_arch_set(architectures) if architectures else detect_system_archs()
        extra_warnings = []
        if key_count == 0:
            extra_warnings.append("没有找到可复制的 keyring；若源未设置 trusted=yes，apt update 会失败")
        return _write_meta(
            pdir, state, name, "kylin-suite", uri, target_archs, baseline, note, extra_warnings
        )
    except Exception:
        shutil.rmtree(str(pdir), ignore_errors=True)
        raise


def create_from_preset(
    state: State,
    name: str,
    preset_id: str,
    architectures: Sequence[str] = (),
    baseline: Optional[str] = None,
    note: str = "",
    force: bool = False,
) -> Dict[str, object]:
    preset = get_preset(preset_id)
    name = validate_name(name, "profile 名称")
    pdir = state.profile_dir(name)
    if pdir.exists():
        if not force:
            raise KylinPkgError("profile 已存在：%s（加 --force 覆盖）" % name)
        shutil.rmtree(str(pdir))
    _ensure_layout(pdir)
    try:
        extra_warnings: List[str] = []
        if architectures:
            target_archs = normalize_arch_set(architectures)
        elif preset.architectures:
            preset_archs = normalize_arch_set(preset.architectures)
            if len(preset_archs) == 1:
                target_archs = preset_archs
            else:
                try:
                    host_archs = detect_system_archs()
                except KylinPkgError:
                    host_archs = []
                common = [arch for arch in host_archs if arch in preset_archs]
                target_archs = common or [preset_archs[0]]
                if not common:
                    extra_warnings.append(
                        "预设支持 %s，但未检测到匹配的本机架构，已默认 %s；"
                        "可用 --arch 覆盖"
                        % (", ".join(preset_archs), target_archs[0])
                    )
        else:
            target_archs = detect_system_archs()

        primary_arch = target_archs[0]
        lines = [
            "# kylinpkg preset: %s" % preset.id,
            "# %s" % preset.name,
            "# source: %s" % SOURCE_DOC,
            "# 可在 GUI 或 kylinpkg profile edit 中修改以下源",
        ]
        lines.extend(
            line.replace("$(ARCH)", primary_arch) for line in preset.sources
        )
        if preset.notes:
            lines.append("")
            for note in preset.notes:
                lines.append("# 注意：" + note)
        atomic_write_text(pdir / "sources.list", "\n".join(lines) + "\n", 0o600)
        if preset.preferences:
            pref_lines = [
                "# kylinpkg preset: %s" % preset.id,
                "# %s" % preset.name,
                "# source: %s" % SOURCE_DOC,
                "# 对应 /etc/apt/preferences.d/kylin.pref，可在 GUI 或 "
                "kylinpkg profile edit 中修改",
                "",
            ]
            pref_lines.extend(preset.preferences)
            atomic_write_text(
                pdir / "preferences.d" / "kylin.pref",
                "\n".join(pref_lines) + "\n",
                0o600,
            )
        key_count = _copy_keyrings_from_apt(Path("/etc/apt"), pdir)
        if key_count == 0:
            extra_warnings.append(
                "没有找到可复制的 keyring；若源未设置 trusted=yes，apt update 会因签名失败"
            )
        if preset.preferences:
            extra_warnings.append(
                "预设自带 apt 优先级配置，已写入 preferences.d/kylin.pref；"
                "Pin-Priority 会影响包版本选择，请确认与本机系统版本匹配"
            )
        _write_meta(
            pdir,
            state,
            name,
            "preset",
            preset.id,
            target_archs,
            baseline,
            note or preset.description,
            extra_warnings,
            with_auth=False,
            notices=preset.notes,
        )
        materialize_signed_by(state, name)
        return load_profile(state, name)
    except Exception:
        shutil.rmtree(str(pdir), ignore_errors=True)
        raise


def fingerprint(state: State, name: str) -> str:
    """profile 内容指纹；源/pin/keyring 改动后让隔离索引失效。"""
    pdir = state.profile_dir(name)
    if not (pdir / "profile.json").is_file():
        raise KylinPkgError("profile 不存在：%s" % name)
    hasher = hashlib.sha256()
    for item in _scan_files(pdir):
        hasher.update(("%s\0%s\n" % (item["path"], item["sha256"])).encode("utf-8"))
    return hasher.hexdigest()


def materialize_signed_by(
    state: State, name: str, extra_roots: Sequence[Path] = ()
) -> List[str]:
    """把 Signed-By 引用的 keyring 复制进 profile，并改写源文件路径。

    这样从 rootfs / 收集包导入的第三方源在另一台机器上也能直接使用。
    """
    meta = load_profile(state, name)
    pdir = state.profile_dir(name)
    entries = deb822.collect_sources(pdir)
    mapping: Dict[str, str] = {}
    warnings: List[str] = []
    for entry in entries:
        for signed in entry.signed_by:
            signed = signed.strip()
            if not signed or signed.startswith("-----BEGIN") or not signed.startswith("/"):
                continue
            if signed in mapping:
                continue
            src: Optional[Path] = None
            for root in extra_roots:
                candidate = Path(root) / signed.lstrip("/")
                if candidate.is_file():
                    src = candidate
                    break
            if src is None:
                host_path = Path(signed)
                if host_path.is_file():
                    src = host_path
            base = Path(signed).name or "keyring.gpg"
            if src is None:
                # 用户可能通过 --keyring 提供了同名 keyring
                for candidate in (
                    pdir / "keyrings" / "trusted.gpg.d" / base,
                    pdir / "keyrings" / "signed-by" / base,
                ):
                    if candidate.is_file():
                        mapping[signed] = str(candidate)
                        src = None
                        break
                if signed in mapping:
                    continue
                warnings.append("Signed-By 指定的 keyring 未找到：%s" % signed)
                continue
            dst = pdir / "keyrings" / "signed-by" / base
            if dst.exists() and sha256_file(dst) != sha256_file(src):
                stem = Path(base).stem
                suffix = Path(base).suffix
                dst = pdir / "keyrings" / "signed-by" / (
                    "%s-%s%s" % (stem, sha256_file(src)[:8], suffix)
                )
            copy_file(src, dst, 0o600)
            mapping[signed] = str(dst)

    if mapping:
        for path in deb822.iter_source_files(pdir):
            text = path.read_text(encoding="utf-8", errors="replace")
            rewritten = text
            for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
                rewritten = rewritten.replace(old, new)
            if rewritten != text:
                atomic_write_text(path, rewritten, 0o600)
        for _old, new in mapping.items():
            if any(char.isspace() for char in new):
                warnings.append("keyring 路径含空格，apt 源选项可能解析失败：%s" % new)

    new_entries = deb822.collect_sources(pdir)
    meta["files"] = _scan_files(pdir)
    meta["sources_summary"] = [_redacted_summary(entry) for entry in new_entries]
    stale_marker = "Signed-By 指定的 keyring 不存在"
    meta["warnings"] = [
        warning for warning in (meta.get("warnings") or []) if stale_marker not in warning
    ] + warnings
    atomic_write_text(
        pdir / "profile.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    )
    return warnings


def load_profile(state: State, name: str) -> Dict[str, object]:
    pdir = state.profile_dir(name)
    meta_path = pdir / "profile.json"
    if not meta_path.is_file():
        raise KylinPkgError("profile 不存在：%s" % name)
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise KylinPkgError("profile 元数据损坏：%s（%s）" % (meta_path, exc)) from exc


def list_profiles(state: State) -> List[Dict[str, object]]:
    items: List[Dict[str, object]] = []
    if not state.profiles_dir.is_dir():
        return items
    for pdir in sorted(state.profiles_dir.iterdir()):
        meta_path = pdir / "profile.json"
        if not meta_path.is_file():
            continue
        try:
            items.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return items


def bind_baseline(state: State, name: str, baseline: str) -> Dict[str, object]:
    meta = load_profile(state, name)
    if baseline and baseline != baseline_mod.RESERVED_EMPTY:
        bmeta = baseline_mod.load_meta(state, baseline)
        problem = baseline_mod.check_compatible(meta, bmeta)
        if problem:
            raise KylinPkgError(problem)
    meta["baseline"] = baseline or None
    pdir = state.profile_dir(name)
    atomic_write_text(pdir / "profile.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    return meta


def remove_profile(state: State, name: str, purge_roots: bool = False) -> None:
    pdir = state.profile_dir(name)
    if not pdir.exists():
        raise KylinPkgError("profile 不存在：%s" % name)
    shutil.rmtree(str(pdir))
    if purge_roots:
        roots = state.roots_dir / validate_name(name, "profile 名称")
        if roots.exists():
            shutil.rmtree(str(roots))


def profile_sources(state: State, name: str) -> List[deb822.SourceEntry]:
    load_profile(state, name)
    return deb822.collect_sources(state.profile_dir(name))


def check_profile(state: State, name: str) -> List[str]:
    meta = load_profile(state, name)
    pdir = state.profile_dir(name)
    entries = deb822.collect_sources(pdir)
    warnings = list(meta.get("warnings") or [])
    warnings += deb822.validate_sources(entries)
    warnings += _arch_hints(entries, meta.get("architectures") or [])
    return warnings


# ---------------------------------------------------------------------------
# 源配置查看与编辑
# ---------------------------------------------------------------------------

def _is_source_rel(rel: str) -> bool:
    return rel == "sources.list" or rel.startswith("sources.list.d/")


def _is_editable_rel(rel: str) -> bool:
    rel = str(rel).replace("\\", "/").strip()
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        return False
    parts = rel.split("/")
    if len(parts) == 1:
        return parts[0] in ("sources.list", "preferences", "auth.conf")
    if len(parts) != 2:
        return False
    directory, name = parts
    if not name or name.startswith(".") or name.endswith((".bak", ".save", ".disabled", "~")):
        return False
    if directory == "sources.list.d":
        return name.endswith((".list", ".sources"))
    if directory in ("preferences.d", "auth.conf.d"):
        return True
    return False


def _profile_text_path(
    state: State, name: str, rel: str, allow_missing: bool = False
) -> Path:
    pdir = state.profile_dir(name)
    if not (pdir / "profile.json").is_file():
        raise KylinPkgError("profile 不存在：%s" % name)
    rel = str(rel).replace("\\", "/").strip()
    if not _is_editable_rel(rel):
        raise KylinPkgError(
            "该文件不允许编辑：%s（只支持 sources.list、sources.list.d、"
            "preferences、preferences.d、auth.conf、auth.conf.d）" % rel
        )
    path = pdir / rel
    resolved = path.resolve()
    root = pdir.resolve()
    if resolved != root and root not in resolved.parents:
        raise KylinPkgError("文件路径越界：%s" % rel)
    if not allow_missing and not path.is_file():
        raise KylinPkgError("文件不存在：%s" % rel)
    return path


def profile_files(state: State, name: str, include_keyrings: bool = True) -> List[Dict[str, object]]:
    load_profile(state, name)
    pdir = state.profile_dir(name)
    result: List[Dict[str, object]] = []
    for item in _scan_files(pdir):
        rel = str(item["path"])
        editable = _is_editable_rel(rel)
        if not editable and not include_keyrings:
            continue
        result.append(dict(item, editable=editable))
    return result


def read_profile_file(state: State, name: str, rel: str) -> str:
    path = _profile_text_path(state, name, rel)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise KylinPkgError("读取 %s 失败：%s" % (rel, exc)) from exc


def _remaining_sources(pdir: Path, exclude: Path) -> List[deb822.SourceEntry]:
    entries: List[deb822.SourceEntry] = []
    for path in deb822.iter_source_files(pdir):
        if path.resolve() == exclude.resolve():
            continue
        entries.extend(deb822.parse_sources_file(path))
    return entries


def _profile_has_auth(pdir: Path) -> bool:
    conf = pdir / "auth.conf"
    if conf.is_file() and conf.stat().st_size > 0:
        return True
    parts = pdir / "auth.conf.d"
    return parts.is_dir() and any(path.is_file() for path in parts.iterdir())


def refresh_profile_meta(state: State, name: str) -> Dict[str, object]:
    """源/preferences/auth 改动后，重算元数据、警告与索引指纹。"""
    load_profile(state, name)
    materialize_signed_by(state, name)
    meta = load_profile(state, name)
    pdir = state.profile_dir(name)
    entries = deb822.collect_sources(pdir)
    if not entries:
        raise KylinPkgError("编辑后 profile 中没有可用的 apt 源")
    warnings: List[str] = []
    warnings.extend(deb822.validate_sources(entries))
    warnings.extend(_arch_hints(entries, meta.get("architectures") or []))
    warnings.extend(meta.get("notices") or [])
    with_auth = _profile_has_auth(pdir)
    if with_auth:
        warnings.append("profile 包含 apt 凭据（auth.conf），状态目录与备份请妥善保管")
    baseline = meta.get("baseline")
    if baseline:
        try:
            bmeta = baseline_mod.load_meta(state, str(baseline))
            problem = baseline_mod.check_compatible(meta, bmeta)
            if problem:
                warnings.append(problem)
        except KylinPkgError as exc:
            warnings.append("默认 baseline 不可用：%s" % exc)
    # 去重但保持顺序
    warnings = list(dict.fromkeys(warnings))
    meta["files"] = _scan_files(pdir)
    meta["sources_summary"] = [_redacted_summary(entry) for entry in entries]
    meta["warnings"] = warnings
    meta["with_auth"] = with_auth
    atomic_write_text(
        pdir / "profile.json", json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
    )
    return load_profile(state, name)


def write_profile_file(state: State, name: str, rel: str, content: str) -> Dict[str, object]:
    path = _profile_text_path(state, name, rel, allow_missing=True)
    rel = str(rel).replace("\\", "/").strip()
    if _is_source_rel(rel):
        # 先做语法校验；语义（至少一条源）由 refresh_profile_meta 兜底
        deb822.parse_sources_text(content, rel)
    old = path.read_bytes() if path.is_file() else None
    ensure_dir(path.parent, 0o700)
    atomic_write_text(path, content, 0o600)
    try:
        return refresh_profile_meta(state, name)
    except Exception:
        if old is None:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            atomic_write_bytes(path, old, 0o600)
        raise


def delete_profile_file(state: State, name: str, rel: str) -> Dict[str, object]:
    path = _profile_text_path(state, name, rel)
    rel = str(rel).replace("\\", "/").strip()
    pdir = state.profile_dir(name)
    if _is_source_rel(rel):
        if not _remaining_sources(pdir, path):
            raise KylinPkgError("删除该文件后就没有 apt 源了，操作已取消")
    old = path.read_bytes()
    if rel == "sources.list":
        # sources.list 是 apt 的主入口文件，保留空文件而不是删除
        atomic_write_text(path, "", 0o600)
    else:
        path.unlink()
    try:
        return refresh_profile_meta(state, name)
    except Exception:
        atomic_write_bytes(path, old, 0o600)
        raise
