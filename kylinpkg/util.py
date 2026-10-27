# SPDX-License-Identifier: MIT
# Copyright (c) 2026 mohao
"""通用工具：错误类型、命令执行、哈希、原子写、文件复制。"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
import shlex
import shutil
import signal
import subprocess
import threading
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit


class KylinPkgError(Exception):
    """可向用户直接展示的错误。"""


class CommandError(KylinPkgError):
    def __init__(self, cmd: Sequence[str], returncode: int, stdout: str = "", stderr: str = ""):
        self.cmd = list(cmd)
        self.returncode = returncode
        self.stdout = stdout or ""
        self.stderr = stderr or ""
        super().__init__(self.detail())

    def detail(self) -> str:
        out = (self.stderr or self.stdout).strip()
        if not out:
            out = "命令执行失败（退出码 %d）" % self.returncode
        return out


class OperationCancelled(KylinPkgError):
    """用户主动中断了当前操作。"""


def _kill_process(proc: subprocess.Popen, kill_group: bool) -> None:
    try:
        if kill_group and os.name == "posix":
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except Exception:
            pass


class CancelToken:
    """跨线程中断令牌；取消时会终止已注册的子进程。

    run() 在带 cancel 时会启动新会话（进程组），取消/超时时先 SIGTERM
    整个组，2 秒后仍在则 SIGKILL，避免 apt 的子 methods 残留。
    """

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._procs: List[Tuple[subprocess.Popen, bool]] = []

    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self._event.is_set():
            raise OperationCancelled("操作已中断")

    def cancel(self) -> None:
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            procs = list(self._procs)
        for proc, kill_group in procs:
            self._terminate(proc, kill_group)

    def register(self, proc: subprocess.Popen, kill_group: bool = False) -> None:
        with self._lock:
            if not self._event.is_set():
                self._procs.append((proc, kill_group))
                return
        self._terminate(proc, kill_group)

    def unregister(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs = [(item, group) for item, group in self._procs if item is not proc]

    @staticmethod
    def _terminate(proc: subprocess.Popen, kill_group: bool) -> None:
        if proc.poll() is not None:
            return
        try:
            if kill_group and os.name == "posix":
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            else:
                proc.terminate()
        except (ProcessLookupError, PermissionError, OSError):
            try:
                proc.terminate()
            except Exception:
                pass

        def force() -> None:
            if proc.poll() is None:
                _kill_process(proc, kill_group)

        timer = threading.Timer(2.0, force)
        timer.daemon = True
        timer.start()


def iso_now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def human_size(num: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(num) < 1024.0 or unit == "TiB":
            if unit == "B":
                return "%d %s" % (num, unit)
            return "%.1f %s" % (num, unit)
        num /= 1024.0
    return "%.1f TiB" % num


def dir_size(path: Path) -> int:
    """统计目录内普通文件大小（不跟随符号链接）。"""
    path = Path(path)
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            pass
    return total


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_file(path: Path, algorithm: str) -> str:
    algorithm = algorithm.lower().replace("-", "")
    if algorithm in ("md5", "md5sum"):
        algorithm = "md5"
    elif algorithm in ("sha256", "sha256sum"):
        algorithm = "sha256"
    elif algorithm in ("sha1", "sha1sum"):
        algorithm = "sha1"
    elif algorithm in ("sha512", "sha512sum"):
        algorithm = "sha512"
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path, mode: int = 0o700) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, mode)
    except OSError:
        pass
    return path


def atomic_write_bytes(path: Path, data: bytes, mode: int = 0o600) -> None:
    path = Path(path)
    ensure_dir(path.parent, 0o700)
    tmp = path.with_name(path.name + ".tmp.%d" % os.getpid())
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str, mode: int = 0o600) -> None:
    atomic_write_bytes(path, text.encode("utf-8"), mode)


def copy_file(src: Path, dst: Path, mode: Optional[int] = 0o600) -> None:
    """复制文件并解引用符号链接。"""
    src = Path(src)
    dst = Path(dst)
    ensure_dir(dst.parent, 0o700)
    tmp = dst.with_name(dst.name + ".tmp.%d" % os.getpid())
    shutil.copyfile(str(src), str(tmp))
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, dst)


def run(
    cmd: Sequence[str],
    check: bool = True,
    timeout: Optional[int] = None,
    input_text: Optional[str] = None,
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
    cancel: Optional[CancelToken] = None,
) -> subprocess.CompletedProcess:
    if cancel is not None:
        cancel.check()
    env = os.environ.copy()
    env.setdefault("DEBIAN_FRONTEND", "noninteractive")
    env.setdefault("APT_LISTCHANGES_FRONTEND", "none")
    if env_extra:
        env.update(env_extra)
    kill_group = bool(cancel is not None and os.name == "posix")
    stdin = subprocess.PIPE if input_text is not None else subprocess.DEVNULL
    try:
        proc = subprocess.Popen(
            [str(x) for x in cmd],
            stdin=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            cwd=str(cwd) if cwd else None,
            env=env,
            start_new_session=kill_group,
        )
    except FileNotFoundError as exc:
        raise KylinPkgError("找不到命令：%s" % cmd[0]) from exc
    if cancel is not None:
        cancel.register(proc, kill_group=kill_group)
    try:
        try:
            stdout, stderr = proc.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _kill_process(proc, kill_group)
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            raise KylinPkgError(
                "命令超时（%ss）：%s" % (timeout, " ".join(map(str, cmd)))
            ) from exc
        except KeyboardInterrupt:
            _kill_process(proc, kill_group)
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            raise
    finally:
        if cancel is not None:
            cancel.unregister(proc)
    if cancel is not None and cancel.cancelled():
        raise OperationCancelled("操作已中断")
    if check and proc.returncode != 0:
        raise CommandError(cmd, proc.returncode, stdout, stderr)
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def require_commands(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise KylinPkgError("缺少必需命令：%s" % ", ".join(missing))


def redact_uri(uri: str) -> str:
    """隐藏 URI 中的密码，用于日志/展示。"""
    try:
        parts = urlsplit(uri)
    except ValueError:
        return uri
    if not parts.password:
        return uri
    netloc = parts.hostname or ""
    if parts.username:
        netloc = parts.username + ":***@" + netloc
    if parts.port:
        netloc += ":%d" % parts.port
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_name(name: str, what: str = "名称") -> str:
    if not _SAFE_NAME_RE.match(name or ""):
        raise KylinPkgError(
            "%s不合法：%r（只允许字母、数字、点、下划线、短横线，且不能以符号开头）"
            % (what, name)
        )
    return name


def shell_join(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(x)) for x in cmd)
