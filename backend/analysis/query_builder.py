"""Query Builder - Builds 4-layer context for LLM queries."""

import re
from .code_index import CodeIndex


# Query type patterns
SUMMARY_PATTERNS = [
    r"^(what|give|show|describe|explain|summarize|overview|tell me about|summary)",
    r"project\b",
    r"repository\b",
    r"codebase\b",
    r"overall\b",
    r"general\b",
    r"purpose\b",
    r"tech stack\b",
    r"architecture\b",
    r"what does .* do\b",
    r"how does .* work\b",
]

SPECIFIC_PATTERNS = [
    r"file\b",
    r"function\b",
    r"class\b",
    r"method\b",
    r"import\b",
    r"dependency\b",
    r"caller\b",
    r"who calls\b",
    r"who uses\b",
    r"what calls\b",
    r"what uses\b",
    r"show me\b",
    r"read\b",
    r"open\b",
    r"content\b",
    r"code\b",
    r"implementation\b",
    r"body\b",
    r"source\b",
]


def detect_query_type(question: str) -> str:
    """
    Detect if question is asking for summary or specific details.
    
    Returns:
        'summary' - Only needs Layers 1-2 (file metadata + AST structure)
        'specific' - Needs all 4 layers (including dependencies + code chunks)
    """
    question_lower = question.lower().strip()
    
    # Check for specific file references (e.g., "auth.py", "src/api.ts")
    if re.search(r'[\w/]+\.\w+', question_lower):
        return "specific"
    
    # Check for specific query patterns
    for pattern in SPECIFIC_PATTERNS:
        if re.search(pattern, question_lower):
            return "specific"
    
    # Check for summary query patterns
    for pattern in SUMMARY_PATTERNS:
        if re.search(pattern, question_lower):
            return "summary"
    
    # Default to specific (safer - includes all context)
    return "specific"


def extract_keywords(question: str) -> list[str]:
    """Extract meaningful keywords from a question."""
    # Remove common stop words
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
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', question.lower())
    
    # Filter stop words and short words
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Also extract file paths
    file_patterns = re.findall(r'[\w/]+\.\w+', question)
    keywords.extend(file_patterns)
    
    return list(set(keywords))


def build_layer1(index: CodeIndex) -> str:
    """Build Layer 1: File Metadata Index (always included)."""
    files = index.get_all_files()
    if not files:
        return ""
    
    lines = ["## Layer 1: File Metadata Index"]
    lines.append("| Path | Language | Size | Lines |")
    lines.append("|------|----------|------|-------|")
    
    for f in sorted(files, key=lambda x: x["path"]):
        size_str = f"{f['size']}B" if f['size'] < 1024 else f"{f['size']//1024}KB"
        lines.append(f"| {f['path']} | {f['language']} | {size_str} | {f['line_count']} |")
    
    return "\n".join(lines)


def build_layer2(index: CodeIndex) -> str:
    """Build Layer 2: AST Structure Map (always included)."""
    asts = index.get_all_asts()
    if not asts:
        return ""
    
    lines = ["## Layer 2: AST Structure Map"]
    
    # Group by file
    by_file = {}
    for ast in asts:
        fp = ast["file_path"]
        if fp not in by_file:
            by_file[fp] = {"functions": [], "classes": []}
        if ast["type"] == "function":
            by_file[fp]["functions"].append(ast)
        else:
            by_file[fp]["classes"].append(ast)
    
    for fp, data in sorted(by_file.items()):
        lines.append(f"\n### {fp}")
        if data["functions"]:
            funcs = [f"{a['name']}({a['signature'].split('(', 1)[1]}" if '(' in a['signature'] else a['name']
                     for a in data["functions"]]
            lines.append(f"- Functions: {', '.join(funcs)}")
        if data["classes"]:
            classes = [a['name'] for a in data["classes"]]
            lines.append(f"- Classes: {', '.join(classes)}")
    
    return "\n".join(lines)


def build_layer3(index: CodeIndex, keywords: list[str]) -> str:
    """Build Layer 3: Dependency Graph (question-driven)."""
    lines = ["## Layer 3: Dependency Graph"]
    found_any = False
    
    for keyword in keywords:
        # Search for imports
        importers = index.get_importers(keyword)
        imports = index.get_imports(keyword)
        
        if importers:
            if not found_any:
                lines.append("")
                found_any = True
            lines.append(f"\n### Who imports '{keyword}':")
            for imp in importers[:5]:
                lines.append(f"- {imp}")
        
        if imports:
            if not found_any:
                lines.append("")
                found_any = True
            lines.append(f"\n### What '{keyword}' imports:")
            for imp in imports[:5]:
                lines.append(f"- {imp}")
    
    if not found_any:
        return ""
    
    return "\n".join(lines)


