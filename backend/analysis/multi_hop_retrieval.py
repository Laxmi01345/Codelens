"""Multi-hop Retrieval - Follows relationships to find related code."""

from typing import Optional
from .code_property_graph import CodePropertyGraph, NodeType, EdgeType
from .code_index import CodeIndex


class MultiHopRetriever:
    """
    Multi-hop retrieval that follows code relationships.
    
    Interview point: "Instead of single-step retrieval, we follow
    the call chain to find related code the user might need."
    
    Example:
        Query: "How does login work?"
        Hop 1: Find "login" function
        Hop 2: Find what "login" calls (validate_password, create_session)
        Hop 3: Find what calls "login" (auth_router, middleware)
    """
    
    def __init__(self, index: CodeIndex, cpg: Optional[CodePropertyGraph] = None):
        self.index = index
        self.cpg = cpg
    
    def retrieve(self, query: str, hops: int = 2, limit: int = 5) -> list[dict]:
        """
        Multi-hop retrieval following code relationships.
        
        Args:
            query: Search query
            hops: Number of relationship hops to follow
            limit: Max results per hop
        
        Returns:
            Combined results from all hops
        """
        all_results = []
        seen_ids = set()
        
        # Hop 1: Direct semantic search
        direct_results = self.index.search_chunks(query, limit=limit)
        for result in direct_results:
            if result["id"] not in seen_ids:
                result["hop"] = 1
                result["reason"] = "direct_match"
                all_results.append(result)
                seen_ids.add(result["id"])
        
        # Hop 2+: Follow relationships
        if self.cpg and hops > 1:
            for hop in range(2, hops + 1):
                new_results = []
                
                # For each result from previous hop, find related code
                for prev_result in all_results[-limit:]:  # Only process latest batch
                    related = self._find_related(prev_result, hop)
                    for r in related:
                        if r["id"] not in seen_ids:
                            new_results.append(r)
                            seen_ids.add(r["id"])
                
                all_results.extend(new_results)
                
                if not new_results:
                    break  # No more related code found
        
        return all_results
    
    def _find_related(self, result: dict, hop: int) -> list[dict]:
        """Find code related to a result through CPG relationships."""
        related = []
        
        # Extract function name from result
        func_name = result.get("name", "")
        if not func_name:
            return related
        
        # Find callers (who uses this function)
        if self.cpg:
            callers = self.cpg.get_callers(func_name, max_depth=1)
            for caller in callers[:2]:  # Limit to 2 callers
                # Search for caller in index
                caller_results = self.index.search_chunks(caller["name"], limit=1)
                for r in caller_results:
                    r["hop"] = hop
                    r["reason"] = f"calls_{func_name}"
                    related.append(r)
            
            # Find callees (what this function uses)
            callees = self.cpg.get_callees(func_name, max_depth=1)
            for callee in callees[:2]:
                callee_results = self.index.search_chunks(callee["name"], limit=1)
                for r in callee_results:
                    r["hop"] = hop
                    r["reason"] = f"called_by_{func_name}"
                    related.append(r)
        
        return related


class ContextualRetriever:
    """
    Combines multi-hop retrieval with context-aware ranking.
    
    Interview point: "We don't just find relevant code - we find
    code that's relevant in the context of the user's question."
    """
    
    def __init__(self, index: CodeIndex, cpg: Optional[CodePropertyGraph] = None):
        self.index = index
        self.cpg = cpg
        self.multi_hop = MultiHopRetriever(index, cpg)
    
    def retrieve(self, query: str, context: dict = None, limit: int = 10) -> list[dict]:
        """
        Context-aware retrieval.
        
        Args:
            query: Search query
            context: Additional context (current file, recent queries, etc.)
            limit: Max results
        
        Returns:
            Context-ranked results
        """
        # Get multi-hop results
        results = self.multi_hop.retrieve(query, hops=2, limit=limit)
        
        # Apply context boosting
        if context:
            results = self._apply_context_boost(results, context)
        
        # Sort by final score
        results.sort(key=lambda x: x.get("final_score", x.get("score", 0)), reverse=True)
        
        return results[:limit]
    
    def _apply_context_boost(self, results: list[dict], context: dict) -> list[dict]:
        """Boost results based on context."""
        current_file = context.get("current_file", "")
        recent_files = context.get("recent_files", [])
        
        for result in results:
            score = result.get("score", 0)
            boost = 0
            
            # Boost if in current file
            if current_file and result.get("file") == current_file:
                boost += 0.2
            
            # Boost if in recently viewed files
            if result.get("file") in recent_files:
                boost += 0.1
            
            # Boost based on hop (earlier hops are better)
            hop = result.get("hop", 1)
            hop_boost = max(0, 0.3 - (hop - 1) * 0.1)
            boost += hop_boost
            
            result["final_score"] = score + boost
        
        return results
