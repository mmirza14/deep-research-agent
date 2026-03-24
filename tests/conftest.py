"""Shared fixtures for deep-research agent tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_graph(tmp_path):
    """Create a temporary graph.json and patch GRAPH_PATH everywhere."""
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "edges": []}))

    # Patch the config constant AND every module that imports it at top level
    patches = [
        patch("research_agent.config.GRAPH_PATH", graph_path),
        patch("research_agent.graph.store.GRAPH_PATH", graph_path),
        patch("research_agent.mcp_server.GRAPH_PATH", graph_path),
    ]
    for p in patches:
        p.start()

    # Also patch the default parameter on load_graph/save_graph
    import research_agent.graph.store as _store
    _orig_load = _store.load_graph.__wrapped__ if hasattr(_store.load_graph, '__wrapped__') else None
    _store.load_graph.__defaults__ = (graph_path,)
    _store.save_graph.__defaults__ = (graph_path,)

    yield graph_path

    # Restore defaults
    from research_agent.config import GRAPH_PATH as _orig_path
    _store.load_graph.__defaults__ = (_orig_path,)
    _store.save_graph.__defaults__ = (_orig_path,)
    for p in patches:
        p.stop()


@pytest.fixture()
def sample_findings():
    """Return a list of realistic node dicts for testing."""
    return [
        {
            "id": "aaa111bbb222",
            "label": "TOON vs JSON Token Format Benchmark",
            "type": "source",
            "description": "Tensorlake benchmark comparing TOON format against JSON, XML, YAML.",
            "confidence": 0.85,
            "provenance": {"session_id": "test123", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {"url": "https://tensorlake.ai/blog/toon-benchmark", "source_type": "blog", "domain": "tensorlake.ai"},
        },
        {
            "id": "bbb222ccc333",
            "label": "XML uses 88% more tokens than TOON",
            "type": "claim",
            "description": "XML encoding uses 5167 tokens vs TOON's 2744 — 88% overhead.",
            "confidence": 0.87,
            "provenance": {"session_id": "test123", "subagent": "researcher-1", "mode": "survey"},
            "metadata": {},
        },
        {
            "id": "ccc333ddd444",
            "label": "Reflexion loops multiply token cost",
            "type": "claim",
            "description": "A 10-cycle Reflexion loop can consume 50x the tokens of a single pass.",
            "confidence": 0.90,
            "provenance": {"session_id": "test123", "subagent": "researcher-2", "mode": "survey"},
            "metadata": {},
        },
        {
            "id": "ddd444eee555",
            "label": "Context editing reduces tokens 84%",
            "type": "claim",
            "description": "Context editing reduces token consumption by 84% in 100-turn dialogues.",
            "confidence": 0.83,
            "provenance": {"session_id": "test123", "subagent": "researcher-2", "mode": "survey"},
            "metadata": {},
        },
        {
            "id": "eee555fff666",
            "label": "MemGPT: Virtual Context Management",
            "type": "source",
            "description": "MemGPT implements virtual context management for LLMs.",
            "confidence": 0.92,
            "provenance": {"session_id": "test123", "subagent": "researcher-3", "mode": "survey"},
            "metadata": {"url": "https://arxiv.org/abs/2310.08560", "source_type": "academic"},
        },
    ]


@pytest.fixture()
def sample_defender_json():
    """A Defender response with a valid JSON block."""
    return """### CHALLENGE 1 — TOON Benchmark

- **Node:** [bbb222ccc333] XML uses 88% more tokens than TOON
- **Response:** PARTIALLY CONCEDE
- **Reasoning:** The COI is real. Token counts are mechanically verifiable but accuracy claims are not.
- **Post-challenge confidence:** 0.70
- **Proposed change:** Add COI caveat about Tensorlake.

---

### CHALLENGE 2 — Reflexion 50x

- **Node:** [ccc333ddd444] Reflexion loops multiply token cost
- **Response:** CONCEDE
- **Reasoning:** The 50x figure is an analytical extrapolation, not empirical.
- **Post-challenge confidence:** 0.75
- **Proposed change:** Label as analytical worst-case estimate.

```json
[
  {
    "node_id": "bbb222ccc333",
    "response": "PARTIALLY CONCEDE",
    "confidence": 0.70,
    "change_description": "Add COI caveat about Tensorlake.",
    "secondary_updates": [
      {"node_id": "aaa111bbb222", "confidence": 0.68}
    ]
  },
  {
    "node_id": "ccc333ddd444",
    "response": "CONCEDE",
    "confidence": 0.75,
    "change_description": "Label 50x as analytical worst-case estimate.",
    "secondary_updates": []
  }
]
```"""


@pytest.fixture()
def sample_defender_markdown():
    """A Defender response with markdown only (no JSON block)."""
    return """### CHALLENGE 1

- **Node:** [ddd444eee555] Context editing reduces tokens 84%
- **Response:** CONCEDE
- **Reasoning:** No source for the 84% figure.
- **Post-challenge confidence:** 0.55
- **Proposed change:** Reframe as illustrative estimate requiring source attribution.

---

### CHALLENGE 2

- **Node:** [eee555fff666] MemGPT: Virtual Context Management
- **Response:** DEFEND
- **Reasoning:** Well-sourced academic paper with independent citations.
- **Post-challenge confidence:** 0.92
- **Proposed change:** None needed.
"""
