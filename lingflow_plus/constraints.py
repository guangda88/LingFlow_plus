"""约束层

TokenQuota、RateLimiter、FileLock、ContextBudget 四大约束。
确保多项目并行执行时的资源安全。
"""

import fcntl
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LOCKS_DIR = Path.home() / ".lingflow-plus" / "locks"
STATE_PATH = Path.home() / ".lingflow-plus" / "state.json"


@dataclass
class TokenBudget:
    """单项目 token 预算"""
    project: str
    allocated: int = 0
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.allocated - self.used)

    @property
    def usage_ratio(self) -> float:
        return self.used / self.allocated if self.allocated > 0 else 0.0


class TokenQuotaManager:
    """GLM API Token 配额管理器

    跟踪 5 小时窗口内的 token 消耗，按项目分配预算。
    """

    def __init__(self, window_tokens: int = 5_000_000, window_seconds: int = 18000):
        self.window_tokens = window_tokens
        self.window_seconds = window_seconds
        self._budgets: Dict[str, TokenBudget] = {}
        self._lock = Lock()
        self._window_start = time.time()
        self._total_used = 0

    def allocate(self, project: str, tokens: int) -> TokenBudget:
        """为项目分配 token 预算"""
        with self._lock:
            self._check_window_reset()
            budget = TokenBudget(project=project, allocated=tokens)
            self._budgets[project] = budget
            logger.info(f"Allocated {tokens} tokens for {project}")
            return budget

    def consume(self, project: str, tokens: int) -> bool:
        """消耗 token，返回是否成功（超预算返回 False）"""
        with self._lock:
            self._check_window_reset()
            budget = self._budgets.get(project)
            if not budget:
                logger.warning(f"No budget for project {project}")
                return False
            if budget.remaining < tokens:
                logger.warning(f"Token budget exhausted for {project}: {budget.remaining} < {tokens}")
                return False
            budget.used += tokens
            self._total_used += tokens
            return True

    def get_status(self) -> Dict[str, Any]:
        """获取配额状态"""
        with self._lock:
            self._check_window_reset()
            return {
                "window_total": self.window_tokens,
                "window_used": self._total_used,
                "window_remaining": self.window_tokens - self._total_used,
                "window_elapsed": round(time.time() - self._window_start, 1),
                "projects": {name: {"allocated": b.allocated, "used": b.used, "remaining": b.remaining}
                             for name, b in self._budgets.items()},
            }

    def _check_window_reset(self) -> None:
        """检查是否需要重置窗口"""
        if time.time() - self._window_start >= self.window_seconds:
            self._window_start = time.time()
            self._total_used = 0
            for budget in self._budgets.values():
                budget.used = 0


class RateLimiter:
    """请求速率限制器

    指数退避 + 滑动窗口。
    """

    def __init__(self, max_rpm: int = 60, max_concurrent: int = 5):
        self.max_rpm = max_rpm
        self.max_concurrent = max_concurrent
        self._timestamps: List[float] = []
        self._active = 0
        self._lock = Lock()
        self._backoff_until: float = 0

    def acquire(self) -> float:
        """获取执行许可，返回需要等待的秒数"""
        with self._lock:
            now = time.time()
            if now < self._backoff_until:
                return self._backoff_until - now

            self._timestamps = [t for t in self._timestamps if now - t < 60]
            if len(self._timestamps) >= self.max_rpm:
                wait = 60 - (now - self._timestamps[0]) + 0.1
                return wait

            if self._active >= self.max_concurrent:
                return 0.5

            self._timestamps.append(now)
            self._active += 1
            return 0.0

    def release(self) -> None:
        """释放执行许可"""
        with self._lock:
            self._active = max(0, self._active - 1)

    def trigger_backoff(self, seconds: float = 30.0) -> None:
        """触发退避（如收到 429 响应）"""
        with self._lock:
            self._backoff_until = time.time() + seconds
            logger.warning(f"Rate limiter backoff triggered: {seconds}s")

    def get_status(self) -> Dict[str, Any]:
        """获取速率状态"""
        with self._lock:
            now = time.time()
            recent = [t for t in self._timestamps if now - t < 60]
            return {
                "rpm_used": len(recent),
                "rpm_limit": self.max_rpm,
                "active_requests": self._active,
                "max_concurrent": self.max_concurrent,
                "backoff_remaining": max(0, self._backoff_until - now),
            }


class FileLock:
    """基于 fcntl.flock 的文件级互斥锁

    用于防止多个进程同时修改同一文件。
    """

    def __init__(self, locks_dir: Optional[str] = None):
        self._locks_dir = Path(locks_dir) if locks_dir else LOCKS_DIR
        self._locks_dir.mkdir(parents=True, exist_ok=True)
        self._fd_map: Dict[str, Any] = {}

    def acquire(self, filepath: str, timeout: float = 30.0) -> bool:
        """获取文件锁"""
        lock_path = str(self._locks_dir / _safe_lock_name(filepath))
        start = time.time()
        while time.time() - start < timeout:
            try:
                fd = open(lock_path, "w")
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fd_map[filepath] = fd
                return True
            except (IOError, OSError):
                try:
                    fd.close()
                except Exception:
                    pass
                time.sleep(0.1)
        logger.warning(f"FileLock timeout for {filepath}")
        return False

    def release(self, filepath: str) -> None:
        """释放文件锁"""
        fd = self._fd_map.pop(filepath, None)
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                fd.close()
            except (IOError, OSError):
                pass

    def is_locked(self, filepath: str) -> bool:
        """检查文件是否被锁"""
        lock_path = str(self._locks_dir / _safe_lock_name(filepath))
        try:
            fd = open(lock_path, "w")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            fd.close()
            return False
        except (IOError, OSError):
            try:
                fd.close()
            except Exception:
                pass
            return True


class ContextBudget:
    """项目上下文预算管理

    每个项目有独立上下文预算，超限时自动触发压缩。
    """

    def __init__(self, default_limit: int = 8000, compress_threshold: float = 0.85):
        self.default_limit = default_limit
        self.compress_threshold = compress_threshold
        self._limits: Dict[str, int] = {}
        self._usage: Dict[str, int] = {}

    def set_limit(self, project: str, limit: int) -> None:
        """设置项目上下文限制"""
        self._limits[project] = limit

    def get_limit(self, project: str) -> int:
        """获取项目上下文限制"""
        return self._limits.get(project, self.default_limit)

    def track(self, project: str, tokens: int) -> None:
        """记录 token 消耗"""
        self._usage[project] = self._usage.get(project, 0) + tokens

    def should_compress(self, project: str) -> bool:
        """是否需要压缩上下文"""
        usage = self._usage.get(project, 0)
        limit = self.get_limit(project)
        return usage >= limit * self.compress_threshold

    def reset(self, project: str) -> None:
        """重置项目上下文使用量"""
        self._usage[project] = 0

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有项目上下文状态"""
        result = {}
        for project in set(list(self._limits.keys()) + list(self._usage.keys())):
            limit = self.get_limit(project)
            used = self._usage.get(project, 0)
            result[project] = {
                "limit": limit,
                "used": used,
                "remaining": max(0, limit - used),
                "usage_ratio": round(used / limit, 3) if limit > 0 else 0,
                "should_compress": used >= limit * self.compress_threshold,
            }
        return result


def _safe_lock_name(filepath: str) -> str:
    """将文件路径转换为安全的锁文件名"""
    import hashlib
    return hashlib.md5(filepath.encode()).hexdigest() + ".lock"
