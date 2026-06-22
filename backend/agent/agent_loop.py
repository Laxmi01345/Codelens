"""Agent Loop - Core agentic loop with Cerebras tool-use."""

import json
import os
import sys
from typing import Optional
from cerebras.cloud.sdk import Cerebras

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_client.client import MCPClientManager
from agent.prompts import SYSTEM_PROMPT, get_section_prompt
from agent.tools import AGENT_TOOLS


# Cerebras configuration
MODEL = "zai-glm-4.7"
MAX_ITERATIONS = 15


async def agent_loop(
    question: str,
    repo_url: str,
    mcp_client: MCPClientManager,
    max_iterations: int = MAX_ITERATIONS,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Run the agentic loop to answer a question about a repository.

    Args:
        question: The question or analysis task
        repo_url: GitHub repository URL
        mcp_client: MCP client manager for tool execution
        max_iterations: Maximum tool call iterations
        system_prompt: Custom system prompt (uses default if None)

    Returns:
        Final answer string
    """
    client = Cerebras()

    # Build messages
    messages = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
        {"role": "user", "content": f"Repository: {repo_url}\n\n{question}"},
    ]

    for iteration in range(max_iterations):
        print(f"[Agent] Iteration {iteration + 1}/{max_iterations}")

        # Call Cerebras with tools
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]
        message = choice.message

        # Check if tool calls are present
        if not message.tool_calls:
            # No tool calls - return final answer
            print("[Agent] No more tool calls, returning answer")
            return message.content or ""

        # Append assistant message with tool calls
        messages.append(message)

        # Execute each tool call
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            print(f"[Agent] Calling tool: {function_name}")

            # Execute tool
            result = await _execute_tool(
                function_name, arguments, repo_url, mcp_client
            )

            # Append tool result
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result) if isinstance(result, dict) else str(result),
                }
            )

    # Max iterations reached
    print("[Agent] Max iterations reached")
    return "Analysis incomplete - maximum iterations reached. Please try again."


async def _execute_tool(
    function_name: str,
    arguments: dict,
    repo_url: str,
    mcp_client: MCPClientManager,
) -> dict:
    """Execute a tool call and return the result."""
    github = mcp_client.github
    tree_sitter = mcp_client.tree_sitter
    uml = mcp_client.uml

    try:
        if function_name == "read_file":
            content = await github.get_file_content(
                arguments.get("repo_url", repo_url),
                arguments["path"],
            )
            return {"content": content or "File not found"}

        elif function_name == "list_directory":
            items = await github.list_directory(
                arguments.get("repo_url", repo_url),
                arguments.get("path", ""),
            )
            return {"items": items}

        elif function_name == "search_code":
            results = await github.search_code(
                arguments.get("repo_url", repo_url),
                arguments["query"],
            )
            return {"results": results}

        elif function_name == "get_file_tree":
            tree = await github.get_file_tree(
                arguments.get("repo_url", repo_url),
                max_depth=arguments.get("max_depth", 3),
            )
            return {"tree": tree}

        elif function_name == "analyze_code":
            symbols = await tree_sitter.extract_symbols(
                arguments["code"],
                arguments["language"],
            )
            complexity = await tree_sitter.analyze_complexity(
                arguments["code"],
                arguments["language"],
            )
            return {"symbols": symbols, "complexity": complexity}

        elif function_name == "generate_diagram":
            result = await uml.generate_diagram(
                arguments["diagram_type"],
                arguments["diagram_code"],
            )
            return result

        elif function_name == "get_repository_overview":
            # Try common files
            overview_files = [
                "README.md",
                "readme.md",
                "README.rst",
                "package.json",
                "setup.py",
                "pyproject.toml",
                "Cargo.toml",
                "go.mod",
            ]
            content = None
            for file in overview_files:
                content = await github.get_file_content(
                    arguments.get("repo_url", repo_url), file
                )
                if content:
                    return {"file": file, "content": content[:5000]}
            return {"content": "No overview file found"}

        else:
            return {"error": f"Unknown tool: {function_name}"}

    except Exception as e:
        return {"error": str(e)}


def build_diagram_code(
    diagram_type: str,
    title: str,
    elements: list[dict],
) -> str:
    """Build diagram code from structured data."""
    from mcp_client.uml_mcp import UMMMCP

    if diagram_type == "class":
        classes = []
        for elem in elements:
            if elem.get("type") == "class":
                classes.append(
                    {
                        "name": elem.get("name", "Unknown"),
                        "methods": elem.get("methods", []),
                        "attributes": elem.get("attributes", []),
                    }
                )
        return UMMMCP.build_mermaid_class_diagram(classes)

    elif diagram_type == "sequence":
        return UMMMCP.build_mermaid_sequence_diagram(elements)

    elif diagram_type == "flowchart":
        nodes = [e for e in elements if e.get("is_node", True)]
        edges = [e for e in elements if not e.get("is_node", True)]
        return UMMMCP.build_mermaid_flowchart(nodes, edges)

    else:
        # Return raw mermaid code
        return "\n".join(e.get("code", "") for e in elements)
