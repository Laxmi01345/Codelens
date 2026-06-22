"""AST Parser - Extracts functions, classes, imports from source code using regex."""

import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import PurePosixPath


@dataclass
class FunctionDef:
    name: str
    args: list[str]
    line: int
    is_async: bool = False
    decorators: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ClassDef:
    name: str
    bases: list[str]
    line: int
    decorators: list[str] = field(default_factory=list)
    methods: list[FunctionDef] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class Import:
    module: str
    names: list[str] = field(default_factory=list)
    is_from: bool = False
    line: int = 0


@dataclass
class FileAST:
    path: str
    language: str
    functions: list[FunctionDef] = field(default_factory=list)
    classes: list[ClassDef] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    line_count: int = 0
    complexity_score: float = 0.0


# Language detection by extension
EXTENSION_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".swift": "swift",
    ".kt": "kotlin",
}


def detect_language(file_path: str) -> str:
    """Detect language from file extension."""
    ext = PurePosixPath(file_path).suffix.lower()
    return EXTENSION_MAP.get(ext, "unknown")


def parse_file(file_path: str, content: str) -> FileAST:
    """Parse a source file and extract AST data."""
    lang = detect_language(file_path)
    ast = FileAST(path=file_path, language=lang, line_count=content.count("\n") + 1)

    if lang == "python":
        _parse_python(content, ast)
    elif lang in ("javascript", "typescript"):
        _parse_js_ts(content, ast)
    elif lang == "go":
        _parse_go(content, ast)
    elif lang == "java":
        _parse_java(content, ast)
    elif lang == "rust":
        _parse_rust(content, ast)

    ast.complexity_score = _estimate_complexity(ast)
    return ast


# ──────────────────────────────────────────────
# Python Parser
# ──────────────────────────────────────────────

