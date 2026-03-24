"""Tests for transcript dedup and mutation summary formatting (Fix 5)."""

from research_agent.socratic.transcript import Transcript


def test_transcript_dedup_consecutive_same_content():
    """Same role + same content = deduplicated."""
    t = Transcript(session_id="t1", stage="findings")
    t.add_entry(1, "critic", "Challenge: the source is unreliable.")
    t.add_entry(1, "critic", "Challenge: the source is unreliable.")  # duplicate

    assert len(t.entries) == 1


def test_transcript_no_dedup_different_roles():
    """Same content but different roles = kept."""
    t = Transcript(session_id="t1", stage="findings")
    t.add_entry(1, "critic", "The source is unreliable.")
    t.add_entry(1, "defender", "The source is unreliable.")  # different role

    assert len(t.entries) == 2


def test_transcript_no_dedup_different_content():
    """Different content = kept."""
    t = Transcript(session_id="t1", stage="findings")
    t.add_entry(1, "critic", "Challenge 1: source credibility.")
    t.add_entry(1, "critic", "Challenge 2: confidence calibration.")

    assert len(t.entries) == 2


def test_transcript_markdown_output():
    """Markdown rendering includes round headers."""
    t = Transcript(session_id="t1", stage="findings")
    t.add_entry(1, "critic", "Challenge text.")
    t.add_entry(1, "defender", "Defense text.")

    md = t.to_markdown()
    assert "## Round 1 — Critic" in md
    assert "## Round 1 — Defender" in md
    assert "Challenge text." in md
    assert "Defense text." in md
