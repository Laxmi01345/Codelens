"""Analysis Pipeline - Orchestrates static analysis, graph building, and context engineering."""

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from .ast_parser import parse_file, FileAST
from .graph_builder import DependencyGraph, build_dependency_graph
from .file_cache import FileCache


@dataclass
class AnalysisContext:
    """Enriched context for LLM analysis."""
    repo_url: str
    asts: list[FileAST] = field(default_factory=list)
    graph: Optional[DependencyGraph] = None
    graph_summary: Optional[dict] = None
    changed_files: list[str] = field(default_factory=list)
    new_files: list[str] = field(default_factory=list)
    needs_full_analysis: bool = True
    cache_hit: bool = False


class AnalysisPipeline:
    """
    Pipeline that enriches repository data with static analysis.

    Flow:
    1. Parse source files with regex-based AST parser
    2. Build dependency graph from imports
    3. Check file cache for incremental analysis
    4. Generate enriched context for LLM
    """

    def __init__(self, cache: Optional[FileCache] = None):
        self.cache = cache or FileCache()

    async def analyze(
        self,
        repo_url: str,
        source_files: dict[str, str],
        key_files: dict[str, str],
        force_refresh: bool = False,
    ) -> AnalysisContext:
        """
        Run the analysis pipeline.

        Args:
            repo_url: Repository URL
            source_files: Dict of source file paths to contents
            key_files: Dict of config file paths to contents
            force_refresh: Force full re-analysis

        Returns:
            AnalysisContext with enriched data
        """
        print(f"[Pipeline] Analyzing {len(source_files)} source files for {repo_url}")

        ctx = AnalysisContext(repo_url=repo_url)

        # Step 1: Parse all source files
        ctx.asts = self._parse_files(source_files)
        print(f"[Pipeline] Parsed {len(ctx.asts)} files into ASTs")

        # Step 2: Build dependency graph
        ctx.graph = build_dependency_graph(ctx.asts)
        ctx.graph_summary = ctx.graph.to_summary()
        print(f"[Pipeline] Built graph: {ctx.graph_summary['total_modules']} nodes, "
              f"{ctx.graph_summary['total_edges']} edges")

        # Step 3: Check cache for incremental analysis
        all_files = {**source_files, **key_files}

        if not force_refresh:
            cached = self.cache.get_cached_analysis(repo_url)
            if cached:
                ctx.cache_hit = True
                ctx.needs_full_analysis = False
                print("[Pipeline] Cache hit - skipping full analysis")
                return ctx

            if not self.cache.needs_full_analysis(repo_url, all_files):
                ctx.changed_files, ctx.new_files = self.cache.get_changed_files(
                    repo_url, all_files
                )
                ctx.needs_full_analysis = False
                print(f"[Pipeline] Incremental: {len(ctx.changed_files)} changed, "
                      f"{len(ctx.new_files)} new files")
                return ctx

        # Step 4: Store hashes for next run
        self.cache.store_analysis(repo_url, all_files, {})  # Empty result, will be filled later
        ctx.needs_full_analysis = True

        return ctx

    def store_result(self, repo_url: str, result: dict) -> None:
        """Store the analysis result in cache."""
        self.cache.save_to_disk(repo_url)

    def _parse_files(self, files: dict[str, str]) -> list[FileAST]:
        """Parse multiple files into ASTs."""
        asts = []
        for path, content in files.items():
            try:
                ast = parse_file(path, content)
                asts.append(ast)
            except Exception as e:
                print(f"[Pipeline] Error parsing {path}: {e}")
        return asts

    def get_relevant_files_for_prompt(
        self,
        asts: list[FileAST],
        graph: DependencyGraph,
        max_files: int = 10,
    ) -> list[str]:
        """
        Select most relevant files for the LLM prompt.

        Priority:
        1. Hub modules (most dependents)
        2. High complexity files
        3. Entry points (files with many imports)
        4. Recently changed files
        """
        scored = []

        # Get hub modules
        hubs = {path for path, _ in graph.get_hub_modules(5)}

        for ast in asts:
            score = 0.0

            # Hub modules are important
            if ast.path in hubs:
                score += 3.0

            # Higher complexity = more important
            score += ast.complexity_score * 0.5

            # More functions = more important
            score += len(ast.functions) * 0.3

            # More classes = more important
            score += len(ast.classes) * 0.5

            # Files with many imports suggest orchestration
            score += len(ast.imports) * 0.2

            scored.append((ast.path, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)

        return [path for path, _ in scored[:max_files]]

    def get_context_summary(self, ctx: AnalysisContext) -> str:
        """Generate a text summary of the analysis context for the LLM."""
        if not ctx.graph_summary:
            return ""

        summary = ctx.graph_summary
        lines = [
            "## Static Analysis Summary",
            f"- Total modules: {summary['total_modules']}",
            f"- Total dependencies: {summary['total_edges']}",
            f"- Languages: {', '.join(summary['languages'])}",
            f"- Has circular dependencies: {summary['has_cycles']}",
        ]

        if summary["hub_modules"]:
            lines.append("\n### Hub Modules (most depended upon)")
            for path, count in summary["hub_modules"]:
                lines.append(f"- {path} ({count} dependents)")

        if summary["isolated_modules"]:
            lines.append("\n### Isolated Modules (no dependencies)")
            for path in summary["isolated_modules"][:5]:
                lines.append(f"- {path}")

        if summary["cycles"]:
            lines.append("\n### Circular Dependencies")
            for cycle_info in summary["cycles"]:
                lines.append(f"- Cycle (depth {cycle_info['depth']}): {' → '.join(cycle_info['cycle'])}")

        return "\n".join(lines)
