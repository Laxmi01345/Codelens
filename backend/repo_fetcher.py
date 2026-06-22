"""Repository Fetcher - Fetches all repository data in parallel."""

import asyncio
import os
import sys
from typing import Optional
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github_client.github import GitHubClient, GitHubAccessError
from analysis.ast_parser import parse_file, FileAST

load_dotenv()

# Key config files to fetch (various common names)
CONFIG_FILE_NAMES = [
    "README.md", "readme.md", "README.rst", "README",
    "package.json", "requirements.txt", "setup.py", "pyproject.toml",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Gemfile", "composer.json", "Dockerfile", "docker-compose.yml",
    ".gitignore", "Makefile", "tsconfig.json", "vite.config.js",
    "vite.config.ts", "next.config.js", "next.config.mjs", "webpack.config.js",
]


async def validate_repo(repo_url: str, github: GitHubClient) -> dict:
    """Validate repository exists and is accessible."""
    return await github.validate_repo(repo_url)


async def list_directory_safe(github: GitHubClient, repo_url: str, path: str = "") -> list:
    """Safely list directory contents."""
    try:
        return await github.list_directory(repo_url, path)
    except Exception as e:
        print(f"[Fetcher] Error listing {path}: {e}")
        return []


async def read_file_safe(github: GitHubClient, repo_url: str, path: str) -> Optional[str]:
    """Safely read a file."""
    try:
        content = await github.get_file_content(repo_url, path)
        return content
    except Exception as e:
        print(f"[Fetcher] Error reading {path}: {e}")
        return None


async def fetch_file_tree(github: GitHubClient, repo_url: str) -> dict:
    """Fetch the file tree structure."""
    try:
        return await github.get_file_tree(repo_url, max_depth=3)
    except Exception as e:
        print(f"[Fetcher] Error fetching file tree: {e}")
        return {}


def _collect_file_paths(tree: dict, prefix: str = "") -> list[str]:
    """Recursively collect all file paths from a file tree."""
    paths = []
    for name, value in tree.items():
        full_path = f"{prefix}/{name}" if prefix else name
        if isinstance(value, dict):
            if value.get("type") == "file":
                paths.append(full_path)
            elif "type" not in value:
                # It's a subdirectory
                paths.extend(_collect_file_paths(value, full_path))
    return paths


async def fetch_key_files(github: GitHubClient, repo_url: str, file_tree: dict) -> dict:
    """Fetch all key configuration files by matching names from the file tree."""
    # Collect ALL file paths from the tree
    all_files = _collect_file_paths(file_tree)
    
    # Also get root directory listing for direct matches
    root_items = await list_directory_safe(github, repo_url, "")
    root_files = {item["name"]: item["path"] for item in root_items if item["type"] == "file"}
    
    # Find config files that exist - check both tree paths and root listing
    files_to_fetch = set()
    
    # Match from config file names
    for config_name in CONFIG_FILE_NAMES:
        # Check direct root listing
        if config_name in root_files:
            files_to_fetch.add(root_files[config_name])
        # Check all file paths (handles nested configs)
        for fpath in all_files:
            basename = fpath.split("/")[-1]
            if basename == config_name:
                files_to_fetch.add(fpath)
    
    # Fetch files in parallel
    tasks = []
    file_list = list(files_to_fetch)
    for file_path in file_list:
        tasks.append(read_file_safe(github, repo_url, file_path))
    
    results = await asyncio.gather(*tasks)
    
    # Build key_files dict
    key_files = {}
    for file_path, content in zip(file_list, results):
        if content:
            key_files[file_path] = content
    
    return key_files


async def _fetch_code_files_recursive(
    github: GitHubClient, repo_url: str, path: str, source_files: dict, max_files: int = 15
) -> None:
    """Recursively fetch code files from a directory up to max_files."""
    if len(source_files) >= max_files:
        return
    
    items = await list_directory_safe(github, repo_url, path)
    for item in items:
        if len(source_files) >= max_files:
            return
        if item["type"] == "file":
            ext = "." + item["name"].rsplit(".", 1)[-1] if "." in item["name"] else ""
            if ext in CODE_EXTENSIONS:
                content = await read_file_safe(github, repo_url, item["path"])
                if content:
                    source_files[item["path"]] = content[:2000]
        elif item["type"] == "dir":
            await _fetch_code_files_recursive(github, repo_url, item["path"], source_files, max_files)


CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".cs", ".cpp", ".c", ".h", ".swift", ".kt"}


async def fetch_source_files(github: GitHubClient, repo_url: str, file_tree: dict) -> dict:
    """Fetch main source files - scans common source directories and all code files."""
    source_dirs = ["src", "lib", "app", "pkg", "internal", "cmd", "source", "backend", "frontend", "server", "api"]
    source_files = {}
    
    # Strategy 1: Look in common source directories (recursive)
    for dir_name in source_dirs:
        if dir_name in file_tree:
            await _fetch_code_files_recursive(github, repo_url, dir_name, source_files, max_files=15)
    
    # Strategy 2: If no source dirs found, grab top-level code files
    if not source_files:
        root_items = await list_directory_safe(github, repo_url, "")
        for item in root_items:
            if item["type"] == "file" and len(source_files) < 10:
                ext = "." + item["name"].rsplit(".", 1)[-1] if "." in item["name"] else ""
                if ext in CODE_EXTENSIONS:
                    content = await read_file_safe(github, repo_url, item["path"])
                    if content:
                        source_files[item["path"]] = content[:2000]
    
    return source_files


async def fetch_repo_data(repo_url: str) -> dict:
    """
    Fetch all repository data in parallel.

    Returns:
        dict with keys: repo_info, file_tree, directory_listing, key_files, source_files, asts
    """
    print(f"[Fetcher] Starting data fetch for {repo_url}")

    # Initialize GitHub client
    github = GitHubClient()

    # Step 1: Validate repo
    print("[Fetcher] Validating repository...")
    repo_info = await validate_repo(repo_url, github)
    print(f"[Fetcher] Repository validated: {repo_info['name']}")

    # Step 2: Fetch file tree and root directory in parallel
    print("[Fetcher] Fetching file tree and directory listing...")
    file_tree_task = fetch_file_tree(github, repo_url)
    root_listing_task = list_directory_safe(github, repo_url, "")

    file_tree, root_listing = await asyncio.gather(
        file_tree_task, root_listing_task
    )

    print(f"[Fetcher] File tree has {len(_collect_file_paths(file_tree))} files")

    # Step 3: Fetch key files and source files in parallel
    print("[Fetcher] Fetching key files and source files...")
    key_files_task = fetch_key_files(github, repo_url, file_tree)
    source_files_task = fetch_source_files(github, repo_url, file_tree)

    key_files, source_files = await asyncio.gather(
        key_files_task, source_files_task
    )

    print(f"[Fetcher] Fetched {len(key_files)} config files, {len(source_files)} source files")

    # Step 4: Parse source files into ASTs
    asts = []
    for path, content in source_files.items():
        try:
            ast = parse_file(path, content)
            asts.append(ast)
        except Exception as e:
            print(f"[Fetcher] Error parsing {path}: {e}")
    print(f"[Fetcher] Parsed {len(asts)} files into ASTs")

    return {
        "repo_info": repo_info,
        "file_tree": file_tree,
        "directory_listing": root_listing,
        "key_files": key_files,
        "source_files": source_files,
        "asts": asts,
    }


if __name__ == "__main__":
    # Test the fetcher
    async def test():
        data = await fetch_repo_data("https://github.com/octocat/Hello-World")
        print("\n=== REPO INFO ===")
        print(data["repo_info"])
        print("\n=== FILE TREE ===")
        print(data["file_tree"])
        print("\n=== KEY FILES ===")
        for name, content in data["key_files"].items():
            print(f"\n--- {name} ---")
            print(content[:200])
        print("\n=== SOURCE FILES ===")
        for name, content in data["source_files"].items():
            print(f"\n--- {name} ---")
            print(content[:200])
    
    asyncio.run(test())
