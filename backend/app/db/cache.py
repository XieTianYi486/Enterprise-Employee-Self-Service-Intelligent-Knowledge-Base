# ============================================================
# 缓存模块
# 两级缓存：内存缓存（cachetools）+ 磁盘缓存（diskcache）
# 旧项目未使用缓存，新项目正式引入
# ============================================================

import hashlib
from functools import wraps
from typing import Any, Callable, Optional

import cachetools
import diskcache as dc

from app.core.config import settings

# --- 内存 LRU 缓存（高频热点数据）---
_memory_cache = cachetools.LRUCache(maxsize=512)

# --- 磁盘持久化缓存（问答结果、会话上下文）---
_disk_cache = dc.Cache(settings.CACHE_DIR)


class CacheManager:
    """统一缓存管理器，提供多级缓存策略"""

    @staticmethod
    def make_key(*args, prefix: str = "cache") -> str:
        """生成缓存 key（对参数进行 SHA256 哈希）"""
        raw = ":".join(str(a) for a in args)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"

    @staticmethod
    def get_from_memory(key: str) -> Optional[Any]:
        """从内存缓存读取"""
        return _memory_cache.get(key)

    @staticmethod
    def set_to_memory(key: str, value: Any) -> None:
        """写入内存缓存"""
        _memory_cache[key] = value

    @staticmethod
    def get_from_disk(key: str) -> Optional[Any]:
        """从磁盘缓存读取"""
        return _disk_cache.get(key)

    @staticmethod
    def set_to_disk(key: str, value: Any, ttl: Optional[int] = None) -> None:
        """写入磁盘缓存，可选 TTL"""
        if ttl is None:
            ttl = settings.CACHE_TTL_ANSWER
        _disk_cache.set(key, value, expire=ttl)

    @staticmethod
    def clear_disk() -> None:
        """清空磁盘缓存"""
        _disk_cache.clear()

    @staticmethod
    def invalidate(*keys: str) -> None:
        """使指定 key 的缓存失效（内存 + 磁盘）"""
        for key in keys:
            _memory_cache.pop(key, None)
            _disk_cache.delete(key)

    @staticmethod
    def clear_by_prefix(prefix: str) -> None:
        """按前缀清除缓存（内存 + 磁盘）"""
        for key in list(_memory_cache.keys()):
            if key.startswith(prefix):
                _memory_cache.pop(key, None)
        for key in list(_disk_cache.iterkeys()):
            if key.startswith(prefix):
                _disk_cache.delete(key)


# --- 全局单例 ---
cache = CacheManager()
