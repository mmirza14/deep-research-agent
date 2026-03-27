"""Pre-review validation checks for research findings.

These run after researchers populate the graph but before Socratic review,
catching common quality issues early (unsourced claims, COI, etc.).
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from research_agent.config import session_graph_path
from research_agent.graph.store import load_graph, save_graph


def _load_session_or_global(session_id: str):
    sgp = session_graph_path(session_id)
    return load_graph(sgp) if sgp.exists() else load_graph()


def _save_session_or_global(graph, session_id: str):
    sgp = session_graph_path(session_id)
    if sgp.exists():
        save_graph(graph, sgp)
    else:
        save_graph(graph)


def validate_session_claims(session_id: str) -> str:
    """Flag quantitative claim nodes that lack citation edges.

    Returns a summary string (empty if nothing flagged).
    """
    graph = _load_session_or_global(session_id)

    # Build set of claim node IDs that have a cites edge
    cited_claims: set[str] = set()
    for e in graph.edges:
        if e.get("relationship") == "cites":
            cited_claims.add(e["source"])

    quant_pattern = re.compile(r"\d+\.?\d*\s*%|\b\d{2,}\b")
    flagged = []

    for node in graph.nodes:
        if node.get("type") != "claim":
            continue
        if node.get("provenance", {}).get("session_id") != session_id:
            continue
        desc = node.get("description", "")
        if not quant_pattern.search(desc):
            continue
        if node["id"] in cited_claims:
            continue

        meta = node.setdefault("metadata", {})
        meta["needs_source"] = True
        node["confidence"] = min(node.get("confidence", 0.5), 0.50)
        flagged.append(f"[{node['id']}] {node['label']}")

    if flagged:
        _save_session_or_global(graph, session_id)
        return (
            f"Validation: flagged {len(flagged)} unsourced quantitative claims "
            f"(confidence capped at 0.50):\n  " + "\n  ".join(flagged)
        )
    return ""


def detect_coi(session_id: str) -> str:
    """Flag claim nodes whose cited source domain appears in the claim text.

    Returns a summary string (empty if nothing flagged).
    """
    graph = _load_session_or_global(session_id)

    # Build map: source node id → domain
    source_domains: dict[str, str] = {}
    for node in graph.nodes:
        if node.get("type") != "source":
            continue
        url = node.get("metadata", {}).get("url") or node.get("metadata", {}).get("domain")
        if not url:
            continue
        domain = node.get("metadata", {}).get("domain") or ""
        if not domain and url:
            try:
                domain = urlparse(url).netloc
            except Exception:
                continue
        if domain:
            source_domains[node["id"]] = domain

    # Build map: claim node id → set of cited source node ids
    claim_sources: dict[str, set[str]] = {}
    for e in graph.edges:
        if e.get("relationship") == "cites":
            claim_sources.setdefault(e["source"], set()).add(e["target"])

    flagged = []
    for node in graph.nodes:
        if node.get("type") != "claim":
            continue
        if session_id and node.get("provenance", {}).get("session_id") != session_id:
            continue

        cited_source_ids = claim_sources.get(node["id"], set())
        text = (node.get("label", "") + " " + node.get("description", "")).lower()

        for src_id in cited_source_ids:
            domain = source_domains.get(src_id, "")
            if not domain:
                continue
            # Extract company name: strip TLD and www
            company = domain.split(".")[-2] if "." in domain else domain
            company = company.replace("www", "").strip()
            if len(company) < 3:
                continue

            if company.lower() in text:
                meta = node.setdefault("metadata", {})
                meta["potential_coi"] = True
                original = node.get("confidence", 0.5)
                node["confidence"] = max(original - 0.10, 0.10)
                flagged.append(f"[{node['id']}] {node['label']} (source: {domain})")
                break  # one COI flag per claim is enough

    if flagged:
        _save_session_or_global(graph, session_id)
        return (
            f"COI detection: flagged {len(flagged)} claims with potential "
            f"conflict of interest:\n  " + "\n  ".join(flagged)
        )
    return ""
