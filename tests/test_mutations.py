"""Tests for graph mutations (Fix 1 + Fix 4)."""

import json

from research_agent.socratic.changelog import Changelog, ChallengeOutcome
from research_agent.socratic.review import _apply_graph_mutations
from research_agent.graph.store import load_graph, save_graph
from research_agent.graph.schema import Graph


def _seed_graph(tmp_graph, nodes, edges=None):
    """Write nodes (and optional edges) into the temp graph file."""
    data = {"nodes": nodes, "edges": edges or []}
    tmp_graph.write_text(json.dumps(data))


def test_apply_mutations_updates_confidence(tmp_graph, sample_findings):
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "bbb222ccc333",
            "node_label": "XML uses 88% more tokens than TOON",
            "response": "CONCEDE",
            "reasoning": "COI is real.",
            "post_confidence": 0.70,
            "proposed_change": "Add COI caveat about Tensorlake source.",
            "secondary_updates": [],
        },
    ]

    mutations = _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    graph = load_graph()
    node = next(n for n in graph.nodes if n["id"] == "bbb222ccc333")
    assert node["confidence"] == 0.70
    assert "[Socratic revision:" in node["description"]
    assert any(m["node_id"] == "bbb222ccc333" and m["field"] == "confidence" for m in mutations)


def test_apply_mutations_secondary_updates(tmp_graph, sample_findings):
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "bbb222ccc333",
            "node_label": "XML uses 88% more tokens than TOON",
            "response": "CONCEDE",
            "reasoning": "COI is real.",
            "post_confidence": 0.70,
            "proposed_change": "Add COI caveat.",
            "secondary_updates": [
                {"node_id": "aaa111bbb222", "confidence": 0.68},
            ],
        },
    ]

    mutations = _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    graph = load_graph()
    primary = next(n for n in graph.nodes if n["id"] == "bbb222ccc333")
    secondary = next(n for n in graph.nodes if n["id"] == "aaa111bbb222")

    assert primary["confidence"] == 0.70
    assert secondary["confidence"] == 0.68

    # Secondary adjustment recorded in changelog
    sec_outcomes = [o for o in changelog.outcomes if o.outcome == "secondary_adjustment"]
    assert len(sec_outcomes) == 1
    assert sec_outcomes[0].node_id == "aaa111bbb222"


def test_apply_mutations_soft_delete(tmp_graph, sample_findings):
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "ddd444eee555",
            "node_label": "Context editing reduces tokens 84%",
            "response": "CONCEDE",
            "reasoning": "Completely unsourced.",
            "post_confidence": 0.10,
            "proposed_change": "Remove until sourced.",
            "secondary_updates": [],
        },
    ]

    _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    graph = load_graph()
    node = next(n for n in graph.nodes if n["id"] == "ddd444eee555")
    assert node.get("withdrawn") is True
    assert node["confidence"] == 0.10

    removed_outcomes = [o for o in changelog.outcomes if o.outcome == "removed"]
    assert len(removed_outcomes) == 1


def test_apply_mutations_defend_no_change(tmp_graph, sample_findings):
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "eee555fff666",
            "node_label": "MemGPT",
            "response": "DEFEND",
            "reasoning": "Well-sourced.",
            "post_confidence": 0.92,
            "proposed_change": "",
            "secondary_updates": [],
        },
    ]

    mutations = _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    graph = load_graph()
    node = next(n for n in graph.nodes if n["id"] == "eee555fff666")
    assert node["confidence"] == 0.92
    # DEFEND produces no mutations
    assert len(mutations) == 0

    retained = [o for o in changelog.outcomes if o.outcome == "retained"]
    assert len(retained) == 1


def test_mutation_returns_records(tmp_graph, sample_findings):
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "ccc333ddd444",
            "node_label": "Reflexion",
            "response": "PARTIALLY CONCEDE",
            "reasoning": "50x is extrapolation.",
            "post_confidence": 0.75,
            "proposed_change": "Label as analytical estimate rather than empirical.",
            "secondary_updates": [],
        },
    ]

    mutations = _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    # Should have confidence + description mutations
    conf_mutations = [m for m in mutations if m["field"] == "confidence"]
    desc_mutations = [m for m in mutations if m["field"] == "description"]
    assert len(conf_mutations) == 1
    assert conf_mutations[0]["old"] == 0.90
    assert conf_mutations[0]["new"] == 0.75
    assert len(desc_mutations) == 1


def test_default_penalty_when_no_confidence(tmp_graph, sample_findings):
    """When Defender doesn't provide post_confidence, default -0.2 penalty applies."""
    _seed_graph(tmp_graph, sample_findings)
    changelog = Changelog(session_id="test123", stage="findings")

    outcomes = [
        {
            "node_id": "bbb222ccc333",
            "node_label": "XML tokens",
            "response": "CONCEDE",
            "reasoning": "Valid concern.",
            "post_confidence": None,
            "proposed_change": "",
            "secondary_updates": [],
        },
    ]

    _apply_graph_mutations(outcomes, changelog, sample_findings, round_number=1)

    graph = load_graph()
    node = next(n for n in graph.nodes if n["id"] == "bbb222ccc333")
    assert node["confidence"] == 0.87 - 0.2  # 0.67
