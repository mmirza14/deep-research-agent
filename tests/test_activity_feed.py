"""Tests for the activity feed graph diffing logic (Phase 2A)."""

from visualization.server import _diff_graph_activities, _last_graph_nodes


def _reset_diff_state():
    """Reset the global diff baseline."""
    _last_graph_nodes.clear()


def _make_graph(nodes):
    """Build a graph dict from a list of node dicts."""
    return {"nodes": nodes, "edges": []}


def _node(nid, ntype="concept", label="Test", confidence=None, flagged=False, withdrawn=False, session_id="s1"):
    n = {
        "id": nid,
        "type": ntype,
        "label": label,
        "provenance": {"session_id": session_id, "timestamp": "2026-03-26T12:00:00Z"},
    }
    if confidence is not None:
        n["confidence"] = confidence
    if flagged:
        n["flagged"] = True
    if withdrawn:
        n["withdrawn"] = True
    return n


def test_new_nodes_generate_activities():
    _reset_diff_state()
    graph = _make_graph([_node("n1", "concept", "Attention"), _node("n2", "source", "Paper A")])
    activities = _diff_graph_activities(graph)
    assert len(activities) == 2
    assert activities[0]["action"] == "discovered concept"
    assert activities[0]["detail"] == "Attention"
    assert activities[0]["node_id"] == "n1"
    assert activities[1]["action"] == "added source"
    assert activities[1]["detail"] == "Paper A"


def test_no_change_no_activities():
    _reset_diff_state()
    graph = _make_graph([_node("n1")])
    _diff_graph_activities(graph)  # baseline
    activities = _diff_graph_activities(graph)  # same graph
    assert len(activities) == 0


def test_confidence_change_generates_activity():
    _reset_diff_state()
    graph1 = _make_graph([_node("n1", confidence=0.8)])
    _diff_graph_activities(graph1)  # baseline
    graph2 = _make_graph([_node("n1", confidence=0.6)])
    activities = _diff_graph_activities(graph2)
    assert len(activities) == 1
    assert activities[0]["action"] == "confidence lowered"
    assert "0.80" in activities[0]["detail"]
    assert "0.60" in activities[0]["detail"]


def test_confidence_raise_generates_activity():
    _reset_diff_state()
    graph1 = _make_graph([_node("n1", confidence=0.5)])
    _diff_graph_activities(graph1)
    graph2 = _make_graph([_node("n1", confidence=0.9)])
    activities = _diff_graph_activities(graph2)
    assert len(activities) == 1
    assert activities[0]["action"] == "confidence raised"


def test_flag_generates_activity():
    _reset_diff_state()
    graph1 = _make_graph([_node("n1")])
    _diff_graph_activities(graph1)
    graph2 = _make_graph([_node("n1", flagged=True)])
    activities = _diff_graph_activities(graph2)
    assert len(activities) == 1
    assert activities[0]["action"] == "flagged"


def test_withdraw_generates_activity():
    _reset_diff_state()
    graph1 = _make_graph([_node("n1")])
    _diff_graph_activities(graph1)
    graph2 = _make_graph([_node("n1", withdrawn=True)])
    activities = _diff_graph_activities(graph2)
    assert len(activities) == 1
    assert activities[0]["action"] == "withdrawn"


def test_all_node_types_have_labels():
    _reset_diff_state()
    types = ["concept", "claim", "source", "question", "direction", "decision"]
    nodes = [_node(f"n{i}", t, f"Label-{t}") for i, t in enumerate(types)]
    activities = _diff_graph_activities(_make_graph(nodes))
    assert len(activities) == 6
    actions = [a["action"] for a in activities]
    assert "discovered concept" in actions
    assert "added claim" in actions
    assert "added source" in actions
    assert "raised question" in actions
    assert "proposed direction" in actions
    assert "recorded decision" in actions


def test_mixed_new_and_modified():
    _reset_diff_state()
    graph1 = _make_graph([_node("n1", confidence=0.7)])
    _diff_graph_activities(graph1)
    graph2 = _make_graph([_node("n1", confidence=0.5), _node("n2", "claim", "New claim")])
    activities = _diff_graph_activities(graph2)
    assert len(activities) == 2
    actions = {a["action"] for a in activities}
    assert "confidence lowered" in actions
    assert "added claim" in actions


def test_session_id_propagated():
    _reset_diff_state()
    graph = _make_graph([_node("n1", session_id="abc123")])
    activities = _diff_graph_activities(graph)
    assert activities[0]["session_id"] == "abc123"
