"""Re-ranking - Cross-encoder re-ranks results for precision."""

import numpy as np
from typing import Optional


class CrossEncoderReranker:
    """
    Re-ranks search results using a cross-encoder model.
    
    Interview point: "Initial retrieval optimizes for recall (find many
    candidates), re-ranking optimizes for precision (pick the best ones)."
    
    How it works:
    1. Initial retrieval (embeddings) finds top-20 candidates
    2. Cross-encoder scores each (query, document) pair
    3. Re-ranked results are more precise
    """
    
    def __init__(self):
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load cross-encoder model."""
        try:
            from sentence_transformers import CrossEncoder
            print("[Reranker] Loading cross-encoder model...")
            self.model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            print("[Reranker] Cross-encoder loaded.")
        except Exception as e:
            print(f"[Reranker] Could not load cross-encoder: {e}")
            print("[Reranker] Using fallback scoring.")
    
    def rerank(self, query: str, results: list[dict], top_k: int = 5) -> list[dict]:
        """
        Re-rank results using cross-encoder scoring.
        
        Args:
            query: Original search query
            results: Initial retrieval results
            top_k: Number of results to return
        
        Returns:
            Re-ranked results
        """
        if not results:
            return []
        
        if not self.model:
            # Fallback: return top_k by original score
            return results[:top_k]
        
        # Prepare (query, document) pairs
        pairs = []
        for result in results:
            # Combine signature and body for scoring
            doc = f"{result.get('signature', '')} {result.get('body', '')[:500]}"
            pairs.append((query, doc))
        
        # Score with cross-encoder
        scores = self.model.predict(pairs)
        
        # Combine with original scores
        for i, (result, score) in enumerate(zip(results, scores)):
            result["rerank_score"] = float(score)
            # Blend scores: 70% cross-encoder + 30% original
            original = result.get("score", 0)
            result["final_score"] = 0.7 * float(score) + 0.3 * original
        
        # Sort by final score
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        
        return results[:top_k]


class HybridReranker:
    """
    Combines multiple re-ranking strategies.
    
    Interview point: "We use a multi-signal re-ranking approach
    combining semantic similarity, code structure, and relevance."
    """
    
    def __init__(self):
        self.cross_encoder = CrossEncoderReranker()
    
    def rerank(self, query: str, results: list[dict], 
               top_k: int = 5, context: dict = None) -> list[dict]:
        """
        Multi-signal re-ranking.
        
        Signals:
        1. Cross-encoder semantic similarity
        2. Code structure relevance (function vs class)
        3. File location (same file as context)
        4. Hop distance (closer is better)
        """
        if not results:
            return []
        
        # Apply cross-encoder re-ranking
        results = self.cross_encoder.rerank(query, results, top_k=len(results))
        
        # Apply additional signals
        for result in results:
            score = result.get("final_score", result.get("score", 0))
            
            # Signal 2: Code structure relevance
            if result.get("type") == "function":
                score += 0.05  # Slight boost for functions
            
            # Signal 3: File location
            if context:
                current_file = context.get("current_file", "")
                if result.get("file") == current_file:
                    score += 0.1
            
            # Signal 4: Hop distance
            hop = result.get("hop", 1)
            hop_penalty = (hop - 1) * 0.05
            score -= hop_penalty
            
            result["final_score"] = score
        
        # Sort by final score
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        
        return results[:top_k]


class SimpleReranker:
    """
    Lightweight reranker without cross-encoder (fallback).
    
    Uses heuristics for re-ranking when cross-encoder is not available.
    """
    
    def rerank(self, query: str, results: list[dict], 
               top_k: int = 5, context: dict = None) -> list[dict]:
        """Simple heuristic re-ranking."""
        for result in results:
            score = result.get("score", 0)
            
            # Boost exact name matches
            if query.lower() in result.get("name", "").lower():
                score += 0.3
            
            # Boost function definitions over just code
            if result.get("type") == "function":
                score += 0.1
            
            # Apply hop penalty
            hop = result.get("hop", 1)
            score -= (hop - 1) * 0.1
            
            result["final_score"] = score
        
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return results[:top_k]
