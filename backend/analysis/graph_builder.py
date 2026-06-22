"""Dependency Graph Builder - Builds module dependency graphs from AST imports."""

from dataclasses import dataclass, field
from collections import defaultdict, deque
from pathlib import PurePosixPath
from typing import Optional
from .ast_parser import FileAST


@dataclass
class GraphNode:
    path: str
    language: str
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    line_count: int = 0
    complexity: float = 0.0


@dataclass
class CycleInfo:
    cycle: list[str]
    depth: int


class DependencyGraph:
    """Directed acyclic graph of module dependencies with cycle detection."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[str, set[str]] = defaultdict(set)  # node -> dependencies
        self.reverse_edges: dict[str, set[str]] = defaultdict(set)  # node -> dependents
        self._cycles: list[CycleInfo] = []

    def add_file(self, ast: FileAST) -> None:
        """Add a parsed file to the graph."""
        node = GraphNode(
            path=ast.path,
            language=ast.language,
            imports=[imp.module for imp in ast.imports],
            functions=[f.name for f in ast.functions],
            classes=[c.name for c in ast.classes],
            line_count=ast.line_count,
            complexity=ast.complexity_score,
        )
        self.nodes[ast.path] = node

        # Add edges based on imports
        for imp in ast.imports:
            target = self._resolve_import(ast.path, imp.module)
            if target:
                self.edges[ast.path].add(target)
                self.reverse_edges[target].add(ast.path)

    def _resolve_import(self, source_path: str, module: str) -> Optional[str]:
        """Resolve an import module name to a file path in the graph."""
        # Try direct path match first (before stdlib check)
        if module in self.nodes:
            return module

        # Get source directory
        source_dir = str(PurePosixPath(source_path).parent)

        # Python import resolution
        if source_path.endswith(".py"):
            return self._resolve_python_import(source_path, source_dir, module)

        # JavaScript/TypeScript import resolution
        if source_path.endswith((".js", ".jsx", ".ts", ".tsx")):
            return self._resolve_js_import(source_path, source_dir, module)

        # Go import resolution
        if source_path.endswith(".go"):
            return self._resolve_go_import(source_path, source_dir, module)

        return None

    def _resolve_python_import(self, source_path: str, source_dir: str, module: str) -> Optional[str]:
        """Resolve Python imports."""
        # Handle relative imports (from . import X, from .. import X)
        if module.startswith("."):
            # Relative import - resolve based on source directory
            relative_path = module.lstrip(".")
            if relative_path:
                # Try various relative paths
                candidates = [
                    f"{source_dir}/{relative_path}.py",
                    f"{source_dir}/{relative_path}/__init__.py",
                ]
                for candidate in candidates:
                    if candidate in self.nodes:
                        return candidate
            return None

        # Absolute import - try various patterns
        candidates = [
            # Direct module match (e.g., "utils" -> "utils.py")
            f"{module}.py",
            # Package match (e.g., "flask" -> "flask/__init__.py")
            f"{module}/__init__.py",
            # In source directory (e.g., "models" -> "src/models.py")
            f"{source_dir}/{module}.py",
            # Package in source directory
            f"{source_dir}/{module}/__init__.py",
            # Try parent directories (for nested packages)
            f"{source_dir}/../{module}.py",
            f"{source_dir}/../{module}/__init__.py",
            # Try common package structures
            f"src/{module}.py",
            f"src/{module}/__init__.py",
            f"lib/{module}.py",
            f"lib/{module}/__init__.py",
        ]

        for candidate in candidates:
            if candidate in self.nodes:
                return candidate

        # Try to match by module name in any path
        for node_path in self.nodes:
            node_stem = PurePosixPath(node_path).stem
            node_parent = str(PurePosixPath(node_path).parent)
            if node_stem == module:
                return node_path
            if node_parent.endswith(f"/{module}") or node_parent.endswith(f"\\{module}"):
                if node_stem == "__init__":
                    return node_path

        return None

    def _resolve_js_import(self, source_path: str, source_dir: str, module: str) -> Optional[str]:
        """Resolve JavaScript/TypeScript imports."""
        # Handle relative imports (./utils, ../utils)
        if module.startswith("./"):
            relative_path = module[2:]
            candidates = [
                f"{source_dir}/{relative_path}.js",
                f"{source_dir}/{relative_path}.jsx",
                f"{source_dir}/{relative_path}.ts",
                f"{source_dir}/{relative_path}.tsx",
                f"{source_dir}/{relative_path}/index.js",
                f"{source_dir}/{relative_path}/index.ts",
            ]
            for candidate in candidates:
                if candidate in self.nodes:
                    return candidate

        elif module.startswith("../"):
            relative_path = module[3:]
            parent_dir = str(PurePosixPath(source_dir).parent)
            candidates = [
                f"{parent_dir}/{relative_path}.js",
                f"{parent_dir}/{relative_path}.jsx",
                f"{parent_dir}/{relative_path}.ts",
                f"{parent_dir}/{relative_path}.tsx",
                f"{parent_dir}/{relative_path}/index.js",
                f"{parent_dir}/{relative_path}/index.ts",
            ]
            for candidate in candidates:
                if candidate in self.nodes:
                    return candidate

        # Absolute import - try to find matching file
        candidates = [
            f"{source_dir}/{module}.js",
            f"{source_dir}/{module}.jsx",
            f"{source_dir}/{module}.ts",
            f"{source_dir}/{module}.tsx",
            f"{source_dir}/{module}/index.js",
            f"{source_dir}/{module}/index.ts",
        ]

        for candidate in candidates:
            if candidate in self.nodes:
                return candidate

        return None

    def _resolve_go_import(self, source_path: str, source_dir: str, module: str) -> Optional[str]:
        """Resolve Go imports."""
        # Go imports are usually full paths like "github.com/user/repo/pkg"
        # Try to find matching files
        for node_path in self.nodes:
            if node_path.endswith(".go"):
                # Check if the module path matches
                if module in node_path or node_path.endswith(f"/{module}.go"):
                    return node_path
        return None

    def _is_stdlib_or_third_party(self, module: str) -> bool:
        """Check if a module is likely standard library or third-party."""
        # Python standard library modules (common ones)
        python_stdlib = {
            "os", "sys", "json", "re", "datetime", "typing", "pathlib",
            "asyncio", "collections", "dataclasses", "hashlib", "time",
            "functools", "itertools", "operator", "string", "textwrap",
            "unicodedata", "io", "codecs", "locale", "platform", "subprocess",
            "shutil", "glob", "fnmatch", "tempfile", "random", "math",
            "decimal", "fractions", "statistics", "secrets", "unittest",
            "logging", "warnings", "contextlib", "abc", "copy", "pprint",
            "enum", "numbers", "bisect", "heapq", "array", "weakref",
            "types", "inspect", "site", "builtins", "marshal", "pickle",
            "sqlite3", "dbm", "xml", "html", "http", "urllib", "ftplib",
            "smtplib", "email", "mailbox", "mimetypes", "webbrowser",
            "cgi", "cgitb", "wsgiref", "xmlrpc", "ipaddress", "calendar",
            "getpass", "gettext", "gzip", "hmac", "imaplib", "imghdr",
            "imp", "importlib", "keyword", "lib2to3", "linecache",
            "lzma", "mailcap", "mmap", "modulefinder", "multiprocessing",
            "netrc", "nis", "nntplib", "optparse", "ossaudiodev",
            "pathlib", "pdb", "pickletools", "pipes", "pkgutil",
            "plistlib", "poplib", "posix", "posixpath", "profile",
            "pstats", "pty", "pwd", "py_compile", "pyclbr",
            "pydoc", "queue", "quopri", "readline",
            "reprlib", "resource", "rlcompleter", "runpy", "sched",
            "select", "selectors", "shelve", "shlex",
            "signal", "smtpd", "sndhdr", "socket",
            "socketserver", "ssl", "stat", "stringprep", "struct",
            "sunau", "symtable", "sysconfig", "syslog", "tabnanny",
            "tarfile", "telnetlib", "termios", "test", "threading",
            "timeit", "tkinter", "token", "tokenize", "tomllib", "trace",
            "traceback", "tracemalloc", "tty", "turtle", "turtledemo",
            "uu", "uuid", "venv", "wave",
            "winreg", "winsound", "xdrlib", "zipapp", "zipfile",
            "zipimport", "zlib",
            # Common third-party
            "flask", "django", "fastapi", "starlette", "pydantic",
            "requests", "httpx", "aiohttp", "urllib3",
            "numpy", "pandas", "scipy", "sklearn", "tensorflow", "torch",
            "sqlalchemy", "psycopg2", "pymysql", "redis", "celery",
            "pytest", "mock", "coverage",
            "click", "argparse", "typer",
            "jinja2", "mako",
            "boto3", "google", "azure",
            "cryptography", "bcrypt", "jwt",
        }

        # JavaScript/Node.js standard modules
        js_stdlib = {
            "fs", "path", "http", "https", "url", "util", "events",
            "stream", "buffer", "crypto", "os", "net", "tls", "readline",
            "child_process", "cluster", "dgram", "dns", "domain", "querystring",
            "repl", "vm", "v8", "zlib",
            # Common npm packages
            "react", "react-dom", "vue", "angular", "svelte",
            "express", "koa", "fastify", "hapi",
            "lodash", "underscore", "moment", "dayjs",
            "axios", "node-fetch", "got",
            "webpack", "vite", "rollup", "esbuild",
            "typescript", "eslint", "prettier",
            "jest", "mocha", "chai", "vitest",
        }

        # Go standard library (common prefixes)
        go_stdlib_prefixes = [
            "fmt", "log", "os", "io", "net", "http", "json", "xml",
            "strings", "strconv", "math", "sort", "sync", "time",
            "context", "errors", "testing", "reflect", "unsafe",
        ]

        module_lower = module.lower().split(".")[0]

        if module_lower in python_stdlib or module_lower in js_stdlib:
            return True

        for prefix in go_stdlib_prefixes:
            if module_lower == prefix or module_lower.startswith(prefix + "/"):
                return True

        # If it looks like a package with dots (e.g., "flask.app"), check the first part
        if "." in module:
            first_part = module.split(".")[0].lower()
            if first_part in python_stdlib or first_part in js_stdlib:
                return True

        return False

    def get_dependencies(self, path: str) -> set[str]:
        """Get all modules that this module depends on (direct)."""
        return self.edges.get(path, set())

    def get_dependents(self, path: str) -> set[str]:
        """Get all modules that depend on this module (reverse dependencies)."""
        return self.reverse_edges.get(path, set())

    def get_transitive_dependencies(self, path: str) -> set[str]:
        """Get all modules that this module transitively depends on (BFS)."""
        visited = set()
        queue = deque([path])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for dep in self.edges.get(current, set()):
                if dep not in visited:
                    queue.append(dep)

        visited.discard(path)
        return visited

    def get_transitive_dependents(self, path: str) -> set[str]:
        """Get all modules that transitively depend on this module (BFS)."""
        visited = set()
        queue = deque([path])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for dep in self.reverse_edges.get(current, set()):
                if dep not in visited:
                    queue.append(dep)

        visited.discard(path)
        return visited

    def detect_cycles(self) -> list[CycleInfo]:
        """Detect cycles using DFS. Returns list of cycles found."""
        self._cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.edges.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    self._cycles.append(CycleInfo(cycle=cycle, depth=len(cycle) - 1))

            path.pop()
            rec_stack.discard(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return self._cycles

    def topological_sort(self) -> list[str]:
        """Return modules in topological order (dependencies first)."""
        # Count how many modules each module depends on (outgoing edges)
        depends_on_count = defaultdict(int)
        for node in self.nodes:
            depends_on_count[node] = len(self.edges.get(node, set()))

        # Start with modules that have no dependencies
        queue = deque([n for n, d in depends_on_count.items() if d == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            # For modules that depend on this one, decrement their count
            for dependent in self.reverse_edges.get(node, set()):
                depends_on_count[dependent] -= 1
                if depends_on_count[dependent] == 0:
                    queue.append(dependent)

        return result

    def get_hub_modules(self, top_n: int = 5) -> list[tuple[str, int]]:
        """Find modules with most dependents (hub modules)."""
        return sorted(
            [(path, len(deps)) for path, deps in self.reverse_edges.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:top_n]

    def get_leaf_modules(self) -> list[str]:
        """Find modules with no dependents (leaf modules)."""
        return [path for path in self.nodes if not self.reverse_edges.get(path)]

    def to_mermaid(self, title: str = "Module Dependencies") -> str:
        """Generate Mermaid flowchart from the dependency graph."""
        lines = [f"flowchart LR"]

        # Add nodes with labels
        for path, node in self.nodes.items():
            label = PurePosixPath(path).stem
            lines.append(f'    {self._safe_id(path)}["{label}"]')

        # Add edges
        for source, targets in self.edges.items():
            for target in targets:
                lines.append(f"    {self._safe_id(source)} --> {self._safe_id(target)}")

        return "\n".join(lines)

    def to_summary(self) -> dict:
        """Generate a summary of the dependency graph."""
        cycles = self.detect_cycles()
        hubs = self.get_hub_modules(5)
        leaves = self.get_leaf_modules()
        topo = self.topological_sort()

        # Find isolated modules (no imports and not imported)
        all_imported = set()
        for deps in self.edges.values():
            all_imported.update(deps)
        isolated = [p for p in self.nodes if not self.edges.get(p) and p not in all_imported]

        return {
            "total_modules": len(self.nodes),
            "total_edges": sum(len(deps) for deps in self.edges.values()),
            "cycles": [{"cycle": c.cycle, "depth": c.depth} for c in cycles],
            "has_cycles": len(cycles) > 0,
            "hub_modules": hubs,
            "leaf_modules": leaves[:10],
            "isolated_modules": isolated[:10],
            "topological_order": topo[:20],
            "languages": list(set(n.language for n in self.nodes.values())),
        }

    @staticmethod
    def _safe_id(path: str) -> str:
        """Convert path to safe Mermaid ID."""
        return path.replace("/", "_").replace(".", "_").replace("-", "_")


def build_dependency_graph(asts: list[FileAST]) -> DependencyGraph:
    """
    Build a dependency graph from a list of parsed files.

    Uses two-phase approach:
    1. Add all files to the graph (nodes only)
    2. Resolve imports and add edges

    This ensures all files are available when resolving imports.
    """
    graph = DependencyGraph()

    # Phase 1: Add all files as nodes (no edge resolution yet)
    for ast in asts:
        node = GraphNode(
            path=ast.path,
            language=ast.language,
            imports=[imp.module for imp in ast.imports],
            functions=[f.name for f in ast.functions],
            classes=[c.name for c in ast.classes],
            line_count=ast.line_count,
            complexity=ast.complexity_score,
        )
        graph.nodes[ast.path] = node

    # Phase 2: Resolve imports and add edges
    for ast in asts:
        for imp in ast.imports:
            target = graph._resolve_import(ast.path, imp.module)
            if target:
                graph.edges[ast.path].add(target)
                graph.reverse_edges[target].add(ast.path)

    return graph
