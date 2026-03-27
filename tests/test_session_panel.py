"""Tests for the session listing backend that powers SessionPanel (Phase 3A)."""

import json
from unittest.mock import patch

import pytest


@pytest.fixture()
def sessions_dir(tmp_path):
    """Create a temporary sessions directory and patch the server to use it."""
    sd = tmp_path / "sessions"
    sd.mkdir()
    with patch("visualization.server.SESSIONS_DIR", sd):
        yield sd


def _make_session(sessions_dir, sid, *, question="test q", phase=None, nodes=None, lit_review=False, insights=False):
    """Helper to create a session directory with optional files."""
    d = sessions_dir / f"session_{sid}"
    d.mkdir()
    if nodes is not None:
        graph = {"nodes": [{"id": f"n{i}"} for i in range(nodes)], "edges": []}
        (d / "graph.json").write_text(json.dumps(graph))
    if phase is not None:
        (d / "state.json").write_text(json.dumps({"phase": phase}))
    if question:
        (d / "pending_research.json").write_text(json.dumps({"research_question": question}))
    if lit_review:
        (d / "literature_review.md").write_text("# Review")
    if insights:
        (d / "insights_report.md").write_text("# Insights")
    return d


def test_list_sessions_empty(sessions_dir):
    from visualization.server import _list_sessions
    assert _list_sessions() == []


def test_list_sessions_returns_metadata(sessions_dir):
    _make_session(sessions_dir, "abc123", question="How does X work?", phase="researching", nodes=5)
    from visualization.server import _list_sessions
    result = _list_sessions()
    assert len(result) == 1
    s = result[0]
    assert s["session_id"] == "abc123"
    assert s["question"] == "How does X work?"
    assert s["status"] == "running"
    assert s["phase"] == "researching"
    assert s["node_count"] == 5
    assert s["has_lit_review"] is False
    assert s["has_insights"] is False


def test_list_sessions_status_mapping(sessions_dir):
    _make_session(sessions_dir, "s1", phase="awaiting_user_input")
    _make_session(sessions_dir, "s2", phase="complete")
    _make_session(sessions_dir, "s3", phase="error")
    _make_session(sessions_dir, "s4", phase="socratic_review_1")
    from visualization.server import _list_sessions
    result = {s["session_id"]: s["status"] for s in _list_sessions()}
    assert result["s1"] == "paused"
    assert result["s2"] == "complete"
    assert result["s3"] == "error"
    assert result["s4"] == "running"


def test_list_sessions_documents_detected(sessions_dir):
    _make_session(sessions_dir, "d1", lit_review=True, insights=True)
    from visualization.server import _list_sessions
    s = _list_sessions()[0]
    assert s["has_lit_review"] is True
    assert s["has_insights"] is True


def test_list_sessions_no_state_with_pending(sessions_dir):
    """A session with pending_research.json but no state.json should be 'running'."""
    _make_session(sessions_dir, "r1", phase=None)
    from visualization.server import _list_sessions
    s = _list_sessions()[0]
    assert s["status"] == "running"


def test_list_sessions_skips_non_session_dirs(sessions_dir):
    (sessions_dir / "not_a_session").mkdir()
    (sessions_dir / "README.md").write_text("ignore me")
    _make_session(sessions_dir, "real1")
    from visualization.server import _list_sessions
    result = _list_sessions()
    assert len(result) == 1
    assert result[0]["session_id"] == "real1"


def test_list_sessions_handles_corrupt_json(sessions_dir):
    d = sessions_dir / "session_bad1"
    d.mkdir()
    (d / "graph.json").write_text("{corrupt")
    (d / "state.json").write_text("{also corrupt")
    (d / "pending_research.json").write_text("{nope")
    from visualization.server import _list_sessions
    result = _list_sessions()
    assert len(result) == 1
    s = result[0]
    assert s["node_count"] == 0
    assert s["status"] == "unknown"
    assert s["question"] == ""


def test_handle_list_sessions_wraps_result(sessions_dir):
    _make_session(sessions_dir, "h1", question="test")
    from visualization.server import handle_list_sessions
    result = handle_list_sessions({})
    assert "sessions" in result
    assert len(result["sessions"]) == 1


def test_handle_set_active_session():
    from visualization.server import handle_set_active_session
    result = handle_set_active_session({"session_id": "abc"})
    assert result["ok"] is True
    assert result["session_id"] == "abc"


def test_handle_set_active_session_missing_id():
    from visualization.server import handle_set_active_session
    result = handle_set_active_session({})
    assert "error" in result
