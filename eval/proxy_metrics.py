#!/usr/bin/env python3
"""Proxy metrics for evaluating context quality improvements.

Computes quantitative metrics from a session's artifacts (graph, changelogs,
transcripts) that serve as proxies for output quality. Run after each research
session to track improvement over time.

Usage:
    python eval/proxy_metrics.py <session_id>
    python eval/proxy_metrics.py 5f9219ae

Output: prints a JSON metrics object and appends to eval/metrics_log.jsonl.
"""

import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "graph.json"
SESSIONS_DIR = DATA_DIR / "sessions"
METRICS_LOG = PROJECT_ROOT / "eval" / "metrics_log.jsonl"


def load_graph() -> dict:
    return json.loads(GRAPH_PATH.read_text())


def load_changelog(session_id: str, stage: str) -> dict | None:
    path = SESSIONS_DIR / f"session_{session_id}" / f"changelog_{stage}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_transcript(session_id: str, stage: str) -> str:
    path = SESSIONS_DIR / f"session_{session_id}" / f"transcript_{stage}.md"
    if not path.exists():
        return ""
    return path.read_text()


# ---------------------------------------------------------------------------
# Metric 1: Truncation coverage delta
# ---------------------------------------------------------------------------

def truncation_coverage(graph: dict, session_id: str) -> dict:
    """How many of the relevance-ranked top-30 were in the positional top-30?"""
    from research_agent.graph.schema import Graph
    from research_agent.socratic.review import load_socratic_scores
    from research_agent.report_writer import _score_finding

    g = Graph(nodes=graph["nodes"], edges=graph["edges"])
    findings = [
        n for n in graph["nodes"]
        if n.get("provenance", {}).get("session_id") == session_id
        and n.get("provenance", {}).get("subagent", "").startswith("researcher")
        and not n.get("withdrawn", False)
    ]

    if len(findings) <= 30:
        return {"total_findings": len(findings), "overlap_pct": 100.0, "promoted": 0, "demoted": 0}

    socratic_scores = load_socratic_scores(session_id)
    scored = []
    for n in findings:
        degree = g.node_degree(n["id"])
        soc = socratic_scores.get(n["id"], 0.7)
        scored.append((_score_finding(n, degree, soc), n["id"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    ranked_top30 = {nid for _, nid in scored[:30]}

    positional_top30 = {n["id"] for n in findings[:30]}
    overlap = ranked_top30 & positional_top30

    return {
        "total_findings": len(findings),
        "overlap_pct": round(len(overlap) / 30 * 100, 1),
        "promoted": len(ranked_top30 - positional_top30),
        "demoted": len(positional_top30 - ranked_top30),
    }


# ---------------------------------------------------------------------------
# Metric 2: Critic tool usage
# ---------------------------------------------------------------------------

def critic_tool_usage(session_id: str) -> dict:
    """Count MCP tool calls in Critic transcript entries."""
    transcript = load_transcript(session_id, "findings")
    transcript += "\n" + load_transcript(session_id, "synthesis")

    # Count tool call patterns — either in markdown code blocks or prose references
    get_neighborhood = len(re.findall(r"get_neighborhood", transcript))
    query_graph = len(re.findall(r"query_graph", transcript))
    get_graph_summary = len(re.findall(r"get_graph_summary", transcript))

    # Estimate Critic-specific references (Critic sections only)
    critic_sections = re.findall(
        r"### Critic.*?(?=### Defender|### Critic|\Z)", transcript, re.DOTALL
    )
    critic_text = "\n".join(critic_sections)
    critic_tool_refs = (
        len(re.findall(r"get_neighborhood", critic_text))
        + len(re.findall(r"query_graph", critic_text))
        + len(re.findall(r"get_graph_summary", critic_text))
    )

    # Evidence-grounded ratio from changelog
    changelog = load_changelog(session_id, "findings")
    outcomes = changelog.get("outcomes", []) if changelog else []
    evidence_markers = ["[", "node", "source", "conf=", "evidence", "edge", "hop"]
    grounded = sum(
        1 for o in outcomes
        if any(m in o.get("challenge_summary", "") for m in evidence_markers)
    )

    return {
        "total_tool_refs_in_transcript": get_neighborhood + query_graph + get_graph_summary,
        "critic_tool_refs": critic_tool_refs,
        "tool_breakdown": {
            "get_neighborhood": get_neighborhood,
            "query_graph": query_graph,
            "get_graph_summary": get_graph_summary,
        },
        "total_challenge_outcomes": len(outcomes),
        "evidence_grounded_challenges": grounded,
        "evidence_grounded_pct": round(grounded / len(outcomes) * 100, 1) if outcomes else 0,
    }


# ---------------------------------------------------------------------------
# Metric 3: Duplicate node rate
# ---------------------------------------------------------------------------

def duplicate_metrics(graph: dict, session_id: str) -> dict:
    """Measure deduplication effectiveness."""
    active = [n for n in graph["nodes"] if not n.get("withdrawn")]
    session_nodes = [
        n for n in active
        if n.get("provenance", {}).get("session_id") == session_id
    ]

    # Caught duplicates (corroborates edges)
    corroborates = [
        e for e in graph["edges"]
        if e.get("relationship") == "corroborates"
        and e.get("provenance", {}).get("session_id") == session_id
    ]

    # Missed duplicates (same-type, 0.6-0.85 string sim)
    claims = [n for n in session_nodes if n["type"] == "claim"]
    missed = 0
    for i, a in enumerate(claims):
        for b in claims[i+1:]:
            ratio = SequenceMatcher(None, a["label"].lower(), b["label"].lower()).ratio()
            if 0.6 < ratio <= 0.85:
                missed += 1

    return {
        "session_nodes": len(session_nodes),
        "caught_duplicates": len(corroborates),
        "potential_missed_duplicates": missed,
        "dedup_rate": round(
            len(corroborates) / (len(corroborates) + missed) * 100, 1
        ) if (len(corroborates) + missed) > 0 else 100.0,
    }


# ---------------------------------------------------------------------------
# Metric 4: Graph density
# ---------------------------------------------------------------------------

def density_metrics(graph: dict, session_id: str) -> dict:
    """Edges per node, cross-topic edges, related_to edges."""
    active = [n for n in graph["nodes"] if not n.get("withdrawn")]
    session_nodes = {
        n["id"] for n in active
        if n.get("provenance", {}).get("session_id") == session_id
    }
    session_edges = [
        e for e in graph["edges"]
        if e["source"] in session_nodes or e["target"] in session_nodes
    ]

    edge_types = Counter(e.get("relationship", "unknown") for e in session_edges)

    return {
        "total_active_nodes": len(active),
        "total_edges": len(graph["edges"]),
        "edges_per_node": round(len(graph["edges"]) / len(active), 2) if active else 0,
        "session_edges": len(session_edges),
        "related_to_edges": edge_types.get("related_to", 0),
        "cross_topic_potential": edge_types.get("related_to", 0) + edge_types.get("corroborates", 0),
        "edge_type_distribution": dict(edge_types.most_common(10)),
    }


# ---------------------------------------------------------------------------
# Metric 5: Thematic summary coverage
# ---------------------------------------------------------------------------

def thematic_coverage(graph: dict) -> dict:
    """Check if the thematic summary captures meaningful themes."""
    from research_agent.graph.schema import Graph
    from research_agent.graph.summarizer import summarize_graph

    g = Graph(nodes=graph["nodes"], edges=graph["edges"])
    summary = summarize_graph(g)

    has_themes = "## Research Themes" in summary
    has_gaps = "## Gaps" in summary
    theme_count = len(re.findall(r"^\*\*[^*]+\*\*\s*\(\d+\s*nodes", summary, re.MULTILINE))
    gap_items = len(re.findall(r"^- \d+ ", summary, re.MULTILINE))

    # Summary token estimate (chars / 4)
    summary_tokens = len(summary) // 4

    return {
        "has_thematic_section": has_themes,
        "theme_count": theme_count,
        "has_gap_detection": has_gaps,
        "gap_items": gap_items,
        "summary_tokens_approx": summary_tokens,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute_all_metrics(session_id: str) -> dict:
    graph = load_graph()

    return {
        "session_id": session_id,
        "truncation_coverage": truncation_coverage(graph, session_id),
        "critic_tool_usage": critic_tool_usage(session_id),
        "duplicate_metrics": duplicate_metrics(graph, session_id),
        "density_metrics": density_metrics(graph, session_id),
        "thematic_coverage": thematic_coverage(graph),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python eval/proxy_metrics.py <session_id>")
        sys.exit(1)

    session_id = sys.argv[1]
    session_dir = SESSIONS_DIR / f"session_{session_id}"
    if not session_dir.exists():
        print(f"Session directory not found: {session_dir}")
        sys.exit(1)

    metrics = compute_all_metrics(session_id)

    # Pretty print
    print(json.dumps(metrics, indent=2))

    # Append to log
    METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_LOG, "a") as f:
        f.write(json.dumps(metrics) + "\n")
    print(f"\nAppended to {METRICS_LOG}")


if __name__ == "__main__":
    main()
