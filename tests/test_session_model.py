"""Tests for Phase 0: per-session graph model, migration, and workspace."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from research_agent.config import session_graph_path
from research_agent.graph.store import (
    load_graph,
    save_graph,
    load_session_graph,
    save_session_graph,
    load_workspace,
)


@pytest.fixture()
def sessions_dir(tmp_path):
    """Create a temp sessions directory and patch config."""
    sd = tmp_path / "sessions"
    sd.mkdir()
    with patch("research_agent.config.SESSIONS_DIR", sd):
        yield sd


# ---------------------------------------------------------------------------
# session_graph_path
# ---------------------------------------------------------------------------

def test_session_graph_path(sessions_dir):
    p = session_graph_path("abc123")
    assert p == sessions_dir / "session_abc123" / "graph.json"


# ---------------------------------------------------------------------------
# load_session_graph / save_session_graph
# ---------------------------------------------------------------------------

def test_save_and_load_session_graph(sessions_dir):
    from research_agent.graph.schema import Graph

    g = Graph(
        nodes=[{"id": "n1", "label": "Test", "type": "concept"}],
        edges=[],
    )
    save_session_graph(g, "s1")

    loaded = load_session_graph("s1")
    assert len(loaded.nodes) == 1
    assert loaded.nodes[0]["id"] == "n1"


def test_load_session_graph_missing_returns_empty(sessions_dir):
    g = load_session_graph("nonexistent")
    assert g.nodes == []
    assert g.edges == []


# ---------------------------------------------------------------------------
# load_workspace
# ---------------------------------------------------------------------------

def test_load_workspace_merges_sessions(sessions_dir):
    from research_agent.graph.schema import Graph

    # Session A
    ga = Graph(
        nodes=[{"id": "a1", "label": "Node A", "type": "concept"}],
        edges=[{"id": "ea1", "source": "a1", "target": "a1", "relationship": "related_to"}],
    )
    save_session_graph(ga, "sa")

    # Session B
    gb = Graph(
        nodes=[{"id": "b1", "label": "Node B", "type": "claim"}],
        edges=[{"id": "eb1", "source": "b1", "target": "b1", "relationship": "supports"}],
    )
    save_session_graph(gb, "sb")

    merged = load_workspace(["sa", "sb"])
    assert len(merged.nodes) == 2
    assert len(merged.edges) == 2
    ids = {n["id"] for n in merged.nodes}
    assert ids == {"a1", "b1"}


def test_load_workspace_deduplicates_by_id(sessions_dir):
    from research_agent.graph.schema import Graph

    # Same node in both sessions
    node = {"id": "shared1", "label": "Shared", "type": "concept"}
    ga = Graph(nodes=[node], edges=[])
    gb = Graph(nodes=[{**node, "label": "Shared (copy)"}], edges=[])
    save_session_graph(ga, "sa")
    save_session_graph(gb, "sb")

    merged = load_workspace(["sa", "sb"])
    assert len(merged.nodes) == 1
    # First session's version wins (canonical)
    assert merged.nodes[0]["label"] == "Shared"


def test_load_workspace_skips_missing_sessions(sessions_dir):
    from research_agent.graph.schema import Graph

    ga = Graph(nodes=[{"id": "a1", "label": "A", "type": "concept"}], edges=[])
    save_session_graph(ga, "sa")

    merged = load_workspace(["sa", "nonexistent"])
    assert len(merged.nodes) == 1


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def test_migrate_global_graph(tmp_path):
    """Global graph.json splits into per-session graphs by provenance."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sessions_dir = data_dir / "sessions"
    graph_path = data_dir / "graph.json"

    # Create a global graph with nodes from two sessions
    graph_data = {
        "nodes": [
            {
                "id": "n1", "label": "Node 1", "type": "concept",
                "provenance": {"session_id": "s1", "subagent": "r1"},
            },
            {
                "id": "n2", "label": "Node 2", "type": "claim",
                "provenance": {"session_id": "s1", "subagent": "r2"},
            },
            {
                "id": "n3", "label": "Node 3", "type": "source",
                "provenance": {"session_id": "s2", "subagent": "r1"},
            },
        ],
        "edges": [
            {
                "id": "e1", "source": "n1", "target": "n2",
                "relationship": "supports",
            },
            {
                "id": "e2", "source": "n3", "target": "n3",
                "relationship": "related_to",
            },
        ],
    }
    graph_path.write_text(json.dumps(graph_data))

    # Import and run migration with patched paths
    from visualization.server import _migrate_global_graph
    with (
        patch("visualization.server.GRAPH_PATH", graph_path),
        patch("visualization.server.SESSIONS_DIR", sessions_dir),
        patch("visualization.server.DATA_DIR", data_dir),
    ):
        _migrate_global_graph()

    # Global graph should be moved to legacy
    assert not graph_path.exists()
    assert (data_dir / "graph_legacy.json").exists()

    # Session s1 should have 2 nodes and 1 edge (n1→n2)
    s1_graph = json.loads((sessions_dir / "session_s1" / "graph.json").read_text())
    assert len(s1_graph["nodes"]) == 2
    assert len(s1_graph["edges"]) == 1
    assert s1_graph["edges"][0]["id"] == "e1"

    # Session s2 should have 1 node and 1 edge
    s2_graph = json.loads((sessions_dir / "session_s2" / "graph.json").read_text())
    assert len(s2_graph["nodes"]) == 1
    assert len(s2_graph["edges"]) == 1


def test_migrate_skips_if_sessions_exist(tmp_path):
    """Migration is a no-op if sessions directory already has content."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sessions_dir = data_dir / "sessions"
    sessions_dir.mkdir()
    (sessions_dir / "session_existing").mkdir()

    graph_path = data_dir / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [{"id": "x", "provenance": {"session_id": "old"}}], "edges": []}))

    from visualization.server import _migrate_global_graph
    with (
        patch("visualization.server.GRAPH_PATH", graph_path),
        patch("visualization.server.SESSIONS_DIR", sessions_dir),
        patch("visualization.server.DATA_DIR", data_dir),
    ):
        _migrate_global_graph()

    # Global graph should NOT be moved
    assert graph_path.exists()


def test_migrate_skips_if_no_global_graph(tmp_path):
    """Migration is a no-op if there's no global graph.json."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    graph_path = data_dir / "graph.json"  # doesn't exist

    from visualization.server import _migrate_global_graph
    with (
        patch("visualization.server.GRAPH_PATH", graph_path),
        patch("visualization.server.SESSIONS_DIR", data_dir / "sessions"),
        patch("visualization.server.DATA_DIR", data_dir),
    ):
        _migrate_global_graph()
    # No crash, no files created
    assert not (data_dir / "sessions").exists()
