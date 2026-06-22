"""File Cache - Content-addressable caching for incremental analysis."""

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ContentHash:
    """Content hash for a single file."""
    path: str
    hash: str
    size: int
    last_modified: float


@dataclass
class CacheEntry:
    """A cached analysis result with file hashes."""
    repo_url: str
    file_hashes: dict[str, str]  # path -> content hash
    analysis_result: dict
    created_at: float
    ttl_seconds: float = 3600.0  # 1 hour default

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


class FileCache:
    """
    Content-addressable file cache for incremental analysis.

    Uses SHA-256 hashes of file contents to detect changes.
    Only re-analyzes files whose content has changed.
    """

    def __init__(self, cache_dir: Optional[str] = None, default_ttl: float = 3600.0):
        self._cache: dict[str, CacheEntry] = {}  # repo_url -> CacheEntry
        self._file_hashes: dict[str, dict[str, str]] = {}  # repo_url -> {path: hash}
        self._cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".codelens", "cache")
        self._default_ttl = default_ttl
        self._stats = {"hits": 0, "misses": 0, "partial_hits": 0}

    def compute_file_hash(self, content: str) -> str:
        """Compute SHA-256 hash of file content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def compute_file_hashes(self, files: dict[str, str]) -> dict[str, str]:
        """Compute hashes for multiple files."""
        return {path: self.compute_file_hash(content) for path, content in files.items()}

    def get_cached_analysis(self, repo_url: str) -> Optional[dict]:
        """Get cached analysis if available and not expired."""
        entry = self._cache.get(repo_url)
        if entry and not entry.is_expired:
            self._stats["hits"] += 1
            return entry.analysis_result

        self._stats["misses"] += 1
        return None

    def store_analysis(
        self,
        repo_url: str,
        files: dict[str, str],
        analysis: dict,
        ttl: Optional[float] = None,
    ) -> None:
        """Store analysis result with file hashes."""
        hashes = self.compute_file_hashes(files)
        self._cache[repo_url] = CacheEntry(
            repo_url=repo_url,
            file_hashes=hashes,
            analysis_result=analysis,
            created_at=time.time(),
            ttl_seconds=ttl or self._default_ttl,
        )
        self._file_hashes[repo_url] = hashes

    def get_changed_files(
        self, repo_url: str, current_files: dict[str, str]
    ) -> tuple[list[str], list[str]]:
        """
        Compare current files against cached hashes.

        Returns:
            (changed_files, new_files) - lists of file paths
        """
        cached_hashes = self._file_hashes.get(repo_url, {})
        current_hashes = self.compute_file_hashes(current_files)

        changed = []
        new = []

        for path, hash_val in current_hashes.items():
            if path in cached_hashes:
                if cached_hashes[path] != hash_val:
                    changed.append(path)
            else:
                new.append(path)

        return changed, new

    def needs_full_analysis(self, repo_url: str, current_files: dict[str, str]) -> bool:
        """Check if a full re-analysis is needed."""
        if repo_url not in self._cache:
            return True

        entry = self._cache[repo_url]
        if entry.is_expired:
            return True

        changed, new = self.get_changed_files(repo_url, current_files)
        return len(new) > 0 or len(changed) > len(current_files) * 0.3  # >30% changed

    def get_affected_modules(
        self, repo_url: str, changed_files: list[str]
    ) -> list[str]:
        """
        Get modules affected by file changes.

        Uses the dependency graph to find transitively affected modules.
        """
        # For now, return changed files directly
        # The graph integration happens in the pipeline
        return changed_files

    def invalidate(self, repo_url: str) -> None:
        """Invalidate cache for a repository."""
        self._cache.pop(repo_url, None)
        self._file_hashes.pop(repo_url, None)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            **self._stats,
            "total": total,
            "hit_rate": round(hit_rate, 3),
            "entries": len(self._cache),
        }

    def save_to_disk(self, repo_url: str) -> bool:
        """Save cache entry to disk for persistence."""
        entry = self._cache.get(repo_url)
        if not entry:
            return False

        try:
            os.makedirs(self._cache_dir, exist_ok=True)
            cache_file = os.path.join(
                self._cache_dir,
                self._url_to_filename(repo_url) + ".json",
            )
            data = {
                "repo_url": entry.repo_url,
                "file_hashes": entry.file_hashes,
                "analysis_result": entry.analysis_result,
                "created_at": entry.created_at,
                "ttl_seconds": entry.ttl_seconds,
            }
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

    def load_from_disk(self, repo_url: str) -> Optional[dict]:
        """Load cache entry from disk."""
        try:
            cache_file = os.path.join(
                self._cache_dir,
                self._url_to_filename(repo_url) + ".json",
            )
            if not os.path.exists(cache_file):
                return None

            with open(cache_file, "r") as f:
                data = json.load(f)

            entry = CacheEntry(**data)
            if entry.is_expired:
                os.remove(cache_file)
                return None

            self._cache[repo_url] = entry
            self._file_hashes[repo_url] = entry.file_hashes
            return entry.analysis_result
        except Exception:
            return None

    @staticmethod
    def _url_to_filename(url: str) -> str:
        """Convert URL to safe filename."""
        return url.replace("https://", "").replace("http://", "").replace("/", "_").replace(".", "_")
