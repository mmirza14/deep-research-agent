"""Tests for claim validation and COI detection (Fix 3 + Fix 7)."""

import json

from research_agent.validation import validate_session_claims, detect_coi
from research_agent.graph.store import load_graph


def _seed(tmp_graph, nodes, edges=None):
    tmp_graph.write_text(json.dumps({"nodes": nodes, "edges": edges or []}))


def test_validate_claims_flags_unsourced_quantitative(tmp_graph):
    nodes = [
        {
            "id": "claim_no_src",
            "label": "84% reduction claim",
            "type": "claim",
            "description": "Context editing reduces tokens by 84% in 100-turn dialogues.",
            "confidence": 0.83,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, nodes)

    result = validate_session_claims("s1")
    assert "flagged 1" in result

    graph = load_graph()
    node = graph.nodes[0]
    assert node["metadata"]["needs_source"] is True
    assert node["confidence"] == 0.50


def test_validate_claims_ignores_sourced(tmp_graph):
    nodes = [
        {
            "id": "claim_sourced",
            "label": "Token reduction claim",
            "type": "claim",
            "description": "Achieves 68.64% output reduction with less than 5% accuracy loss.",
            "confidence": 0.88,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
        {
            "id": "source_tale",
            "label": "TALE paper",
            "type": "source",
            "description": "TALE: Training-free token budget allocation.",
            "confidence": 0.90,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {"url": "https://arxiv.org/abs/2412.18547"},
        },
    ]
    edges = [
        {
            "id": "edge1",
            "source": "claim_sourced",
            "target": "source_tale",
            "relationship": "cites",
            "weight": 1.0,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
        },
    ]
    _seed(tmp_graph, nodes, edges)

    result = validate_session_claims("s1")
    assert result == ""

    graph = load_graph()
    claim = next(n for n in graph.nodes if n["id"] == "claim_sourced")
    assert claim["confidence"] == 0.88  # unchanged


def test_validate_claims_ignores_non_quantitative(tmp_graph):
    nodes = [
        {
            "id": "claim_qual",
            "label": "Stateful agents need context",
            "type": "claim",
            "description": "Stateful agents incur additional overhead for state reconciliation.",
            "confidence": 0.82,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    _seed(tmp_graph, nodes)

    result = validate_session_claims("s1")
    assert result == ""


def test_coi_detection_flags_vendor_claim(tmp_graph):
    nodes = [
        {
            "id": "src_tensorlake",
            "label": "Tensorlake TOON Benchmark",
            "type": "source",
            "description": "Benchmark by Tensorlake.",
            "confidence": 0.85,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {"url": "https://tensorlake.ai/blog/toon", "domain": "tensorlake.ai"},
        },
        {
            "id": "claim_toon",
            "label": "TOON outperforms JSON",
            "type": "claim",
            "description": "Tensorlake's TOON format uses 40% fewer tokens than JSON.",
            "confidence": 0.85,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    edges = [
        {
            "id": "e1",
            "source": "claim_toon",
            "target": "src_tensorlake",
            "relationship": "cites",
            "weight": 1.0,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
        },
    ]
    _seed(tmp_graph, nodes, edges)

    result = detect_coi("s1")
    assert "flagged 1" in result

    graph = load_graph()
    claim = next(n for n in graph.nodes if n["id"] == "claim_toon")
    assert claim["metadata"]["potential_coi"] is True
    assert claim["confidence"] == 0.75  # 0.85 - 0.10


def test_coi_detection_no_false_positive(tmp_graph):
    nodes = [
        {
            "id": "src_arxiv",
            "label": "MemGPT paper",
            "type": "source",
            "description": "MemGPT virtual context management.",
            "confidence": 0.92,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {"url": "https://arxiv.org/abs/2310.08560", "domain": "arxiv.org"},
        },
        {
            "id": "claim_memgpt",
            "label": "Virtual context management improves efficiency",
            "type": "claim",
            "description": "MemGPT's approach achieves better context utilization.",
            "confidence": 0.88,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
    ]
    edges = [
        {
            "id": "e1",
            "source": "claim_memgpt",
            "target": "src_arxiv",
            "relationship": "cites",
            "weight": 1.0,
            "provenance": {"session_id": "s1", "subagent": "researcher-1", "mode": "survey"},
        },
    ]
    _seed(tmp_graph, nodes, edges)

    result = detect_coi("s1")
    assert result == ""

    graph = load_graph()
    claim = next(n for n in graph.nodes if n["id"] == "claim_memgpt")
    assert claim.get("metadata", {}).get("potential_coi") is None
    assert claim["confidence"] == 0.88
