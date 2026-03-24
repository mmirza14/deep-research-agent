"""Tests for cross-session node deduplication (Fix 8)."""

import json

from research_agent.mcp_server import add_node, _load


def _seed(tmp_graph, nodes, edges=None):
    tmp_graph.write_text(json.dumps({"nodes": nodes, "edges": edges or []}))


def test_add_node_exact_duplicate_label(tmp_graph):
    """Exact label match creates corroborates edge instead of new node."""
    existing = [
        {
            "id": "existing123ab",
            "label": "MemGPT: Virtual Context Management",
            "type": "source",
            "description": "MemGPT paper.",
            "confidence": 0.85,
            "provenance": {"session_id": "old", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, existing)

    result = add_node(
        label="MemGPT: Virtual Context Management",
        type="source",
        description="MemGPT virtual context management for LLMs.",
        confidence=0.90,
        session_id="new",
        subagent="researcher-2",
    )

    assert "Near-duplicate" in result
    assert "existing123ab" in result

    graph = _load()
    assert len(graph["nodes"]) == 1  # no new node
    assert len(graph["edges"]) == 1  # corroborates edge added
    assert graph["edges"][0]["relationship"] == "corroborates"
    assert graph["nodes"][0]["confidence"] == 0.90  # 0.85 + 0.05


def test_add_node_near_duplicate(tmp_graph):
    """High similarity (>0.85) creates corroborates edge."""
    existing = [
        {
            "id": "existing123ab",
            "label": "MemGPT Virtual Context Management",
            "type": "concept",
            "description": "MemGPT.",
            "confidence": 0.80,
            "provenance": {"session_id": "old", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, existing)

    result = add_node(
        label="MemGPT: Virtual Context Management",
        type="concept",
        description="MemGPT approach.",
        confidence=0.85,
        session_id="new",
        subagent="researcher-2",
    )

    assert "Near-duplicate" in result
    graph = _load()
    assert len(graph["nodes"]) == 1


def test_add_node_below_threshold(tmp_graph):
    """Low similarity (<0.85) creates a new node."""
    existing = [
        {
            "id": "existing123ab",
            "label": "MemGPT: Virtual Context Management",
            "type": "concept",
            "description": "MemGPT.",
            "confidence": 0.80,
            "provenance": {"session_id": "old", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, existing)

    result = add_node(
        label="OPTIMA: Multi-Agent Token Optimization",
        type="concept",
        description="OPTIMA system.",
        confidence=0.85,
        session_id="new",
        subagent="researcher-2",
    )

    assert "Node added:" in result
    graph = _load()
    assert len(graph["nodes"]) == 2


def test_confidence_boost_capped(tmp_graph):
    """Existing node at 0.93 doesn't exceed 0.95 after boost."""
    existing = [
        {
            "id": "existing123ab",
            "label": "Reflexion paper",
            "type": "source",
            "description": "Reflexion.",
            "confidence": 0.93,
            "provenance": {"session_id": "old", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, existing)

    result = add_node(
        label="Reflexion paper",
        type="source",
        description="Reflexion paper on self-reflection.",
        confidence=0.90,
        session_id="new",
        subagent="researcher-2",
    )

    assert "Near-duplicate" in result
    graph = _load()
    assert graph["nodes"][0]["confidence"] == 0.95  # capped


def test_different_type_no_dedup(tmp_graph):
    """Same label but different type creates new node."""
    existing = [
        {
            "id": "existing123ab",
            "label": "MemGPT",
            "type": "source",
            "description": "MemGPT paper.",
            "confidence": 0.85,
            "provenance": {"session_id": "old", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, existing)

    result = add_node(
        label="MemGPT",
        type="concept",  # different type
        description="The MemGPT concept.",
        confidence=0.80,
        session_id="new",
        subagent="researcher-2",
    )

    assert "Node added:" in result
    graph = _load()
    assert len(graph["nodes"]) == 2
