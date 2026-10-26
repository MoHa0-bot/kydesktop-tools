"""隔离的 apt root：准备目录、拼装 apt 参数、执行 update。"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import baseline as baseline_mod
from . import profile as profile_mod
from .arch import arch_key, normalize_arch_set
from .config import FileLock, State
from .util import CancelToken, CommandError, KylinPkgError, ensure_dir, run, sha256_file

_UPDATE_STAMP = ".last-update"
_FINGERPRINT_STAMP = ".profile-fingerprint"
_UPDATE_MAX_AGE = 12 * 3600


class AptRoot:
    def __init__(
        self,
        state: State,
        profile_name: str,
        architectures: Optional[Sequence[str]] = None,
        baseline_name: Optional[str] = None,
        cancel: Optional[CancelToken] = None,
    ):
        self.state = state
        self.cancel = cancel
        self.profile_name = profile_name
        self.profile_meta = profile_mod.load_profile(state, profile_name)
        self.profile_dir = state.profile_dir(profile_name)
        if architectures:
            self.architectures = normalize_arch_set(architectures)
        else:
            self.architectures = normalize_arch_set(self.profile_meta.get("architectures") or [])
        self.baseline_name = baseline_name or self.profile_meta.get("baseline") or baseline_mod.RESERVED_EMPTY
        self.baseline_meta = baseline_mod.load_meta(state, self.baseline_name)
        problem = baseline_mod.check_compatible(
            {"architectures": list(self.architectures)}, self.baseline_meta
        )
        if problem:
            raise KylinPkgError(problem)
        key = arch_key(self.architectures)
        self.key = key
        self.root = state.root_dir(profile_name, key)
        self.lists_dir = self.root / "var" / "lib" / "apt" / "lists"
        self.archives_dir = self.root / "var" / "cache" / "apt" / "archives"
        self.status_path = self.root / "var" / "lib" / "dpkg" / "status"
        self.log_dir = self.root / "var" / "log" / "apt"

    def prepare(self, force_lists: bool = False) -> None:
        ensure_dir(self.root, 0o700)
        ensure_dir(self.lists_dir / "partial", 0o700)
        ensure_dir(self.archives_dir / "partial", 0o700)
        ensure_dir(self.status_path.parent, 0o700)
        ensure_dir(self.root / "etc" / "apt" / "apt.conf.d", 0o700)
        ensure_dir(self.log_dir, 0o700)
        if force_lists and self.lists_dir.is_dir():
            for path in self.lists_dir.iterdir():
                if path.name == "partial":
                    continue
                if path.is_dir():
                    shutil.rmtree(str(path))
                else:
                    path.unlink()
        self._prepare_status()

    def _prepare_status(self) -> None:
        source = baseline_mod.status_path(self.state, self.baseline_name)
        desired = source.read_bytes() if source is not None else b""
        current = self.status_path.read_bytes() if self.status_path.is_file() else None
        if current == desired:
            return
        ensure_dir(self.status_path.parent, 0o700)
        self.status_path.write_bytes(desired)
        os.chmod(self.status_path, 0o600)
        for name in ("pkgcache.bin", "srcpkgcache.bin"):
            path = self.root / "var" / "cache" / "apt" / name
            if path.exists():
                path.unlink()

    def _trusted_options(self) -> List[str]:
        opts: List[str] = []
        keyring = self.profile_dir / "keyrings" / "trusted.gpg"
        parts = self.profile_dir / "keyrings" / "trusted.gpg.d"
        no_system = (self.profile_dir / "keyrings" / ".no-system-keys").exists()
        host_keyring = Path("/etc/apt/trusted.gpg")
        host_parts = Path("/etc/apt/trusted.gpg.d")
        chosen_keyring: Optional[Path] = None
        if keyring.is_file():
            chosen_keyring = keyring
        elif not no_system and host_keyring.is_file():
            chosen_keyring = host_keyring
        if chosen_keyring is not None:
            opts.extend(["-o", "Dir::Etc::trusted=%s" % chosen_keyring])
        if parts.is_dir():
            opts.extend(["-o", "Dir::Etc::trustedparts=%s" % parts])
        elif not no_system and host_parts.is_dir():
            opts.extend(["-o", "Dir::Etc::trustedparts=%s" % host_parts])
        return opts

    def _auth_options(self) -> List[str]:
        conf = self.profile_dir / "auth.conf"
        parts = self.profile_dir / "auth.conf.d"
        has_parts = parts.is_dir() and any(p.is_file() for p in parts.iterdir())
        has_conf = conf.is_file() and conf.stat().st_size > 0
        if not has_conf and not has_parts:
            return []
        return [
            "-o",
            "Dir::Etc::netrc=%s" % conf,
            "-o",
            "Dir::Etc::netrcparts=%s" % parts,
        ]

    def apt_options(self, archives_dir: Optional[Path] = None) -> List[str]:
        opts: List[str] = [
            "-o", "Dir=%s" % self.root,
            "-o", "Dir::State::status=%s" % self.status_path,
            "-o", "Dir::Etc::sourcelist=%s" % (self.profile_dir / "sources.list"),
            "-o", "Dir::Etc::sourceparts=%s" % (self.profile_dir / "sources.list.d"),
            "-o", "Dir::Etc::preferences=%s" % (self.profile_dir / "preferences"),
            "-o", "Dir::Etc::preferencesparts=%s" % (self.profile_dir / "preferences.d"),
            "-o", "Dir::Etc::parts=%s" % (self.root / "etc" / "apt" / "apt.conf.d"),
            "-o", "APT::Architecture=%s" % self.architectures[0],
            "-o", "Acquire::Languages=none",
            "-o", "Acquire::Retries=3",
            "-o", "Acquire::http::Timeout=30",
            "-o", "Acquire::https::Timeout=30",
            # 国内网络里 IPv6 路由不稳时 apt 可能长时间卡住；默认走 IPv4。
            # 纯 IPv6 环境可在 profile.json 的 apt_options 里覆盖为 false。
            "-o", "Acquire::ForceIPv4=true",
            "-o", "APT::Color=0",
        ]
        for arch in self.architectures:
            opts.extend(["-o", "APT::Architectures::=%s" % arch])
        opts.extend(self._trusted_options())
        opts.extend(self._auth_options())
        if os.geteuid() == 0:
            opts.extend(["-o", "APT::Sandbox::User=root"])
        apt_options = self.profile_meta.get("apt_options") or {}
        if isinstance(apt_options, dict):
            for key, value in apt_options.items():
                opts.extend(["-o", "%s=%s" % (key, value)])
        if archives_dir is not None:
            ensure_dir(Path(archives_dir) / "partial", 0o700)
            opts.extend(["-o", "Dir::Cache::archives=%s/" % Path(archives_dir)])
        return opts

    def lock(self) -> FileLock:
        return FileLock(self.root / ".lock")

    def is_fresh(self, max_age: int = _UPDATE_MAX_AGE) -> bool:
        stamp = self.root / _UPDATE_STAMP
        if not stamp.is_file():
            return False
        try:
            age = time.time() - stamp.stat().st_mtime
        except OSError:
            return False
        if age > max_age:
            return False
        if not self.lists_dir.is_dir():
            return False
        if not any(p.name.endswith("_Packages") for p in self.lists_dir.iterdir() if p.is_file()):
            return False
        fingerprint_stamp = self.root / _FINGERPRINT_STAMP
        if not fingerprint_stamp.is_file():
            return False
        try:
            current = fingerprint_stamp.read_text(encoding="utf-8").strip()
            expected = profile_mod.fingerprint(self.state, self.profile_name)
        except (OSError, KylinPkgError):
            return False
        return current == expected

    def update(self, force: bool = False, no_update: bool = False) -> str:
        with self.lock():
            if self.cancel is not None:
                self.cancel.check()
            self.prepare(force_lists=force)
            if no_update:
                if not self.is_fresh(max_age=10**9):
                    raise KylinPkgError(
                        "指定了 --no-update，但隔离 root 的索引缺失或源配置已变化；"
                        "请先执行 kylinpkg update -p %s" % self.profile_name
                    )
                return ""
            if not force and self.is_fresh():
                return ""
            cmd = ["apt-get"] + self.apt_options() + ["update"]
            try:
                proc = run(cmd, timeout=900, cancel=self.cancel)
            except CommandError as exc:
                raise KylinPkgError("apt-get update 失败：\n%s" % exc.detail()) from exc
            stamp = self.root / _UPDATE_STAMP
            stamp.write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n", encoding="utf-8")
            os.chmod(stamp, 0o600)
            fp_stamp = self.root / _FINGERPRINT_STAMP
            fp_stamp.write_text(
                profile_mod.fingerprint(self.state, self.profile_name) + "\n", encoding="utf-8"
            )
            os.chmod(fp_stamp, 0o600)
            extra = ("\n" + proc.stderr) if proc.stderr.strip() else ""
            return proc.stdout + extra

    def run_tool(
        self,
        tool: str,
        args: Sequence[str],
        timeout: int = 120,
        env_extra: Optional[dict] = None,
    ) -> str:
        cmd = [tool] + self.apt_options() + list(args)
        with self.lock():
            if self.cancel is not None:
                self.cancel.check()
            self.prepare()
            try:
                proc = run(
                    cmd,
                    timeout=timeout,
                    cancel=self.cancel,
                    env_extra=env_extra,
                )
            except CommandError as exc:
                raise KylinPkgError("%s 失败：\n%s" % (tool, exc.detail())) from exc
            extra = ("\n" + proc.stderr) if proc.stderr.strip() else ""
            return proc.stdout + extra

    def run_apt(
        self,
        args: Sequence[str],
        timeout: int = 600,
        extra_options: Sequence[str] = (),
        cwd: Optional[Path] = None,
    ) -> str:
        cmd = ["apt-get"] + self.apt_options() + list(extra_options) + list(args)
        with self.lock():
            if self.cancel is not None:
                self.cancel.check()
            self.prepare()
            try:
                proc = run(cmd, timeout=timeout, cancel=self.cancel, cwd=cwd)
            except CommandError as exc:
                raise KylinPkgError("apt-get 失败：\n%s" % exc.detail()) from exc
            extra = ("\n" + proc.stderr) if proc.stderr.strip() else ""
            return proc.stdout + extra

    def baseline_info(self) -> Dict[str, object]:
        return {
            "name": self.baseline_name,
            "mode": "full" if self.baseline_name == baseline_mod.RESERVED_EMPTY else "delta",
            "installed_count": self.baseline_meta.get("installed_count", 0),
            "status_sha256": self.baseline_meta.get("status_sha256", ""),
        }

    def root_info(self) -> Dict[str, object]:
        return {
            "root": str(self.root),
            "profile": self.profile_name,
            "architectures": list(self.architectures),
            "baseline": self.baseline_name,
        }
