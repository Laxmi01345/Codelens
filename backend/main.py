"""Main Orchestrator - Generates repository analysis using Hybrid approach."""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github_client.github import GitHubAccessError
from repo_fetcher import fetch_repo_data
from hybrid_analyzer import analyze_all_sections
from db_utils import store_repo_analysis, get_repo_analysis
from analysis.pipeline import AnalysisPipeline
from analysis.file_cache import FileCache
from analysis.chunker import chunk_all_files
from analysis.code_index import build_code_index, CodeIndex
from analysis.query_builder import build_4layer_context

load_dotenv()

# Initialize analysis pipeline
_analysis_cache = FileCache(default_ttl=3600.0)
_analysis_pipeline = AnalysisPipeline(cache=_analysis_cache)

# Cache for code indexes (repo_url -> CodeIndex)
_code_index_cache: dict[str, CodeIndex] = {}


def _get_or_build_index(repo_url: str, repo_data: dict, graph=None) -> CodeIndex:
    """Get cached code index or build a new one."""
    if repo_url in _code_index_cache:
        return _code_index_cache[repo_url]
    
    source_files = repo_data.get("source_files", {})
    key_files = repo_data.get("key_files", {})
    # Include config files in the index so the LLM can answer questions about them
    all_files = {**source_files, **key_files}
    asts = repo_data.get("asts", [])
    
    # Chunk all files into semantic units
    chunks = chunk_all_files(all_files, asts)
    print(f"[Index] Created {len(chunks)} code chunks from {len(all_files)} files ({len(source_files)} source + {len(key_files)} config)")
    
    # Build the 4-layer index
    try:
        index = build_code_index(all_files, chunks, graph)
    except Exception as e:
        print(f"[Index] ERROR building index: {e}")
        import traceback
        traceback.print_exc()
        raise
    stats = index.get_stats()
    print(f"[Index] Built index: {stats['files']} files, {stats['asts']} ASTs, "
          f"{stats['chunks']} chunks, {stats['dependencies']} deps")
    
    # Cache for future queries
    _code_index_cache[repo_url] = index
    return index


async def generate_repo_analysis(repo_url: str, force_refresh: bool = False) -> dict:
    """
    Generate comprehensive repository analysis using hybrid approach.

    Args:
        repo_url: GitHub repository URL
        force_refresh: If True, bypass cache and regenerate

    Returns:
        Dictionary with all analysis sections

    Raises:
        GitHubAccessError: If repository cannot be accessed
        ValueError: If URL is invalid
    """
    # Check DB cache first
    if not force_refresh:
        cached = get_repo_analysis(repo_url)
        if cached:
            print(f"[Main] Using cached analysis for {repo_url}")
            return cached

    # Clear code index cache so it rebuilds with all files
    _code_index_cache.pop(repo_url, None)

    print(f"[Main] Starting analysis for {repo_url}")

    # Step 1: Fetch all repository data (parallel GitHub API calls)
    print("[Main] Fetching repository data...")
    try:
        repo_data = await fetch_repo_data(repo_url)
    except GitHubAccessError as e:
        raise e
    except Exception as e:
        raise GitHubAccessError(f"Failed to fetch repository data: {str(e)}")

    # Step 2: Run static analysis pipeline (AST parsing, graph building)
    print("[Main] Running static analysis pipeline...")
    try:
        analysis_ctx = await _analysis_pipeline.analyze(
            repo_url=repo_url,
            source_files=repo_data.get("source_files", {}),
            key_files=repo_data.get("key_files", {}),
            force_refresh=force_refresh,
        )
        # Enrich repo_data with graph summary for the LLM prompt
        repo_data["graph_summary"] = analysis_ctx.graph_summary
        repo_data["asts"] = analysis_ctx.asts
        print(f"[Main] Static analysis: {len(analysis_ctx.asts)} files parsed, "
              f"graph has {analysis_ctx.graph_summary.get('total_modules', 0)} nodes")
    except Exception as e:
        print(f"[Main] Warning: Static analysis failed: {e}")

    # Step 3: Build 4-layer index for documentation generation
    print("[Main] Building 4-layer index...")
    index = _get_or_build_index(repo_url, repo_data, analysis_ctx.graph if 'analysis_ctx' in dir() else None)
    
    # Step 4: Build 4-layer context for documentation prompt
    print("[Main] Building 4-layer context for documentation...")
    from analysis.query_builder import build_4layer_context
    doc_context, doc_relevant_files = build_4layer_context(index, "Generate comprehensive documentation for this repository", repo_url)
    repo_data["four_layer_context"] = doc_context
    repo_data["relevant_files"] = doc_relevant_files
    print(f"[Main] 4-layer context length: {len(doc_context)} chars, {len(doc_relevant_files)} relevant files")

    # Step 5: Analyze all sections (single LLM call with 4-layer context)
    print("[Main] Analyzing repository (single LLM call with 4-layer context)...")
    try:
        sections = analyze_all_sections(repo_data)
    except Exception as e:
        raise Exception(f"Analysis failed: {str(e)}")

    # Step 5.5: Attach relevant source files metadata, commit hash, and file tree
    sections["_relevant_files"] = repo_data.get("relevant_files", [])
    sections["_commit_hash"] = repo_data.get("repo_info", {}).get("commit_hash", "")
    sections["_file_tree"] = repo_data.get("file_tree", {})

    # Step 4: Store in database (optional)
    print("[Main] Storing results...")
    try:
        store_repo_analysis(repo_url, sections)
    except Exception as e:
        print(f"[Main] Warning: Failed to store results: {e}")

    # Step 5: Update file cache
    _analysis_pipeline.store_result(repo_url, sections)

    print(f"[Main] Analysis complete for {repo_url}")
    return sections


