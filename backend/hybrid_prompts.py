"""Hybrid Prompts - Combined prompt for single LLM call analysis."""


SYSTEM_PROMPT = """You are CodeLens, an expert software architect and code analyst.

CRITICAL RULES - VIOLATION IS NOT ACCEPTABLE:
1. You are given EXACT file contents and directory structure from a real GitHub repository.
2. You MUST use ONLY the data provided below. Every statement you make MUST reference a specific file path from the provided data.
3. If information is not present in the provided files, say "Not found in provided files" — DO NOT GUESS, DO NOT HALLUCINATE.
4. Do NOT invent file names, function names, class names, or any code that is not explicitly shown in the provided data.
5. For technology stack: only list technologies that are EXPLICITLY present in the provided config files (package.json, requirements.txt, etc.) or source code.
6. For architecture: only describe what you can infer from the actual file contents and directory structure provided.
7. Every section must contain specific file paths as evidence for your claims."""


def build_hybrid_prompt(repo_data: dict) -> str:
    """
    Build a single comprehensive prompt from repository data.

    Args:
        repo_data: Dictionary containing:
            - repo_info: Repository metadata
            - file_tree: Directory structure
            - key_files: Content of config files
            - source_files: Content of main source files
            - asts: Parsed AST data (optional)
            - graph_summary: Dependency graph summary (optional)

    Returns:
        Combined prompt string
    """
    repo_info = repo_data.get("repo_info", {})
    file_tree = repo_data.get("file_tree", {})
    key_files = repo_data.get("key_files", {})
    source_files = repo_data.get("source_files", {})
    asts = repo_data.get("asts", [])
    graph_summary = repo_data.get("graph_summary", {})

    # Format file tree
    tree_str = _format_file_tree(file_tree)

    # Format key files
    key_files_str = ""
    for name, content in key_files.items():
        limited_content = content[:3000] if len(content) > 3000 else content
        key_files_str += f"\n### FILE: {name}\n```\n{limited_content}\n```\n"

    # Extract descriptions from config files
    descriptions_from_config = []
    for name, content in key_files.items():
        if "package.json" in name:
            import json as _json
            try:
                pkg = _json.loads(content)
                if pkg.get("description"):
                    descriptions_from_config.append(f"package.json: {pkg['description']}")
            except Exception:
                pass
        elif "pyproject.toml" in name:
            for line in content.split("\n"):
                if line.strip().startswith("description"):
                    desc = line.split("=", 1)[-1].strip().strip('"').strip("'")
                    if desc:
                        descriptions_from_config.append(f"pyproject.toml: {desc}")

    descriptions_str = ""
    if descriptions_from_config:
        descriptions_str = "\n## Descriptions from Config Files\n" + "\n".join(f"- {d}" for d in descriptions_from_config) + "\n"

    # Format source files
    source_files_str = ""
    for name, content in source_files.items():
        limited_content = content[:2000] if len(content) > 2000 else content
        source_files_str += f"\n### FILE: {name}\n```\n{limited_content}\n```\n"

    topics = repo_info.get("topics", [])
    topics_str = ", ".join(topics) if topics else "None"

    # Format AST data (functions, classes, imports)
    ast_str = _format_asts(asts)

    # Format graph summary
    graph_str = _format_graph_summary(graph_summary)

    prompt = f"""=== REPOSITORY DATA BELOW — USE ONLY THIS DATA ===

## Repository Metadata
- URL: https://github.com/{repo_info.get('name', 'unknown')}
- Description: {repo_info.get('description', 'No description provided on GitHub')}
- Primary Language: {repo_info.get('language', 'Not specified')}
- Default Branch: {repo_info.get('default_branch', 'main')}
- Topics/Tags: {topics_str}

NOTE: The "Description" and "Topics" above are from GitHub. If README.md is missing, use these as the primary sources for understanding the project's purpose.
{descriptions_str}
## Directory Structure (complete file tree)
```text
{tree_str}
```

## Config File Contents (actual file contents from the repo)
{key_files_str if key_files_str else "No configuration files were found in the repository root."}

## Source File Contents (actual file contents from the repo)
{source_files_str if source_files_str else "No source files were found in common source directories (src/, lib/, app/, etc.)."}

{ast_str}
{graph_str}
=== END OF REPOSITORY DATA ===

Now generate documentation based ONLY on the data above. Every claim must cite a specific file path from the data above.

---

## Section 1: Purpose & Scope

Write 2-4 paragraphs covering:
- What does this project do?
- Who is it for?
- What are its main capabilities?
- What is its current status?

IMPORTANT: Determine project purpose from these sources (in order of priority):
1. README.md content (if present)
2. Repository description from GitHub metadata
3. package.json "description" field, pyproject.toml "description" field, or similar
4. Docstrings in main entry point files (e.g., __init__.py, main.py, app.py)
5. File and directory names that indicate purpose

Cite your source: "As stated in README.md...", "According to pyproject.toml...", "Based on the GitHub description..."

---

## Section 2: Repository Layout

Output the directory tree using the EXACT format below. Use the real file/folder names from the repository data provided above.

Example format (copy this exact style):

```
my-project/
├── .gitignore
├── README.md
├── package.json
├── src/
│   ├── assets/
│   │   └── logo.png
│   ├── components/
│   │   ├── Button.js
│   │   └── Navbar.js
│   └── index.js
└── tests/
    └── alpha.test.js
```

Rules:
- Use ├── for items that have more items below them
- Use └── for the last item in a folder
- Use │ for vertical lines connecting items in nested folders
- Indent with spaces to show nesting depth
- Include actual file names and folder names from the repository
- Show 2-3 levels deep, not everything

After the tree, add a blank line and a short paragraph explaining the folder structure pattern.

---

## Section 3: Source Layer

List key source files with their actual roles, based on the source file contents provided above.

You MUST use a Markdown table:

| File | Purpose |
|------|---------|
| src/flask/__init__.py | Package init, exports Flask class |
| src/flask/app.py | Main Flask application class |
| src/flask/cli.py | CLI command definitions |

List 5-10 most important files.

---

## Section 4: Technology Stack

Identify technologies from the actual config files and source code provided above.

You MUST use a Markdown table in this exact format:

| Category | Technology | Evidence |
|----------|------------|----------|
| Language | Python | repo_info.language, .py file extensions |
| Backend Framework | FastAPI | import in backend/app/api.py |
| Vector Database | ChromaDB | import in backend/app/database.py |
| Frontend Framework | React 19 | package.json dependencies |
| Build Tool | Vite | vite.config.js present |
| Deployment | Docker | Dockerfile present |

Only list technologies with actual evidence from the provided files.

---

## Section 5: Architecture

Based on the directory structure and source file contents provided above:

1. **Architecture Overview**: 2-3 paragraphs describing the actual architecture based on files
2. **Component Diagram**: Generate a Mermaid class diagram using ONLY classes/components found in the source files. Use the static analysis data above to identify classes and their relationships.
3. **Data Flow**: Generate a Mermaid flowchart based on actual code paths. Use the dependency graph data above to show module relationships.
4. **Key Patterns**: Identify design patterns actually used in the code

IMPORTANT: Only include components that exist in the provided source files. Do NOT invent components.

Generate valid Mermaid code for diagrams:
```mermaid
classDiagram
    ...
```

```mermaid
flowchart TD
    ...
```
"""
    return prompt


