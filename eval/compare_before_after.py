#!/usr/bin/env python3
"""Before/after comparison for context quality improvements.

Runs old and new logic against session_5f9219ae and writes a comparison
report to eval/comparison_report.md.

Usage:
    python eval/compare_before_after.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.graph.schema import Graph
from research_agent.graph.store import load_graph
from research_agent.socratic.review import (
    get_session_findings,
    format_findings_for_review,
    load_socratic_scores,
)
from research_agent.report_writer import (
    _score_finding,
    _rank_findings,
    _load_changelog,
    _format_changelog_for_report,
)
from research_agent.graph.summarizer import summarize_graph

SESSION_ID = "5f9219ae"
OUTPUT = PROJECT_ROOT / "eval" / "comparison_report.md"


def compare_truncation():
    """#1: Compare positional vs ranked truncation."""
    findings = get_session_findings(SESSION_ID)
    graph = load_graph()
    socratic_scores = load_socratic_scores(SESSION_ID)

    # Positional order (old) — first 30 by insertion order
    positional_ids = [n["id"] for n in findings[:30]]

    # Ranked order (new) — top 30 by composite score
    ranked = _rank_findings(findings, SESSION_ID)
    ranked_ids = [n["id"] for n in ranked[:30]]

    # Overlap
    positional_set = set(positional_ids)
    ranked_set = set(ranked_ids)
    overlap = positional_set & ranked_set
    only_positional = positional_set - ranked_set
    only_ranked = ranked_set - positional_set

    # Score the findings that got promoted/demoted
    node_map = {n["id"]: n for n in findings}
    scores = {}
    for n in findings:
        degree = graph.node_degree(n["id"])
        soc = socratic_scores.get(n["id"], 0.7)
        scores[n["id"]] = _score_finding(n, degree, soc)

    lines = [
        "## 1. Relevance-Ranked Truncation\n",
        f"Total findings: {len(findings)}",
        f"Top-30 overlap between old/new: {len(overlap)}/{30} ({len(overlap)/30*100:.0f}%)",
        f"Findings promoted into top-30 by ranking: {len(only_ranked)}",
        f"Findings dropped from top-30 by ranking: {len(only_positional)}",
        "",
    ]

    if only_ranked:
        lines.append("### Promoted (now in top-30, weren't before)")
        promoted = sorted(only_ranked, key=lambda nid: scores[nid], reverse=True)
        for nid in promoted[:10]:
            n = node_map[nid]
            old_pos = next(i for i, f in enumerate(findings) if f["id"] == nid)
            lines.append(
                f"- [{nid}] **{n['label'][:60]}** — score={scores[nid]:.3f}, "
                f"conf={n.get('confidence', 0.5):.2f}, old position=#{old_pos+1}"
            )

    if only_positional:
        lines.append("\n### Demoted (were in top-30, now dropped)")
        demoted = sorted(only_positional, key=lambda nid: scores[nid])
        for nid in demoted[:10]:
            n = node_map[nid]
            lines.append(
                f"- [{nid}] **{n['label'][:60]}** — score={scores[nid]:.3f}, "
                f"conf={n.get('confidence', 0.5):.2f}"
            )

    return "\n".join(lines)


def compare_graph_summary():
    """#2: Compare old structural vs new thematic summary."""
    graph = load_graph()
    active_nodes = [n for n in graph.nodes if not n.get("withdrawn", False)]

    # Old summary: structural only
    type_counts = Counter(n["type"] for n in active_nodes)
    old_lines = [
        f"Graph: {len(active_nodes)} nodes, {len(graph.edges)} edges.",
        "", "Nodes by type:",
    ]
    for t, c in type_counts.most_common():
        old_lines.append(f"  {t}: {c}")
    low_conf = [n for n in active_nodes if n.get("confidence", 1.0) < 0.4]
    if low_conf:
        old_lines.append(f"\nLow-confidence nodes ({len(low_conf)}):")
        for n in low_conf[:5]:
            old_lines.append(f"  - [{n['id']}] {n['label']} (conf={n['confidence']:.2f})")
    recent = active_nodes[-10:]
    old_lines.append("\nRecent nodes:")
    for n in reversed(recent):
        old_lines.append(f"  - [{n['id']}] {n['label']} ({n['type']})")
    edge_counts: Counter = Counter()
    for e in graph.edges:
        edge_counts[e["source"]] += 1
        edge_counts[e["target"]] += 1
    if edge_counts:
        old_lines.append("\nMost connected nodes:")
        for nid, count in edge_counts.most_common(5):
            node = graph.get_node(nid)
            label = node["label"] if node else nid
            old_lines.append(f"  - {label}: {count} connections")
    old_summary = "\n".join(old_lines)

    # New summary: structural + thematic
    new_summary = summarize_graph(graph)

    # Measure the difference
    old_len = len(old_summary)
    new_len = len(new_summary)
    has_themes = "## Research Themes" in new_summary
    has_gaps = "## Gaps" in new_summary
    theme_count = new_summary.count("** (") if has_themes else 0

    lines = [
        "## 2. Semantic Graph Summary\n",
        f"Old summary length: {old_len} chars",
        f"New summary length: {new_len} chars (+{new_len - old_len})",
        f"Has thematic clusters: {has_themes}",
        f"Number of themes: {theme_count}",
        f"Has gap detection: {has_gaps}",
        "",
        "### Old summary (structural only)",
        "```",
        old_summary[:1500],
        "```",
        "",
        "### New summary (structural + thematic)",
        "```",
        new_summary[:3000],
        "```",
    ]
    return "\n".join(lines)