def _parse_python(content: str, ast: FileAST) -> None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Function definitions
        m = re.match(r"(async\s+)?def\s+(\w+)\s*\((.*?)\)", stripped)
        if m:
            is_async = m.group(1) is not None
            name = m.group(2)
            args_str = m.group(3)
            args = [a.strip().split(":")[0].split("=")[0].strip()
                    for a in args_str.split(",") if a.strip() and a.strip() != "self"]
            decorators = _collect_decorators(lines, i)
            docstring = _extract_docstring(lines, i)
            ast.functions.append(FunctionDef(
                name=name, args=args, line=i + 1,
                is_async=is_async, decorators=decorators, docstring=docstring,
            ))

        # Class definitions
        m = re.match(r"class\s+(\w+)\s*(?:\((.*?)\))?\s*:", stripped)
        if m:
            name = m.group(1)
            bases_str = m.group(2)
            bases = [b.strip() for b in bases_str.split(",")] if bases_str else []
            decorators = _collect_decorators(lines, i)
            docstring = _extract_docstring(lines, i)
            ast.classes.append(ClassDef(
                name=name, bases=bases, line=i + 1,
                decorators=decorators, docstring=docstring,
            ))

        # Imports
        m = re.match(r"from\s+([\w.]+)\s+import\s+(.+)", stripped)
        if m:
            module = m.group(1)
            names = [n.strip().split(" as ")[0] for n in m.group(2).split(",")]
            ast.imports.append(Import(module=module, names=names, is_from=True, line=i + 1))

        m = re.match(r"import\s+([\w.,\s]+)", stripped)
        if m and not stripped.startswith("from"):
            names = [n.strip().split(" as ")[0] for n in m.group(1).split(",")]
            for name in names:
                ast.imports.append(Import(module=name, names=[name], is_from=False, line=i + 1))

    # Exports (__all__)
    m = re.search(r"__all__\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if m:
        ast.exports = [s.strip().strip("'\"") for s in m.group(1).split(",") if s.strip()]


def _collect_decorators(lines: list[str], func_line: int) -> list[str]:
    decorators = []
    i = func_line - 1
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("@"):
            decorators.insert(0, stripped)
        elif stripped == "" or stripped.startswith("#"):
            i -= 1
            continue
        else:
            break
        i -= 1
    return decorators


def _extract_docstring(lines: list[str], def_line: int) -> Optional[str]:
    idx = def_line  # 0-based index of def line
    if idx + 1 < len(lines):
        next_line = lines[idx + 1].strip()
        if next_line.startswith('"""') or next_line.startswith("'''"):
            quote = next_line[:3]
            if next_line.count(quote) >= 2 and len(next_line) > 6:
                return next_line[3:-3]
            for j in range(idx + 2, min(idx + 10, len(lines))):
                if quote in lines[j]:
                    return "\n".join(lines[idx + 2:j])[:200]
    return None


# ──────────────────────────────────────────────
# JavaScript / TypeScript Parser
# ──────────────────────────────────────────────

def _parse_js_ts(content: str, ast: FileAST) -> None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Functions
        m = re.match(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\((.*?)\)", stripped)
        if m:
            name = m.group(1)
            args = [a.strip().split(":")[0].split("=")[0].strip()
                    for a in m.group(2).split(",") if a.strip()]
            ast.functions.append(FunctionDef(name=name, args=args, line=i + 1,
                                             is_async="async" in stripped))

        # Arrow functions: const name = (...) =>
        m = re.match(r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\((.*?)\)\s*=>", stripped)
        if m:
            name = m.group(1)
            args = [a.strip().split(":")[0].split("=")[0].strip()
                    for a in m.group(2).split(",") if a.strip()]
            ast.functions.append(FunctionDef(name=name, args=args, line=i + 1,
                                             is_async="async" in stripped))

        # Classes
        m = re.match(r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*\{", stripped)
        if m:
            name = m.group(1)
            bases = [m.group(2)] if m.group(2) else []
            ast.classes.append(ClassDef(name=name, bases=bases, line=i + 1))

        # Imports
        m = re.match(r'import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+[\'"](.+?)[\'"]', stripped)
        if m:
            names_str = m.group(1) or m.group(2)
            names = [n.strip().split(" as ")[0] for n in names_str.split(",")]
            module = m.group(3)
            ast.imports.append(Import(module=module, names=names, is_from=True, line=i + 1))

        # Requires
        m = re.match(r'(?:const|let|var)\s+(\w+)\s*=\s*require\([\'"](.+?)[\'"]\)', stripped)
        if m:
            ast.imports.append(Import(module=m.group(2), names=[m.group(1)], is_from=False, line=i + 1))

    # Exports
    export_matches = re.findall(r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)", content)
    ast.exports = export_matches


# ──────────────────────────────────────────────
# Go Parser
# ──────────────────────────────────────────────

def _parse_go(content: str, ast: FileAST) -> None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Functions
        m = re.match(r"func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\((.*?)\)", stripped)
        if m:
            name = m.group(1)
            args = [a.strip().split()[0] for a in m.group(2).split(",") if a.strip()]
            ast.functions.append(FunctionDef(name=name, args=args, line=i + 1))

        # Structs (like classes)
        m = re.match(r"type\s+(\w+)\s+struct\s*\{", stripped)
        if m:
            ast.classes.append(ClassDef(name=m.group(1), bases=[], line=i + 1))

        # Interfaces
        m = re.match(r"type\s+(\w+)\s+interface\s*\{", stripped)
        if m:
            ast.classes.append(ClassDef(name=m.group(1), bases=["interface"], line=i + 1))

        # Imports
        m = re.match(r'import\s+(?:\(\s*)?(?:.*"?([\w./]+)"?\s*)', stripped)
        if m:
            ast.imports.append(Import(module=m.group(1), names=[], is_from=False, line=i + 1))


# ──────────────────────────────────────────────
# Java Parser
# ──────────────────────────────────────────────

def _parse_java(content: str, ast: FileAST) -> None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Methods
        m = re.match(r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\((.*?)\)", stripped)
        if m and "{" in stripped:
            name = m.group(1)
            args = [a.strip().split()[-1] for a in m.group(2).split(",") if a.strip()]
            ast.functions.append(FunctionDef(name=name, args=args, line=i + 1))

        # Classes
        m = re.match(r"(?:public\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?\s*\{", stripped)
        if m:
            name = m.group(1)
            bases = []
            if m.group(2):
                bases.append(m.group(2))
            if m.group(3):
                bases.extend([b.strip() for b in m.group(3).split(",")])
            ast.classes.append(ClassDef(name=name, bases=bases, line=i + 1))

        # Imports
        m = re.match(r"import\s+([\w.]+);", stripped)
        if m:
            ast.imports.append(Import(module=m.group(1), names=[], is_from=False, line=i + 1))


# ──────────────────────────────────────────────
# Rust Parser
# ──────────────────────────────────────────────

def _parse_rust(content: str, ast: FileAST) -> None:
    lines = content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Functions
        m = re.match(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\((.*?)\)", stripped)
        if m:
            name = m.group(1)
            args = [a.strip().split(":")[0].strip() for a in m.group(2).split(",") if a.strip() and a.strip() != "self"]
            ast.functions.append(FunctionDef(name=name, args=args, line=i + 1,
                                             is_async="async" in stripped))

        # Structs
        m = re.match(r"(?:pub\s+)?struct\s+(\w+)", stripped)
        if m:
            ast.classes.append(ClassDef(name=m.group(1), bases=[], line=i + 1))

        # Traits
        m = re.match(r"(?:pub\s+)?trait\s+(\w+)", stripped)
        if m:
            ast.classes.append(ClassDef(name=m.group(1), bases=["trait"], line=i + 1))

        # Use statements
        m = re.match(r"use\s+([\w:]+)", stripped)
        if m:
            ast.imports.append(Import(module=m.group(1), names=[], is_from=False, line=i + 1))

    # Exports (pub items)
    pub_matches = re.findall(r"pub\s+(?:fn|struct|trait|enum)\s+(\w+)", content)
    ast.exports = pub_matches


# ──────────────────────────────────────────────
# Complexity Estimation
# ──────────────────────────────────────────────

def _estimate_complexity(ast: FileAST) -> float:
    """Estimate complexity score (0-10) based on AST features."""
    score = 0.0

    # Functions add complexity
    score += len(ast.functions) * 0.5

    # Classes add complexity
    score += len(ast.classes) * 1.0

    # Imports suggest dependencies
    score += len(ast.imports) * 0.2

    # Large files are more complex
    if ast.line_count > 500:
        score += 2.0
    elif ast.line_count > 200:
        score += 1.0

    return min(score, 10.0)
