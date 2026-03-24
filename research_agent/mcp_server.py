#!/usr/bin/env python3
"""Standalone MCP stdio server exposing graph tools.

Each agent process spawns its own instance of this server.
All instances read/write the same graph.json file on disk,
so there's no in-memory caching — every call loads fresh state.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Resolve paths relative to project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "graph.json"

mcp = FastMCP("research-graph")


# --- Graph I/O (no caching — always fresh from disk) ---

def _load() -> dict:
    if not GRAPH_PATH.exists():
        return {"nodes": [], "edges": []}
    return json.loads(GRAPH_PATH.read_text())


def _save(data: dict) -> None:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(data, indent=2))


# --- Tools ---

@mcp.tool()
def add_node(
    label: str,
    type: str,
    description: str,
    confidence: float = 0.5,
    url: str = "",
    source_type: str = "",
    session_id: str = "",
    subagent: str = "",
    mode: str = "survey",
) -> str:
    """Add a node to the knowledge graph.

    Args:
        label: Short display name for the node.
        type: One of concept, claim, source, question, direction, decision.
        description: 1-3 sentence summary of what this node represents.
        confidence: 0-1 float indicating how well-supported this node is.
        url: URL if this is a source node.
        source_type: One of academic, industry, blog, book, government, other.
        session_id: Current research session ID.
        subagent: Name of the agent creating this node.
        mode: Research mode — survey, analysis, or direction.
    """
    import uuid
    from difflib import SequenceMatcher

    graph = _load()

    # --- Cross-session deduplication ---
    for existing in graph["nodes"]:
        if existing.get("type") != type:
            continue
        if existing.get("withdrawn", False):
            continue
        ratio = SequenceMatcher(
            None, existing["label"].lower(), label.lower()
        ).ratio()
        if ratio > 0.85:
            edge_id = uuid.uuid4().hex[:12]
            graph["edges"].append({
                "id": edge_id,
                "source": existing["id"],
                "target": existing["id"],
                "relationship": "corroborates",
                "weight": ratio,
                "provenance": {
                    "session_id": session_id,
                    "subagent": subagent,
                    "mode": mode,
                },
            })
            old_conf = existing.get("confidence", 0.5)
            existing["confidence"] = min(old_conf + 0.05, 0.95)
            _save(graph)
            return (
                f"Near-duplicate found: [{existing['id']}] {existing['label']} "
                f"(similarity={ratio:.2f}). Linked via corroborates edge. "
                f"Confidence boosted {old_conf:.2f} → {existing['confidence']:.2f}."
            )

    node_id = uuid.uuid4().hex[:12]
    # Extract domain for source nodes
    domain = None
    if type == "source" and url:
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc or None
        except Exception:
            pass

    node = {
        "id": node_id,
        "label": label,
        "type": type,
        "description": description,
        "confidence": confidence,
        "provenance": {
            "session_id": session_id,
            "subagent": subagent,
            "mode": mode,
        },
        "metadata": {
            "url": url or None,
            "source_type": source_type or None,
            "user_added": False,
            "domain": domain,
        },
    }
    graph["nodes"].append(node)
    _save(graph)
    return f"Node added: {node_id}"


@mcp.tool()
def add_edge(
    source_id: str,
    target_id: str,
    relationship: str,
    weight: float = 1.0,
    session_id: str = "",
    subagent: str = "",
    mode: str = "survey",
) -> str:
    """Add an edge between two nodes in the knowledge graph.

    Args:
        source_id: ID of the source node.
        target_id: ID of the target node.
        relationship: One of supports, contradicts, subtopic_of, cites, example_of,
                      leads_to, authored_by, challenged_by, replaces, related_to.
        weight: Strength of the relationship (0-1).
        session_id: Current research session ID.
        subagent: Name of the agent creating this edge.
        mode: Research mode — survey, analysis, or direction.
    """
    import uuid

    graph = _load()
    edge_id = uuid.uuid4().hex[:12]
    edge = {
        "id": edge_id,
        "source": source_id,
        "target": target_id,
        "relationship": relationship,
        "weight": weight,
        "provenance": {
            "session_id": session_id,
            "subagent": subagent,
            "mode": mode,
        },
    }
    graph["edges"].append(edge)
    _save(graph)
    return f"Edge added: {edge_id}"


@mcp.tool()
def update_node(
    node_id: str,
    confidence: float | None = None,
    description: str | None = None,
) -> str:
    """Update confidence or description on an existing node.

    Args:
        node_id: ID of the node to update.
        confidence: New confidence value (optional).
        description: New description (optional).
    """
    graph = _load()
    for node in graph["nodes"]:
        if node["id"] == node_id:
            if confidence is not None:
                node["confidence"] = confidence
            if description is not None:
                node["description"] = description
            _save(graph)
            return f"Node {node_id} updated."
    return f"Node {node_id} not found."


@mcp.tool()
def get_graph_summary() -> str:
    """Get a compressed text summary of the current knowledge graph.

    Returns node counts by type, low-confidence areas, recent nodes,
    and most-connected nodes.
    """
    from collections import Counter

    graph = _load()
    # Filter out withdrawn nodes from summaries
    nodes = [n for n in graph["nodes"] if not n.get("withdrawn", False)]
    edges = graph["edges"]

    if not nodes:
        return "Knowledge graph is empty. No nodes or edges yet."

    type_counts = Counter(n["type"] for n in nodes)

    lines = [
        f"Graph: {len(nodes)} nodes, {len(edges)} edges.",
        "",
        "Nodes by type:",
    ]
    for t, c in type_counts.most_common():
        lines.append(f"  {t}: {c}")

    # Low-confidence nodes
    low_conf = [n for n in nodes if n.get("confidence", 1.0) < 0.4]
    if low_conf:
        lines.append("")
        lines.append(f"Low-confidence nodes ({len(low_conf)}):")
        for n in low_conf[:5]:
            lines.append(f"  - [{n['id']}] {n['label']} (conf={n['confidence']:.2f})")

    # Recent additions (last 10)
    recent = nodes[-10:]
    lines.append("")
    lines.append("Recent nodes:")
    for n in reversed(recent):
        lines.append(f"  - [{n['id']}] {n['label']} ({n['type']})")

    # Most connected nodes
    edge_counts: Counter[str] = Counter()
    for e in edges:
        edge_counts[e["source"]] += 1
        edge_counts[e["target"]] += 1

    if edge_counts:
        lines.append("")
        lines.append("Most connected nodes:")
        node_map = {n["id"]: n for n in nodes}
        for nid, count in edge_counts.most_common(5):
            label = node_map.get(nid, {}).get("label", nid)
            lines.append(f"  - {label}: {count} connections")

    return "\n".join(lines)


@mcp.tool()
def detect_coi(session_id: str = "") -> str:
    """Detect potential conflicts of interest in claim nodes.

    Checks if any claim's cited source domain appears in the claim's text,
    indicating the source may have a commercial interest in the claim.

    Args:
        session_id: If provided, only check claims from this session.
    """
    from urllib.parse import urlparse as _urlparse

    graph = _load()
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Map source node id → domain
    source_domains: dict[str, str] = {}
    for n in nodes:
        if n.get("type") != "source":
            continue
        domain = n.get("metadata", {}).get("domain")
        if domain:
            source_domains[n["id"]] = domain

    # Map claim → cited source ids
    claim_sources: dict[str, set[str]] = {}
    for e in edges:
        if e.get("relationship") == "cites":
            claim_sources.setdefault(e["source"], set()).add(e["target"])

    flagged = []
    for n in nodes:
        if n.get("type") != "claim":
            continue
        if session_id and n.get("provenance", {}).get("session_id") != session_id:
            continue

        text = (n.get("label", "") + " " + n.get("description", "")).lower()
        for src_id in claim_sources.get(n["id"], set()):
            domain = source_domains.get(src_id, "")
            if not domain:
                continue
            company = domain.split(".")[-2] if "." in domain else domain
            company = company.replace("www", "").strip()
            if len(company) < 3:
                continue
            if company.lower() in text:
                meta = n.setdefault("metadata", {})
                meta["potential_coi"] = True
                original = n.get("confidence", 0.5)
                n["confidence"] = max(original - 0.10, 0.10)
                flagged.append(f"[{n['id']}] {n['label']} (source: {domain})")
                break

    if flagged:
        _save(graph)
        return f"COI detected in {len(flagged)} claims:\n" + "\n".join(flagged)
    return "No conflicts of interest detected."


@mcp.tool()
def validate_claims(session_id: str = "") -> str:
    """Flag quantitative claim nodes that lack citation edges to source nodes.

    Checks all claim nodes (optionally filtered by session_id) for numeric
    content in their description. If a quantitative claim has no 'cites' edge,
    its confidence is capped at 0.50 and it is tagged with needs_source=true.

    Args:
        session_id: If provided, only validate claims from this session.
    """
    import re as _re

    graph = _load()
    nodes = graph["nodes"]
    edges = graph["edges"]

    # Build set of claim node IDs that have a cites edge (claim → source)
    cited_claims: set[str] = set()
    for e in edges:
        if e.get("relationship") == "cites":
            cited_claims.add(e["source"])

    quant_pattern = _re.compile(r"\d+\.?\d*\s*%|\b\d{2,}\b")
    flagged = []

    for node in nodes:
        if node.get("type") != "claim":
            continue
        if session_id and node.get("provenance", {}).get("session_id") != session_id:
            continue
        desc = node.get("description", "")
        if not quant_pattern.search(desc):
            continue
        if node["id"] in cited_claims:
            continue

        # Flag it
        meta = node.setdefault("metadata", {})
        meta["needs_source"] = True
        node["confidence"] = min(node.get("confidence", 0.5), 0.50)
        flagged.append(f"[{node['id']}] {node['label']} (conf capped at {node['confidence']:.2f})")

    if flagged:
        _save(graph)

    if not flagged:
        return "All quantitative claims have citation edges."
    return f"Flagged {len(flagged)} unsourced quantitative claims:\n" + "\n".join(flagged)


@mcp.tool()
def get_neighborhood(node_id: str, depth: int = 1) -> str:
    """Get all nodes and edges within N hops of a given node.

    Args:
        node_id: The center node ID.
        depth: Number of hops (default 1).
    """
    graph = _load()
    nodes = graph["nodes"]
    edges = graph["edges"]

    visited: set[str] = {node_id}
    frontier: set[str] = {node_id}

    for _ in range(depth):
        next_frontier: set[str] = set()
        for e in edges:
            if e["source"] in frontier:
                next_frontier.add(e["target"])
            if e["target"] in frontier:
                next_frontier.add(e["source"])
        next_frontier -= visited
        visited |= next_frontier
        frontier = next_frontier

    result_nodes = [n for n in nodes if n["id"] in visited]
    result_edges = [
        e for e in edges
        if e["source"] in visited and e["target"] in visited
    ]
    return json.dumps({"nodes": result_nodes, "edges": result_edges}, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
