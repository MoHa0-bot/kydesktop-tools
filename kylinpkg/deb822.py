"""Deb822 风格文本解析：dpkg status / Packages / sources.list(.d)。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from .arch import normalize_arch
from .util import KylinPkgError

_ONE_LINE_RE = re.compile(
    r"^(?P<type>deb|deb-src)\s+"
    r"(?:\[(?P<opts>[^\]]*)\]\s+)?"
    r"(?P<uri>\S+)\s+"
    r"(?P<suite>\S+)"
    r"(?:\s+(?P<components>.*?))?\s*$"
)


class Deb822Error(KylinPkgError):
    pass


def parse_paragraphs(text: str, allow_comments: bool = False) -> List[Dict[str, str]]:
    """解析以空行分隔的 RFC822 段落；续行以空白开头。"""
    paragraphs: List[Dict[str, str]] = []
    current: Dict[str, str] = {}
    last_key: Optional[str] = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r")
        if allow_comments and line.lstrip().startswith("#"):
            continue
        if not line.strip():
            if current:
                paragraphs.append(current)
                current = {}
                last_key = None
            continue
        if line[0] in " \t":
            if last_key is None:
                raise Deb822Error("第 %d 行：续行前没有字段" % lineno)
            current[last_key] = current[last_key] + "\n" + line.strip()
            continue
        if ":" not in line:
            raise Deb822Error("第 %d 行不是合法的 Deb822 字段：%s" % (lineno, line[:120]))
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            raise Deb822Error("第 %d 行：字段名为空" % lineno)
        current[key] = value.strip()
        last_key = key
    if current:
        paragraphs.append(current)
    return paragraphs


def parse_status_text(text: str) -> List[Dict[str, str]]:
    return parse_paragraphs(text, allow_comments=False)


def status_records(paragraphs: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    records = []
    for para in paragraphs:
        name = para.get("Package", "").strip()
        version = para.get("Version", "").strip()
        arch = para.get("Architecture", "").strip() or "all"
        status = para.get("Status", "").strip()
        installed = bool(status) and status.split()[-1] == "installed"
        if not name:
            continue
        records.append(
            {
                "package": name,
                "version": version,
                "architecture": arch,
                "status": status,
                "installed": installed,
            }
        )
    return records


def status_summary(paragraphs: List[Dict[str, str]]) -> Dict[str, object]:
    records = status_records(paragraphs)
    installed = [r for r in records if r["installed"]]
    arches = []
    for rec in installed:
        arch = rec["architecture"]
        if arch and arch != "all" and arch not in arches:
            arches.append(arch)
    duplicates = []
    seen = set()
    for rec in installed:
        key = (rec["package"], rec["architecture"])
        if key in seen:
            duplicates.append(key)
        seen.add(key)
    return {
        "package_count": len(records),
        "installed_count": len(installed),
        "architectures": arches,
        "duplicates": duplicates,
    }


def installed_version_map(paragraphs: List[Dict[str, str]]) -> Dict[Tuple[str, str], str]:
    result: Dict[Tuple[str, str], str] = {}
    for rec in status_records(paragraphs):
        if not rec["installed"]:
            continue
        result[(rec["package"], rec["architecture"])] = rec["version"]
    return result


@dataclass
class SourceEntry:
    types: List[str]
    uri: str
    suites: List[str]
    components: List[str]
    architectures: List[str] = field(default_factory=list)
    options: Dict[str, str] = field(default_factory=dict)
    signed_by: List[str] = field(default_factory=list)
    source_file: str = ""
    line: int = 0
    enabled: bool = True

    def describe(self) -> str:
        opts = ""
        if self.options:
            opts = " [" + " ".join("%s=%s" % (k, v) for k, v in self.options.items()) + "]"
        return "%s%s %s %s %s" % (
            "/".join(self.types),
            opts,
            self.uri,
            " ".join(self.suites),
            " ".join(self.components),
        )


def _parse_options(text: str) -> Dict[str, str]:
    import shlex

    options: Dict[str, str] = {}
    try:
        tokens = shlex.split(text)
    except ValueError as exc:
        raise Deb822Error("源选项解析失败：%s" % exc) from exc
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            options[key.strip()] = value.strip()
        else:
            options[token.strip()] = ""
    return options


def _split_words(value: str) -> List[str]:
    return [item for item in re.split(r"[\s,]+", value.strip()) if item]


def _parse_one_line(text: str, source_file: str) -> List[SourceEntry]:
    entries: List[SourceEntry] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _ONE_LINE_RE.match(line)
        if not match:
            raise Deb822Error("%s:%d 无法解析的源行：%s" % (source_file, lineno, line[:160]))
        options = _parse_options(match.group("opts") or "")
        archs: List[str] = []
        for key in ("arch", "arch+="):
            if options.get(key):
                for item in _split_words(options[key]):
                    try:
                        arch = normalize_arch(item)
                    except KylinPkgError:
                        arch = item
                    if arch not in archs:
                        archs.append(arch)
        signed_by = _split_words(options.get("signed-by", ""))
        components = _split_words(match.group("components") or "")
        entries.append(
            SourceEntry(
                types=[match.group("type")],
                uri=match.group("uri"),
                suites=[match.group("suite")],
                components=components,
                architectures=archs,
                options=options,
                signed_by=signed_by,
                source_file=source_file,
                line=lineno,
            )
        )
    return entries


def _parse_deb822(text: str, source_file: str) -> List[SourceEntry]:
    entries: List[SourceEntry] = []
    for index, para in enumerate(parse_paragraphs(text, allow_comments=True), 1):
        enabled = para.get("Enabled", "yes").strip().lower() not in ("no", "false", "0")
        types = _split_words(para.get("Types", "deb"))
        uris = _split_words(para.get("URIs", ""))
        suites = _split_words(para.get("Suites", ""))
        components = _split_words(para.get("Components", ""))
        archs = []
        for item in _split_words(para.get("Architectures", "")):
            try:
                arch = normalize_arch(item)
            except KylinPkgError:
                arch = item
            if arch not in archs:
                archs.append(arch)
        signed_by = _split_words(para.get("Signed-By", ""))
        options: Dict[str, str] = {}
        if para.get("Trusted"):
            options["trusted"] = para["Trusted"].strip()
        if para.get("Comment"):
            options["comment"] = para["Comment"].strip()
        for uri in uris:
            entries.append(
                SourceEntry(
                    types=types or ["deb"],
                    uri=uri,
                    suites=suites,
                    components=components,
                    architectures=archs,
                    options=options,
                    signed_by=signed_by,
                    source_file=source_file,
                    line=index,
                    enabled=enabled,
                )
            )
    return entries


def looks_like_deb822(text: str) -> bool:
    markers = (
        "Types:",
        "URIs:",
        "Suites:",
        "Components:",
        "Architectures:",
        "Signed-By:",
        "Enabled:",
    )
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(markers):
            return True
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9-]*:", line):
            # 其他 Deb822 字段（如 X-Repolib-Name），继续往后找关键字段
            continue
        if not raw[:1].isspace():
            # 出现 deb ... 这类一行式源
            return False
    return False


def parse_sources_text(text: str, source_file: str = "<memory>") -> List[SourceEntry]:
    if looks_like_deb822(text):
        return _parse_deb822(text, source_file)
    return _parse_one_line(text, source_file)


def parse_sources_file(path: Path) -> List[SourceEntry]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise Deb822Error("无法读取源文件 %s：%s" % (path, exc)) from exc
    return parse_sources_text(text, str(path))


def iter_source_files(apt_dir: Path) -> List[Path]:
    apt_dir = Path(apt_dir)
    files: List[Path] = []
    main = apt_dir / "sources.list"
    if main.is_file():
        files.append(main)
    parts = apt_dir / "sources.list.d"
    if parts.is_dir():
        for path in sorted(parts.iterdir()):
            if not path.is_file():
                continue
            name = path.name
            if name.startswith(".") or name.endswith((".bak", ".save", ".disabled", "~")):
                continue
            if name.endswith((".list", ".sources")):
                files.append(path)
    return files


def collect_sources(apt_dir: Path) -> List[SourceEntry]:
    entries: List[SourceEntry] = []
    for path in iter_source_files(apt_dir):
        entries.extend(parse_sources_file(path))
    return [entry for entry in entries if entry.enabled]


def source_architectures(entries: Iterable[SourceEntry]) -> List[str]:
    archs: List[str] = []
    for entry in entries:
        for arch in entry.architectures:
            if arch not in archs:
                archs.append(arch)
    return archs


def validate_sources(entries: Iterable[SourceEntry]) -> List[str]:
    """返回告警列表；不抛异常。"""
    warnings: List[str] = []
    seen = set()
    for entry in entries:
        if not entry.enabled:
            continue
        if not entry.uri:
            warnings.append("%s:%s 源缺少 URI" % (entry.source_file, entry.line))
            continue
        if not entry.suites:
            warnings.append("%s:%s 源缺少 suite" % (entry.source_file, entry.line))
        for suite in entry.suites:
            for component in entry.components or [""]:
                key = (entry.uri, suite, component)
                if key in seen:
                    warnings.append("重复的源：%s %s %s" % (entry.uri, suite, component))
                seen.add(key)
        parts = urlsplit(entry.uri)
        if parts.scheme == "file":
            path = Path(unquote(parts.path))
            if not path.exists():
                warnings.append("file: 源路径不存在：%s" % path)
        inline_key = any(item.startswith("-----BEGIN") for item in entry.signed_by)
        if not inline_key:
            for signed in entry.signed_by:
                if "/" in signed or signed.endswith((".gpg", ".asc", ".key")):
                    if not Path(signed).exists():
                        warnings.append("Signed-By 指定的 keyring 不存在：%s" % signed)
    return warnings


def parse_packages_text(text: str) -> List[Dict[str, str]]:
    return parse_paragraphs(text, allow_comments=False)