def _format_asts(asts: list) -> str:
    """Format AST data for the prompt."""
    if not asts:
        return ""

    lines = ["## Static Analysis (Functions, Classes, Imports)"]

    for ast in asts:
        if not ast.functions and not ast.classes:
            continue

        lines.append(f"\n### {ast.path}")

        if ast.functions:
            func_names = [f.name for f in ast.functions[:10]]
            lines.append(f"- Functions: {', '.join(func_names)}")

        if ast.classes:
            class_names = [c.name for c in ast.classes[:5]]
            lines.append(f"- Classes: {', '.join(class_names)}")

        if ast.imports:
            import_modules = [imp.module for imp in ast.imports[:10]]
            lines.append(f"- Imports: {', '.join(import_modules)}")

    return "\n".join(lines)


def _format_graph_summary(summary: dict) -> str:
    """Format dependency graph summary for the prompt."""
    if not summary or summary.get("total_modules", 0) == 0:
        return ""

    lines = ["## Dependency Graph Analysis"]

    lines.append(f"- Total modules: {summary['total_modules']}")
    lines.append(f"- Total dependencies: {summary['total_edges']}")
    lines.append(f"- Languages: {', '.join(summary.get('languages', []))}")
    lines.append(f"- Has circular dependencies: {summary.get('has_cycles', False)}")

    if summary.get("hub_modules"):
        lines.append("\n### Hub Modules (most depended upon)")
        for path, count in summary["hub_modules"][:5]:
            lines.append(f"- {path} ({count} dependents)")

    if summary.get("isolated_modules"):
        lines.append("\n### Isolated Modules (no dependencies)")
        for path in summary["isolated_modules"][:5]:
            lines.append(f"- {path}")

    if summary.get("cycles"):
        lines.append("\n### Circular Dependencies")
        for cycle_info in summary["cycles"]:
            lines.append(f"- Cycle: {' → '.join(cycle_info['cycle'])}")

    return "\n".join(lines)


def _format_file_tree(tree: dict, indent: int = 0) -> str:
    """Format file tree as indented text."""
    lines = []
    prefix = "    " * indent
    
    for name, value in tree.items():
        if isinstance(value, dict):
            if "type" in value:
                if value["type"] == "file":
                    size = value.get("size", 0)
                    lines.append(f"{prefix}├── {name} ({size} bytes)")
                else:
                    lines.append(f"{prefix}├── {name}/")
            else:
                lines.append(f"{prefix}├── {name}/")
                lines.append(_format_file_tree(value, indent + 1))
        else:
            lines.append(f"{prefix}├── {name}")
    
    return "\n".join(lines)


CHAT_SYSTEM_PROMPT = """You are CodeLens, an interactive code assistant.
You help users understand the codebase by answering questions and providing insights.

When answering questions:
1. Use the provided context to answer
2. Provide specific file paths and line numbers
3. Explain code behavior clearly
4. Suggest improvements when relevant

Be concise but thorough. Use code examples when helpful."""
