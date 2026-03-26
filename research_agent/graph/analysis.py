"""Graph structural analysis for Direction Finding (Phase 5).

Pre-computes a structured analysis of the knowledge graph to inject into the
Direction agent's context. Also exports STOPWORDS for reuse by query_graph.
"""

from __future__ import annotations

import re
import string
from collections import Counter, defaultdict

from research_agent.graph.schema import Graph


# ---------------------------------------------------------------------------
# Stopwords — shared with query_graph in mcp_server.py
# ---------------------------------------------------------------------------

STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "can", "shall", "not", "no", "nor",
    "so", "if", "then", "than", "that", "this", "these", "those", "it",
    "its", "as", "up", "out", "about", "into", "over", "after", "before",
    "between", "under", "through", "during", "each", "all", "both", "such",
    "more", "most", "other", "some", "any", "only", "very", "also", "just",
    "how", "what", "which", "who", "when", "where", "why", "while",
})

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def tokenize(text: str) -> set[str]:
    """Lowercase, strip punctuation, remove stopwords."""
    cleaned = _PUNCT_RE.sub(" ", text.lower())
    return {w for w in cleaned.split() if w and w not in STOPWORDS and len(w) > 1}


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _build_adjacency(graph: Graph) -> dict[str, set[str]]:
    """Build undirected adjacency list from edges."""
    adj: dict[str, set[str]] = defaultdict(set)
    for e in graph.edges:
        adj[e["source"]].add(e["target"])
        adj[e["target"]].add(e["source"])
    return adj


def _connected_components(graph: Graph, adj: dict[str, set[str]]) -> list[list[dict]]:
    """BFS connected components. Returns list of node-lists."""
    visited: set[str] = set()
    components: list[list[dict]] = []
    node_map = {n["id"]: n for n in graph.nodes if not n.get("withdrawn")}

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

    # Sort by size descending
    components.sort(key=len, reverse=True)
    return components


def _find_unsupported_leaves(graph: Graph, adj: dict[str, set[str]]) -> list[dict]:
    """Nodes with degree <= 1 and no inbound supports/cites edge."""
    node_map = {n["id"]: n for n in graph.nodes if not n.get("withdrawn")}
    inbound_support: set[str] = set()
    for e in graph.edges:
        if e["relationship"] in ("supports", "cites"):
            inbound_support.add(e["target"])

    leaves = []
    for nid, node in node_map.items():
        if node["type"] not in ("claim", "concept"):
            continue
        degree = len(adj.get(nid, set()))
        if degree <= 1 and nid not in inbound_support:
            leaves.append(node)
    return leaves


def _find_uncontested_hubs(graph: Graph, adj: dict[str, set[str]]) -> list[dict]:
    """High-confidence, high-degree nodes with no contradictions."""
    node_map = {n["id"]: n for n in graph.nodes if not n.get("withdrawn")}
    contradiction_nodes: set[str] = set()
    for e in graph.edges:
        if e["relationship"] in ("contradicts", "challenged_by"):
            contradiction_nodes.add(e["source"])
            contradiction_nodes.add(e["target"])

    hubs = []
    for nid, node in node_map.items():
        degree = len(adj.get(nid, set()))
        if degree >= 3 and node.get("confidence", 0) >= 0.7 and nid not in contradiction_nodes:
            hubs.append({**node, "_degree": degree})
    hubs.sort(key=lambda n: n["_degree"], reverse=True)
    return hubs


def _find_unanswered_questions(graph: Graph) -> list[dict]:
    """Question nodes with no edges to any claim node."""
    node_map = {n["id"]: n for n in graph.nodes if not n.get("withdrawn")}
    claim_ids = {n["id"] for n in graph.nodes if n.get("type") == "claim" and not n.get("withdrawn")}

    # Build set of question IDs that have at least one edge to a claim
    answered: set[str] = set()
    for e in graph.edges:
        src, tgt = e["source"], e["target"]
        if src in claim_ids or tgt in claim_ids:
            if node_map.get(src, {}).get("type") == "question":
                answered.add(src)
            if node_map.get(tgt, {}).get("type") == "question":
                answered.add(tgt)

    return [
        n for n in graph.nodes
        if n.get("type") == "question" and not n.get("withdrawn") and n["id"] not in answered
    ]


def _find_cross_cluster_overlaps(
    components: list[list[dict]],
) -> list[tuple[int, int, set[str]]]:
    """Jaccard similarity between cluster keyword sets. Returns pairs above threshold."""
    if len(components) < 2:
        return []

    # Only consider clusters with >= 2 nodes
    clusters = [(i, comp) for i, comp in enumerate(components) if len(comp) >= 2]

    keyword_sets: list[tuple[int, set[str]]] = []
    for idx, comp in clusters:
        keywords: set[str] = set()
        for node in comp:
            text = f"{node.get('label', '')} {node.get('description', '')}"
            keywords |= tokenize(text)
        keyword_sets.append((idx, keywords))

    overlaps = []
    for i in range(len(keyword_sets)):
        for j in range(i + 1, len(keyword_sets)):
            idx_a, kw_a = keyword_sets[i]
            idx_b, kw_b = keyword_sets[j]
            intersection = kw_a & kw_b
            union = kw_a | kw_b
            if not union:
                continue
            jaccard = len(intersection) / len(union)
            if jaccard > 0.15:
                overlaps.append((idx_a, idx_b, intersection))

    overlaps.sort(key=lambda x: len(x[2]), reverse=True)
    return overlaps


