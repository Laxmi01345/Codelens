"""AST-Aware Code Chunker - Splits code into function/class-level chunks."""

from dataclasses import dataclass, field
from typing import Optional
from .ast_parser import FileAST, FunctionDef, ClassDef


@dataclass
class CodeChunk:
    """A semantic chunk of code (function, class, or file-level)."""
    id: str
    file: str
    type: str  # 'function', 'class', 'file'
    name: str
    signature: str
    body: str
    imports: list[str] = field(default_factory=list)
    line_start: int = 0
    line_end: int = 0
    docstring: Optional[str] = None


def extract_body(content: str, start_line: int, end_line: Optional[int] = None) -> str:
    """Extract lines from content between start and end line numbers."""
    lines = content.split("\n")
    if end_line is None:
        end_line = len(lines)
    return "\n".join(lines[start_line - 1:end_line])


def find_function_end(content: str, start_line: int) -> int:
    """Find the end line of a function by detecting dedent."""
    lines = content.split("\n")
    if start_line > len(lines):
        return len(lines)
    
    base_indent = None
    for i in range(start_line, len(lines)):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        current_indent = len(line) - len(line.lstrip())
        if base_indent is None:
            base_indent = current_indent
        elif current_indent <= base_indent and i > start_line:
            return i
    return len(lines)


def chunk_file(path: str, content: str, ast: FileAST) -> list[CodeChunk]:
    """Split a single file into semantic chunks based on AST."""
    chunks = []
    lines = content.split("\n")
    
    # Create file-level chunk with imports
    import_lines = []
    for imp in ast.imports:
        if imp.is_from:
            import_lines.append(f"from {imp.module} import {', '.join(imp.names or [])}")
        else:
            import_lines.append(f"import {imp.module}")
    
    # Chunk each function
    for func in ast.functions:
        end_line = find_function_end(content, func.line)
        body = extract_body(content, func.line, end_line)
        
        signature = _build_func_signature(func)
        chunk_id = f"{path}::{func.name}"
        
        chunks.append(CodeChunk(
            id=chunk_id,
            file=path,
            type="function",
            name=func.name,
            signature=signature,
            body=body,
            imports=import_lines,
            line_start=func.line,
            line_end=end_line,
            docstring=func.docstring,
        ))
    
    # Chunk each class
    for cls in ast.classes:
        end_line = find_function_end(content, cls.line)
        body = extract_body(content, cls.line, end_line)
        
        signature = _build_class_signature(cls)
        chunk_id = f"{path}::{cls.name}"
        
        chunks.append(CodeChunk(
            id=chunk_id,
            file=path,
            type="class",
            name=cls.name,
            signature=signature,
            body=body,
            imports=import_lines,
            line_start=cls.line,
            line_end=end_line,
            docstring=cls.docstring,
        ))
    
    # If no functions/classes, create a file-level chunk
    if not chunks and content.strip():
        chunks.append(CodeChunk(
            id=f"{path}::(file)",
            file=path,
            type="file",
            name=path.split("/")[-1],
            signature=f"# File: {path}",
            body=content[:5000],
            imports=import_lines,
            line_start=1,
            line_end=len(lines),
        ))
    
    return chunks


def chunk_all_files(
    source_files: dict[str, str],
    asts: list[FileAST],
) -> list[CodeChunk]:
    """Chunk all source files into semantic chunks."""
    all_chunks = []
    
    # Create a lookup from path to AST
    ast_lookup = {ast.path: ast for ast in asts}
    
    for path, content in source_files.items():
        ast = ast_lookup.get(path)
        if ast:
            chunks = chunk_file(path, content, ast)
            all_chunks.extend(chunks)
        elif content.strip():
            # No AST available, create a single file chunk
            all_chunks.append(CodeChunk(
                id=f"{path}::(file)",
                file=path,
                type="file",
                name=path.split("/")[-1],
                signature=f"# File: {path}",
                body=content[:5000],
                imports=[],
                line_start=1,
                line_end=len(content.split("\n")),
            ))
    
    return all_chunks


def _build_func_signature(func: FunctionDef) -> str:
    """Build a function signature string."""
    parts = []
    if func.is_async:
        parts.append("async")
    parts.append("def")
    parts.append(f"{func.name}({func.args})")
    return " ".join(parts)


def _build_class_signature(cls: ClassDef) -> str:
    """Build a class signature string."""
    parts = ["class", cls.name]
    if cls.bases:
        parts.append(f"({', '.join(cls.bases)})")
    return " ".join(parts)
