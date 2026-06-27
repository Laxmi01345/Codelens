"""Code Index - Embeddings-based semantic search for code chunks."""

import sqlite3
import numpy as np
from typing import Optional
from .chunker import CodeChunk

# Try to import sentence-transformers (optional dependency)
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDING_AVAILABLE = True
except ImportError:
    EMBEDDING_AVAILABLE = False
    print("[CodeIndex] sentence-transformers not installed.")


class CodeIndex:
    """Embeddings-based semantic search for code chunks."""
    
    def __init__(self, use_embeddings: bool = True):
        self.conn = sqlite3.connect(":memory:")
        self._create_tables()
        
        # Embedding support
        self.use_embeddings = use_embeddings and EMBEDDING_AVAILABLE
        self.embedding_model = None
        self.embeddings = {}  # chunk_id -> embedding vector
        self.chunk_ids = []   # ordered list for vector operations
        
        if self.use_embeddings:
            print("[CodeIndex] Loading embedding model...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[CodeIndex] Embedding model loaded.")
        else:
            raise RuntimeError("Embeddings required but sentence-transformers not installed")
    
    def _create_tables(self):
        """Create the index tables."""
        # File metadata table
        self.conn.execute("""
            CREATE TABLE files (
                path TEXT PRIMARY KEY,
                name TEXT,
                language TEXT,
                size INTEGER,
                line_count INTEGER
            )
        """)
        
        # AST structure table
        self.conn.execute("""
            CREATE TABLE asts (
                file_path TEXT,
                type TEXT,
                name TEXT,
                signature TEXT,
                line INTEGER,
                docstring TEXT,
                PRIMARY KEY (file_path, type, name)
            )
        """)
        
        # Code chunks table (metadata only, vectors stored in memory)
        self.conn.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                file TEXT,
                type TEXT,
                name TEXT,
                signature TEXT,
                body TEXT,
                imports TEXT
            )
        """)
        
        # Dependency graph table
        self.conn.execute("""
            CREATE TABLE deps (
                source TEXT,
                target TEXT,
                type TEXT,
                PRIMARY KEY (source, target, type)
            )
        """)
        
        self.conn.commit()
    
    def add_file(self, path: str, content: str, language: str):
        """Add file metadata to the index."""
        line_count = len(content.split("\n"))
        name = path.split("/")[-1]
        self.conn.execute(
            "INSERT OR REPLACE INTO files VALUES (?, ?, ?, ?, ?)",
            (path, name, language, len(content), line_count)
        )
        self.conn.commit()
    
    def add_ast(self, file_path: str, chunk: CodeChunk):
        """Add AST structure to the index."""
        self.conn.execute(
            "INSERT OR REPLACE INTO asts VALUES (?, ?, ?, ?, ?, ?)",
            (file_path, chunk.type, chunk.name, chunk.signature,
             chunk.line_start, chunk.docstring)
        )
        self.conn.commit()
    
    def add_chunk(self, chunk: CodeChunk):
        """Add a code chunk and generate embedding."""
        imports_str = "\n".join(chunk.imports) if chunk.imports else ""
        self.conn.execute(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chunk.id, chunk.file, chunk.type, chunk.name,
             chunk.signature, chunk.body, imports_str)
        )
        self.conn.commit()
        
        # Generate embedding for semantic search
        if self.use_embeddings and self.embedding_model:
            text = f"{chunk.name} {chunk.signature} {chunk.body[:500]}"
            embedding = self.embedding_model.encode(text)
            self.embeddings[chunk.id] = embedding
            self.chunk_ids.append(chunk.id)
    
    def add_dependency(self, source: str, target: str, dep_type: str = "import"):
        """Add a dependency edge to the graph."""
        self.conn.execute(
            "INSERT OR REPLACE INTO deps VALUES (?, ?, ?)",
            (source, target, dep_type)
        )
        self.conn.commit()
    
    def search_chunks(self, query: str, limit: int = 5) -> list[dict]:
        """Embedding-based semantic search for relevant code chunks."""
        if not self.use_embeddings or not self.embedding_model:
            raise RuntimeError("Embeddings not available")
        
        # Encode query
        query_embedding = self.embedding_model.encode(query)
        
        # Compute cosine similarity with all chunks
        scores = []
        for chunk_id, chunk_emb in self.embeddings.items():
            similarity = np.dot(query_embedding, chunk_emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb)
            )
            scores.append((chunk_id, float(similarity)))
        
        # Sort by similarity (descending)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Fetch top results
        results = []
        for chunk_id, score in scores[:limit]:
            result = self.conn.execute(
                "SELECT id, file, name, signature, body FROM chunks WHERE id = ?",
                (chunk_id,)
            ).fetchone()
            if result:
                results.append({
                    "id": result[0],
                    "file": result[1],
                    "name": result[2],
                    "signature": result[3],
                    "body": result[4],
                    "score": score,
                })
        
        return results
    
    def get_importers(self, module_path: str) -> list[str]:
        """Get files that import a given module."""
        results = self.conn.execute(
            "SELECT source FROM deps WHERE target LIKE ? AND type = 'import'",
            (f"%{module_path}%",)
        ).fetchall()
        return [r[0] for r in results]
    
    def get_imports(self, file_path: str) -> list[str]:
        """Get modules imported by a file."""
        results = self.conn.execute(
            "SELECT target FROM deps WHERE source = ? AND type = 'import'",
            (file_path,)
        ).fetchall()
        return [r[0] for r in results]
    
    def get_all_files(self) -> list[dict]:
        """Get all file metadata."""
        results = self.conn.execute("SELECT * FROM files").fetchall()
        return [
            {"path": r[0], "name": r[1], "language": r[2],
             "size": r[3], "line_count": r[4]}
            for r in results
        ]
    
    def get_all_asts(self) -> list[dict]:
        """Get all AST structures."""
        results = self.conn.execute("SELECT * FROM asts").fetchall()
        return [
            {"file_path": r[0], "type": r[1], "name": r[2],
             "signature": r[3], "line": r[4], "docstring": r[5]}
            for r in results
        ]
    
    def get_stats(self) -> dict:
        """Get index statistics."""
        files_count = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        asts_count = self.conn.execute("SELECT COUNT(*) FROM asts").fetchone()[0]
        chunks_count = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        deps_count = self.conn.execute("SELECT COUNT(*) FROM deps").fetchone()[0]
        return {
            "files": files_count,
            "asts": asts_count,
            "chunks": chunks_count,
            "dependencies": deps_count,
            "embeddings": len(self.embeddings),
        }


def build_code_index(
    source_files: dict[str, str],
    chunks: list[CodeChunk],
    graph=None,
) -> CodeIndex:
    """Build a complete code index from source files, chunks, and graph."""
    index = CodeIndex()
    
    # Add file metadata
    for path, content in source_files.items():
        ext = path.split(".")[-1].lower() if "." in path else ""
        lang_map = {
            "py": "Python", "js": "JavaScript", "jsx": "JavaScript",
            "ts": "TypeScript", "tsx": "TypeScript", "go": "Go",
            "rs": "Rust", "java": "Java", "rb": "Ruby",
            "php": "PHP", "cs": "C#", "cpp": "C++", "c": "C",
            "h": "C", "swift": "Swift", "kt": "Kotlin",
        }
        language = lang_map.get(ext, ext.upper())
        index.add_file(path, content, language)
    
    # Add AST structures and chunks
    for chunk in chunks:
        index.add_ast(chunk.file, chunk)
        index.add_chunk(chunk)
    
    # Add dependencies from graph if available
    if graph:
        for source in graph.nodes:
            for target in graph.edges.get(source, set()):
                index.add_dependency(source, target, "import")
    
    return index
