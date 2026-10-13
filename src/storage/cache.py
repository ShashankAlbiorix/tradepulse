import hashlib
import re
import time
from typing import Dict, Set, Optional

from config.settings import settings


class DeduplicationCache:
    """
    Fingerprint-based deduplication cache with TTL management to prevent
    repeated analysis of duplicate or syndicated news articles across feeds.
    """

    def __init__(self, ttl_hours: Optional[int] = None):
        """
        Args:
            ttl_hours: Time-to-live in hours before fingerprint expires.
        """
        self.ttl_seconds = (ttl_hours or settings.DEDUPLICATION_CACHE_TTL_HOURS or 48) * 3600
        self._cache: Dict[str, float] = {}  # hash -> timestamp

    def _normalize_title(self, title: str) -> str:
        """Strip punctuation, whitespace and lowercase for canonical title matching."""
        return re.sub(r'[^a-z0-9]', '', title.lower().strip())

    def _generate_hashes(self, url: str, title: str) -> tuple[str, str]:
        """
        Compute deterministic SHA-256 hashes for canonical title and URL.
        """
        title_key = f"title:{self._normalize_title(title)}"
        url_key = f"url:{url.strip().lower()}"
        return (
            hashlib.sha256(title_key.encode("utf-8")).hexdigest(),
            hashlib.sha256(url_key.encode("utf-8")).hexdigest()
        )

    def _cleanup_expired(self):
        """
        Evict entries older than TTL threshold.
        """
        now = time.time()
        expired_keys = [k for k, ts in self._cache.items() if now - ts > self.ttl_seconds]
        for k in expired_keys:
            del self._cache[k]

    def is_duplicate(self, url: str, title: str) -> bool:
        """
        Check if an article title or URL hash exists and has not expired.
        """
        self._cleanup_expired()
        t_hash, u_hash = self._generate_hashes(url, title)
        return (t_hash in self._cache) or (u_hash in self._cache)

    def mark_seen(self, url: str, title: str):
        """
        Record article title and URL hashes with current timestamp.
        """
        now = time.time()
        t_hash, u_hash = self._generate_hashes(url, title)
        self._cache[t_hash] = now
        self._cache[u_hash] = now

    def size(self) -> int:
        """Return count of active fingerprints."""
        self._cleanup_expired()
        return len(self._cache)

    def clear(self):
        """Flush cache."""
        self._cache.clear()
