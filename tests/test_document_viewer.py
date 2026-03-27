"""Tests for the document retrieval backend (Phase 4A)."""

from unittest.mock import patch

import pytest


@pytest.fixture()
def sessions_dir(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    with patch("visualization.server.SESSIONS_DIR", sd):
        yield sd


def _make_session_with_docs(sessions_dir, sid, lit_review=None, insights=None):
    d = sessions_dir / f"session_{sid}"
    d.mkdir()
    if lit_review:
        (d / "literature_review.md").write_text(lit_review)
    if insights:
        (d / "insights_report.md").write_text(insights)
    return d


def test_get_document_literature_review(sessions_dir):
    _make_session_with_docs(sessions_dir, "doc1", lit_review="# Literature Review\n\nFindings here.")
    from visualization.server import handle_get_document
    result = handle_get_document({"session_id": "doc1", "doc_type": "literature_review"})
    assert result["session_id"] == "doc1"
    assert result["doc_type"] == "literature_review"
    assert result["title"] == "Literature Review"
    assert "Findings here" in result["content"]


def test_get_document_insights(sessions_dir):
    _make_session_with_docs(sessions_dir, "doc2", insights="# Insights\n\nKey insight.")
    from visualization.server import handle_get_document
    result = handle_get_document({"session_id": "doc2", "doc_type": "insights"})
    assert result["doc_type"] == "insights"
    assert "Key insight" in result["content"]


def test_get_document_missing_file(sessions_dir):
    _make_session_with_docs(sessions_dir, "doc3")  # no docs
    from visualization.server import handle_get_document
    result = handle_get_document({"session_id": "doc3", "doc_type": "literature_review"})
    assert "error" in result


def test_get_document_unknown_type(sessions_dir):
    _make_session_with_docs(sessions_dir, "doc4")
    from visualization.server import handle_get_document
    result = handle_get_document({"session_id": "doc4", "doc_type": "nonexistent"})
    assert "error" in result
    assert "Unknown doc_type" in result["error"]


def test_get_document_missing_params():
    from visualization.server import handle_get_document
    result = handle_get_document({})
    assert "error" in result


def test_get_document_all_types(sessions_dir):
    """Verify all supported doc_type values map to correct filenames."""
    d = sessions_dir / "session_all"
    d.mkdir()
    doc_types = {
        "literature_review": "literature_review.md",
        "insights": "insights_report.md",
        "transcript_findings": "transcript_findings.md",
        "transcript_synthesis": "transcript_synthesis.md",
        "changelog_findings": "changelog_findings.md",
        "changelog_synthesis": "changelog_synthesis.md",
    }
    for doc_type, filename in doc_types.items():
        (d / filename).write_text(f"Content for {doc_type}")

    from visualization.server import handle_get_document
    for doc_type in doc_types:
        result = handle_get_document({"session_id": "all", "doc_type": doc_type})
        assert "error" not in result, f"Failed for {doc_type}: {result}"
        assert f"Content for {doc_type}" in result["content"]