def compare_critic_access():
    """#3: Measure what the Critic can now do vs before."""
    # Read existing transcript to see what the old Critic did
    transcript_path = (
        PROJECT_ROOT / "data" / "sessions" / f"session_{SESSION_ID}" / "transcript_findings.md"
    )
    transcript = transcript_path.read_text() if transcript_path.exists() else ""

    # Count Critic turns
    critic_turns = transcript.count("### Critic")

    # The old Critic had no tool access — check for any MCP tool patterns
    old_tool_calls = transcript.count("get_neighborhood") + transcript.count("query_graph")

    # Load changelog to see challenge quality
    changelog_data = _load_changelog(SESSION_ID, "findings")
    outcomes = changelog_data.get("outcomes", []) if changelog_data else []

    # Challenges with specific evidence citations vs vague challenges
    evidence_grounded = 0
    surface_level = 0
    for o in outcomes:
        summary = o.get("challenge_summary", "")
        # Heuristic: if it references a node ID or specific data, it's grounded
        if any(c in summary for c in ["[", "node", "source", "conf=", "evidence"]):
            evidence_grounded += 1
        else:
            surface_level += 1

    lines = [
        "## 3. MCP Tools for Socratic Critic\n",
        f"Existing transcript Critic turns: {critic_turns}",
        f"Existing tool references in old transcript: {old_tool_calls} (expected: 0)",
        f"Total challenge outcomes: {len(outcomes)}",
        f"Evidence-grounded challenges (heuristic): {evidence_grounded}",
        f"Surface-level challenges (heuristic): {surface_level}",
        "",
        "**Expected improvement**: After re-running with MCP access, the Critic should:",
        "- Call get_neighborhood to verify source chains before challenging",
        "- Call query_graph to find contradicting evidence",
        "- Produce challenges that cite specific node IDs and graph relationships",
        "",
        "**How to verify**: Re-run Socratic review on this session and compare transcripts.",
        "Count tool_use blocks in the new transcript. Evidence-grounded ratio should increase.",
    ]
    return "\n".join(lines)