async def generate_section(
    repo_url: str, section: str, context: dict = None
) -> str:
    """Generate a single analysis section (for backward compatibility)."""
    result = await generate_repo_analysis(repo_url)
    return result.get(section, "")


async def chat_with_repo(
    repo_url: str,
    question: str,
    history: list[dict] = None,
    stream: bool = False,
) -> str:
    """
    Interactive chat about a repository using 4-layer hierarchical context.
    
    Args:
        repo_url: GitHub repository URL
        question: User's question
        history: Previous conversation messages (list of {"role": "user/assistant", "content": "..."})
        stream: If True, return a generator that yields chunks (for streaming)
    """
    from cerebras.cloud.sdk import Cerebras
    from dotenv import load_dotenv
    from github_client.github import GitHubClient

    load_dotenv()

    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY not found")

    client = Cerebras(api_key=api_key)

    # Fetch repo data if not cached
    if repo_url not in _code_index_cache:
        print(f"[Chat] Building code index for {repo_url}...")
        repo_data = await fetch_repo_data(repo_url)
        
        # Build the 4-layer index
        analysis_ctx = await _analysis_pipeline.analyze(
            repo_url=repo_url,
            source_files=repo_data.get("source_files", {}),
            key_files=repo_data.get("key_files", {}),
            force_refresh=False,
        )
        _get_or_build_index(repo_url, repo_data, analysis_ctx.graph)
    else:
        print(f"[Chat] Using cached index for {repo_url}")

    index = _code_index_cache[repo_url]

    # Build 4-layer context
    context, _ = build_4layer_context(index, question, repo_url)
    print(f"[Chat] Context length: {len(context)} chars")

    # Check if question is about issues
    issue_keywords = ["issue", "issues", "bug", "bugs", "feature request", "problem", "error"]
    is_issue_question = any(keyword in question.lower() for keyword in issue_keywords)

    # Fetch issues if question is about them
    if is_issue_question:
        try:
            github = GitHubClient()
            issues = await github.get_issues(repo_url, state="open", limit=15)
            if issues:
                issues_str = "\n".join([
                    f"- #{issue['number']}: {issue['title']} [{issue['state']}]"
                    f" Labels: {', '.join(issue['labels']) if issue['labels'] else 'none'}"
                    for issue in issues
                ])
                context += f"\n\n## Open Issues (showing {len(issues)} most recent):\n{issues_str}"
        except Exception as e:
            print(f"[Chat] Warning: Could not fetch issues: {e}")

    # Build messages with conversation memory
    messages = [
        {"role": "system", "content": """You are CodeLens, an interactive code assistant.
You help users understand the codebase by answering questions about a GitHub repository.

You have access to a 4-layer hierarchical context:
- Layer 1: File metadata (names, sizes, languages)
- Layer 2: AST structure (functions, classes, imports)
- Layer 3: Dependency graph (which files import what)
- Layer 4: Relevant code chunks (actual function/class bodies)

Rules:
1. Answer based ONLY on the provided context
2. Cite specific file paths and function names when making observations
3. Be concise but thorough
4. If information is not in the context, say so
5. Use code examples when helpful
6. When asked about issues, list them with numbers and titles
7. When asked about specific files, reference Layer 2 for structure and Layer 4 for code
8. When asked about dependencies, reference Layer 3
9. Remember the conversation context - if user asks follow-up questions, reference previous messages"""},
    ]
    
    # Add conversation history (last 4 messages for memory)
    if history:
        for msg in history[-4:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current context + question
    messages.append({"role": "user", "content": f"Repository: {repo_url}\n\nContext:\n{context}\n\nQuestion: {question}"})

    # Streaming mode - return generator
    if stream:
        def stream_response():
            response = client.chat.completions.create(
                model="zai-glm-4.7",
                messages=messages,
                max_tokens=2048,
                stream=True,
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        return stream_response()

    # Non-streaming mode
    response = client.chat.completions.create(
        model="zai-glm-4.7",
        messages=messages,
        max_tokens=2048,
    )

    return response.choices[0].message.content or "No response generated."

    return response.choices[0].message.content or "No response generated."


if __name__ == "__main__":
    # Test the orchestrator
    import sys
    
    if len(sys.argv) > 1:
        repo = sys.argv[1]
    else:
        repo = "https://github.com/octocat/Hello-World"
    
    result = asyncio.run(generate_repo_analysis(repo))
    print("\n" + "=" * 60)
    print("ANALYSIS RESULT")
    print("=" * 60)
    for section, content in result.items():
        print(f"\n### {section.upper()}")
        print(content[:500] + "..." if len(content) > 500 else content)
