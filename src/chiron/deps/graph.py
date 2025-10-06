#!/usr/bin/env python3
"""Generate dependency graph visualization for Chiron architecture.

This script analyzes Python imports across the codebase and generates
a dependency graph showing relationships between modules.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    "vendor",
    ".venv",
    "tmpreposim2",
    "__pycache__",
    ".git",
    "tests",
)

DEFAULT_MODULE_NAMESPACES: tuple[str, ...] = (
    "ingestion",
    "retrieval",
    "reasoning",
    "decision",
    "execution",
    "monitoring",
    "common",
    "model",
    "security",
    "governance",
    "observability",
    "api",
    "chiron",
    "scripts",
    "sdk",
)


def _has_python_files(directory: Path) -> bool:
    """Return True when the directory tree contains Python files."""

    try:
        next(directory.rglob("*.py"))
    except (StopIteration, OSError):
        return False
    return True


def _is_excluded(path: Path, patterns: Iterable[str]) -> bool:
    """Return True if any of the patterns appear in the path."""

    path_str = str(path)
    return any(pattern in path_str for pattern in patterns)


@lru_cache(maxsize=1)
def discover_modules(repo_root: Path) -> set[str]:
    """Return the known module namespaces for the repository."""

    modules: set[str] = set(DEFAULT_MODULE_NAMESPACES)

    # Include top-level python-bearing directories.
    for entry in repo_root.iterdir():
        if not entry.is_dir():
            continue
        if _is_excluded(entry, DEFAULT_EXCLUDE_PATTERNS):
            continue
        if _has_python_files(entry):
            modules.add(entry.name)

    # Detect src-layout namespaces like src/chiron/<module>.
    src_root = repo_root / "src"
    if src_root.is_dir():
        for namespace_dir in src_root.iterdir():
            if not namespace_dir.is_dir():
                continue
            if _is_excluded(namespace_dir, DEFAULT_EXCLUDE_PATTERNS):
                continue
            namespace = namespace_dir.name
            if not _has_python_files(namespace_dir):
                continue

            modules.add(namespace)

            for module_dir in namespace_dir.iterdir():
                if not module_dir.is_dir():
                    continue
                if module_dir.name.startswith("__"):
                    continue
                if _is_excluded(module_dir, DEFAULT_EXCLUDE_PATTERNS):
                    continue
                if _has_python_files(module_dir):
                    modules.add(f"{namespace}.{module_dir.name}")

    return modules


def _resolve_module(file_path: Path, repo_root: Path, modules: set[str]) -> str | None:
    """Resolve the module namespace for a given file."""

    try:
        relative = file_path.relative_to(repo_root)
    except ValueError:
        return None

    parts = relative.parts
    if not parts:
        return None

    if parts[0] == "src":
        if len(parts) < 2:
            return None

        namespace = parts[1]
        candidate = namespace
        if len(parts) >= 3 and parts[2] != "__init__.py":
            candidate = f"{namespace}.{parts[2]}"

        if candidate in modules:
            return candidate
        if namespace in modules:
            return namespace
        return None

    candidate = parts[0]
    if candidate in modules:
        return candidate
    return None


def _match_known_module(import_path: str, modules: set[str]) -> str | None:
    """Return the longest namespace match for the import path."""

    segments = import_path.split(".")
    for index in range(len(segments), 0, -1):
        candidate = ".".join(segments[:index])
        if candidate in modules:
            return candidate
    return None


def parse_imports(
    file_path: Path, repo_root: Path, modules: set[str] | None = None
) -> list[str]:
    """Extract import statements from a Python file.

    Only considers absolute imports, not relative imports within the same module.
    """
    modules = modules or discover_modules(repo_root)

    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    # Determine the module this file belongs to
    current_module = _resolve_module(file_path, repo_root, modules)

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                match = _match_known_module(alias.name, modules)
                if match and match != current_module:
                    imports.add(match)
                elif not match:
                    imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # Skip relative imports (e.g., from .base import ...)
            if node.level > 0:
                continue
            if node.module:
                match = _match_known_module(node.module, modules)
                if match and match != current_module:
                    imports.add(match)
                elif not match:
                    module_root = node.module.split(".")[0]
                    if module_root != current_module:
                        imports.add(module_root)
    return sorted(imports)


def analyze_dependencies(
    repo_root: Path,
    exclude_patterns: list[str] | None = None,
    modules: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Analyze dependencies across all Python files in the repository."""
    if exclude_patterns is None:
        exclude_patterns = list(DEFAULT_EXCLUDE_PATTERNS)

    exclude_set = set(exclude_patterns)
    modules = modules or discover_modules(repo_root)

    graph: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"internal_deps": set(), "external_deps": set(), "files": []}
    )

    for py_file in repo_root.rglob("*.py"):
        # Skip excluded patterns
        if _is_excluded(py_file, exclude_set):
            continue

        # Determine which module this file belongs to
        try:
            relative = py_file.relative_to(repo_root)
        except ValueError:
            continue

        module_name = _resolve_module(py_file, repo_root, modules)
        if not module_name:
            continue

        imports = parse_imports(py_file, repo_root, modules)
        graph[module_name]["files"].append(str(relative))

        for imp in imports:
            if imp in modules and imp != module_name:
                graph[module_name]["internal_deps"].add(imp)
            elif imp not in modules:
                graph[module_name]["external_deps"].add(imp)

    # Convert sets to lists for JSON serialization
    result = {}
    for module, data in graph.items():
        result[module] = {
            "internal_deps": sorted(data["internal_deps"]),
            "external_deps": sorted(data["external_deps"]),
            "file_count": len(data["files"]),
        }

    return result


