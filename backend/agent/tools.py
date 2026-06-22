"""Agent Tool Definitions - Tool schemas for Cerebras LLM function calling."""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from a GitHub repository. Use this to examine source code files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "Full GitHub repository URL (e.g., https://github.com/facebook/react)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to the file within the repository (e.g., src/index.js)",
                    },
                },
                "required": ["repo_url", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and subdirectories in a directory of a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "Full GitHub repository URL",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory path within the repository (empty string for root)",
                    },
                },
                "required": ["repo_url", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for code patterns or keywords in a GitHub repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "Full GitHub repository URL",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search query or pattern to find in code",
                    },
                },
                "required": ["repo_url", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_tree",
            "description": "Get the file/folder structure of a repository. Useful for understanding project layout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "Full GitHub repository URL",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (default: 3)",
                    },
                },
                "required": ["repo_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_code",
            "description": "Analyze code using AST parsing to extract symbols (classes, functions, imports).",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Source code to analyze",
                    },
                    "language": {
                        "type": "string",
                        "description": "Programming language (python, javascript, typescript, etc.)",
                    },
                },
                "required": ["code", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_diagram",
            "description": "Generate a UML or Mermaid diagram from code or design. Use for architecture, class, sequence, flowchart, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "diagram_type": {
                        "type": "string",
                        "description": "Type of diagram: mermaid, plantuml, graphviz, d2",
                    },
                    "diagram_code": {
                        "type": "string",
                        "description": "The diagram code/content to render",
                    },
                },
                "required": ["diagram_type", "diagram_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repository_overview",
            "description": "Get a high-level overview of a repository including README, package.json, or similar config files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {
                        "type": "string",
                        "description": "Full GitHub repository URL",
                    },
                },
                "required": ["repo_url"],
            },
        },
    },
]


# Tool name to function mapping for execution
TOOL_EXECUTORS = {
    "read_file": "_execute_read_file",
    "list_directory": "_execute_list_directory",
    "search_code": "_execute_search_code",
    "get_file_tree": "_execute_get_file_tree",
    "analyze_code": "_execute_analyze_code",
    "generate_diagram": "_execute_generate_diagram",
    "get_repository_overview": "_execute_get_repository_overview",
}