# ---------------------------------------------------------------------------
# Cluster label helper
# ---------------------------------------------------------------------------

def _cluster_label(comp: list[dict]) -> str:
    """Pick a representative label for a cluster — the most-connected node or first node."""
    if not comp:
        return "empty"
    # Simple: pick the first concept or claim, falling back to first node
    for n in comp:
        if n["type"] in ("concept", "question", "decision"):
            return n["label"]
    return comp[0]["label"]


def _type_breakdown(comp: list[dict]) -> str:
    counts = Counter(n["type"] for n in comp)
    return ", ".join(f"{c} {t}" for t, c in counts.most_common())


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_graph_structure(graph: Graph, session_id: str | None = None) -> str:
    """Run all structural analyses and return a formatted markdown report."""
    if not graph.nodes:
        return "Graph is empty — no structural analysis possible."

    active_nodes = [n for n in graph.nodes if not n.get("withdrawn")]
    if not active_nodes:
        return "Graph has no active nodes — no structural analysis possible."

    adj = _build_adjacency(graph)
    components = _connected_components(graph, adj)
    leaves = _find_unsupported_leaves(graph, adj)
    hubs = _find_uncontested_hubs(graph, adj)
    unanswered = _find_unanswered_questions(graph)
    overlaps = _find_cross_cluster_overlaps(components)

    sections: list[str] = ["## Graph Structural Analysis", ""]

    # --- Connected Components ---
    isolated = [c for c in components if len(c) == 1]
    multi = [c for c in components if len(c) >= 2]

    sections.append(f"### Connected Components")
    sections.append(f"{len(multi)} cluster(s), {len(isolated)} isolated node(s).")
    sections.append("")
    for i, comp in enumerate(multi[:10]):  # cap at 10 clusters in output
        label = _cluster_label(comp)
        breakdown = _type_breakdown(comp)
        session_note = ""
        if session_id:
            session_nodes = [n for n in comp if n.get("provenance", {}).get("session_id") == session_id]
            if session_nodes:
                session_note = f" — {len(session_nodes)} nodes from session {session_id}"
        sections.append(f"- **Cluster {i+1}** ({len(comp)} nodes): \"{label}\" [{breakdown}]{session_note}")

    if isolated:
        sections.append("")
        sections.append(f"Isolated nodes ({len(isolated)}):")
        for comp in isolated[:10]:
            n = comp[0]
            sections.append(f"  - [{n['id']}] \"{n['label']}\" ({n['type']}, conf={n.get('confidence', 0):.2f})")
        if len(isolated) > 10:
            sections.append(f"  - ... and {len(isolated) - 10} more")

    # --- Unsupported Leaf Nodes ---
    sections.append("")
    sections.append(f"### Unsupported Leaf Nodes")
    if leaves:
        sections.append(f"{len(leaves)} claim/concept node(s) with no supporting evidence:")
        for n in leaves[:15]:
            sections.append(f"  - [{n['id']}] \"{n['label']}\" ({n['type']}, conf={n.get('confidence', 0):.2f})")
        if len(leaves) > 15:
            sections.append(f"  - ... and {len(leaves) - 15} more")
    else:
        sections.append("None found — all claim/concept nodes have supporting evidence.")

    # --- Uncontested Hubs ---
    sections.append("")
    sections.append(f"### Uncontested Hubs")
    sections.append("High-confidence (>=0.7), well-connected (>=3 edges) nodes with no contradictions — potential blind spots.")
    if hubs:
        for n in hubs[:10]:
            sections.append(f"  - [{n['id']}] \"{n['label']}\" (conf={n.get('confidence', 0):.2f}, {n['_degree']} connections)")
        if len(hubs) > 10:
            sections.append(f"  - ... and {len(hubs) - 10} more")
    else:
        sections.append("None found.")

    # --- Unanswered Questions ---
    sections.append("")
    sections.append(f"### Unanswered Questions")
    if unanswered:
        sections.append(f"{len(unanswered)} question(s) with no linked claims:")
        for n in unanswered[:15]:
            sess = n.get("provenance", {}).get("session_id", "unknown")
            sections.append(f"  - [{n['id']}] \"{n['label']}\" (session: {sess})")
        if len(unanswered) > 15:
            sections.append(f"  - ... and {len(unanswered) - 15} more")
    else:
        sections.append("None — all questions have at least one linked claim.")

    # --- Cross-Cluster Overlaps ---
    sections.append("")
    sections.append(f"### Cross-Cluster Thematic Overlaps")
    if overlaps:
        sections.append("Cluster pairs sharing thematic keywords (potential bridging opportunities):")
        for idx_a, idx_b, shared in overlaps[:5]:
            label_a = _cluster_label(components[idx_a])
            label_b = _cluster_label(components[idx_b])
            top_kw = sorted(shared)[:10]
            sections.append(
                f"  - **Cluster {idx_a+1}** (\"{label_a}\") ↔ **Cluster {idx_b+1}** (\"{label_b}\"): "
                f"shared keywords: {', '.join(top_kw)}"
            )
    else:
        sections.append("No significant thematic overlaps detected between clusters.")

    return "\n".join(sections)
