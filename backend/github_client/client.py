"""GitHub API Client Manager - Manages GitHub API access."""

import os
from typing import Optional
from .github import GitHubClient


class GitHubClientManager:
    """Manages GitHub API client."""

    def __init__(self):
        self.github: Optional[GitHubClient] = None
        self._connected = False

    async def connect(self, token: Optional[str] = None) -> None:
        """Initialize GitHub client."""
        if token:
            os.environ["GITHUB_TOKEN"] = token

        self.github = GitHubClient()
        self._connected = True
        print("[GitHub] Client initialized")

    def ensure_connected(self) -> None:
        """Ensure client is initialized."""
        if not self._connected:
            self.github = GitHubClient()
            self._connected = True

    async def disconnect(self) -> None:
        """Disconnect GitHub client."""
        self.github = None
        self._connected = False
        print("[GitHub] Client disconnected")
