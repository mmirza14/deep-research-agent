from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from research_agent.config import GRAPH_PATH, SNAPSHOTS_DIR
from research_agent.graph.schema import Graph


def load_graph(path: Path = GRAPH_PATH) -> Graph:
    if not path.exists():
        return Graph()
    data = json.loads(path.read_text())
    return Graph(nodes=data.get("nodes", []), edges=data.get("edges", []))


def save_graph(graph: Graph, path: Path = GRAPH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"nodes": graph.nodes, "edges": graph.edges}, indent=2))


def snapshot_graph(session_id: str, path: Path = GRAPH_PATH) -> Path | None:
    if not path.exists():
        return None
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest = SNAPSHOTS_DIR / f"{session_id}_{ts}.json"
    shutil.copy2(path, dest)
    return dest


def _find_snapshot(session_id: str) -> Path | None:
    """Find the most recent snapshot file for a given session."""
    if not SNAPSHOTS_DIR.exists():
        return None
    matches = sorted(SNAPSHOTS_DIR.glob(f"{session_id}_*.json"))
    return matches[-1] if matches else None


def diff_graph_since(session_id: str) -> dict:
    """Compare current graph against the pre-session snapshot.

    Detects user edits made during the analysis pause by checking provenance
    (session_id == "user", metadata.user_added == True).

    Returns dict with:
        user_added_nodes: nodes added by user since snapshot
        user_modified_nodes: nodes with changed confidence/description
        user_deleted_node_ids: node IDs present in snapshot but not current
        flagged_nodes: question nodes linked via challenged_by with user provenance
        user_added_edges: edges added by user since snapshot
    """
    snapshot_path = _find_snapshot(session_id)

    if snapshot_path:
        snap_data = json.loads(snapshot_path.read_text())
    else:
        snap_data = {"nodes": [], "edges": []}

    current = load_graph()

    snap_node_ids = {n["id"] for n in snap_data["nodes"]}
    snap_nodes_by_id = {n["id"]: n for n in snap_data["nodes"]}
    snap_edge_ids = {e["id"] for e in snap_data.get("edges", [])}

    current_node_ids = {n["id"] for n in current.nodes}

    user_added_nodes = []
    flagged_nodes = []
    user_modified_nodes = []

    for node in current.nodes:
        nid = node["id"]
        is_user = node.get("metadata", {}).get("user_added", False)

        if nid not in snap_node_ids and is_user:
            # Check if it's a flag (question node with challenged_by edge)
            is_flag = (
                node.get("type") == "question"
                and any(
                    e["source"] == nid and e.get("relationship") == "challenged_by"
                    for e in current.edges
                )
            )
            if is_flag:
                flagged_nodes.append(node)
            else:
                user_added_nodes.append(node)
        elif nid in snap_node_ids:
            old = snap_nodes_by_id[nid]
            old_conf = old.get("confidence", 0.5)
            new_conf = node.get("confidence", 0.5)
            old_desc = old.get("description", "")
            new_desc = node.get("description", "")
            if old_conf != new_conf or old_desc != new_desc:
                user_modified_nodes.append({
                    "id": nid,
                    "label": node.get("label", ""),
                    "old_confidence": old_conf,
                    "new_confidence": new_conf,
                    "old_description": old_desc,
                    "new_description": new_desc,
                })

    user_deleted_node_ids = list(snap_node_ids - current_node_ids)

    user_added_edges = [
        e for e in current.edges
        if e["id"] not in snap_edge_ids
        and e.get("provenance", {}).get("session_id") == "user"
    ]

    return {
        "user_added_nodes": user_added_nodes,
        "user_modified_nodes": user_modified_nodes,
        "user_deleted_node_ids": user_deleted_node_ids,
        "flagged_nodes": flagged_nodes,
        "user_added_edges": user_added_edges,
    }
