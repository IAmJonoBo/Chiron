"""Tests for chiron.deps.graph module - dependency graph visualization."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chiron.deps.graph import (
    analyze_dependencies,
    generate_mermaid,
    parse_imports,
)


class TestParseImports:
    """Tests for parse_imports function."""

    def test_parse_imports_simple(self, tmp_path: Path) -> None:
        """Test parsing simple imports."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
import os
import sys
from pathlib import Path
""")

        imports = parse_imports(py_file, tmp_path)

        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports

    def test_parse_imports_from_imports(self, tmp_path: Path) -> None:
        """Test parsing from imports."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
from collections import defaultdict
from typing import Any
""")

        imports = parse_imports(py_file, tmp_path)

        assert "collections" in imports
        assert "typing" in imports

    def test_parse_imports_skips_relative(self, tmp_path: Path) -> None:
        """Test that relative imports are skipped."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
from .base import BaseClass
from ..utils import helper
import os
""")

        imports = parse_imports(py_file, tmp_path)

        # Relative imports should be skipped
        assert "base" not in imports
        assert "utils" not in imports
        # Absolute import should be included
        assert "os" in imports

    def test_parse_imports_deduplicates(self, tmp_path: Path) -> None:
        """Test that duplicate imports are deduplicated."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
import json
from json import dumps
from json.decoder import JSONDecoder
""")

        imports = parse_imports(py_file, tmp_path)

        # Should only have json once despite multiple imports
        assert imports.count("json") == 1

    def test_parse_imports_syntax_error(self, tmp_path: Path) -> None:
        """Test handling syntax errors in files."""
        py_file = tmp_path / "bad.py"
        py_file.write_text("""
