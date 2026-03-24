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
