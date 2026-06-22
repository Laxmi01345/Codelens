"""Agent Module - Cerebras-powered agentic loop."""

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "agent_loop":
        from .agent_loop import agent_loop
        return agent_loop
    elif name == "AGENT_TOOLS":
        from .tools import AGENT_TOOLS
        return AGENT_TOOLS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["agent_loop", "AGENT_TOOLS"]
