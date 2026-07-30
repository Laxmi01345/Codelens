"""Hybrid Analyzer - Single LLM call for all sections."""

import os
import sys
import re
from typing import Optional
from cerebras.cloud.sdk import Cerebras
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid_prompts import SYSTEM_PROMPT, build_hybrid_prompt

load_dotenv()

# Cerebras model
MODEL = "zai-glm-4.7"


def get_llm_client() -> Cerebras:
    """Get Cerebras client."""
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY not found in environment")
    return Cerebras(api_key=api_key)


def analyze_all_sections(repo_data: dict) -> dict:
    """
    Generate all documentation sections in a single LLM call.
    
    Args:
        repo_data: Repository data from repo_fetcher
        
    Returns:
        Dictionary with all 5 sections
    """
    print("[Analyzer] Building hybrid prompt...")
    prompt = build_hybrid_prompt(repo_data)
    
    print(f"[Analyzer] Prompt length: {len(prompt)} chars")
    
    client = get_llm_client()
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    
    print("[Analyzer] Calling LLM (single call)...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=8192,
    )
    
    content = response.choices[0].message.content or ""
    print(f"[Analyzer] LLM response length: {len(content)} chars")
    print(f"[Analyzer] Raw LLM response (first 500 chars):")
    print(content[:500])
    print("---")
    
    # Parse response into sections
    repo_url = repo_data.get("repo_url", "")
    commit_hash = repo_data.get("repo_info", {}).get("commit_hash", "")
    all_relevant_files = repo_data.get("relevant_files", [])
    sections = parse_sections(content, repo_url, commit_hash)
    
    # Attach per-section relevant files (iterate over copy to avoid dict mutation)
    section_names = [k for k in sections.keys() if not k.startswith("_")]
    for section_name in section_names:
        section_content = sections[section_name]
        if section_content:
            sections[f"_relevant_files_{section_name}"] = _assign_files_to_section(
                section_name, section_content, all_relevant_files, repo_data
            )
    
    return sections


# File categories for each section
SECTION_FILE_MAP = {
    "purpose_scope": ["readme", "package.json", "pyproject.toml", "setup.py", "setup.cfg"],
    "repo_layout": [],  # Uses tree from file_tree instead
    "source_layer": [".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java"],
    "tech_stack": ["package.json", "requirements.txt", "pyproject.toml", "setup.py",
                   "Cargo.toml", "go.mod", "pom.xml", "Gemfile", "composer.json",
                   "Dockerfile", "docker-compose", ".gitignore", "Makefile",
                   "tsconfig.json", "vite.config", "tailwind.config", "webpack.config",
                   "render.yaml", "railway.json", "Procfile"],
    "architecture_text": [".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java"],
}


def _assign_files_to_section(section_name: str, content: str, all_files: list[dict], repo_data: dict) -> list[dict]:
    """
    Assign files to a section based on topic, not content scanning.
    
    This avoids the issue where repo_layout mentions ALL files in the tree.
    """
    if not all_files:
        return []
    
    # Special case: repo_layout uses file_tree, not relevant files
    if section_name == "repo_layout":
        return []
    
    # Get file patterns for this section
    patterns = SECTION_FILE_MAP.get(section_name, [])
    if not patterns:
        return all_files[:10]  # Fallback: top 10 files
    
    result = []
    for f in all_files:
        path = f["path"].lower()
        # Check if file matches any pattern
        for pattern in patterns:
            if pattern in path:
                result.append(f)
                break
    
    # For source_layer and architecture_text, also include files mentioned in content
    if section_name in ("source_layer", "architecture_text"):
        content_lower = content.lower()
        for f in all_files:
            path = f["path"]
            # Check if the filename (without extension) is mentioned in content
            filename = path.split("/")[-1].split(".")[0].lower()
            if len(filename) > 3 and filename in content_lower:
                if f not in result:
                    result.append(f)
    
    return result[:15]  # Cap at 15 files per section


