"""把下载目录转换成 apt 可直接使用的扁平离线源。"""

from __future__ import annotations

import gzip
import io
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import deb822
from .manifest import read_manifest, verify_manifest
from .util import KylinPkgError, atomic_write_bytes, atomic_write_text, run, sha256_file


def _packages_index(out_dir: Path) -> bytes:
    debs = out_dir / "debs"
    if not debs.is_dir():
        raise KylinPkgError("没有 debs 目录：%s" % debs)
    if shutil.which("apt-ftparchive"):
        proc = run(["apt-ftparchive", "packages", "debs"], cwd=out_dir, timeout=300)
        return proc.stdout.encode("utf-8")
    if shutil.which("dpkg-scanpackages"):
        proc = run(["dpkg-scanpackages", "-m", "debs", "/dev/null"], cwd=out_dir, timeout=300)
        return proc.stdout.encode("utf-8")
    raise KylinPkgError("需要 apt-ftparchive 或 dpkg-scanpackages 来生成 Packages")


def _gzip_bytes(data: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(data)
    return buf.getvalue()


def _manifest_archs(out_dir: Path) -> str:
    try:
        manifest = read_manifest(out_dir)
    except KylinPkgError:
        return "all"
    archs = []
    for item in manifest.get("packages") or []:
        arch = item.get("architecture")
        if arch and arch not in archs:
            archs.append(arch)
    real = [arch for arch in archs if arch != "all"]
    if real:
        return " ".join(real)
    return " ".join(archs) or "all"


def build_repo(
    out_dir: Path,
    suite: str = "kylinpkg-offline",
    origin: str = "kylinpkg",
    label: str = "kylinpkg offline",
) -> Path:
    out_dir = Path(out_dir).resolve()
    debs = out_dir / "debs"
    if not debs.is_dir():
        raise KylinPkgError("没有 debs 目录：%s" % debs)
    if not any(debs.glob("*.deb")):
        raise KylinPkgError("debs 目录中没有 .deb：%s" % debs)

    index = _packages_index(out_dir)
    atomic_write_bytes(out_dir / "Packages", index, 0o644)
    atomic_write_bytes(out_dir / "Packages.gz", _gzip_bytes(index), 0o644)

    archs = _manifest_archs(out_dir)
    if shutil.which("apt-ftparchive"):
        cmd = [
            "apt-ftparchive",
            "-o",
            "APT::FTPArchive::Release::Suite=%s" % suite,
            "-o",
            "APT::FTPArchive::Release::Origin=%s" % origin,
            "-o",
            "APT::FTPArchive::Release::Label=%s" % label,
            "-o",
            "APT::FTPArchive::Release::Architectures=%s" % archs,
            "release",
            ".",
        ]
        proc = run(cmd, cwd=out_dir, timeout=300)
        atomic_write_bytes(out_dir / "Release", proc.stdout.encode("utf-8"), 0o644)
    else:
        # 极简 Release；apt 对 [trusted=yes] 的本地源不强制要求完整字段
        text = "Origin: %s\nLabel: %s\nSuite: %s\nArchitectures: %s\n" % (
            origin,
            label,
            suite,
            archs,
        )
        atomic_write_text(out_dir / "Release", text, 0o644)

    snippet = (
        "# 在目标机上使用（把路径改成实际拷贝位置）\n"
        "deb [trusted=yes] file:%s ./\n" % str(out_dir)
    )
    atomic_write_text(out_dir / "sources.list", snippet, 0o644)
    return out_dir


def _packages_hashes(out_dir: Path) -> Dict[str, str]:
    path = Path(out_dir) / "Packages"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    result: Dict[str, str] = {}
    for para in deb822.parse_packages_text(text):
        filename = para.get("Filename", "")
        digest = para.get("SHA256", "")
        if filename:
            result[Path(filename).name] = digest
    return result


def verify_repo(out_dir: Path) -> Tuple[List[str], List[str]]:
    out_dir = Path(out_dir).resolve()
    errors, warnings = verify_manifest(out_dir)
    packages_hashes = _packages_hashes(out_dir)
    if not packages_hashes:
        errors.append("缺少 Packages 索引")
    else:
        manifest = read_manifest(out_dir)
        for item in manifest.get("packages") or []:
            name = item.get("filename")
            if not name:
                continue
            if name not in packages_hashes:
                errors.append("Packages 中没有 %s" % name)
            elif packages_hashes[name] != item.get("sha256"):
                errors.append("Packages 中 %s 的 SHA256 与 manifest 不一致" % name)
    if not (out_dir / "Packages.gz").is_file():
        errors.append("缺少 Packages.gz")
    if not (out_dir / "Release").is_file():
        warnings.append("缺少 Release（[trusted=yes] 下通常仍可用）")
    if not (out_dir / "sources.list").is_file():
        warnings.append("缺少 sources.list 片段")
    return errors, warnings


def list_repo(out_dir: Path) -> str:
    manifest = read_manifest(Path(out_dir))
    lines = [
        "profile: %s   架构: %s" % (manifest.get("profile"), ",".join(manifest.get("architectures") or [])),
        "包数: %s   总大小: %s bytes" % (
            (manifest.get("totals") or {}).get("count", 0),
            (manifest.get("totals") or {}).get("bytes", 0),
        ),
    ]
    for item in manifest.get("packages") or []:
        lines.append(
            "  %-28s %-18s %-28s %s"
            % (
                item.get("package", "?"),
                item.get("version", "?"),
                item.get("architecture", "?"),
                item.get("filename", "?"),
            )
        )
    return "\n".join(lines)
