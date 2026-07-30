"""Repo Cloner - Shallow clones repos for complete local file access."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs",
    ".java", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".swift", ".kt", ".m", ".mm",
}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "vendor", "target", ".gradle",
}

IGNORE_FILES = {
    ".DS_Store", "Thumbs.db", "desktop.ini",
}

MAX_FILE_SIZE = 100_000  # 100KB per file


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract owner and repo from GitHub URL."""
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parts = repo_url.split("/")
    for i, part in enumerate(parts):
        if part == "github.com" and i + 2 < len(parts):
            return parts[i + 1], parts[i + 2]
    raise ValueError(f"Invalid GitHub URL: {repo_url}")


def clone_repo(repo_url: str, token: Optional[str] = None) -> str:
    """
    Shallow clone a GitHub repository to a temp directory.

    Args:
        repo_url: GitHub repository URL
        token: Optional GitHub token for private repos

    Returns:
        Path to the cloned repository
    """
    owner, repo = _parse_repo_url(repo_url)
    temp_dir = tempfile.mkdtemp(prefix="codelens_")

    clone_url = f"https://github.com/{owner}/{repo}.git"
    if token:
        clone_url = f"https://{token}@github.com/{owner}/{repo}.git"

    cmd = [
        "git", "clone",
        "--depth", "1",
        "--filter=blob:limit=100k",
        "--no-checkout",
        clone_url,
        os.path.join(temp_dir, repo),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Git clone failed: {result.stderr}")

    repo_path = os.path.join(temp_dir, repo)

    checkout_cmd = ["git", "checkout", "main"]
    result = subprocess.run(
        checkout_cmd, capture_output=True, text=True,
        cwd=repo_path, timeout=30,
    )
    if result.returncode != 0:
        checkout_cmd = ["git", "checkout", "master"]
        result = subprocess.run(
            checkout_cmd, capture_output=True, text=True,
            cwd=repo_path, timeout=30,
        )
        if result.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Git checkout failed: {result.stderr}")

    return repo_path


def cleanup_repo(repo_path: str) -> None:
    """Remove a cloned repository."""
    parent = os.path.dirname(repo_path)
    if parent and os.path.basename(parent).startswith("codelens_"):
        shutil.rmtree(parent, ignore_errors=True)
    else:
        shutil.rmtree(repo_path, ignore_errors=True)


def read_all_files(repo_path: str) -> tuple[dict[str, str], dict[str, str], dict]:
    """
    Read all source and config files from a cloned repo.

    Args:
        repo_path: Path to the cloned repository

    Returns:
        Tuple of (source_files, key_files, file_tree)
        - source_files: dict of path -> content for code files
        - key_files: dict of path -> content for config files
        - file_tree: nested dict representing directory structure
    """
    source_files = {}
    key_files = {}
    file_tree = {}

    config_names = {
        "README.md", "readme.md", "README.rst", "README",
        "package.json", "requirements.txt", "setup.py", "pyproject.toml",
        "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "Gemfile", "composer.json", "Dockerfile", "docker-compose.yml",
        "docker-compose.yaml", ".gitignore", "Makefile", "tsconfig.json",
        "vite.config.js", "vite.config.ts", "next.config.js", "next.config.mjs",
        "webpack.config.js", "tailwind.config.js", "tailwind.config.ts",
        "render.yaml", "railway.json", "Procfile", ".env.example",
        "setup.cfg", "tox.ini", "Cargo.lock", "yarn.lock", "pnpm-lock.yaml",
    }

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS and not d.startswith(".")
        ]

        rel_root = os.path.relpath(root, repo_path)
        if rel_root == ".":
            rel_root = ""

        current_tree = file_tree
        if rel_root:
            for part in rel_root.split("/"):
                if part not in current_tree:
                    current_tree[part] = {}
                current_tree = current_tree[part]

        for fname in sorted(files):
            if fname in IGNORE_FILES:
                continue
            if fname.startswith("."):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.join(rel_root, fname) if rel_root else fname
            rel_path = rel_path.replace("\\", "/")

            try:
                size = os.path.getsize(full_path)
            except OSError:
                continue

            current_tree[fname] = {"type": "file", "size": size}

            if size > MAX_FILE_SIZE or size == 0:
                continue

            if fname in config_names or fname.lower() in {n.lower() for n in config_names}:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    key_files[rel_path] = content
                except Exception:
                    continue

            ext = os.path.splitext(fname)[1].lower()
            if ext in CODE_EXTENSIONS:
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    source_files[rel_path] = content
                except Exception:
                    continue

    return source_files, key_files, file_tree


def get_repo_info(repo_path: str) -> dict:
    """Extract basic repo info from a cloned repository."""
    info = {
        "name": os.path.basename(repo_path),
        "description": "",
        "language": None,
        "default_branch": "main",
        "topics": [],
        "private": False,
    }

    readme_path = None
    for name in ["README.md", "readme.md", "README.rst", "README"]:
        path = os.path.join(repo_path, name)
        if os.path.exists(path):
            readme_path = path
            break

    if readme_path:
        try:
            with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines[:10]:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("!"):
                    info["description"] = stripped[:200]
                    break
        except Exception:
            pass

    lang_counts = {}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in CODE_EXTENSIONS:
                lang_counts[ext] = lang_counts.get(ext, 0) + 1

    if lang_counts:
        ext_to_lang = {
            ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
            ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go",
            ".rs": "Rust", ".java": "Java", ".rb": "Ruby",
            ".php": "PHP", ".cs": "C#", ".cpp": "C++",
            ".c": "C", ".h": "C", ".swift": "Swift", ".kt": "Kotlin",
        }
        top_ext = max(lang_counts, key=lang_counts.get)
        info["language"] = ext_to_lang.get(top_ext, top_ext)

    branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, cwd=repo_path, timeout=10,
    )
    if branch_result.returncode == 0:
        info["default_branch"] = branch_result.stdout.strip()

    # Get commit hash
    commit_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=repo_path, timeout=10,
    )
    if commit_result.returncode == 0:
        info["commit_hash"] = commit_result.stdout.strip()[:8]
    else:
        info["commit_hash"] = ""

    return info
