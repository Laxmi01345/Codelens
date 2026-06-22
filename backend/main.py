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

load_dotenv()

# Initialize analysis pipeline
_analysis_cache = FileCache(default_ttl=3600.0)
_analysis_pipeline = AnalysisPipeline(cache=_analysis_cache)


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

    # Step 3: Analyze all sections (single LLM call)
    print("[Main] Analyzing repository (single LLM call)...")
    try:
        sections = analyze_all_sections(repo_data)
    except Exception as e:
        raise Exception(f"Analysis failed: {str(e)}")

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
) -> str:
    """Interactive chat about a repository using single LLM call with context."""
    from cerebras.cloud.sdk import Cerebras
    from dotenv import load_dotenv
    from repo_fetcher import fetch_repo_data
    from db_utils import get_repo_analysis
    from github_client.github import GitHubClient

    load_dotenv()

    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY not found")

    client = Cerebras(api_key=api_key)

    # Get analysis context from cache/DB
    analysis = get_repo_analysis(repo_url)

    # Build context
    context_parts = []
    if analysis:
        context_parts.append(f"Purpose: {analysis.get('purpose_scope', 'N/A')[:1000]}")
        context_parts.append(f"Tech Stack: {analysis.get('tech_stack', 'N/A')[:1000]}")
        context_parts.append(f"Architecture: {analysis.get('architecture_text', 'N/A')[:1000]}")

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
                context_parts.append(f"\n## Open Issues (showing {len(issues)} most recent):\n{issues_str}")
        except Exception as e:
            print(f"[Chat] Warning: Could not fetch issues: {e}")

    # Also fetch key files for direct context
    try:
        repo_data = await fetch_repo_data(repo_url)
        for name, content in list(repo_data.get("key_files", {}).items())[:5]:
            context_parts.append(f"\n--- {name} ---\n{content[:1500]}")
        for name, content in list(repo_data.get("source_files", {}).items())[:5]:
            context_parts.append(f"\n--- {name} ---\n{content[:1500]}")
    except Exception as e:
        print(f"[Chat] Warning: Could not fetch repo data: {e}")

    context = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": """You are CodeLens, an interactive code assistant.
You help users understand the codebase by answering questions about a GitHub repository.

Rules:
1. Answer based ONLY on the provided context
2. Cite specific file paths when making observations
3. Be concise but thorough
4. If information is not in the context, say so
5. Use code examples when helpful
6. When asked about issues, list them with numbers and titles"""},
        {"role": "user", "content": f"Repository: {repo_url}\n\nContext:\n{context}\n\nQuestion: {question}"},
    ]

    response = client.chat.completions.create(
        model="zai-glm-4.7",
        messages=messages,
        max_tokens=2048,
    )

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