import os
def broken(
# Syntax error - unclosed parenthesis
""")

        imports = parse_imports(py_file, tmp_path)

        # Should return empty list for files with syntax errors
        assert imports == []

    def test_parse_imports_unicode_error(self, tmp_path: Path) -> None:
        """Test handling files with encoding issues."""
        py_file = tmp_path / "binary.py"
        # Write binary data that will cause UnicodeDecodeError
        py_file.write_bytes(b"\xff\xfe invalid unicode")

        imports = parse_imports(py_file, tmp_path)

        # Should return empty list for files with encoding errors
        assert imports == []

    def test_parse_imports_skips_same_module(self, tmp_path: Path) -> None:
        """Test that imports from the same module are skipped."""
        # Create a file in chiron module
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        py_file = chiron_dir / "test.py"
        py_file.write_text("""
from chiron.core import something
from chiron.utils import helper
import external_module
""")

        imports = parse_imports(py_file, tmp_path)

        # Should skip chiron imports since file is in chiron module
        assert "chiron" not in imports
        # But external imports should be included
        assert "external_module" in imports

    def test_parse_imports_nested_modules(self, tmp_path: Path) -> None:
        """Test parsing imports with nested module paths."""
        py_file = tmp_path / "test.py"
        py_file.write_text("""
from collections.abc import Mapping
from typing.io import TextIO
import os.path
""")

        imports = parse_imports(py_file, tmp_path)

        # Should only get the root module name
        assert "collections" in imports
        assert "typing" in imports
        assert "os" in imports


class TestAnalyzeDependencies:
    """Tests for analyze_dependencies function."""

    def test_analyze_dependencies_empty_repo(self, tmp_path: Path) -> None:
        """Test analyzing dependencies in an empty repository."""
        graph = analyze_dependencies(tmp_path)

        # Should return empty graph for empty repo
        assert graph == {}

    def test_analyze_dependencies_single_module(self, tmp_path: Path) -> None:
        """Test analyzing dependencies for a single module."""
        # Create a chiron module
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        test_file = chiron_dir / "test.py"
        test_file.write_text("""
import os
import json
from pathlib import Path
""")

        graph = analyze_dependencies(tmp_path)

        assert "chiron" in graph
        assert "os" in graph["chiron"]["external_deps"]
        assert "json" in graph["chiron"]["external_deps"]
        assert "pathlib" in graph["chiron"]["external_deps"]
        assert graph["chiron"]["file_count"] == 1

    def test_analyze_dependencies_with_internal_deps(self, tmp_path: Path) -> None:
        """Test analyzing dependencies with internal module dependencies."""
        # Create common module
        common_dir = tmp_path / "common"
        common_dir.mkdir()
        common_file = common_dir / "utils.py"
        common_file.write_text("def helper(): pass")

        # Create chiron module that imports from common
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        chiron_file = chiron_dir / "main.py"
        chiron_file.write_text("""
from common import utils
import json
""")

        graph = analyze_dependencies(tmp_path)

        assert "chiron" in graph
        assert "common" in graph["chiron"]["internal_deps"]
        assert "json" in graph["chiron"]["external_deps"]

    def test_analyze_dependencies_excludes_patterns(self, tmp_path: Path) -> None:
        """Test that excluded patterns are properly skipped."""
        # Create a file in excluded directory
        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        chiron_in_venv = venv_dir / "chiron"
        chiron_in_venv.mkdir()
        venv_file = chiron_in_venv / "test.py"
        venv_file.write_text("import os")

        # Create a normal file
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        normal_file = chiron_dir / "test.py"
        normal_file.write_text("import json")

        graph = analyze_dependencies(tmp_path)

        # Should only analyze normal file, not .venv file
        assert "chiron" in graph
        assert graph["chiron"]["file_count"] == 1

    def test_analyze_dependencies_multiple_files(self, tmp_path: Path) -> None:
        """Test analyzing multiple files in a module."""
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()

        file1 = chiron_dir / "file1.py"
        file1.write_text("import os")

        file2 = chiron_dir / "file2.py"
        file2.write_text("import json")

        file3 = chiron_dir / "file3.py"
        file3.write_text("import sys")

        graph = analyze_dependencies(tmp_path)

        assert "chiron" in graph
        assert graph["chiron"]["file_count"] == 3
        assert "os" in graph["chiron"]["external_deps"]
        assert "json" in graph["chiron"]["external_deps"]
        assert "sys" in graph["chiron"]["external_deps"]

    def test_analyze_dependencies_custom_exclude_patterns(
        self, tmp_path: Path
    ) -> None:
        """Test analyzing with custom exclude patterns."""
        # Create test directory
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        chiron_in_tests = test_dir / "chiron"
        chiron_in_tests.mkdir()
        test_file = chiron_in_tests / "test.py"
        test_file.write_text("import os")

        # Create normal directory
        chiron_dir = tmp_path / "chiron"
        chiron_dir.mkdir()
        normal_file = chiron_dir / "main.py"
        normal_file.write_text("import json")

        graph = analyze_dependencies(tmp_path, exclude_patterns=["tests"])

        # Should exclude tests directory
        assert "chiron" in graph
        assert graph["chiron"]["file_count"] == 1
        assert "json" in graph["chiron"]["external_deps"]
        assert "os" not in graph["chiron"]["external_deps"]


class TestGenerateMermaid:
    """Tests for generate_mermaid function."""

    def test_generate_mermaid_empty_graph(self) -> None:
        """Test generating Mermaid diagram from empty graph."""
        graph: dict[str, dict] = {}

        result = generate_mermaid(graph)

        assert "```mermaid" in result
        assert "graph TD" in result
        assert "```" in result

    def test_generate_mermaid_single_module(self) -> None:
        """Test generating Mermaid diagram for single module."""
        graph = {
            "chiron": {
                "internal_deps": [],
                "external_deps": ["os", "json"],
                "file_count": 1,
            }
        }

        result = generate_mermaid(graph)

        assert "chiron[Chiron]" in result
        # No internal deps, so no arrows
        assert "-->" not in result

    def test_generate_mermaid_with_dependencies(self) -> None:
        """Test generating Mermaid diagram with dependencies."""
        graph = {
            "chiron": {
                "internal_deps": ["common"],
                "external_deps": ["os"],
                "file_count": 2,
            },
            "common": {
                "internal_deps": [],
                "external_deps": ["json"],
                "file_count": 1,
            },
        }

        result = generate_mermaid(graph)

        assert "chiron[Chiron]" in result
        assert "common[Common]" in result
        assert "chiron --> common" in result

    def test_generate_mermaid_pipeline_styling(self) -> None:
        """Test that pipeline stages get special styling."""
        graph = {
            "ingestion": {
                "internal_deps": ["common"],
                "external_deps": [],
                "file_count": 1,
            },
            "common": {
                "internal_deps": [],
                "external_deps": [],
                "file_count": 1,
            },
        }

        result = generate_mermaid(graph)

        # Pipeline modules should have special styling
        assert "ingestion[Ingestion]:::pipeline" in result
        # Non-pipeline modules should not
        assert "common[Common]:::" not in result or "common[Common]\n" in result

    def test_generate_mermaid_sorted_output(self) -> None:
        """Test that Mermaid output is sorted."""
        graph = {
            "zebra": {
                "internal_deps": ["apple"],
                "external_deps": [],
                "file_count": 1,
            },
            "apple": {
                "internal_deps": [],
                "external_deps": [],
                "file_count": 1,
            },
            "banana": {
                "internal_deps": [],
                "external_deps": [],
                "file_count": 1,
            },
        }

        result = generate_mermaid(graph)

        # Find positions in output
        apple_pos = result.index("apple")
        banana_pos = result.index("banana")
        zebra_pos = result.index("zebra")

        # Should be in alphabetical order
        assert apple_pos < banana_pos < zebra_pos

    def test_generate_mermaid_multiple_dependencies(self) -> None:
        """Test generating diagram with multiple dependencies."""
        graph = {
            "chiron": {
                "internal_deps": ["common", "api", "observability"],
                "external_deps": [],
                "file_count": 5,
            },
            "common": {"internal_deps": [], "external_deps": [], "file_count": 2},
            "api": {"internal_deps": ["common"], "external_deps": [], "file_count": 3},
            "observability": {
                "internal_deps": [],
                "external_deps": [],
                "file_count": 1,
            },
        }

        result = generate_mermaid(graph)

        # Should have all dependencies
        assert "chiron --> api" in result
        assert "chiron --> common" in result
        assert "chiron --> observability" in result
        assert "api --> common" in result
