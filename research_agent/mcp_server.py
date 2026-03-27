#!/usr/bin/env python3
"""Standalone MCP stdio server exposing graph tools.

Each agent process spawns its own instance of this server.
When launched with --session <id>, reads/writes the session-specific graph.
Otherwise falls back to the global graph.json (legacy mode).

No in-memory caching — every call loads fresh state from disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Resolve paths relative to project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
GRAPH_PATH = DATA_DIR / "graph.json"

# Parse --session arg to scope graph I/O to a specific session
_session_id: str | None = None
_args = sys.argv[1:]
if "--session" in _args:
    _idx = _args.index("--session")
    if _idx + 1 < len(_args):
        _session_id = _args[_idx + 1]

if _session_id:
    from research_agent.config import session_graph_path
    GRAPH_PATH = session_graph_path(_session_id)

# Per-session embedding index path (lives next to the session graph.json)
EMBEDDING_INDEX_PATH = GRAPH_PATH.parent / "graph_index.npz"

mcp = FastMCP("research-graph")


# --- Graph I/O (no caching — always fresh from disk) ---

def _load() -> dict:
    """Load the active session's graph (used for reads and writes)."""
    if not GRAPH_PATH.exists():
        return {"nodes": [], "edges": []}
    return json.loads(GRAPH_PATH.read_text())


def _save(data: dict) -> None:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(data, indent=2))