def compare_search_quality():
    """#4: Compare keyword-only vs semantic search."""
    graph = load_graph()
    node_map = {n["id"]: n for n in graph.nodes if not n.get("withdrawn")}

    # Test queries that should benefit from semantic search
    test_queries = [
        "cost reduction in large language models",
        "environmental impact of cosmetic ingredients",
        "regulatory compliance timeline",
        "alternative formulations for banned substances",
        "consumer safety evidence",
    ]

    from research_agent.graph.analysis import tokenize

    lines = [
        "## 4. Semantic Search for query_graph\n",
        f"Graph nodes available for search: {len(node_map)}",
        "",
    ]

    for q in test_queries:
        # Keyword search (old method)
        query_tokens = tokenize(q)
        keyword_hits = []
        for node in node_map.values():
            text = f"{node.get('label', '')} {node.get('description', '')}"
            node_tokens = tokenize(text)
            overlap = len(query_tokens & node_tokens)
            if overlap > 0:
                keyword_hits.append((overlap, node))
        keyword_hits.sort(key=lambda x: x[0], reverse=True)

        lines.append(f"### Query: \"{q}\"")
        lines.append(f"Keyword matches: {len(keyword_hits)}")
        if keyword_hits:
            lines.append("Top 3 keyword hits:")
            for score, n in keyword_hits[:3]:
                lines.append(f"  - [{n['id']}] {n['label'][:70]} (overlap={score})")
        else:
            lines.append("  (no keyword matches)")

        # Semantic search — try if available
        try:
            from research_agent.graph.embeddings import GraphIndex
            from research_agent.config import EMBEDDING_MODEL, EMBEDDING_INDEX_PATH

            index = GraphIndex(model_name=EMBEDDING_MODEL, index_path=EMBEDDING_INDEX_PATH)
            if index.available:
                index.index_nodes(list(node_map.values()))
                sem_results = index.search(q, top_k=5)
                lines.append(f"Semantic matches: {len(sem_results)}")
                lines.append("Top 3 semantic hits:")
                for nid, score in sem_results[:3]:
                    n = node_map.get(nid, {})
                    lines.append(f"  - [{nid}] {n.get('label', '?')[:70]} (sim={score:.3f})")

                # How many semantic hits were NOT in keyword top-10?
                kw_top10 = {n["id"] for _, n in keyword_hits[:10]}
                sem_top5 = {nid for nid, _ in sem_results[:5]}
                novel = sem_top5 - kw_top10
                lines.append(f"Novel semantic finds (not in keyword top-10): {len(novel)}")
            else:
                lines.append("Semantic search: unavailable (sentence-transformers not installed)")
                lines.append("Install with: pip install sentence-transformers")
        except ImportError:
            lines.append("Semantic search: unavailable (sentence-transformers not installed)")
            lines.append("Install with: pip install sentence-transformers")

        lines.append("")

    return "\n".join(lines)


def compare_dedup():
    """#5: Measure current duplicate rate in the graph."""
    graph = load_graph()
    active_nodes = [n for n in graph.nodes if not n.get("withdrawn")]

    # Count existing corroborates edges (dedup events)
    corroborates = [e for e in graph.edges if e.get("relationship") == "corroborates"]

    # Find potential duplicates the old method missed (same-type nodes with similar labels)
    from difflib import SequenceMatcher
    potential_dupes = []
    claims = [n for n in active_nodes if n["type"] == "claim"]
    for i, a in enumerate(claims):
        for b in claims[i+1:]:
            ratio = SequenceMatcher(None, a["label"].lower(), b["label"].lower()).ratio()
            if 0.6 < ratio <= 0.85:  # below old threshold but suspiciously similar
                potential_dupes.append((ratio, a, b))

    potential_dupes.sort(key=lambda x: x[0], reverse=True)

    lines = [
        "## 5. Researcher Cross-Awareness\n",
        f"Active nodes: {len(active_nodes)}",
        f"Existing corroborates edges (caught duplicates): {len(corroborates)}",
        f"Potential missed duplicates (0.6-0.85 string similarity): {len(potential_dupes)}",
        "",
    ]

    if potential_dupes:
        lines.append("### Top potential duplicates the old method missed")
        for ratio, a, b in potential_dupes[:10]:
            lines.append(
                f"- **{ratio:.2f}** similarity:\n"
                f"  A: [{a['id']}] {a['label'][:60]}\n"
                f"  B: [{b['id']}] {b['label'][:60]}"
            )

    # Graph density
    edges_per_node = len(graph.edges) / len(active_nodes) if active_nodes else 0
    lines.append(f"\nGraph density: {edges_per_node:.2f} edges/node")
    lines.append(
        "**Expected improvement**: After re-running researchers with cross-awareness, "
        "expect fewer duplicates and higher density (more related_to edges)."
    )

    return "\n".join(lines)


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    sections = [
        "# Context Quality Improvements — Before/After Comparison",
        f"\nSession: `{SESSION_ID}`",
        f"Graph: `{PROJECT_ROOT / 'data' / 'graph.json'}`\n",
        "---\n",
    ]

    print("Running comparison #1: Relevance-Ranked Truncation...")
    sections.append(compare_truncation())
    sections.append("\n---\n")

    print("Running comparison #2: Semantic Graph Summary...")
    sections.append(compare_graph_summary())
    sections.append("\n---\n")

    print("Running comparison #3: MCP Tools for Critic...")
    sections.append(compare_critic_access())
    sections.append("\n---\n")

    print("Running comparison #4: Semantic Search...")
    sections.append(compare_search_quality())
    sections.append("\n---\n")

    print("Running comparison #5: Researcher Cross-Awareness...")
    sections.append(compare_dedup())

    report = "\n".join(sections)
    OUTPUT.write_text(report)
    print(f"\nComparison report saved: {OUTPUT}")


if __name__ == "__main__":
    main()
