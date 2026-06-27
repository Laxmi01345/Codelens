"""Vector Store - Qdrant integration for persistent embeddings."""

import os
from typing import Optional
from dataclasses import dataclass

# Try to import Qdrant (optional dependency)
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    print("[VectorStore] qdrant-client not installed. Using in-memory embeddings.")


@dataclass
class VectorStore:
    """
    Qdrant vector store for persistent embeddings.
    
    Interview point: "We use Qdrant for persistent vector storage,
    enabling fast semantic search across large codebases with
    filtering by file, language, and code type."
    
    Benefits over in-memory:
    1. Persistence - survives restarts
    2. Filtering - search by file, language, type
    3. Scalability - handles millions of vectors
    4. Performance - optimized ANN search
    """
    
    def __init__(self, collection_name: str = "code_chunks"):
        self.collection_name = collection_name
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to Qdrant server."""
        if not QDRANT_AVAILABLE:
            print("[VectorStore] Qdrant not available, using fallback")
            return
        
        try:
            # Connect to Qdrant (Docker or cloud)
            qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
            api_key = os.getenv("QDRANT_API_KEY")
            
            if api_key:
                # Cloud Qdrant
                self.client = QdrantClient(url=qdrant_url, api_key=api_key)
            else:
                # Local Docker Qdrant
                self.client = QdrantClient(url=qdrant_url)
            
            # Create collection if it doesn't exist
            self._ensure_collection()
            print(f"[VectorStore] Connected to Qdrant at {qdrant_url}")
            
        except Exception as e:
            print(f"[VectorStore] Could not connect to Qdrant: {e}")
            self.client = None
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        if not self.client:
            return
        
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if self.collection_name not in collection_names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # all-MiniLM-L6-v2 dimension
                    distance=Distance.COSINE,
                ),
            )
            print(f"[VectorStore] Created collection: {self.collection_name}")
    
    def upsert_chunks(self, chunks: list[dict], embeddings: list[list[float]]):
        """
        Upsert code chunks with their embeddings.
        
        Args:
            chunks: List of chunk metadata (id, file, type, name, signature, body)
            embeddings: List of embedding vectors
        """
        if not self.client:
            return
        
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point = PointStruct(
                id=hash(chunk["id"]) % (2**31),  # Convert to int
                vector=embedding,
                payload={
                    "chunk_id": chunk["id"],
                    "file": chunk.get("file", ""),
                    "type": chunk.get("type", ""),
                    "name": chunk.get("name", ""),
                    "signature": chunk.get("signature", ""),
                    "body": chunk.get("body", "")[:2000],  # Limit body size
                },
            )
            points.append(point)
        
        # Batch upsert (max 100 per batch)
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
        
        print(f"[VectorStore] Upserted {len(points)} chunks")
    
    def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        file_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Search for similar code chunks.
        
        Args:
            query_embedding: Query vector
            limit: Max results
            file_filter: Filter by file path
            type_filter: Filter by chunk type (function, class, etc.)
        
        Returns:
            List of matching chunks with scores
        """
        if not self.client:
            return []
        
        # Build filter conditions
        must_conditions = []
        
        if file_filter:
            must_conditions.append(
                FieldCondition(key="file", match=MatchValue(value=file_filter))
            )
        
        if type_filter:
            must_conditions.append(
                FieldCondition(key="type", match=MatchValue(value=type_filter))
            )
        
        query_filter = Filter(must=must_conditions) if must_conditions else None
        
        # Search
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=query_filter,
        )
        
        return [
            {
                "id": hit.payload.get("chunk_id", ""),
                "file": hit.payload.get("file", ""),
                "type": hit.payload.get("type", ""),
                "name": hit.payload.get("name", ""),
                "signature": hit.payload.get("signature", ""),
                "body": hit.payload.get("body", ""),
                "score": hit.score,
            }
            for hit in results
        ]
    
    def get_stats(self) -> dict:
        """Get collection statistics."""
        if not self.client:
            return {"status": "disconnected"}
        
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "status": "connected",
                "vectors": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def delete_collection(self):
        """Delete the collection (for testing)."""
        if self.client:
            try:
                self.client.delete_collection(self.collection_name)
                print(f"[VectorStore] Deleted collection: {self.collection_name}")
            except Exception:
                pass


# Global instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create global vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