def generate_mermaid(graph: dict[str, dict[str, Any]]) -> str:
    """Generate a Mermaid diagram from the dependency graph."""
    lines = ["```mermaid", "graph TD"]

    # Define core pipeline stages with special styling
    pipeline_stages = [
        "ingestion",
        "retrieval",
        "reasoning",
        "decision",
        "execution",
        "monitoring",
    ]

    # Add nodes
    for module in sorted(graph.keys()):
        if module in pipeline_stages:
            lines.append(f"    {module}[{module.title()}]:::pipeline")
        else:
            lines.append(f"    {module}[{module.title()}]")

    lines.append("")

    # Add edges for internal dependencies
    for module, data in sorted(graph.items()):
        for dep in sorted(data["internal_deps"]):
            lines.append(f"    {module} --> {dep}")

    lines.append("")
    lines.append("    classDef pipeline fill:#e1f5ff,stroke:#01579b,stroke-width:2px")
    lines.append("```")

    return "\n".join(lines)


def detect_cycles(graph: dict[str, dict[str, Any]]) -> list[list[str]]:
    """Detect circular dependencies in the module graph."""
    cycles = []

    def visit(
        node: str, path: list[str], visited: set[str], rec_stack: set[str]
    ) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for dep in graph.get(node, {}).get("internal_deps", []):
            if dep not in visited:
                visit(dep, path.copy(), visited, rec_stack)
            elif dep in rec_stack:
                # Found a cycle
                cycle_start = path.index(dep)
                cycles.append(path[cycle_start:] + [dep])

        rec_stack.remove(node)

    visited_set: set[str] = set()
    for module in graph:
        if module not in visited_set:
            visit(module, [], visited_set, set())

    return cycles


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate dependency graph for Chiron")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root directory",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file (default: docs/dependency-graph.md)",
    )
    parser.add_argument(
        "--format",
        choices=["mermaid", "json"],
        default="mermaid",
        help="Output format",
    )
    parser.add_argument(
        "--check-cycles",
        action="store_true",
        help="Check for circular dependencies and exit with error if found",
    )

    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_path = args.output or repo_root / "docs" / "dependency-graph.md"

    print(f"Analyzing dependencies in {repo_root}...", file=sys.stderr)
    graph = analyze_dependencies(repo_root)

    if args.check_cycles:
        cycles = detect_cycles(graph)
        if cycles:
            print(f"ERROR: Found {len(cycles)} circular dependencies:", file=sys.stderr)
            for cycle in cycles:
                print(f"  {' -> '.join(cycle)}", file=sys.stderr)
            return 1
        print("✓ No circular dependencies detected", file=sys.stderr)

    if args.format == "json":
        content = json.dumps(graph, indent=2)
    else:
        # Generate Mermaid markdown document
        lines = [
            "# Chiron Dependency Graph",
            "",
            "This diagram shows the internal dependencies between Chiron modules.",
            "Generated automatically by `scripts/generate_dependency_graph.py`.",
            "",
            "## Module Dependencies",
            "",
            generate_mermaid(graph),
            "",
            "## Module Details",
            "",
        ]

        for module in sorted(graph.keys()):
            data = graph[module]
            lines.append(f"### {module.title()}")
            lines.append(f"- Files: {data['file_count']}")
            if data["internal_deps"]:
                lines.append(
                    f"- Internal dependencies: {', '.join(data['internal_deps'])}"
                )
            if data["external_deps"]:
                ext_deps = data["external_deps"][:10]  # Limit to first 10
                if len(data["external_deps"]) > 10:
                    ext_deps.append("...")
                lines.append(f"- External dependencies: {', '.join(ext_deps)}")
            lines.append("")

        content = "\n".join(lines)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"✓ Dependency graph written to {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