def build_layer4(index: CodeIndex, question: str, limit: int = 5) -> str:
    """Build Layer 4: Semantic Code Chunks (embeddings-based search)."""
    chunks = index.search_chunks(question, limit=limit)
    if not chunks:
        return ""
    
    lines = ["## Layer 4: Relevant Code Chunks (Semantic Search)"]
    
    for chunk in chunks:
        lines.append(f"\n### {chunk['file']}::{chunk['name']}")
        lines.append(f"**Signature:** `{chunk['signature']}`")
        lines.append(f"**Relevance Score:** {chunk['score']:.4f}")
        lines.append(f"**Body:**")
        lines.append(f"```")
        # Truncate body to 2000 chars
        body = chunk['body'][:2000]
        if len(chunk['body']) > 2000:
            body += "\n... (truncated)"
        lines.append(body)
        lines.append("```")
    
    return "\n".join(lines)


def build_4layer_context(
    index: CodeIndex,
    question: str,
    repo_url: str = "",
) -> tuple[str, list[dict]]:
    """
    Build complete 4-layer context for LLM.
    
    Returns:
        Tuple of (context_string, relevant_files) where relevant_files is a list
        of dicts with file metadata and relevance scores.
    
    Smart layer selection based on query type:
    - Summary queries: Only Layers 1-2 (~3K tokens)
    - Specific queries: All 4 layers (~8K tokens)
    """
    # Detect query type
    query_type = detect_query_type(question)
    
    context_parts = []
    relevant_files = []
    seen_files = set()
    
    # Add repo URL if provided
    if repo_url:
        context_parts.append(f"# Repository: {repo_url}")
    
    # Layer 1: File Metadata (ALWAYS)
    layer1 = build_layer1(index)
    if layer1:
        context_parts.append(layer1)
        # All files are relevant for Layer 1
        for f in index.get_all_files():
            if f["path"] not in seen_files:
                relevant_files.append({
                    "path": f["path"],
                    "language": f["language"],
                    "size": f["size"],
                    "line_count": f["line_count"],
                    "source": "file_metadata",
                })
                seen_files.add(f["path"])
    
    # Layer 2: AST Structure (ALWAYS)
    layer2 = build_layer2(index)
    if layer2:
        context_parts.append(layer2)
        # Files with AST structures are relevant
        for ast in index.get_all_asts():
            fp = ast["file_path"]
            if fp not in seen_files:
                relevant_files.append({
                    "path": fp,
                    "language": "",
                    "size": 0,
                    "line_count": 0,
                    "source": "ast_structure",
                    "ast_name": ast["name"],
                    "ast_type": ast["type"],
                })
                seen_files.add(fp)
    
    # Layers 3-4: Only for specific queries
    if query_type == "specific":
        # Extract keywords for question-driven layers
        keywords = extract_keywords(question)
        
        # Layer 3: Dependency Graph (QUESTION-DRIVEN)
        layer3 = build_layer3(index, keywords)
        if layer3:
            context_parts.append(layer3)
            # Files in dependency graph are relevant
            for keyword in keywords:
                importers = index.get_importers(keyword)
                imports = index.get_imports(keyword)
                for fp in importers + imports:
                    if fp not in seen_files:
                        relevant_files.append({
                            "path": fp,
                            "language": "",
                            "size": 0,
                            "line_count": 0,
                            "source": "dependency_graph",
                        })
                        seen_files.add(fp)
        
        # Layer 4: Code Chunks (QUESTION-DRIVEN)
        layer4 = build_layer4(index, question, limit=5)
        if layer4:
            context_parts.append(layer4)
            # Chunks with high relevance scores are relevant
            chunks = index.search_chunks(question, limit=5)
            for chunk in chunks:
                fp = chunk["file"]
                if fp not in seen_files:
                    relevant_files.append({
                        "path": fp,
                        "language": "",
                        "size": 0,
                        "line_count": 0,
                        "source": "semantic_search",
                        "relevance_score": chunk["score"],
                        "chunk_name": chunk["name"],
                    })
                    seen_files.add(fp)
    
    return "\n\n".join(context_parts), relevant_files
