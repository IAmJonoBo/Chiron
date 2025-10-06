import json
import sys
from pathlib import Path

import pytest

from chiron.deps import graph
from chiron.deps.graph import (
    analyze_dependencies,
    detect_cycles,
    generate_mermaid,
    parse_imports,
)


def test_parse_imports_filters_relative_and_self(tmp_path: Path) -> None:
    repo_root = tmp_path
    module_dir = repo_root / "ingestion"
    module_dir.mkdir()
    file_path = module_dir / "sample.py"
    file_path.write_text(
        "import os\n"
        "import retrieval.pipeline as pipeline\n"
        "from execution.runner import run\n"
        "from ingestion.utils import helper\n"
        "from .local import value\n"
    )

    imports = parse_imports(file_path, repo_root)

    assert set(imports) == {"os", "retrieval", "execution"}


def test_parse_imports_handles_src_namespace(tmp_path: Path) -> None:
    repo_root = tmp_path
    chiron_root = repo_root / "src" / "chiron"
    deps_dir = chiron_root / "deps"
    obs_dir = chiron_root / "observability"
    service_dir = chiron_root / "service"

    (chiron_root).mkdir(parents=True)
    deps_dir.mkdir()
    obs_dir.mkdir()
    service_dir.mkdir()

    (deps_dir / "__init__.py").write_text("\n")
    (obs_dir / "__init__.py").write_text("\n")
    (service_dir / "__init__.py").write_text("\n")

    file_path = deps_dir / "alpha.py"
    file_path.write_text(
        "import chiron.observability.metrics\n"
        "from chiron.service.routes import router\n"
        "from chiron.deps import guard\n"
        "import json\n"
    )

    imports = parse_imports(file_path, repo_root)

    assert imports == ["chiron.observability", "chiron.service", "json"]


def test_analyze_dependencies_builds_internal_and_external_edges(tmp_path: Path) -> None:
    repo_root = tmp_path
    (repo_root / "ingestion").mkdir()
    (repo_root / "retrieval").mkdir()
    (repo_root / "scripts").mkdir()

    (repo_root / "ingestion" / "alpha.py").write_text(
        "import retrieval.handlers\nfrom execution.core import run\n"
    )
    (repo_root / "retrieval" / "beta.py").write_text(
        "import json\nfrom observability.metrics import trace\n"
    )
    (repo_root / "scripts" / "gamma.py").write_text(
        "from ingestion import alpha\n"
    )
    (repo_root / "vendor").mkdir()
    (repo_root / "vendor" / "ignored.py").write_text("import os\n")

    graph_data = analyze_dependencies(repo_root)

    assert graph_data["ingestion"]["internal_deps"] == ["execution", "retrieval"]
    assert graph_data["ingestion"]["external_deps"] == []
    assert graph_data["ingestion"]["file_count"] == 1

    assert graph_data["retrieval"]["internal_deps"] == ["observability"]
    assert graph_data["retrieval"]["external_deps"] == ["json"]
    assert graph_data["retrieval"]["file_count"] == 1

    assert graph_data["scripts"]["internal_deps"] == ["ingestion"]
    assert graph_data["scripts"]["external_deps"] == []
    assert graph_data["scripts"]["file_count"] == 1


def test_analyze_dependencies_handles_src_layout(tmp_path: Path) -> None:
    repo_root = tmp_path
    chiron_root = repo_root / "src" / "chiron"
    deps_dir = chiron_root / "deps"
    obs_dir = chiron_root / "observability"

    deps_dir.mkdir(parents=True)
    obs_dir.mkdir(parents=True)

    (chiron_root / "__init__.py").write_text("\n")
    (deps_dir / "__init__.py").write_text("\n")
    (obs_dir / "__init__.py").write_text("\n")

    (deps_dir / "graph.py").write_text(
        "import json\nfrom chiron.observability import metrics\n"
    )
    (obs_dir / "metrics.py").write_text("import logging\n")

    graph_data = analyze_dependencies(repo_root)

    assert graph_data["chiron.deps"]["internal_deps"] == ["chiron.observability"]
    assert graph_data["chiron.deps"]["external_deps"] == ["json"]
    assert graph_data["chiron.deps"]["file_count"] == 2

    assert graph_data["chiron.observability"]["external_deps"] == ["logging"]
    assert graph_data["chiron.observability"]["file_count"] == 2


def test_generate_mermaid_and_detect_cycles() -> None:
    sample_graph = {
        "ingestion": {"internal_deps": ["retrieval"], "external_deps": ["os"], "file_count": 2},
        "retrieval": {"internal_deps": ["ingestion"], "external_deps": [], "file_count": 1},
    }

    mermaid = generate_mermaid(sample_graph)

    assert "```mermaid" in mermaid
    assert "ingestion --> retrieval" in mermaid

    cycles = detect_cycles(sample_graph)

    assert ["ingestion", "retrieval", "ingestion"] in cycles


def test_graph_main_writes_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_path = tmp_path / "graph.json"

    monkeypatch.setattr(
        graph,
        "analyze_dependencies",
        lambda repo_root, exclude_patterns=None: {
            "ingestion": {
                "internal_deps": ["retrieval"],
                "external_deps": ["os"],
                "file_count": 3,
            }
        },
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deps-graph",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_path),
            "--format",
            "json",
        ],
    )

    exit_code = graph.main()

    assert exit_code == 0
    content = json.loads(output_path.read_text())
    assert content["ingestion"]["file_count"] == 3
    assert content["ingestion"]["external_deps"] == ["os"]


def test_graph_main_cycle_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    output_path = tmp_path / "graph.md"

    monkeypatch.setattr(
        graph,
        "analyze_dependencies",
        lambda repo_root, exclude_patterns=None: {
            "ingestion": {"internal_deps": ["retrieval"], "external_deps": [], "file_count": 1},
            "retrieval": {"internal_deps": ["ingestion"], "external_deps": [], "file_count": 1},
        },
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "deps-graph",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(output_path),
            "--check-cycles",
        ],
    )

    exit_code = graph.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "ERROR: Found" in captured.err
    assert not output_path.exists()
