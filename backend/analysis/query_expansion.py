"""Query Expansion - Generates multiple search queries for better recall."""

import os
import json
from typing import Optional


class QueryExpander:
    """
    Expands a single user query into multiple search queries.
    
    Interview point: "Query expansion improves recall by generating
    multiple perspectives on the same question."
    
    Example:
        User: "How does authentication work?"
        Expanded:
            1. "authentication login validate credentials"
            2. "auth middleware session token JWT"
            3. "user password verify check"
    """
    
    def __init__(self):
        self.expansion_count = 3  # Number of expanded queries
    
    def expand(self, question: str, context: str = "") -> list[str]:
        """
        Expand a query into multiple search queries.
        
        Args:
            question: Original user question
            context: Optional context (file names, function names)
        
        Returns:
            List of expanded queries (including original)
        """
        # Rule-based expansion (no LLM needed)
        expanded = [question]  # Always include original
        
        # Extract keywords
        keywords = self._extract_keywords(question)
        
        # Generate variations
        expanded.extend(self._generate_variations(question, keywords))
        
        # Add context-based queries if available
        if context:
            expanded.extend(self._context_queries(keywords, context))
        
        return expanded[:self.expansion_count + 1]  # Limit to N+1 queries
    
    def _extract_keywords(self, question: str) -> list[str]:
        """Extract meaningful keywords from question."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "dare", "ought",
            "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above", "below",
            "between", "out", "off", "over", "under", "again", "further", "then",
            "once", "here", "there", "when", "where", "why", "how", "all", "each",
            "every", "both", "few", "more", "most", "other", "some", "such", "no",
            "not", "only", "own", "same", "so", "than", "too", "very", "just",
            "don", "now", "about", "what", "which", "who", "whom", "this", "that",
            "these", "those", "tell", "me", "about", "does", "it", "do",
        }
        
        words = question.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def _generate_variations(self, question: str, keywords: list[str]) -> list[str]:
        """Generate query variations from keywords."""
        variations = []
        
        # Variation 1: Keywords only (no stop words)
        if keywords:
            variations.append(" ".join(keywords[:5]))
        
        # Variation 2: Synonyms/related terms
        synonym_map = {
            "auth": "authentication login",
            "login": "auth authenticate",
            "user": "account person",
            "error": "exception failure",
            "function": "method def",
            "class": "type object",
            "import": "require include",
            "api": "endpoint route",
            "database": "db storage",
            "test": "spec assertion",
        }
        
        expanded_keywords = []
        for kw in keywords:
            if kw in synonym_map:
                expanded_keywords.extend(synonym_map[kw].split())
            else:
                expanded_keywords.append(kw)
        
        if expanded_keywords != keywords:
            variations.append(" ".join(expanded_keywords[:5]))
        
        return variations
    
    def _context_queries(self, keywords: list[str], context: str) -> list[str]:
        """Generate context-aware queries."""
        queries = []
        
        # Extract file names from context
        import re
        files = re.findall(r'[\w/]+\.\w+', context)
        
        if files:
            # Query combining keywords with file names
            queries.append(f"{' '.join(keywords[:3])} {files[0]}")
        
        return queries


class LLMQueryExpander:
    """
    LLM-based query expansion for better quality.
    
    Uses Cerebras to generate semantic variations.
    """
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Cerebras client."""
        try:
            from cerebras.cloud.sdk import Cerebras
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv("CEREBRAS_API_KEY")
            if api_key:
                self.client = Cerebras(api_key=api_key)
        except Exception:
            pass
    
    def expand(self, question: str, context: str = "") -> list[str]:
        """Expand query using LLM."""
        if not self.client:
            # Fallback to rule-based
            return QueryExpander().expand(question, context)
        
        try:
            prompt = f"""Generate 3 search queries to find relevant code for this question.
Each query should focus on different aspects of the question.

Question: {question}

Context (file names, functions): {context}

Return JSON array of 3 queries. Example: ["query1", "query2", "query3"]
Only return the JSON array, no other text."""

            response = self.client.chat.completions.create(
                model="zai-glm-4.7",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            
            content = response.choices[0].message.content.strip()
            # Parse JSON array
            queries = json.loads(content)
            if isinstance(queries, list):
                return [question] + queries[:3]  # Include original
            
        except Exception as e:
            print(f"[QueryExpander] LLM expansion failed: {e}")
        
        # Fallback
        return QueryExpander().expand(question, context)
