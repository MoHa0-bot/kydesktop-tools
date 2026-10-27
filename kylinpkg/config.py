# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""状态目录布局与文件锁。"""

from __future__ import annotations

import fcntl
import os
import shutil
from pathlib import Path
from typing import Optional

from .util import dir_size, ensure_dir, validate_name

ENV_HOME = "KYLINPKG_HOME"
ENV_OUTPUT = "KYLINPKG_OUTPUT_DIR"


def default_state_dir() -> Path:
    override = os.environ.get(ENV_HOME)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "share" / "kylinpkg"


def default_output_dir(profile: str, arch_key: str) -> Path:
    """默认下载输出目录：/tmp/kylinpkg-out/<profile>-<arch>。"""
    root = Path(os.environ.get(ENV_OUTPUT, "/tmp/kylinpkg-out")).expanduser()
    return root / ("%s-%s" % (profile, arch_key))


class State:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root).expanduser() if root else default_state_dir()
        self.profiles_dir = self.root / "profiles"
        self.baselines_dir = self.root / "baselines"
        self.roots_dir = self.root / "roots"
        self.downloads_dir = self.root / "downloads"
        self.logs_dir = self.root / "logs"

    def ensure(self) -> "State":
        ensure_dir(self.root, 0o700)
        for path in (
            self.profiles_dir,
            self.baselines_dir,
            self.roots_dir,
            self.downloads_dir,
            self.logs_dir,
        ):
            ensure_dir(path, 0o700)
        return self

    def profile_dir(self, name: str) -> Path:
        return self.profiles_dir / validate_name(name, "profile 名称")

    def baseline_dir(self, name: str) -> Path:
        return self.baselines_dir / validate_name(name, "baseline 名称")

    def root_dir(self, profile: str, arch_key: str) -> Path:
        return self.roots_dir / validate_name(profile, "profile 名称") / arch_key

    def output_dir(self, profile: str, arch_key: str) -> Path:
        return self.downloads_dir / ("%s-%s" % (profile, arch_key))

    def cache_size(self, profile: Optional[str] = None) -> int:
        """隔离 root 中可重建的索引/包缓存大小。"""
        target = self.roots_dir
        if profile:
            target = target / validate_name(profile, "profile 名称")
        return dir_size(target)

    def clear_cache(self, profile: Optional[str] = None) -> int:
        """删除隔离 root 缓存并返回释放字节数；不会动 profile/baseline。"""
        target = self.roots_dir
        if profile:
            target = target / validate_name(profile, "profile 名称")
        freed = dir_size(target)
        if target.exists():
            shutil.rmtree(str(target))
        if profile is None:
            ensure_dir(self.roots_dir, 0o700)
        return freed


class FileLock:
    """基于 flock 的进程锁；同一 root 上不允许并发 apt。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._fh = None

    def __enter__(self) -> "FileLock":
        ensure_dir(self.path.parent, 0o700)
        self._fh = open(self.path, "a+")
        fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fh is not None:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None