def add_source_citations(content: str, repo_url: str, commit_hash: str) -> str:
    """
    Post-process LLM output to add inline source citations.
    
    Finds file path mentions and converts them to GitHub links.
    e.g., "src/api.py" -> "[src/api.py](https://github.com/owner/repo/blob/{commit}/src/api.py)"
    """
    if not commit_hash or not repo_url:
        return content
    
    # Extract owner/repo from URL
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parts = repo_url.split("/")
    owner, repo = "", ""
    for i, part in enumerate(parts):
        if part == "github.com" and i + 2 < len(parts):
            owner, repo = parts[i + 1], parts[i + 2]
            break
    
    if not owner or not repo:
        return content
    
    base_url = f"https://github.com/{owner}/{repo}/blob/{commit_hash}"
    
    # Pattern to match file paths (relative paths with extensions)
    # Matches: src/api.py, lib/utils.ts, package.json, etc.
    file_pattern = re.compile(
        r'(?<![/\w])'  # Not preceded by / or word char
        r'((?:[\w.-]+/)*[\w.-]+\.(?:py|js|jsx|ts|tsx|go|rs|java|rb|php|cs|cpp|c|h|swift|kt|json|yaml|yml|toml|md|txt))'
        r'(?![/\w])',  # Not followed by / or word char
    )
    
    def replace_file_ref(match):
        file_path = match.group(1)
        # Don't link if it's already a markdown link
        return f'[{file_path}]({base_url}/{file_path})'
    
    # Only replace file paths that aren't already inside markdown links
    lines = content.split('\n')
    result_lines = []
    for line in lines:
        # Skip lines that are already markdown links or code blocks
        if line.strip().startswith('```') or '](' in line:
            result_lines.append(line)
        else:
            result_lines.append(file_pattern.sub(replace_file_ref, line))
    
    return '\n'.join(result_lines)


def parse_sections(content: str, repo_url: str = "", commit_hash: str = "") -> dict:
    """
    Parse LLM response into individual sections.
    
    Args:
        content: Full LLM response
        
    Returns:
        Dictionary with parsed sections
    """
    sections = {
        "purpose_scope": "",
        "repo_layout": "",
        "source_layer": "",
        "tech_stack": "",
        "architecture_text": "",
    }
    
    # Try to split by section headers
    section_patterns = {
        "purpose_scope": [
            r"##\s*Section\s*1[:\s]*Purpose\s*(?:&|and)\s*Scope",
            r"##\s*Purpose\s*(?:&|and)\s*Scope",
            r"#\s*Purpose\s*(?:&|and)\s*Scope",
        ],
        "repo_layout": [
            r"##\s*Section\s*2[:\s]*Repository\s*Layout",
            r"##\s*Repository\s*Layout",
            r"#\s*Repository\s*Layout",
        ],
        "source_layer": [
            r"##\s*Section\s*3[:\s]*Source\s*Layer",
            r"##\s*Source\s*Layer",
            r"#\s*Source\s*Layer",
        ],
        "tech_stack": [
            r"##\s*Section\s*4[:\s]*Technology\s*Stack",
            r"##\s*Technology\s*Stack",
            r"##\s*Tech\s*Stack",
            r"#\s*Tech\s*Stack",
        ],
        "architecture_text": [
            r"##\s*Section\s*5[:\s]*Architecture",
            r"##\s*Architecture",
            r"#\s*Architecture",
        ],
    }
    
    # Find all section starts
    section_starts = []
    for section_name, patterns in section_patterns.items():
        for pattern in patterns:
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            if matches:
                section_starts.append((matches[0].start(), section_name))
                break
    
    # Sort by position
    section_starts.sort(key=lambda x: x[0])
    
    # Extract content between sections
    for i, (start, section_name) in enumerate(section_starts):
        if i + 1 < len(section_starts):
            end = section_starts[i + 1][0]
        else:
            end = len(content)
        
        section_content = content[start:end].strip()
        # Remove the header line (## Section X: ...) and any trailing blank lines
        section_content = re.sub(r"^##?\s*(?:Section\s*\d[:\s]*)?.*\n", "", section_content, count=1)
        # Remove leading blank lines
        section_content = re.sub(r"^\n+", "", section_content)
        sections[section_name] = section_content.strip()
    
    # Log parsed sections
    for name, content in sections.items():
        print(f"[Analyzer] Section '{name}': {len(content)} chars")
        if not content:
            print(f"[Analyzer] WARNING: Section '{name}' is EMPTY")
        else:
            print(f"[Analyzer] Section '{name}' first 200 chars: {content[:200]}")
    if not any(sections.values()):
        print("[Analyzer] Section parsing failed, trying fallback split...")
        sections = _fallback_split(content)
    
    # If still empty, put everything in purpose_scope
    if not any(sections.values()):
        print("[Analyzer] Fallback split failed, using full content")
        sections["purpose_scope"] = content
    
    # Add source citations to each section
    if repo_url and commit_hash:
        for name in sections:
            if sections[name]:
                sections[name] = add_source_citations(sections[name], repo_url, commit_hash)
    
    return sections


def _fallback_split(content: str) -> dict:
    """Fallback: split content by --- separators."""
    sections = {
        "purpose_scope": "",
        "repo_layout": "",
        "source_layer": "",
        "tech_stack": "",
        "architecture_text": "",
    }
    
    # Split by ---
    parts = re.split(r"\n---\n", content)
    
    section_keys = list(sections.keys())
    for i, part in enumerate(parts):
        if i < len(section_keys) and part.strip():
            sections[section_keys[i]] = part.strip()
    
    return sections
