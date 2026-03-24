"""Phase 3: WebSocket server for real-time mind map sync.

Watches graph.json for agent-side changes and broadcasts to all connected
browser clients. Accepts user mutations (add/edit/delete nodes, add edges,
flag for re-investigation) and writes them back to graph.json so the agent
sees them on its next read.

Also serves the built React app as static files.

Usage:
    python -m visualization.server          # production (serves built React app)
    python -m visualization.server --dev    # dev mode (CORS headers for Vite on :5173)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import websockets
from websockets.asyncio.server import serve as ws_serve

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "graph.json"
DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"

PORT = 8420
POLL_INTERVAL = 0.5  # seconds between graph.json checks

# Track connected clients
clients: set[websockets.asyncio.server.ServerConnection] = set()

# Last known hash of graph.json for change detection
_last_graph_hash: str = ""


# ---------------------------------------------------------------------------
# Graph I/O
# ---------------------------------------------------------------------------

def _load_graph() -> dict:
    if not GRAPH_PATH.exists():
        return {"nodes": [], "edges": []}
    return json.loads(GRAPH_PATH.read_text())


def _save_graph(data: dict) -> None:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GRAPH_PATH.write_text(json.dumps(data, indent=2))


def _graph_hash() -> str:
    if not GRAPH_PATH.exists():
        return ""
    return hashlib.md5(GRAPH_PATH.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# User mutations — write to graph.json
# ---------------------------------------------------------------------------

def handle_add_node(data: dict) -> dict:
    graph = _load_graph()
    node_id = uuid.uuid4().hex[:12]
    node = {
        "id": node_id,
        "label": data.get("label", "New node"),
        "type": data.get("type", "concept"),
        "description": data.get("description", ""),
        "confidence": data.get("confidence", 0.5),
        "provenance": {
            "session_id": "user",
            "subagent": "mind_map_ui",
            "mode": "direction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {
            "url": data.get("url"),
            "source_type": data.get("source_type"),
            "user_added": True,
        },
    }
    graph["nodes"].append(node)
    _save_graph(graph)
    return node


def handle_update_node(data: dict) -> bool:
    graph = _load_graph()
    node_id = data.get("id")
    for node in graph["nodes"]:
        if node["id"] == node_id:
            for field in ("label", "description", "confidence"):
                if field in data and data[field] is not None:
                    node[field] = data[field]
            _save_graph(graph)
            return True
    return False


def handle_add_edge(data: dict) -> dict | None:
    graph = _load_graph()
    node_ids = {n["id"] for n in graph["nodes"]}
    src, tgt = data.get("source"), data.get("target")
    if src not in node_ids or tgt not in node_ids:
        return None
    edge_id = uuid.uuid4().hex[:12]
    edge = {
        "id": edge_id,
        "source": src,
        "target": tgt,
        "relationship": data.get("relationship", "related_to"),
        "weight": data.get("weight", 1.0),
        "provenance": {
            "session_id": "user",
            "subagent": "mind_map_ui",
            "mode": "direction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    graph["edges"].append(edge)
    _save_graph(graph)
    return edge


def handle_delete_node(data: dict) -> bool:
    graph = _load_graph()
    node_id = data.get("id")
    original_len = len(graph["nodes"])
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != node_id]
    graph["edges"] = [
        e for e in graph["edges"]
        if e["source"] != node_id and e["target"] != node_id
    ]
    if len(graph["nodes"]) < original_len:
        _save_graph(graph)
        return True
    return False


def handle_flag_node(data: dict) -> bool:
    """Flag a node for re-investigation by adding a linked question node."""
    graph = _load_graph()
    node_id = data.get("id")
    target_node = None
    for n in graph["nodes"]:
        if n["id"] == node_id:
            target_node = n
            break
    if not target_node:
        return False

    # Create a question node linked to the flagged node
    q_id = uuid.uuid4().hex[:12]
    question = {
        "id": q_id,
        "label": f"Re-investigate: {target_node['label']}",
        "type": "question",
        "description": data.get("reason", f"User flagged '{target_node['label']}' for re-investigation."),
        "confidence": 0.0,
        "provenance": {
            "session_id": "user",
            "subagent": "mind_map_ui",
            "mode": "direction",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "metadata": {"url": None, "source_type": None, "user_added": True},
    }
    edge = {
        "id": uuid.uuid4().hex[:12],
        "source": q_id,
        "target": node_id,
        "relationship": "challenged_by",
        "weight": 1.0,
        "provenance": question["provenance"],
    }
    graph["nodes"].append(question)
    graph["edges"].append(edge)

    # Lower the flagged node's confidence
    target_node["confidence"] = max(0.0, target_node.get("confidence", 0.5) - 0.2)

    _save_graph(graph)
    return True


def handle_resume_session(data: dict) -> dict:
    """User clicked 'Proceed to Synthesis'. Write resume signal to state.json."""
    session_id = data.get("session_id")
    if not session_id:
        return {"error": "session_id required"}

    state_path = DATA_DIR / "sessions" / f"session_{session_id}" / "state.json"
    if not state_path.exists():
        return {"error": "no active session"}

    state = json.loads(state_path.read_text())
    if state.get("phase") != "awaiting_user_input":
        return {"error": f"session not paused (phase={state.get('phase')})"}

    state["phase"] = "resume_synthesis"
    state["resumed_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2))
    return {"ok": True, "session_id": session_id}


HANDLERS = {
    "add_node": handle_add_node,
    "update_node": handle_update_node,
    "add_edge": handle_add_edge,
    "delete_node": handle_delete_node,
    "flag_node": handle_flag_node,
    "resume_session": handle_resume_session,
}


# ---------------------------------------------------------------------------
# Session state broadcasting (Phase 4: Analysis Mode)
# ---------------------------------------------------------------------------

_last_session_state: dict | None = None


def _find_active_session_state() -> dict | None:
    """Check for any session in awaiting_user_input phase."""
    sessions_dir = DATA_DIR / "sessions"
    if not sessions_dir.exists():
        return None
    for session_dir in sorted(sessions_dir.iterdir(), reverse=True):
        state_path = session_dir / "state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                if state.get("phase") == "awaiting_user_input":
                    return state
            except (json.JSONDecodeError, OSError):
                continue
    return None


async def broadcast_session_state() -> None:
    """Broadcast active session state to all connected clients."""
    global _last_session_state
    state = _find_active_session_state()
    if state != _last_session_state:
        _last_session_state = state
        payload = json.dumps({"type": "session_state", "data": state})
        if clients:
            await asyncio.gather(
                *(c.send(payload) for c in clients),
                return_exceptions=True,
            )


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

async def ws_handler(websocket: websockets.asyncio.server.ServerConnection) -> None:
    clients.add(websocket)
    try:
        # Send current graph state on connect
        graph = _load_graph()
        await websocket.send(json.dumps({"type": "graph_update", "data": graph}))

        # Send active session state if any (Phase 4 analysis mode)
        session_state = _find_active_session_state()
        if session_state:
            await websocket.send(json.dumps({"type": "session_state", "data": session_state}))

        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"type": "error", "data": "Invalid JSON"}))
                continue

            msg_type = msg.get("type")
            handler = HANDLERS.get(msg_type)
            if handler:
                result = handler(msg.get("data", {}))
                # Broadcast updated graph to ALL clients (including sender)
                await broadcast_graph()
            else:
                await websocket.send(json.dumps({
                    "type": "error",
                    "data": f"Unknown message type: {msg_type}",
                }))
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)


async def broadcast_graph() -> None:
    global _last_graph_hash
    graph = _load_graph()
    _last_graph_hash = _graph_hash()
    payload = json.dumps({"type": "graph_update", "data": graph})
    if clients:
        await asyncio.gather(
            *(c.send(payload) for c in clients),
            return_exceptions=True,
        )


# ---------------------------------------------------------------------------
# File watcher — polls graph.json for agent-side changes
# ---------------------------------------------------------------------------

async def watch_graph() -> None:
    global _last_graph_hash
    _last_graph_hash = _graph_hash()
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        current = _graph_hash()
        if current != _last_graph_hash:
            await broadcast_graph()
        await broadcast_session_state()


# ---------------------------------------------------------------------------
# HTTP handler for static files (production mode)
# ---------------------------------------------------------------------------

async def http_handler(
    connection: websockets.asyncio.server.ServerConnection,
    request: websockets.http11.Request,
) -> websockets.http11.Response | None:
    """Serve static files for non-WebSocket HTTP requests.

    Called by websockets as process_request(connection, request).
    Return a Response to short-circuit the WebSocket handshake,
    or None to proceed with the handshake.
    """
    # Let WebSocket upgrade requests through
    if any(h.lower() == "upgrade" for h in request.headers.get_all("Connection")):
        return None

    path = request.path

    # API endpoint: graph data
    if path == "/api/graph":
        graph = _load_graph()
        body = json.dumps(graph).encode()
        return websockets.http11.Response(
            200, "OK",
            websockets.datastructures.Headers({
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            }),
            body,
        )

    # Static file serving from dist/
    if not DIST_DIR.exists():
        return None  # Let WebSocket handler take over

    if path == "/":
        path = "/index.html"

    file_path = DIST_DIR / path.lstrip("/")
    if file_path.is_file():
        content_type, _ = mimetypes.guess_type(str(file_path))
        body = file_path.read_bytes()
        return websockets.http11.Response(
            200, "OK",
            websockets.datastructures.Headers({
                "Content-Type": content_type or "application/octet-stream",
                "Cache-Control": "no-cache" if path.endswith(".html") else "max-age=3600",
            }),
            body,
        )

    # SPA fallback — serve index.html for unknown routes
    index = DIST_DIR / "index.html"
    if index.is_file():
        body = index.read_bytes()
        return websockets.http11.Response(
            200, "OK",
            websockets.datastructures.Headers({"Content-Type": "text/html"}),
            body,
        )

    return websockets.http11.Response(404, "Not Found", websockets.datastructures.Headers({}), b"Not found")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(dev: bool = False) -> None:
    origins: list | None = None
    if dev:
        origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
        print("Dev mode: allowing CORS from Vite dev server")

    server = await ws_serve(
        ws_handler,
        "localhost",
        PORT,
        process_request=http_handler if not dev else None,
        origins=origins if dev else None,
    )

    print(f"WebSocket server: ws://localhost:{PORT}")
    if not dev and DIST_DIR.exists():
        print(f"Mind map UI:      http://localhost:{PORT}")
    elif dev:
        print("Run 'npm run dev' in visualization/web/ for the React UI")

    # Start file watcher
    asyncio.create_task(watch_graph())

    await server.serve_forever()


if __name__ == "__main__":
    dev_mode = "--dev" in sys.argv
    asyncio.run(main(dev=dev_mode))
