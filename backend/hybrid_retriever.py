"""Hybrid Retriever - BM25 + Embeddings + Re-ranking for production RAG."""

import os
import sqlite3
import numpy as np
from typing import Optional
from dataclasses import dataclass

# Try to import dependencies
try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("[HybridRetriever] sentence-transformers not installed.")

try:
    from qdrant_client import QdrantClient
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


@dataclass
class RetrievalResult:
    """A single retrieval result."""
    id: str
    file: str
    name: str
    signature: str
    body: str
    score: float
    source: str  # "bm25", "embeddings", "hybrid"
    rank: int


class BM25Index:
    """
    SQLite FTS5-based BM25 index for keyword search.
    
    Interview point: "BM25 excels at exact keyword matching -
    function names, error codes, and identifiers."
    """
    
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self._create_table()
    
    def _create_table(self):
        """Create FTS5 virtual table."""
        self.conn.execute("""
            CREATE VIRTUAL TABLE chunks USING fts5(
                id,
                file,
                type,
                name,
                signature,
                body,
                tokenize='porter unicode61'
            )
        """)
        self.conn.commit()
    
    def add_chunks(self, chunks: list[dict]):
        """Add chunks to BM25 index."""
        for chunk in chunks:
            self.conn.execute(
                "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    chunk["id"],
                    chunk.get("file", ""),
                    chunk.get("type", ""),
                    chunk.get("name", ""),
                    chunk.get("signature", ""),
                    chunk.get("body", ""),
                    "",  # imports
                )
            )
        self.conn.commit()
    
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """BM25 search."""
        try:
            results = self.conn.execute(
                "SELECT id, file, name, signature, body, rank FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT ?",
                (query, limit)
            ).fetchall()
            
            return [
                {
                    "id": r[0],
                    "file": r[1],
                    "name": r[2],
                    "signature": r[3],
                    "body": r[4],
                    "score": -r[5],  # Negate because FTS5 rank is lower = better
                }
                for r in results
            ]
        except sqlite3.OperationalError:
            return []


