import json
import time
import threading
import os
import sys
from pathlib import Path
from typing import Optional

# ============================================================
# 跨平台文件锁（解决 pytest-xdist 多进程并发写同一 JSON 的问题）
# Windows 用 msvcrt.locking，Linux/macOS 用 fcntl.flock
# 用独立的 .lock 辅助文件，避免 msvcrt.locking 锁数据文件后 ftruncate 导致锁隐式释放
# ============================================================
class _FileLock:
    """跨平台文件锁，用独立的 .lock 辅助文件"""

    def __init__(self, path: Path):
        self._lock_path = Path(str(path) + ".lock")
        self._fd = None

    def __enter__(self):
        self._fd = os.open(str(self._lock_path), os.O_RDWR | os.O_CREAT)
        if sys.platform.startswith("win"):
            import msvcrt
            msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        try:
            if self._fd is None:
                return
            if sys.platform.startswith("win"):
                import msvcrt
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None


# 存储路径
TOKEN_CACHE_DIR = Path(__file__).resolve().parent.parent / "reports" / "cache"
TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_CACHE_FILE = TOKEN_CACHE_DIR / ".token_cache.json"
TOKEN_POOL_FILE = TOKEN_CACHE_DIR / ".token_pool.json"
TOKEN_EXPIRY_SECONDS = 3600

# 单账号缓存的模块级可重入锁
_cache_lock = threading.RLock()


# ============================================================
# 单账号缓存（conftest.py 在用）
# 线程 RLock（进程内） + _FileLock（跨进程） → 双重保护
# ============================================================

def save_token_to_cache(token: str, expiry: int = None):
    """保存单账号 token 到文件缓存（线程+进程安全）"""
    expiry = expiry or TOKEN_EXPIRY_SECONDS
    data = {
        "token": token,
        "saved_at": time.time(),
        "expires_at": time.time() + expiry,
    }
    with _cache_lock:
        with _FileLock(TOKEN_CACHE_FILE):
            TOKEN_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_token_from_cache() -> Optional[str]:
    """读取缓存 token，过期/损坏自动删除并返回 None（线程+进程安全）"""
    with _cache_lock:
        with _FileLock(TOKEN_CACHE_FILE):
            if not TOKEN_CACHE_FILE.exists():
                return None
            try:
                data = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
                expires_at = data.get("expires_at", 0)
                if time.time() > expires_at:
                    TOKEN_CACHE_FILE.unlink(missing_ok=True)
                    return None
                return data.get("token")
            except (json.JSONDecodeError, KeyError, TypeError):
                TOKEN_CACHE_FILE.unlink(missing_ok=True)
                return None


def clear_token_cache():
    """清除单账号缓存（线程+进程安全）"""
    with _cache_lock:
        if TOKEN_CACHE_FILE.exists():
            with _FileLock(TOKEN_CACHE_FILE):
                TOKEN_CACHE_FILE.unlink(missing_ok=True)


# ============================================================
# 多账号 TokenPool
# 锁架构：
#   threading.RLock（进程内线程安全）+ _FileLock（跨进程安全）
#   所有公开方法两层锁都罩住整个 读→改→写 流程
#   内部方法 _load_from_file / _save_to_file 假设已持有两层锁
#   _loaded 标志仅在同一进程内有效（进程间各自独立），跨进程靠 _FileLock 同步
# ============================================================

class TokenPool:
    """多账号 token 池，线程+进程安全，按 username 存取"""

    def __init__(self, pool_file: Optional[Path] = None):
        """初始化 TokenPool，可自定义存储文件路径（默认 reports/cache/.token_pool.json）"""
        self._pool_file = pool_file or TOKEN_POOL_FILE
        self._tokens: dict[str, dict] = {}
        self._loaded = False
        self._lock = threading.RLock()

    # ---------- 内部方法：假设外层已持 RLock + _FileLock ----------

    def _load_from_file(self):
        """从文件加载到内存（每次都读：调用方已持 FileLock，保证读的是最新内容）"""
        if self._pool_file.exists():
            try:
                data = json.loads(self._pool_file.read_text(encoding="utf-8"))
                self._tokens = data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, TypeError):
                self._tokens = {}
        else:
            self._tokens = {}
        self._loaded = True

    def _save_to_file(self):
        """把内存 dict 写入 JSON 文件"""
        self._pool_file.write_text(
            json.dumps(self._tokens, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # ---------- 公开方法：两层锁罩住整个读改写 ----------

    def put(self, username: str, token: str, expires_at: Optional[float] = None):
        """存入 token（读 → 改 → 写 全程原子）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                if expires_at is None:
                    expires_at = time.time() + TOKEN_EXPIRY_SECONDS
                self._tokens[username] = {
                    "token": token,
                    "saved_at": time.time(),
                    "expires_at": expires_at,
                }
                self._save_to_file()

    def acquire(self, username: str) -> Optional[str]:
        """获取 token，过期自动清理并返回 None（读 → 改 → 写 全程原子）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                entry = self._tokens.get(username)
                if not entry:
                    return None
                if time.time() > entry.get("expires_at", 0):
                    self._tokens.pop(username, None)
                    self._save_to_file()
                    return None
                return entry["token"]

    def release(self, username: str):
        """占位：归还 token（当前实现为 acquire 后自动过期清理，无需显式释放）"""
        pass

    def remove(self, username: str):
        """删除指定账号（读 → 改 → 写 全程原子）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                self._tokens.pop(username, None)
                self._save_to_file()

    def remove_expired(self) -> int:
        """批量清理过期 token，返回清理数量（遍历显式快照，无 RuntimeError）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                now = time.time()
                expired_keys = [
                    u for u, e in list(self._tokens.items())
                    if now > e.get("expires_at", 0)
                ]
                for u in expired_keys:
                    self._tokens.pop(u, None)
                if expired_keys:
                    self._save_to_file()
                return len(expired_keys)

    def list_usernames(self) -> list:
        """列出所有活跃账号（原子化清理过期 + 读取 key 快照）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                now = time.time()
                expired_keys = [
                    u for u, e in list(self._tokens.items())
                    if now > e.get("expires_at", 0)
                ]
                for u in expired_keys:
                    self._tokens.pop(u, None)
                if expired_keys:
                    self._save_to_file()
                return list(self._tokens.keys())

    def clear(self):
        """清空池（原子化）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._tokens.clear()
                self._save_to_file()

    def is_expired(self, username: str) -> bool:
        """判断是否过期（不存在也算过期）"""
        with self._lock:
            with _FileLock(self._pool_file):
                self._load_from_file()
                entry = self._tokens.get(username)
                if not entry:
                    return True
                return time.time() > entry.get("expires_at", 0)


token_pool = TokenPool()