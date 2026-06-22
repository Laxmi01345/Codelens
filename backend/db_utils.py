"""Database utilities for CodeLens - PostgreSQL operations (optional)."""

import os
from contextlib import contextmanager
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Check if psycopg2 is available and database is configured
DB_AVAILABLE = False
try:
    import psycopg2
    DB_AVAILABLE = True
except ImportError:
    print("[DB] psycopg2 not installed - database caching disabled")


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
    """Create table if not exists."""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def store_repo_analysis(repo_url: str, data: dict) -> None:
    """Store or update repository analysis results."""
    if not DB_AVAILABLE:
        print("[DB] Database not available - skipping store")
        return

    try:
        with get_cursor() as cursor:
            ensure_schema(cursor)

            query = """
            INSERT INTO repo_analysis
            (repo_url, purpose_scope, repo_layout, source_layer, tech_stack, architecture_text)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (repo_url) DO UPDATE SET
            purpose_scope = EXCLUDED.purpose_scope,
            repo_layout = EXCLUDED.repo_layout,
            source_layer = EXCLUDED.source_layer,
            tech_stack = EXCLUDED.tech_stack,
            architecture_text = EXCLUDED.architecture_text;
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
                ),
            )
    except Exception as e:
        print(f"[DB] Error storing analysis: {e}")


def get_repo_analysis(repo_url: str) -> Optional[dict]:
    """Retrieve cached repository analysis."""
    if not DB_AVAILABLE:
        print("[DB] Database not available - skipping cache check")
        return None

    try:
        with get_cursor() as cursor:
            ensure_schema(cursor)

            cursor.execute(
                """
                SELECT repo_url, purpose_scope, repo_layout, source_layer, tech_stack,
                       architecture_text
                FROM repo_analysis
                WHERE repo_url = %s
                """,
                (repo_url,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "repo_url": row[0],
                "purpose_scope": row[1],
                "repo_layout": row[2],
                "source_layer": row[3],
                "tech_stack": row[4],
                "architecture_text": row[5],
            }
    except Exception as e:
        print(f"[DB] Error retrieving analysis: {e}")
        return None