class EmbeddingsIndex:
    """
    In-memory embeddings index for semantic search.
    
    Interview point: "Embeddings understand semantic meaning -
    'user sessions' matches 'auth logic' without exact keywords."
    """
    
    def __init__(self):
        self.model = None
        self.embeddings = {}
        self.chunk_ids = []
        self._load_model()
    
    def _load_model(self):
        """Load embedding model."""
        if not EMBEDDINGS_AVAILABLE:
            return
        
        try:
            print("[EmbeddingsIndex] Loading model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            print("[EmbeddingsIndex] Model loaded.")
        except Exception as e:
            print(f"[EmbeddingsIndex] Could not load model: {e}")
    
    def add_chunks(self, chunks: list[dict]):
        """Add chunks and generate embeddings."""
        if not self.model:
            return
        
        for chunk in chunks:
            text = f"{chunk.get('name', '')} {chunk.get('signature', '')} {chunk.get('body', '')[:500]}"
            embedding = self.model.encode(text)
            self.embeddings[chunk["id"]] = embedding
            self.chunk_ids.append(chunk["id"])
    
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Embedding-based semantic search."""
        if not self.model or not self.embeddings:
            return []
        
        query_embedding = self.model.encode(query)
        
        scores = []
        for chunk_id, emb in self.embeddings.items():
            similarity = np.dot(query_embedding, emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(emb)
            )
            scores.append((chunk_id, float(similarity)))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            {"id": cid, "score": score}
            for cid, score in scores[:limit]
        ]


class HybridRetriever:
    """
    Production hybrid retriever combining BM25 + Embeddings + Re-ranking.
    
    Pipeline:
    1. Query Expansion (optional)
    2. BM25 search (keyword matching)
    3. Embedding search (semantic matching)
    4. Reciprocal Rank Fusion (combine results)
    5. Cross-encoder re-ranking (precision)
    
    Interview point: "We use a multi-stage retrieval pipeline:
    BM25 for exact matches, embeddings for semantic understanding,
    RRF to combine, and cross-encoder for precision."
    """
    
    def __init__(self):
        self.bm25 = BM25Index()
        self.embeddings = EmbeddingsIndex()
        self.reranker = None
        self.chunks = {}  # chunk_id -> chunk data
        self._load_reranker()
    
    def _load_reranker(self):
        """Load cross-encoder re-ranker."""
        if not EMBEDDINGS_AVAILABLE:
            return
        
        try:
            print("[HybridRetriever] Loading cross-encoder...")
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            print("[HybridRetriever] Cross-encoder loaded.")
        except Exception as e:
            print(f"[HybridRetriever] Could not load cross-encoder: {e}")
    
    def index_chunks(self, chunks: list[dict]):
        """Index chunks in both BM25 and embeddings."""
        # Store chunk data
        for chunk in chunks:
            self.chunks[chunk["id"]] = chunk
        
        # Index in BM25
        self.bm25.add_chunks(chunks)
        print(f"[HybridRetriever] Indexed {len(chunks)} chunks in BM25")
        
        # Index in embeddings
        self.embeddings.add_chunks(chunks)
        print(f"[HybridRetriever] Indexed {len(chunks)} chunks in embeddings")
    
    def retrieve(
        self,
        query: str,
        limit: int = 5,
        alpha: float = 0.5,  # BM25 weight (1-alpha for embeddings)
        use_reranking: bool = True,
    ) -> list[RetrievalResult]:
        """
        Hybrid retrieval with Reciprocal Rank Fusion.
        
        Args:
            query: Search query
            limit: Max results
            alpha: BM25 weight (0.5 = equal weight)
            use_reranking: Whether to apply cross-encoder re-ranking
        
        Returns:
            Ranked list of retrieval results
        """
        # Stage 1: BM25 search
        bm25_results = self.bm25.search(query, limit=limit * 4)
        
        # Stage 2: Embedding search
        embed_results = self.embeddings.search(query, limit=limit * 4)
        
        # Stage 3: Reciprocal Rank Fusion
        k = 60  # RRF constant
        rrf_scores = {}
        
        # BM25 scores
        for rank, result in enumerate(bm25_results):
            chunk_id = result["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + alpha * (1 / (k + rank + 1))
        
        # Embedding scores
        for rank, result in enumerate(embed_results):
            chunk_id = result["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + (1 - alpha) * (1 / (k + rank + 1))
        
        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        # Build initial results
        results = []
        for rank, chunk_id in enumerate(sorted_ids[:limit * 2]):
            chunk = self.chunks.get(chunk_id, {})
            results.append(RetrievalResult(
                id=chunk_id,
                file=chunk.get("file", ""),
                name=chunk.get("name", ""),
                signature=chunk.get("signature", ""),
                body=chunk.get("body", ""),
                score=rrf_scores[chunk_id],
                source="hybrid",
                rank=rank,
            ))
        
        # Stage 4: Re-ranking (if enabled)
        if use_reranking and self.reranker and results:
            results = self._rerank(query, results, limit)
        else:
            results = results[:limit]
        
        return results
    
    def _rerank(self, query: str, results: list[RetrievalResult], limit: int) -> list[RetrievalResult]:
        """Re-rank results using cross-encoder."""
        # Prepare (query, document) pairs
        pairs = [
            (query, f"{r.signature} {r.body[:500]}")
            for r in results
        ]
        
        # Score with cross-encoder
        scores = self.reranker.predict(pairs)
        
        # Update scores
        for result, score in zip(results, scores):
            # Blend: 70% cross-encoder + 30% RRF
            result.score = 0.7 * float(score) + 0.3 * result.score
        
        # Sort by final score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results[:limit]
    
    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "total_chunks": len(self.chunks),
            "bm25_indexed": len(self.bm25.chunk_ids) if hasattr(self.bm25, 'chunk_ids') else 0,
            "embeddings_indexed": len(self.embeddings.embeddings),
            "reranker_available": self.reranker is not None,
        }


# Global instance
_retriever: Optional[HybridRetriever] = None


def get_retriever() -> HybridRetriever:
    """Get or create global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever
