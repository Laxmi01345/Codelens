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
    sections = parse_sections(content)
    
    return sections


def parse_sections(content: str) -> dict:
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
