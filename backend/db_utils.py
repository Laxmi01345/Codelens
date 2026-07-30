"""Database utilities for CodeLens - PostgreSQL operations (optional) with JSON file fallback."""

import os
import json
import hashlib
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# JSON file cache directory
CACHE_DIR = Path.home() / ".codelens" / "cache"

# Check if psycopg2 is available and database is configured
DB_AVAILABLE = False
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    print("[DB] psycopg2 not installed - using JSON file cache")


def is_db_available() -> bool:
    """Check if database is available."""
    if not DB_AVAILABLE:
        return False
    try:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            # Try individual vars
            psycopg2.connect(
                dbname=os.getenv("DB_NAME", "repo_analysis_db"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres"),
                host=os.getenv("DB_HOST", "localhost"),
                port=os.getenv("DB_PORT", "5432"),
            ).close()
        else:
            conn = psycopg2.connect(database_url)
            conn.close()
        return True
    except Exception:
        return False


def _get_cache_path(repo_url: str) -> Path:
    """Get JSON cache file path for a repo URL."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Hash the URL to get a safe filename
    url_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{url_hash}.json"


def _store_to_json(repo_url: str, data: dict) -> None:
    """Store analysis to JSON file."""
    try:
        cache_path = _get_cache_path(repo_url)
        cache_data = {
            "repo_url": repo_url,
            "purpose_scope": data.get("purpose_scope", ""),
            "repo_layout": data.get("repo_layout", ""),
            "source_layer": data.get("source_layer", ""),
            "tech_stack": data.get("tech_stack", ""),
            "architecture_text": data.get("architecture_text", ""),
            "_relevant_files": data.get("_relevant_files", []),
            "_commit_hash": data.get("_commit_hash", ""),
            "_file_tree": data.get("_file_tree", {}),
        }
        # Store per-section relevant files
        for key in data:
            if key.startswith("_relevant_files_"):
                cache_data[key] = data[key]
        cache_path.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
        print(f"[DB] Saved analysis to JSON cache: {cache_path.name}")
    except Exception as e:
        print(f"[DB] Error saving to JSON cache: {e}")


def _load_from_json(repo_url: str) -> Optional[dict]:
    """Load analysis from JSON file."""
    try:
        cache_path = _get_cache_path(repo_url)
        if not cache_path.exists():
            return None
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"[DB] Loaded analysis from JSON cache: {cache_path.name}")
        return data
    except Exception as e:
        print(f"[DB] Error loading from JSON cache: {e}")
        return None


def list_cached_repos() -> list[dict]:
    """List all repos in the JSON cache."""
    try:
        if not CACHE_DIR.exists():
            return []
        repos = []
        for f in CACHE_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                repos.append({
                    "url": data.get("repo_url", ""),
                    "name": data.get("repo_url", "").replace("https://github.com/", ""),
                })
            except Exception:
                continue
        return repos
    except Exception:
        return []


def get_connection():
    """Get PostgreSQL connection from DATABASE_URL or individual env vars."""
    if not DB_AVAILABLE:
        raise RuntimeError("psycopg2 not installed")

    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return psycopg2.connect(database_url)
    else:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "repo_analysis_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
        )


@contextmanager
def get_cursor():
    """Context manager for database cursor with automatic commit/rollback."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def ensure_schema(cursor):
    """Create table if not exists, add metadata column if missing."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS repo_analysis (
            repo_url VARCHAR(500) PRIMARY KEY,
            purpose_scope TEXT,
            repo_layout TEXT,
            source_layer TEXT,
            tech_stack TEXT,
            architecture_text TEXT,
            architecture_diagram TEXT,
            rpc_protocol TEXT,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Add metadata column if table already existed without it
    cursor.execute(
        """
        DO $$ BEGIN
            ALTER TABLE repo_analysis ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
        """
    )


def store_repo_analysis(repo_url: str, data: dict) -> None:
    """Store or update repository analysis results. Falls back to JSON file if DB unavailable."""
    # Try PostgreSQL first
    if DB_AVAILABLE:
        try:
            with get_cursor() as cursor:
                ensure_schema(cursor)

                # Build metadata dict for per-section files, commit hash, file tree
                metadata = {
                    "_commit_hash": data.get("_commit_hash", ""),
                    "_file_tree": data.get("_file_tree", {}),
                }
                # Store per-section relevant files
                for key in data:
                    if key.startswith("_relevant_files_"):
                        metadata[key] = data[key]
                # Store global relevant files
                if "_relevant_files" in data:
                    metadata["_relevant_files"] = data["_relevant_files"]

                query = """
                INSERT INTO repo_analysis
                (repo_url, purpose_scope, repo_layout, source_layer, tech_stack, architecture_text, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (repo_url) DO UPDATE SET
                purpose_scope = EXCLUDED.purpose_scope,
                repo_layout = EXCLUDED.repo_layout,
                source_layer = EXCLUDED.source_layer,
                tech_stack = EXCLUDED.tech_stack,
                architecture_text = EXCLUDED.architecture_text,
                metadata = EXCLUDED.metadata;
                """

                cursor.execute(
                    query,
                    (
                        repo_url,
                        data.get("purpose_scope", ""),
                        data.get("repo_layout", ""),
                        data.get("source_layer", ""),
                        data.get("tech_stack", ""),
                        data.get("architecture_text", ""),
                        json.dumps(metadata),
                    ),
                )
                print(f"[DB] Stored analysis in PostgreSQL for {repo_url}")
                return
        except Exception as e:
            print(f"[DB] PostgreSQL error, falling back to JSON: {e}")

    # Fallback to JSON file
    _store_to_json(repo_url, data)


def get_repo_analysis(repo_url: str) -> Optional[dict]:
    """Retrieve cached repository analysis. Falls back to JSON file if DB unavailable."""
    # Try PostgreSQL first
    if DB_AVAILABLE:
        try:
            with get_cursor() as cursor:
                ensure_schema(cursor)

                cursor.execute(
                    """
                    SELECT repo_url, purpose_scope, repo_layout, source_layer, tech_stack,
                           architecture_text, metadata
                    FROM repo_analysis
                    WHERE repo_url = %s
                    """,
                    (repo_url,),
                )

                row = cursor.fetchone()

                if row:
                    result = {
                        "repo_url": row[0],
                        "purpose_scope": row[1],
                        "repo_layout": row[2],
                        "source_layer": row[3],
                        "tech_stack": row[4],
                        "architecture_text": row[5],
                    }
                    # Unpack metadata (per-section files, commit hash, file tree)
                    metadata = row[6] or {}
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    result.update(metadata)
                    return result
        except Exception as e:
            print(f"[DB] PostgreSQL error, falling back to JSON: {e}")

    # Fallback to JSON file
    return _load_from_json(repo_url)
