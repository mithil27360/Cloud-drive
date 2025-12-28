import time
import json
import sqlite3
import hashlib
import logging
import threading
import pickle
from typing import Any, Optional, Union, Dict, List
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    l1_size: int = 1000  # Number of items in memory
    l2_path: str = "cache.db"
    default_ttl: int = 3600 * 24  # 24 Hours default TTL

class TieredCacheManager:
    """
    Research-Grade Multi-Level Cache System.
    
    Architecture:
    - L1: In-Memory LRU Cache (Microsecond latency)
    - L2: SQLite Persistent Cache (Millisecond latency)
    
    Features:
    - Canonical Key Generation (handles nested dicts/lists safely)
    - Time-To-Live (TTL) enforcement
    - Thread-safe operations
    - Automatic L1 population on L2 hits (Write-Back)
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls, config: CacheConfig = CacheConfig()):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(TieredCacheManager, cls).__new__(cls)
                    cls._instance.initialize(config)
        return cls._instance
    
    def initialize(self, config: CacheConfig):
        self.config = config
        self.l1_cache = OrderedDict()
        self.l1_lock = threading.Lock()
        self._init_l2_db()
        logger.info(f"Cache Manager Initialized (L1: {config.l1_size}, L2: {config.l2_path})")

    def _init_l2_db(self):
        """Initialize L2 SQLite storage."""
        try:
            with sqlite3.connect(self.config.l2_path, check_same_thread=False) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_store (
                        key TEXT PRIMARY KEY,
                        value BLOB,
                        created_at REAL,
                        expires_at REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache_store(expires_at)")
                
                # Background cleanup of expired items could go here
        except Exception as e:
            logger.error(f"L2 Cache Init Failed: {e}")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate a robust canonical hash key for any combination of arguments.
        Determinsitcally serializes complex objects.
        """
        try:
            payload = {
                "args": args,
                "kwargs": kwargs
            }
            # Sort keys for determinism
            serialized = json.dumps(payload, sort_keys=True, default=str)
            hash_part = hashlib.sha256(serialized.encode()).hexdigest()
            return f"{prefix}:{hash_part}"
        except Exception as e:
            logger.error(f"Key Generation Failed: {e}")
            return f"{prefix}:{time.time()}" # Fallback (no cache hit likely)

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve item from cache (L1 -> L2).
        Returns None if not found or expired.
        """
        # 1. Check L1 (Memory)
        with self.l1_lock:
            if key in self.l1_cache:
                item, expires_at = self.l1_cache[key]
                if time.time() < expires_at:
                    # LRU Move to end
                    self.l1_cache.move_to_end(key)
                    # logger.debug(f"L1 Hit: {key}")
                    return item
                else:
                    del self.l1_cache[key] # Expired

        # 2. Check L2 (Disk)
        try:
            with sqlite3.connect(self.config.l2_path, check_same_thread=False) as conn:
                cursor = conn.execute(
                    "SELECT value, expires_at FROM cache_store WHERE key = ?", 
                    (key,)
                )
                row = cursor.fetchone()
                
                if row:
                    value_blob, expires_at = row
                    if time.time() < expires_at:
                        # Deserialize
                        data = pickle.loads(value_blob)
                        
                        # Populate L1 (Promote)
                        self.set(key, data, ttl=(expires_at - time.time()))
                        # logger.debug(f"L2 Hit: {key}")
                        return data
                    else:
                        # Lazy delete expired
                        conn.execute("DELETE FROM cache_store WHERE key = ?", (key,))
        except Exception as e:
            logger.error(f"L2 Read Error: {e}")
            
        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Write item to cache (L1 + L2).
        """
        if ttl is None:
            ttl = self.config.default_ttl
            
        expires_at = time.time() + ttl
        
        # 1. Write L1
        with self.l1_lock:
            self.l1_cache[key] = (value, expires_at)
            self.l1_cache.move_to_end(key)
            # Evict if full
            if len(self.l1_cache) > self.config.l1_size:
                self.l1_cache.popitem(last=False)
                
        # 2. Write L2
        try:
            blob = pickle.dumps(value)
            with sqlite3.connect(self.config.l2_path, check_same_thread=False) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache_store (key, value, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (key, blob, time.time(), expires_at))
        except Exception as e:
            logger.error(f"L2 Write Error: {e}")

    def invalidate(self, key_pattern: str):
        """
        Invalidate keys matching pattern (SQL LIKE).
        Warning: Only affects L2 efficiently. L1 clear is naive.
        """
        with self.l1_lock:
            self.l1_cache.clear() # Simplistic for now
            
        try:
            with sqlite3.connect(self.config.l2_path, check_same_thread=False) as conn:
                conn.execute("DELETE FROM cache_store WHERE key LIKE ?", (key_pattern,))
        except Exception as e:
            logger.error(f"Invalidation Error: {e}")

    def cached_operation(self, prefix: str, ttl: int = 300):
        """
        Decorator to cache function results.
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generate key based on function args
                key = self._generate_key(prefix, *args, **kwargs)
                
                # Check cache
                cached = self.get(key)
                if cached is not None:
                    return cached
                
                # Execute
                result = func(*args, **kwargs)
                
                # Store
                self.set(key, result, ttl=ttl)
                return result
            return wrapper
        return decorator

# Global Instance
cache_manager = TieredCacheManager()
