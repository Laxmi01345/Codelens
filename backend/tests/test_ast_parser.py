"""Tests for AST Parser."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from analysis.ast_parser import parse_file, FileAST


class TestPythonParser:
    """Tests for Python code parsing."""

    def test_parse_functions(self):
        code = """def add(a, b):
    return a + b

def subtract(x, y):
    return x - y
"""
        ast = parse_file("math.py", code)
        assert len(ast.functions) == 2
        assert ast.functions[0].name == "add"
        assert ast.functions[0].args == ["a", "b"]
        assert ast.functions[1].name == "subtract"
        assert ast.functions[1].args == ["x", "y"]

    def test_parse_async_function(self):
        code = """async def fetch_data():
    pass
"""
        ast = parse_file("async_utils.py", code)
        assert len(ast.functions) == 1
        assert ast.functions[0].name == "fetch_data"
        assert ast.functions[0].is_async is True

    def test_parse_classes(self):
        code = """class Service:
    pass

class BaseService(Service):
    pass
"""
        ast = parse_file("models.py", code)
        assert len(ast.classes) == 2
        assert ast.classes[0].name == "Service"
        assert ast.classes[0].bases == []
        assert ast.classes[1].name == "BaseService"
        assert ast.classes[1].bases == ["Service"]

    def test_parse_imports(self):
        code = """import os
from pathlib import Path
from typing import Optional, List
"""
        ast = parse_file("utils.py", code)
        assert len(ast.imports) == 3
        assert ast.imports[0].module == "os"
        assert ast.imports[1].module == "pathlib"
        assert ast.imports[1].names == ["Path"]
        assert ast.imports[2].names == ["Optional", "List"]

    def test_parse_exports(self):
        code = """__all__ = ["MyClass", "my_function"]

def my_function():
    pass

class MyClass:
    pass
"""
        ast = parse_file("package.py", code)
        assert ast.exports == ["MyClass", "my_function"]

    def test_language_detection(self):
        ast = parse_file("test.py", "pass")
        assert ast.language == "python"

    def test_line_count(self):
        code = "line1\nline2\nline3"
        ast = parse_file("test.py", code)
        assert ast.line_count == 3

    def test_decorators(self):
        code = """@staticmethod
def my_func():
    pass
"""
        ast = parse_file("decorators.py", code)
        assert len(ast.functions) == 1
        assert "@staticmethod" in ast.functions[0].decorators


class TestJavaScriptParser:
    """Tests for JavaScript/TypeScript code parsing."""

    def test_parse_functions(self):
        code = """function add(a, b) {
    return a + b;
}

const subtract = (x, y) => x - y;
"""
        ast = parse_file("math.js", code)
        assert len(ast.functions) == 2
        assert ast.functions[0].name == "add"
        assert ast.functions[1].name == "subtract"

    def test_parse_classes(self):
        code = """class Service extends BaseService {
}
"""
        ast = parse_file("service.js", code)
        assert len(ast.classes) == 1
        assert ast.classes[0].name == "Service"
        assert ast.classes[0].bases == ["BaseService"]

    def test_parse_imports(self):
        code = """import React from 'react';
import { useState } from 'react';
const lodash = require('lodash');
"""
        ast = parse_file("app.js", code)
        assert len(ast.imports) == 3
        assert ast.imports[0].module == "react"
        assert ast.imports[1].names == ["useState"]

    def test_parse_exports(self):
        code = """export function myFunc() {}
export class MyClass {}
"""
        ast = parse_file("module.js", code)
        assert len(ast.exports) == 2
        assert "myFunc" in ast.exports
        assert "MyClass" in ast.exports


class TestGoParser:
    """Tests for Go code parsing."""

    def test_parse_functions(self):
        code = """func Add(a int, b int) int {
    return a + b
}
"""
        ast = parse_file("math.go", code)
        assert len(ast.functions) == 1
        assert ast.functions[0].name == "Add"

    def test_parse_structs(self):
        code = """type Service struct {
}
"""
        ast = parse_file("models.go", code)
        assert len(ast.classes) == 1
        assert ast.classes[0].name == "Service"


class TestRustParser:
    """Tests for Rust code parsing."""

    def test_parse_functions(self):
        code = """pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        ast = parse_file("math.rs", code)
        assert len(ast.functions) == 1
        assert ast.functions[0].name == "add"

    def test_parse_structs(self):
        code = """pub struct Service {
}
"""
        ast = parse_file("models.rs", code)
        assert len(ast.classes) == 1
        assert ast.classes[0].name == "Service"


class TestComplexity:
    """Tests for complexity estimation."""

    def test_simple_file(self):
        code = """def simple():
    pass
"""
        ast = parse_file("simple.py", code)
        assert ast.complexity_score < 2.0

    def test_complex_file(self):
        code = """import os
from typing import Optional

class ServiceA:
    pass

class ServiceB:
    pass

def func1(): pass
def func2(): pass
def func3(): pass
def func4(): pass
def func5(): pass
def func6(): pass
def func7(): pass
def func8(): pass
def func9(): pass
def func10(): pass
""" + "\n".join([f"def extra{i}(): pass" for i in range(50)])
        ast = parse_file("complex.py", code)
        assert ast.complexity_score > 3.0


if __name__ == "__main__":
    # Run tests manually
    import traceback

    test_classes = [
        TestPythonParser,
        TestJavaScriptParser,
        TestGoParser,
        TestRustParser,
        TestComplexity,
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
