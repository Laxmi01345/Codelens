"""GitHub Client Module - Manages GitHub API access."""

from .github import GitHubClient, GitHubAccessError
from .client import GitHubClientManager

__all__ = ["GitHubClient", "GitHubAccessError", "GitHubClientManager"]
