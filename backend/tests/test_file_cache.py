"""Tests for File Cache."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.file_cache import FileCache


class TestFileCache:
    """Tests for content-addressable file cache."""

    def test_compute_hash(self):
        cache = FileCache()
        h1 = cache.compute_file_hash("hello world")
        h2 = cache.compute_file_hash("hello world")
        h3 = cache.compute_file_hash("different content")
        assert h1 == h2  # Same content = same hash
        assert h1 != h3  # Different content = different hash

    def test_compute_file_hashes(self):
        cache = FileCache()
        files = {"a.py": "content_a", "b.py": "content_b"}
        hashes = cache.compute_file_hashes(files)
        assert "a.py" in hashes
        assert "b.py" in hashes
        assert hashes["a.py"] != hashes["b.py"]

    def test_store_and_retrieve(self):
        cache = FileCache()
        files = {"a.py": "content_a"}
        analysis = {"result": "test_analysis"}

        cache.store_analysis("https://github.com/test/repo", files, analysis)
        cached = cache.get_cached_analysis("https://github.com/test/repo")
        assert cached == analysis

    def test_cache_miss(self):
        cache = FileCache()
        cached = cache.get_cached_analysis("https://github.com/nonexistent/repo")
        assert cached is None

    def test_get_changed_files(self):
        cache = FileCache()
        files = {"a.py": "content_a", "b.py": "content_b"}
        cache.store_analysis("https://github.com/test/repo", files, {})

        # Same files - no changes
        changed, new = cache.get_changed_files("https://github.com/test/repo", files)
        assert len(changed) == 0
        assert len(new) == 0

        # Modified file
        new_files = {"a.py": "modified_a", "b.py": "content_b"}
        changed, new = cache.get_changed_files("https://github.com/test/repo", new_files)
        assert "a.py" in changed
        assert len(new) == 0

        # New file
        new_files = {"a.py": "content_a", "b.py": "content_b", "c.py": "content_c"}
        changed, new = cache.get_changed_files("https://github.com/test/repo", new_files)
        assert len(changed) == 0
        assert "c.py" in new

    def test_needs_full_analysis(self):
        cache = FileCache()
        files = {"a.py": "content_a", "b.py": "content_b"}

        # No cache - needs full analysis
        assert cache.needs_full_analysis("https://github.com/test/repo", files) is True

        # Store and check - should not need full analysis
        cache.store_analysis("https://github.com/test/repo", files, {})
        assert cache.needs_full_analysis("https://github.com/test/repo", files) is False

        # Many changes - needs full analysis
        changed_files = {f"file{i}.py": f"content{i}" for i in range(10)}
        assert cache.needs_full_analysis("https://github.com/test/repo", changed_files) is True

    def test_invalidate(self):
        cache = FileCache()
        files = {"a.py": "content_a"}
        cache.store_analysis("https://github.com/test/repo", files, {})

        # Verify cached
        assert cache.get_cached_analysis("https://github.com/test/repo") is not None

        # Invalidate
        cache.invalidate("https://github.com/test/repo")
        assert cache.get_cached_analysis("https://github.com/test/repo") is None

    def test_stats(self):
        cache = FileCache()
        files = {"a.py": "content_a"}

        # Cache miss
        cache.get_cached_analysis("https://github.com/test/repo")
        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0

        # Store and cache hit
        cache.store_analysis("https://github.com/test/repo", files, {})
        cache.get_cached_analysis("https://github.com/test/repo")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 0.5


class TestCachePersistence:
    """Tests for disk persistence."""

    def test_save_and_load(self):
        import tempfile
        import shutil

        temp_dir = tempfile.mkdtemp()
        try:
            cache = FileCache(cache_dir=temp_dir)
            files = {"a.py": "content_a"}
            analysis = {"result": "test"}

            cache.store_analysis("https://github.com/test/repo", files, analysis)
            cache.save_to_disk("https://github.com/test/repo")

            # Create new cache and load
            cache2 = FileCache(cache_dir=temp_dir)
            loaded = cache2.load_from_disk("https://github.com/test/repo")
            assert loaded == analysis
        finally:
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_classes = [
        TestFileCache,
        TestCachePersistence,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n=== {test_class.__name__} ===")
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                test = test_class()
                try:
                    getattr(test, method_name)()
                    print(f"  PASS: {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL: {method_name}: {e}")
                    failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
