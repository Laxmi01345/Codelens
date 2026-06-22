"""LLM Utilities - Cerebras API integration for CodeLens."""

import os
from typing import Optional
from cerebras.cloud.sdk import Cerebras
from dotenv import load_dotenv

load_dotenv()


# Models
MODEL_FAST = "zai-glm-4.7"
MODEL_ARCHITECTURE = "zai-glm-4.7"


def get_client() -> Cerebras:
    """Get Cerebras client."""
    api_key = os.getenv("CEREBRAS_API_KEY")
    if not api_key:
        raise ValueError("CEREBRAS_API_KEY not found in environment")
    return Cerebras(api_key=api_key)


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = MODEL_FAST,
    max_tokens: int = 4096,
) -> str:
    """Generate a response using Cerebras LLM."""
    client = get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content or ""


def generate_response_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str = MODEL_FAST,
    max_tokens: int = 4096,
) -> dict:
    """Generate a response with tool calls."""
    client = get_client()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        max_tokens=max_tokens,
    )

    choice = response.choices[0]
    return {
        "content": choice.message.content,
        "tool_calls": choice.message.tool_calls,
    }


def generate_purpose_scope(repo_url: str, readme_content: str) -> str:
    """Generate purpose and scope analysis."""
    system = """You are a technical documentation expert.
Analyze the repository and provide a clear overview.
Focus on: purpose, target users, key features, and current status.
Use Markdown formatting. Be concise (2-4 paragraphs)."""

    prompt = f"""Analyze this repository:

Repository: {repo_url}

README Content:
```
{readme_content[:3000]}
```

Provide a clear project overview."""

    return generate_response(prompt, system, MODEL_FAST)


def generate_tech_stack(deps_content: str) -> str:
    """Generate tech stack analysis."""
    system = """You are a technology analyst.
Identify the complete technology stack from dependency files.
Categorize: Languages, Frameworks, Databases, Build Tools, Testing, Other."""

    prompt = f"""Analyze these dependencies and identify the tech stack:

```
{deps_content[:2000]}
```

List all technologies organized by category."""

    return generate_response(prompt, system, MODEL_FAST)


def generate_architecture_analysis(
    purpose: str,
    tech_stack: str,
    key_files: list[str],
) -> str:
    """Generate architecture analysis with diagrams."""
    system = """You are a software architect.
Analyze the codebase and provide:
1. Architecture overview (2-3 paragraphs)
2. Mermaid class diagram showing main components
3. Mermaid flowchart showing data flow
4. Design patterns identified

Use valid Mermaid syntax. Be thorough but concise."""

    prompt = f"""Analyze the architecture based on:

Purpose: {purpose}
Tech Stack: {tech_stack}
Key Files: {', '.join(key_files[:20])}

Provide architecture analysis with Mermaid diagrams."""

    return generate_response(prompt, system, MODEL_ARCHITECTURE)


def generate_section_analysis(
    section: str,
    repo_url: str,
    context: dict,
) -> str:
    """Generate analysis for a specific section."""
    from .agent.prompts import get_section_prompt

    prompt = get_section_prompt(section)
    if not prompt:
        raise ValueError(f"Unknown section: {section}")

    # Add context
    context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
    full_prompt = f"{prompt}\n\nContext:\n{context_str}\n\nRepository: {repo_url}"

    return generate_response(full_prompt, system_prompt=None, model=MODEL_FAST)
