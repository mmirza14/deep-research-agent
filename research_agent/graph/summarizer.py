"""Compress graph state into a text summary for agent context injection."""

from __future__ import annotations

from collections import Counter

from research_agent.graph.schema import Graph


def summarize_graph(graph: Graph) -> str:
    if not graph.nodes:
        return "Knowledge graph is empty. No nodes or edges yet."

    type_counts = Counter(n["type"] for n in graph.nodes)
    edge_count = len(graph.edges)

    lines = [
        f"Graph: {len(graph.nodes)} nodes, {edge_count} edges.",
        "",
        "Nodes by type:",
    ]
    for t, c in type_counts.most_common():
        lines.append(f"  {t}: {c}")

    # Low-confidence nodes
    low_conf = [n for n in graph.nodes if n.get("confidence", 1.0) < 0.4]
    if low_conf:
        lines.append("")
        lines.append(f"Low-confidence nodes ({len(low_conf)}):")
        for n in low_conf[:5]:
            lines.append(f"  - [{n['id']}] {n['label']} (conf={n['confidence']:.2f})")

    # Recent additions (last 10 by list order, which is insertion order)
    recent = graph.nodes[-10:]
    lines.append("")
    lines.append("Recent nodes:")
    for n in reversed(recent):
        lines.append(f"  - [{n['id']}] {n['label']} ({n['type']})")

    # Key clusters — nodes with most edges
    edge_counts: Counter[str] = Counter()
    for e in graph.edges:
        edge_counts[e["source"]] += 1
        edge_counts[e["target"]] += 1

    if edge_counts:
        lines.append("")
        lines.append("Most connected nodes:")
        for nid, count in edge_counts.most_common(5):
            node = graph.get_node(nid)
            label = node["label"] if node else nid
            lines.append(f"  - {label}: {count} connections")

    return "\n".join(lines)
