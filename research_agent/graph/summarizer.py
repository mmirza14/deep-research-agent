"""Compress graph state into a text summary for agent context injection.

Provides both a structural summary (node counts, hubs, low-confidence areas)
and a thematic summary (connected-component clusters with top descriptions).
"""

from __future__ import annotations

from collections import Counter, defaultdict

from research_agent.graph.schema import Graph


# ---------------------------------------------------------------------------
# Thematic clustering helpers
# ---------------------------------------------------------------------------

def _build_adjacency(graph: Graph) -> dict[str, set[str]]:
    """Build undirected adjacency list from edges."""
    adj: defaultdict[str, set[str]] = defaultdict(set)
    for e in graph.edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    return dict(adj)


def _connected_components(
    active_nodes: list[dict], adj: dict[str, set[str]]
) -> list[list[dict]]:
    """BFS connected components over active nodes. Returns list of node-lists (descending size)."""
    node_map = {n["id"]: n for n in active_nodes}
    visited: set[str] = set()
    components: list[list[dict]] = []

    for nid in node_map:
        if nid in visited:
            continue
        queue = [nid]
        visited.add(nid)
        comp: list[dict] = []
        while queue:
            cur = queue.pop(0)
            node = node_map.get(cur)
            if node:
                comp.append(node)
            for neighbor in adj.get(cur, set()):
                if neighbor not in visited and neighbor in node_map:
                    visited.add(neighbor)
                    queue.append(neighbor)
        components.append(comp)

    components.sort(key=len, reverse=True)
    return components


def _cluster_label(comp: list[dict], adj: dict[str, set[str]]) -> str:
    """Pick the highest-degree node's label as the cluster name."""
    if not comp:
        return "empty"
    best = max(comp, key=lambda n: len(adj.get(n["id"], set())))
    return best["label"]


def _summarize_thematic(
    active_nodes: list[dict], graph: Graph, max_clusters: int = 10, max_tokens: int = 800
) -> list[str]:
    """Generate thematic cluster summary lines."""
    adj = _build_adjacency(graph)
    components = _connected_components(active_nodes, adj)

    # Only clusters with >= 2 nodes are thematically interesting
    multi = [c for c in components if len(c) >= 2]
    if not multi:
        return []

    lines = ["", "## Research Themes", ""]
    char_budget = max_tokens * 4  # rough chars-per-token estimate
    chars_used = 0

    for comp in multi[:max_clusters]:
        label = _cluster_label(comp, adj)
        edge_count = sum(
            1 for e in graph.edges
            if e["source"] in {n["id"] for n in comp}
            and e["target"] in {n["id"] for n in comp}
        )
        header = f"**{label}** ({len(comp)} nodes, {edge_count} edges)"
        lines.append(header)
        chars_used += len(header)

        # Top 3 descriptions by confidence
        ranked = sorted(comp, key=lambda n: n.get("confidence", 0), reverse=True)
        for n in ranked[:3]:
            desc = n.get("description", n.get("label", ""))
            if len(desc) > 120:
                desc = desc[:117] + "..."
            entry = f'- "{desc}" (conf={n.get("confidence", 0.5):.2f})'
            lines.append(entry)
            chars_used += len(entry)

        lines.append("")
        if chars_used > char_budget:
            lines.append(
                f"({len(multi) - multi.index(comp) - 1} more clusters omitted. "
                "Use `query_graph` for details on specific themes.)"
            )
            break

    # Gaps: question nodes with no linked claims
    question_ids = {n["id"] for n in active_nodes if n.get("type") == "question"}
    claim_ids = {n["id"] for n in active_nodes if n.get("type") == "claim"}
    answered: set[str] = set()
    for e in graph.edges:
        src, tgt = e["source"], e["target"]
        if src in claim_ids or tgt in claim_ids:
            if src in question_ids:
                answered.add(src)
            if tgt in question_ids:
                answered.add(tgt)
    unanswered = question_ids - answered
    if unanswered:
        lines.append("## Gaps")
        unanswered_nodes = [n for n in active_nodes if n["id"] in unanswered]
        labels = [n["label"] for n in unanswered_nodes[:5]]
        lines.append(f"- {len(unanswered)} question node(s) have no linked claims: {', '.join(labels)}")

    # Disconnected cluster pairs
    if len(multi) >= 2:
        # Check which cluster pairs have no cross-edges
        disconnected_pairs = []
        for i in range(min(len(multi), 5)):
            ids_i = {n["id"] for n in multi[i]}
            for j in range(i + 1, min(len(multi), 5)):
                ids_j = {n["id"] for n in multi[j]}
                has_cross = any(
                    (e["source"] in ids_i and e["target"] in ids_j)
                    or (e["source"] in ids_j and e["target"] in ids_i)
                    for e in graph.edges
                )
                if not has_cross:
                    disconnected_pairs.append(
                        f"{_cluster_label(multi[i], adj)} ↔ {_cluster_label(multi[j], adj)}"
                    )
        if disconnected_pairs:
            if "## Gaps" not in lines:
                lines.append("## Gaps")
            lines.append(
                f"- {len(disconnected_pairs)} cluster pair(s) have no cross-links: "
                + "; ".join(disconnected_pairs[:3])
            )

    return lines


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def summarize_graph(graph: Graph) -> str:
    """Produce a combined structural + thematic summary of the knowledge graph."""
    if not graph.nodes:
        return "Knowledge graph is empty. No nodes or edges yet."

    # Filter out withdrawn nodes from all summaries
    active_nodes = [n for n in graph.nodes if not n.get("withdrawn", False)]

    type_counts = Counter(n["type"] for n in active_nodes)
    edge_count = len(graph.edges)

    lines = [
        f"Graph: {len(active_nodes)} nodes, {edge_count} edges.",
        "",
        "Nodes by type:",
    ]
    for t, c in type_counts.most_common():
        lines.append(f"  {t}: {c}")

    # Low-confidence nodes
    low_conf = [n for n in active_nodes if n.get("confidence", 1.0) < 0.4]
    if low_conf:
        lines.append("")
        lines.append(f"Low-confidence nodes ({len(low_conf)}):")
        for n in low_conf[:5]:
            lines.append(f"  - [{n['id']}] {n['label']} (conf={n['confidence']:.2f})")

    # Recent additions (last 10 by list order, which is insertion order)
    recent = active_nodes[-10:]
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

    # Thematic summary — connected component clusters with top descriptions
    thematic = _summarize_thematic(active_nodes, graph)
    if thematic:
        lines.extend(thematic)

    return "\n".join(lines)
