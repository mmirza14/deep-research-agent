"""Tests for Defender response parsing (Fix 1 + Fix 2)."""

from research_agent.socratic.review import (
    _parse_defender_json,
    _parse_defender_response,
)


def test_parse_defender_json_valid(sample_findings, sample_defender_json):
    """JSON block is parsed correctly with secondary updates."""
    outcomes = _parse_defender_json(sample_defender_json, sample_findings)
    assert outcomes is not None
    assert len(outcomes) == 2

    # First outcome
    assert outcomes[0]["node_id"] == "bbb222ccc333"
    assert outcomes[0]["response"] == "PARTIALLY CONCEDE"
    assert outcomes[0]["post_confidence"] == 0.70
    assert len(outcomes[0]["secondary_updates"]) == 1
    assert outcomes[0]["secondary_updates"][0]["node_id"] == "aaa111bbb222"
    assert outcomes[0]["secondary_updates"][0]["confidence"] == 0.68

    # Second outcome
    assert outcomes[1]["node_id"] == "ccc333ddd444"
    assert outcomes[1]["response"] == "CONCEDE"
    assert outcomes[1]["post_confidence"] == 0.75
    assert outcomes[1]["secondary_updates"] == []


def test_parse_defender_json_missing_falls_back(sample_findings, sample_defender_markdown):
    """No JSON block returns None, triggering regex fallback."""
    result = _parse_defender_json(sample_defender_markdown, sample_findings)
    assert result is None


def test_parse_defender_json_malformed_falls_back(sample_findings):
    """Malformed JSON block returns None."""
    text = '```json\n[{"broken": true, missing_quote}]\n```'
    result = _parse_defender_json(text, sample_findings)
    assert result is None


def test_parse_defender_response_uses_json_first(sample_findings, sample_defender_json):
    """When JSON block exists, _parse_defender_response uses it."""
    outcomes = _parse_defender_response(sample_defender_json, sample_findings)
    assert len(outcomes) == 2
    # Should have secondary_updates (only present from JSON path)
    assert "secondary_updates" in outcomes[0]
    assert len(outcomes[0]["secondary_updates"]) == 1


def test_parse_defender_response_regex_fallback(sample_findings, sample_defender_markdown):
    """When no JSON block, regex parsing works."""
    outcomes = _parse_defender_response(sample_defender_markdown, sample_findings)
    assert len(outcomes) == 2

    concede = [o for o in outcomes if o["response"] == "CONCEDE"][0]
    assert concede["node_id"] == "ddd444eee555"
    assert concede["post_confidence"] == 0.55

    defend = [o for o in outcomes if o["response"] == "DEFEND"][0]
    assert defend["node_id"] == "eee555fff666"
    assert defend["post_confidence"] == 0.92


def test_parse_all_response_types(sample_findings):
    """DEFEND, CONCEDE, and PARTIALLY CONCEDE are all recognized."""
    text = """```json
[
  {"node_id": "aaa111bbb222", "response": "DEFEND", "confidence": 0.85, "change_description": "", "secondary_updates": []},
  {"node_id": "bbb222ccc333", "response": "CONCEDE", "confidence": 0.50, "change_description": "Lower conf.", "secondary_updates": []},
  {"node_id": "ccc333ddd444", "response": "PARTIALLY CONCEDE", "confidence": 0.75, "change_description": "Add caveat.", "secondary_updates": []}
]
```"""
    outcomes = _parse_defender_response(text, sample_findings)
    responses = {o["response"] for o in outcomes}
    assert responses == {"DEFEND", "CONCEDE", "PARTIALLY CONCEDE"}


def test_parse_dedup_keeps_last(sample_findings):
    """When same node_id appears twice in regex mode, last occurrence wins."""
    text = """### Challenge 1

- **Node:** [bbb222ccc333] XML tokens
- **Response:** DEFEND
- **Reasoning:** First pass defense.
- **Post-challenge confidence:** 0.87

---

### Challenge 1 revised

- **Node:** [bbb222ccc333] XML tokens
- **Response:** CONCEDE
- **Reasoning:** Actually, the Critic is right.
- **Post-challenge confidence:** 0.60
- **Proposed change:** Add caveat.
"""
    outcomes = _parse_defender_response(text, sample_findings)
    # Only one outcome for this node_id
    assert len(outcomes) == 1
    assert outcomes[0]["response"] == "CONCEDE"
    assert outcomes[0]["post_confidence"] == 0.60
