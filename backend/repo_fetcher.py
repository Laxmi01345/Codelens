"""Repository Fetcher - Fetches repo data via shallow git clone."""

import os
import sys
from typing import Optional
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github_client.github import GitHubClient, GitHubAccessError
from repo_cloner import clone_repo, cleanup_repo, read_all_files, get_repo_info
from analysis.ast_parser import parse_file

load_dotenv()


async def validate_repo(repo_url: str, github: GitHubClient) -> dict:
    """Validate repository exists and is accessible."""
    return await github.validate_repo(repo_url)


def _clone_and_read(repo_url: str) -> dict:
    """Clone repo and read all files locally."""
    token = os.getenv("GITHUB_TOKEN")
    repo_path = clone_repo(repo_url, token=token)

    try:
        source_files, key_files, file_tree = read_all_files(repo_path)
        repo_info = get_repo_info(repo_path)
        return {
            "repo_path": repo_path,
            "repo_info": repo_info,
            "source_files": source_files,
            "key_files": key_files,
            "file_tree": file_tree,
        }
    except Exception:
        cleanup_repo(repo_path)
        raise


async def fetch_repo_data(repo_url: str) -> dict:
    """
    Fetch all repository data via shallow git clone.

    Returns:
        dict with keys: repo_info, file_tree, key_files, source_files, asts
    """
    print(f"[Fetcher] Starting data fetch for {repo_url}")

    github = GitHubClient()

    print("[Fetcher] Validating repository...")
    try:
        repo_info_api = await validate_repo(repo_url, github)
    except GitHubAccessError:
        repo_info_api = None

    print("[Fetcher] Cloning repository (shallow)...")
    repo_data = _clone_and_read(repo_url)

    if repo_info_api:
        repo_data["repo_info"].update({
            "description": repo_info_api.get("description", repo_data["repo_info"].get("description", "")),
            "topics": repo_info_api.get("topics", []),
        })

    print(f"[Fetcher] Read {len(repo_data['source_files'])} source files, "
          f"{len(repo_data['key_files'])} config files")

    asts = []
    for path, content in repo_data["source_files"].items():
        try:
            ast = parse_file(path, content)
            asts.append(ast)
        except Exception as e:
            print(f"[Fetcher] Error parsing {path}: {e}")
    print(f"[Fetcher] Parsed {len(asts)} files into ASTs")

    cleanup_repo(repo_data["repo_path"])

    return {
        "repo_info": repo_data["repo_info"],
        "file_tree": repo_data["file_tree"],
        "key_files": repo_data["key_files"],
        "source_files": repo_data["source_files"],
        "asts": asts,
    }


if __name__ == "__main__":
    import asyncio

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