def _load_all_sessions() -> dict:
    """Load a merged read-only view of ALL session graphs for cross-session dedup.

    Returns {"nodes": [...], "edges": [...]} with nodes from every session.
    Falls back to the active session graph if no sessions directory exists.
    """
    if not SESSIONS_DIR.exists():
        return _load()

    all_nodes = []
    all_edges = []
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()

    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        gp = session_dir / "graph.json"
        if not gp.exists():
            continue
        try:
            data = json.loads(gp.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for node in data.get("nodes", []):
            if node["id"] not in seen_node_ids:
                seen_node_ids.add(node["id"])
                all_nodes.append(node)
        for edge in data.get("edges", []):
            if edge["id"] not in seen_edge_ids:
                seen_edge_ids.add(edge["id"])
                all_edges.append(edge)

    if not all_nodes:
        return _load()

    return {"nodes": all_nodes, "edges": all_edges}


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
    # Load ALL session graphs for dedup comparison so we catch duplicates
    # across sessions, not just within the active session.
    all_graphs = _load_all_sessions()

    # Try semantic similarity first, fall back to string matching
    _semantic_dup_id = None
    _semantic_dup_ratio = 0.0
    try:
        from research_agent.config import EMBEDDING_MODEL
        from research_agent.graph.embeddings import GraphIndex, cosine_similarity

        index = GraphIndex(model_name=EMBEDDING_MODEL, index_path=EMBEDDING_INDEX_PATH)
        if index.available and index.load():
            candidate_text = f"{label} {description}"
            results = index.search(candidate_text, top_k=3)
            for existing_id, score in results:
                existing_node = next(
                    (n for n in all_graphs["nodes"]
                     if n["id"] == existing_id and n.get("type") == type
                     and not n.get("withdrawn", False)),
                    None,
                )
                if existing_node and score > 0.85:
                    _semantic_dup_id = existing_id
                    _semantic_dup_ratio = score
                    break
    except Exception:
        pass

    for existing in all_graphs["nodes"]:
        if existing.get("type") != type:
            continue
        if existing.get("withdrawn", False):
            continue
        # Use semantic match if found, otherwise string match
        if _semantic_dup_id and existing["id"] == _semantic_dup_id:
            ratio = _semantic_dup_ratio
        else:
            ratio = SequenceMatcher(
                None, existing["label"].lower(), label.lower()
            ).ratio()
        if ratio > 0.85:
            # Duplicate found. Add corroborates edge to THIS session's graph.
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
            # If the duplicate node lives in THIS session, boost its confidence
            local_node = next(
                (n for n in graph["nodes"] if n["id"] == existing["id"]), None
            )
            old_conf = existing.get("confidence", 0.5)
            if local_node:
                local_node["confidence"] = min(old_conf + 0.05, 0.95)
            _save(graph)
            return (
                f"Near-duplicate found: [{existing['id']}] {existing['label']} "
                f"(similarity={ratio:.2f}). Linked via corroborates edge. "
                f"Original confidence: {old_conf:.2f}."
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

    # Incrementally update per-session embedding index
    try:
        from research_agent.config import EMBEDDING_MODEL
        from research_agent.graph.embeddings import GraphIndex

        index = GraphIndex(model_name=EMBEDDING_MODEL, index_path=EMBEDDING_INDEX_PATH)
        if index.available:
            index.load()
            index.index_node(node_id, f"{label} {description}")
            index.save()
    except Exception:
        pass

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
    most-connected nodes, and thematic research clusters with top findings.
    """
    from research_agent.graph.schema import Graph
    from research_agent.graph.summarizer import summarize_graph

    raw = _load()
    graph = Graph(nodes=raw["nodes"], edges=raw["edges"])
    return summarize_graph(graph)


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
def query_graph(query: str) -> str:
    """Search the knowledge graph by keyword and semantic similarity.

    Uses embedding-based semantic search (if available) merged with keyword
    overlap. Returns top 10 matches with their 1-hop edges.

    Args:
        query: A natural language search query.
    """
    from research_agent.graph.analysis import tokenize

    graph = _load()
    node_map = {n["id"]: n for n in graph["nodes"] if not n.get("withdrawn")}

    # --- Keyword search ---
    query_tokens = tokenize(query)
    keyword_scores: dict[str, float] = {}
    if query_tokens:
        for node in node_map.values():
            text = f"{node.get('label', '')} {node.get('description', '')}"
            node_tokens = tokenize(text)
            overlap = len(query_tokens & node_tokens)
            if overlap > 0:
                # Normalize to 0-1 range
                keyword_scores[node["id"]] = overlap / len(query_tokens)

    # --- Semantic search ---
    semantic_scores: dict[str, float] = {}
    try:
        from research_agent.config import EMBEDDING_MODEL
        from research_agent.graph.embeddings import GraphIndex

        index = GraphIndex(model_name=EMBEDDING_MODEL, index_path=EMBEDDING_INDEX_PATH)
        if index.available:
            # Try loading persisted index; rebuild if stale
            if not index.load() or index.is_stale(GRAPH_PATH):
                index.index_nodes(list(node_map.values()))
                index.save()

            results = index.search(query, top_k=10)
            for nid, score in results:
                semantic_scores[nid] = score
    except Exception:
        pass  # Fall back to keyword-only

    # --- Merge results ---
    all_ids = set(keyword_scores.keys()) | set(semantic_scores.keys())
    if not all_ids:
        return json.dumps({"results": [], "message": "No matching nodes found."})

    merged: list[tuple[float, str]] = []
    for nid in all_ids:
        kw = keyword_scores.get(nid, 0.0)
        sem = semantic_scores.get(nid, 0.0)
        # Weighted combination: semantic dominates when available
        if semantic_scores:
            combined = 0.6 * sem + 0.4 * kw
        else:
            combined = kw
        merged.append((combined, nid))

    merged.sort(key=lambda x: x[0], reverse=True)
    top = merged[:10]

    # Collect 1-hop edges for result nodes
    result_ids = {nid for _, nid in top}
    result_edges = [
        e for e in graph["edges"]
        if e["source"] in result_ids or e["target"] in result_ids
    ]

    results = [
        {"node": node_map[nid], "score": round(score, 4), "edges": [
            e for e in result_edges
            if e["source"] == nid or e["target"] == nid
        ]}
        for score, nid in top
        if nid in node_map
    ]

    return json.dumps({"results": results}, indent=2)


@mcp.tool()
def get_session_findings(session_id: str) -> str:
    """Get all researcher findings for a given session.

    Returns every node added by researcher subagents in this session,
    with their full metadata (label, description, confidence, sources, etc.).
    Much more efficient than crawling the graph node-by-node.

    Args:
        session_id: The research session ID.
    """
    graph = _load()
    findings = [
        n for n in graph["nodes"]
        if not n.get("withdrawn", False)
        and n.get("provenance", {}).get("session_id") == session_id
        and n.get("provenance", {}).get("subagent", "").startswith("researcher")
    ]
    return json.dumps({"count": len(findings), "findings": findings}, indent=2)


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
