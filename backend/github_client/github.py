"""GitHub Client - Reads files directly from GitHub API without cloning."""

import os
import base64
from typing import Optional
import httpx
from dotenv import load_dotenv

load_dotenv()


class GitHubAccessError(Exception):
    """Raised when GitHub API cannot access the repository."""
    pass


class GitHubClient:
    """Client for GitHub API - reads files without local cloning."""

    def __init__(self):
        self.base_url = "https://api.github.com"
        self.token = os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeLens/1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """Extract owner and repo from GitHub URL."""
        repo_url = repo_url.rstrip("/")
        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]

        parts = repo_url.split("/")
        for i, part in enumerate(parts):
            if part == "github.com" and i + 2 < len(parts):
                return parts[i + 1], parts[i + 2]

        raise ValueError(f"Invalid GitHub URL: {repo_url}. Expected format: https://github.com/owner/repo")

    async def validate_repo(self, repo_url: str) -> dict:
        """
        Validate that a repository exists and is accessible.
        Returns repo info if valid, raises GitHubAccessError if not.
        """
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("full_name"),
                    "private": data.get("private", False),
                    "description": data.get("description", ""),
                    "language": data.get("language"),
                    "default_branch": data.get("default_branch", "main"),
                    "topics": data.get("topics", []),
                }
            elif response.status_code == 404:
                raise GitHubAccessError(
                    f"Repository not found: {owner}/{repo}. "
                    "The repository may not exist, be private, or the URL may be incorrect."
                )
            elif response.status_code == 403:
                raise GitHubAccessError(
                    "GitHub API rate limit exceeded or access denied. "
                    "Please check your GITHUB_TOKEN in .env file."
                )
            elif response.status_code == 401:
                raise GitHubAccessError(
                    "GitHub authentication failed. "
                    "Please check your GITHUB_TOKEN in .env file."
                )
            else:
                raise GitHubAccessError(
                    f"GitHub API error: {response.status_code} - {response.text}"
                )

    async def get_file_content(self, repo_url: str, path: str) -> Optional[str]:
        """Read a single file from GitHub."""
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                if data.get("encoding") == "base64":
                    return base64.b64decode(data["content"]).decode("utf-8")
                return data.get("content", "")
            elif response.status_code == 404:
                return None
            else:
                raise GitHubAccessError(
                    f"GitHub API error reading {path}: {response.status_code}"
                )

    async def list_directory(self, repo_url: str, path: str = "") -> list[dict]:
        """List files and folders in a directory."""
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "name": item["name"],
                        "path": item["path"],
                        "type": item["type"],
                        "size": item.get("size", 0),
                    }
                    for item in data
                ]
            else:
                raise GitHubAccessError(
                    f"GitHub API error listing directory: {response.status_code}"
                )

    async def get_file_tree(
        self, repo_url: str, path: str = "", max_depth: int = 3
    ) -> dict:
        """Get recursive file tree with depth limit."""
        owner, repo = self._parse_repo_url(repo_url)
        
        # Try main branch first, fallback to master
        for branch in ["main", "master"]:
            url = f"{self.base_url}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    tree = data.get("tree", [])
                    
                    root = {}
                    for item in tree:
                        if not item["path"].startswith(path):
                            continue
                        
                        parts = item["path"].split("/")
                        if len(parts) > max_depth + 1:
                            continue
                        
                        current = root
                        for part in parts[:-1]:
                            if part not in current:
                                current[part] = {}
                            current = current[part]
                        
                        if item["type"] == "blob":
                            current[parts[-1]] = {"type": "file", "size": item.get("size", 0)}
                        else:
                            current[parts[-1]] = {"type": "dir"}
                    
                    return root
        
        raise GitHubAccessError(
            f"Could not retrieve file tree for {owner}/{repo}"
        )

    async def search_code(self, repo_url: str, query: str) -> list[dict]:
        """Search for code in a repository."""
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/search/code?q={query}+repo:{owner}/{repo}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "path": item["path"],
                        "name": item["name"],
                        "url": item["html_url"],
                    }
                    for item in data.get("items", [])
                ]
            else:
                return []

    async def get_issues(
        self, repo_url: str, state: str = "open", limit: int = 20
    ) -> list[dict]:
        """
        Fetch issues from a GitHub repository.

        Args:
            repo_url: GitHub repository URL
            state: Filter by state - "open", "closed", or "all"
            limit: Maximum number of issues to return (default 20)

        Returns:
            List of issue dicts with: number, title, state, labels, created_at, url
        """
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": min(limit, 100)}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)

            if response.status_code == 200:
                issues = response.json()
                return [
                    {
                        "number": issue["number"],
                        "title": issue["title"],
                        "state": issue["state"],
                        "labels": [label["name"] for label in issue.get("labels", [])],
                        "created_at": issue["created_at"],
                        "url": issue["html_url"],
                        "body": (issue.get("body") or "")[:500],  # Truncate body
                    }
                    for issue in issues
                    if "pull_request" not in issue  # Exclude PRs (they look like issues)
                ]
            else:
                print(f"[GitHub] Error fetching issues: {response.status_code}")
                return []

    async def get_issue(self, repo_url: str, issue_number: int) -> Optional[dict]:
        """
        Fetch a single issue with full details.

        Args:
            repo_url: GitHub repository URL
            issue_number: Issue number to fetch

        Returns:
            Issue dict with full body content
        """
        owner, repo = self._parse_repo_url(repo_url)
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)

            if response.status_code == 200:
                issue = response.json()
                return {
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "labels": [label["name"] for label in issue.get("labels", [])],
                    "created_at": issue["created_at"],
                    "url": issue["html_url"],
                    "body": issue.get("body") or "",
                    "comments": issue.get("comments", 0),
                }
            else:
                return None
