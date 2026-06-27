"""Code Property Graph - Combines AST + Control Flow + Data Flow."""

import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class NodeType(Enum):
    """Node types in the Code Property Graph."""
    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"
    CALL = "call"
    RETURN = "return"
    IF = "if"
    FOR = "for"
    WHILE = "while"
    ASSIGNMENT = "assignment"
    IMPORT = "import"
    PARAMETER = "parameter"


class EdgeType(Enum):
    """Edge types in the Code Property Graph."""
    # Structural edges (AST)
    DEFINES = "defines"          # File defines Function/Class
    CONTAINS = "contains"        # Class contains Method
    HAS_PARAMETER = "has_param"  # Function has Parameter
    
    # Control Flow edges
    CALLS = "calls"              # Function calls Function
    RETURNS = "returns"          # Function returns Value
    BRANCHES = "branches"        # If branches to Code
    
    # Data Flow edges
    USES = "uses"                # Function uses Variable
    DEFINES_VAR = "defines_var"  # Function defines Variable
    PASSES = "passes"            # Function passes Variable to Function
    
    # Dependency edges
    IMPORTS = "imports"          # File imports Module
    DEPENDS = "depends"          # A depends on B


@dataclass
class CPGNode:
    """A node in the Code Property Graph."""
    id: str
    type: NodeType
    name: str
    file_path: str
    line: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class CPGEdge:
    """An edge in the Code Property Graph."""
    source: str
    target: str
    type: EdgeType
    metadata: dict = field(default_factory=dict)


class CodePropertyGraph:
    """
    Code Property Graph combining AST + Control Flow + Data Flow.
    
    This is more powerful than a simple dependency graph because:
    1. AST edges show structure (class contains method)
    2. Control Flow edges show execution paths (function calls function)
    3. Data Flow edges show variable usage (function uses variable)
    
    Interview point: "We combine three analysis perspectives into one graph
    for comprehensive code understanding."
    """
    
    def __init__(self):
        self.nodes: dict[str, CPGNode] = {}
        self.edges: list[CPGEdge] = []
        self.adjacency: dict[str, list[CPGEdge]] = {}  # source -> edges
        self.reverse_adj: dict[str, list[CPGEdge]] = {}  # target -> edges
    
    def add_node(self, node: CPGNode):
        """Add a node to the graph."""
        self.nodes[node.id] = node
        if node.id not in self.adjacency:
            self.adjacency[node.id] = []
        if node.id not in self.reverse_adj:
            self.reverse_adj[node.id] = []
    
    def add_edge(self, edge: CPGEdge):
        """Add an edge to the graph."""
        self.edges.append(edge)
        if edge.source in self.adjacency:
            self.adjacency[edge.source].append(edge)
        if edge.target in self.reverse_adj:
            self.reverse_adj[edge.target].append(edge)
    
    def get_callers(self, function_name: str, max_depth: int = 3) -> list[str]:
        """
        Find all functions that call the given function (up to max_depth).
        
        Interview point: "Impact analysis - if I change this function,
        what else is affected?"
        """
        visited = set()
        callers = []
        
        def dfs(node_id: str, depth: int):
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            
            for edge in self.reverse_adj.get(node_id, []):
                if edge.type == EdgeType.CALLS:
                    caller_id = edge.source
                    if caller_id not in visited:
                        callers.append(caller_id)
                        dfs(caller_id, depth + 1)
        
        # Find the function node
        for node_id, node in self.nodes.items():
            if node.name == function_name and node.type == NodeType.FUNCTION:
                dfs(node_id, 0)
        
        return callers
    
    def get_callees(self, function_name: str, max_depth: int = 3) -> list[str]:
        """
        Find all functions called by the given function (up to max_depth).
        
        Interview point: "Dependency analysis - what does this function depend on?"
        """
        visited = set()
        callees = []
        
        def dfs(node_id: str, depth: int):
            if depth > max_depth or node_id in visited:
                return
            visited.add(node_id)
            
            for edge in self.adjacency.get(node_id, []):
                if edge.type == EdgeType.CALLS:
                    callee_id = edge.target
                    if callee_id not in visited:
                        callees.append(callee_id)
                        dfs(callee_id, depth + 1)
        
        # Find the function node
        for node_id, node in self.nodes.items():
            if node.name == function_name and node.type == NodeType.FUNCTION:
                dfs(node_id, 0)
        
        return callees
    
    def get_data_flow(self, variable: str) -> list[dict]:
        """
        Trace data flow for a variable - where is it defined and used.
        
        Interview point: "Data flow analysis - track how data moves through code."
        """
        flows = []
        
        for edge in self.edges:
            if edge.type in (EdgeType.DEFINES_VAR, EdgeType.USES, EdgeType.PASSES):
                if variable in edge.metadata.get("variable", ""):
                    source_node = self.nodes.get(edge.source)
                    target_node = self.nodes.get(edge.target)
                    flows.append({
                        "type": edge.type.value,
                        "source": source_node.name if source_node else edge.source,
                        "target": target_node.name if target_node else edge.target,
                        "file": source_node.file_path if source_node else "",
                    })
        
        return flows
    
    def get_control_flow(self, function_name: str) -> list[str]:
        """
        Get the control flow path through a function.
        
        Interview point: "Control flow analysis - understand execution paths."
        """
        path = []
        
        for node_id, node in self.nodes.items():
            if node.name == function_name and node.type == NodeType.FUNCTION:
                # Find all nodes in this function's control flow
                for edge in self.adjacency.get(node_id, []):
                    if edge.type in (EdgeType.BRANCHES, EdgeType.RETURNS):
                        target_node = self.nodes.get(edge.target)
                        if target_node:
                            path.append(f"{edge.type.value}: {target_node.name}")
        
        return path
    
    def get_impact_analysis(self, function_name: str) -> dict:
        """
        Complete impact analysis for a function.
        
        Returns callers, callees, data flows, and control flows.
        """
        return {
            "function": function_name,
            "callers": self.get_callers(function_name),
            "callees": self.get_callees(function_name),
            "data_flows": self.get_data_flow(function_name),
            "control_flow": self.get_control_flow(function_name),
        }
    
    def to_mermaid(self) -> str:
        """Export graph as Mermaid diagram for visualization."""
        lines = ["graph TD"]
        
        # Node type colors
        colors = {
            NodeType.FUNCTION: "#4CAF50",
            NodeType.CLASS: "#2196F3",
            NodeType.CALL: "#FF9800",
            NodeType.VARIABLE: "#9C27B0",
        }
        
        # Add nodes
        for node_id, node in self.nodes.items():
            color = colors.get(node.type, "#607D8B")
            safe_name = node.name.replace('"', "'")
            lines.append(f'    {node_id}["{safe_name}"]:::{node.type.value}')
        
        # Add edges
        for edge in self.edges:
            style = {
                EdgeType.CALLS: "-->",
                EdgeType.DEFINES: "==>",
                EdgeType.CONTAINS: "---",
                EdgeType.USES: "-.->",
            }.get(edge.type, "-->")
            lines.append(f"    {edge.source} {style} {edge.target}")
        
        # Add styles
        for node_type, color in colors.items():
            lines.append(f"    classDef {node_type.value} fill:{color}")
        
        return "\n".join(lines)
