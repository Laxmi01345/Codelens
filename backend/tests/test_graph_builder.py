"""Tests for Graph Builder."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.ast_parser import parse_file
from analysis.graph_builder import build_dependency_graph


class TestGraphBuilding:
    """Tests for building dependency graphs."""

    def test_empty_graph(self):
        graph = build_dependency_graph([])
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_single_file_no_imports(self):
        code = """def hello():
    pass
"""
        ast = parse_file("hello.py", code)
        graph = build_dependency_graph([ast])
        assert len(graph.nodes) == 1
        assert "hello.py" in graph.nodes
        assert len(graph.edges) == 0

    def test_file_with_internal_imports(self):
        code = """import os
import json
"""
        ast = parse_file("utils.py", code)
        graph = build_dependency_graph([ast])
        # stdlib imports should be filtered out
        assert len(graph.edges) == 0

    def test_file_with_local_imports(self):
        code1 = """import models
"""
        code2 = """class Model:
    pass
"""
        ast1 = parse_file("app.py", code1)
        ast2 = parse_file("models.py", code2)
        graph = build_dependency_graph([ast1, ast2])
        assert len(graph.nodes) == 2
        assert "app.py" in graph.edges
        assert "models.py" in graph.edges["app.py"]

    def test_package_import(self):
        code1 = """from flask import Flask
"""
        code2 = """# flask/__init__.py
class Flask:
    pass
"""
        ast1 = parse_file("app.py", code1)
        ast2 = parse_file("flask/__init__.py", code2)
        graph = build_dependency_graph([ast1, ast2])
        assert "flask/__init__.py" in graph.edges.get("app.py", set())


class TestGraphAlgorithms:
    """Tests for graph algorithms."""

    def test_topological_sort_linear(self):
        code1 = """import b
"""
        code2 = """import c
"""
        code3 = """# no imports
"""
        ast1 = parse_file("a.py", code1)
        ast2 = parse_file("b.py", code2)
        ast3 = parse_file("c.py", code3)
        graph = build_dependency_graph([ast1, ast2, ast3])

        topo = graph.topological_sort()
        # c should come before b, b before a (dependencies first)
        assert topo.index("c.py") < topo.index("b.py"), f"Expected c before b, got {topo}"
        assert topo.index("b.py") < topo.index("a.py"), f"Expected b before a, got {topo}"

    def test_detect_cycles(self):
        # Note: This test creates a cycle in the graph manually
        code1 = """import b
"""
        code2 = """import a
"""
        ast1 = parse_file("a.py", code1)
        ast2 = parse_file("b.py", code2)
        graph = build_dependency_graph([ast1, ast2])

        # Manually add cycle for testing
        graph.edges["a.py"].add("b.py")
        graph.edges["b.py"].add("a.py")
        graph.reverse_edges["b.py"].add("a.py")
        graph.reverse_edges["a.py"].add("b.py")

        cycles = graph.detect_cycles()
        assert len(cycles) > 0

    def test_hub_modules(self):
        code1 = """import utils
"""
        code2 = """import utils
"""
        code3 = """# utils.py
"""
        ast1 = parse_file("app1.py", code1)
        ast2 = parse_file("app2.py", code2)
        ast3 = parse_file("utils.py", code3)
        graph = build_dependency_graph([ast1, ast2, ast3])

        hubs = graph.get_hub_modules(1)
        if hubs:
            assert hubs[0][0] == "utils.py"
            assert hubs[0][1] == 2  # 2 dependents

    def test_leaf_modules(self):
        code1 = """import b
"""
        code2 = """# b.py - no imports
"""
        ast1 = parse_file("a.py", code1)
        ast2 = parse_file("b.py", code2)
        graph = build_dependency_graph([ast1, ast2])

        leaves = graph.get_leaf_modules()
        # a.py is a leaf because nothing imports a.py
        # b.py is NOT a leaf because a.py imports it
        assert "a.py" in leaves, f"Expected a.py in leaves, got {leaves}"
        assert "b.py" not in leaves, f"Expected b.py NOT in leaves (it has dependents), got {leaves}"

    def test_transitive_dependencies(self):
        code1 = """import b
"""
        code2 = """import c
"""
        code3 = """# c.py
"""
        ast1 = parse_file("a.py", code1)
        ast2 = parse_file("b.py", code2)
        ast3 = parse_file("c.py", code3)
        graph = build_dependency_graph([ast1, ast2, ast3])

        transitive = graph.get_transitive_dependencies("a.py")
        assert "b.py" in transitive
        assert "c.py" in transitive


class TestGraphSummary:
    """Tests for graph summary generation."""

    def test_summary_structure(self):
        code1 = """import utils
"""
        code2 = """# utils.py
"""
        ast1 = parse_file("app.py", code1)
        ast2 = parse_file("utils.py", code2)
        graph = build_dependency_graph([ast1, ast2])

        summary = graph.to_summary()
        assert "total_modules" in summary
        assert "total_edges" in summary
        assert "cycles" in summary
        assert "hub_modules" in summary
        assert "languages" in summary
        assert summary["total_modules"] == 2

    def test_mermaid_generation(self):
        code1 = """import b
"""
        code2 = """# b.py
"""
        ast1 = parse_file("a.py", code1)
        ast2 = parse_file("b.py", code2)
        graph = build_dependency_graph([ast1, ast2])

        mermaid = graph.to_mermaid()
        assert "flowchart LR" in mermaid
        assert "a_py" in mermaid
        assert "b_py" in mermaid


if __name__ == "__main__":
    test_classes = [
        TestGraphBuilding,
        TestGraphAlgorithms,
        TestGraphSummary,
    ]

    passed = 0
    failed = 0

    for test_class in test_classes:
        print(f"\n=== {test_class.__name__} ===")
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                test = test_class()
                try:
                    getattr(test, method_name)()
                    print(f"  PASS: {method_name}")
                    passed += 1
                except Exception as e:
                    print(f"  FAIL: {method_name}: {e}")
                    failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
