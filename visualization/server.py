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
from dataclasses import dataclass, field
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


def handle_start_research(data: dict) -> dict:
    """Start a new L1 research session from a direction/question node."""
    import subprocess

    node_id = data.get("node_id")
    description = data.get("description", "")
    label = data.get("label", "")
    if not description:
        return {"error": "description required"}

    session_id = uuid.uuid4().hex[:8]
    session_dir = DATA_DIR / "sessions" / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Write pending research metadata
    pending = {
        "research_question": description,
        "origin_node_id": node_id,
        "origin_label": label,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (session_dir / "pending_research.json").write_text(json.dumps(pending, indent=2))

    # Spawn research agent as background process, logging to session dir
    log_path = session_dir / "agent.log"
    log_file = open(log_path, "w")
    subprocess.Popen(
        ["python3", "-m", "research_agent.agent", description, "--session", session_id],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    print(f"Started research session {session_id} from node {node_id}: {label}")
    return {"ok": True, "session_id": session_id}


HANDLERS = {
    "add_node": handle_add_node,
    "update_node": handle_update_node,
    "add_edge": handle_add_edge,
    "delete_node": handle_delete_node,
    "flag_node": handle_flag_node,
    "resume_session": handle_resume_session,
    "start_research": handle_start_research,
}


# ---------------------------------------------------------------------------
# Single-node chat (Phase 5)
# ---------------------------------------------------------------------------

@dataclass
class ChatSession:
    chat_id: str
    node_id: str
    context: str  # Pre-built context: node data + 2-hop neighborhood + graph summary
    history: list = field(default_factory=list)  # [{"role": "user"/"assistant", "text": "..."}]

active_chats: dict[str, ChatSession] = {}

MAX_CHAT_HISTORY = 10  # Max exchanges to keep (20 messages)


def _build_chat_context(node_id: str) -> tuple[dict | None, str]:
    """Build context string for a chat session. Returns (node_data, context_text)."""
    graph = _load_graph()
    node_data = None
    for n in graph["nodes"]:
        if n["id"] == node_id:
            node_data = n
            break

    if not node_data:
        return None, ""

    # 2-hop neighborhood
    visited = {node_id}
    frontier = {node_id}
    for _ in range(2):
        next_frontier = set()
        for e in graph["edges"]:
            if e["source"] in frontier:
                next_frontier.add(e["target"])
            if e["target"] in frontier:
                next_frontier.add(e["source"])
        next_frontier -= visited
        visited |= next_frontier
        frontier = next_frontier

    neighborhood_nodes = [n for n in graph["nodes"] if n["id"] in visited]
    neighborhood_edges = [
        e for e in graph["edges"]
        if e["source"] in visited and e["target"] in visited
    ]

    # Graph summary (simple version — avoid importing agent code in server)
    from collections import Counter
    active = [n for n in graph["nodes"] if not n.get("withdrawn")]
    type_counts = Counter(n["type"] for n in active)
    summary_lines = [f"Graph: {len(active)} nodes, {len(graph['edges'])} edges."]
    for t, c in type_counts.most_common():
        summary_lines.append(f"  {t}: {c}")

    context = json.dumps({
        "node": node_data,
        "neighborhood": {"nodes": neighborhood_nodes, "edges": neighborhood_edges},
        "graph_summary": "\n".join(summary_lines),
    }, indent=2)

    return node_data, context


def handle_chat_start(data: dict) -> dict:
    """Initialize a chat session for a node."""
    node_id = data.get("node_id")
    if not node_id:
        return {"error": "node_id required"}

    node_data, context = _build_chat_context(node_id)
    if not node_data:
        return {"error": f"Node {node_id} not found"}

    chat_id = uuid.uuid4().hex[:8]
    active_chats[chat_id] = ChatSession(
        chat_id=chat_id,
        node_id=node_id,
        context=context,
        history=[],
    )

    print(f"Chat started: {chat_id} for node {node_id} ({node_data.get('label', '')})")
    return {"chat_id": chat_id, "node": node_data}


def handle_chat_end(data: dict) -> dict:
    """End a chat session."""
    chat_id = data.get("chat_id")
    if chat_id in active_chats:
        del active_chats[chat_id]
        print(f"Chat ended: {chat_id}")
        return {"ok": True}
    return {"error": "chat not found"}


async def handle_chat_message(data: dict, websocket) -> None:
    """Handle a chat message — runs agent and streams response back."""
    chat_id = data.get("chat_id")
    text = data.get("text", "").strip()

    if not chat_id or chat_id not in active_chats:
        await websocket.send(json.dumps({
            "type": "chat_error",
            "data": {"chat_id": chat_id, "error": "Chat session not found"},
        }))
        return

    if not text:
        return

    session = active_chats[chat_id]
    session.history.append({"role": "user", "text": text})

    # Trim history to last N exchanges
    if len(session.history) > MAX_CHAT_HISTORY * 2:
        session.history = session.history[-(MAX_CHAT_HISTORY * 2):]

    # Build the prompt
    history_text = ""
    if session.history[:-1]:  # exclude the current message
        lines = []
        for msg in session.history[:-1]:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{prefix}: {msg['text']}")
        history_text = "\n".join(lines)

    # Parse context JSON for prompt injection
    try:
        ctx = json.loads(session.context)
    except json.JSONDecodeError:
        ctx = {"node": {}, "neighborhood": {}, "graph_summary": ""}

    from research_agent.prompts import NODE_CHAT_PROMPT
    system_prompt = NODE_CHAT_PROMPT.format(
        node_json=json.dumps(ctx.get("node", {}), indent=2),
        neighborhood_json=json.dumps(ctx.get("neighborhood", {}), indent=2),
        graph_summary=ctx.get("graph_summary", ""),
        history_text=history_text or "(No prior conversation)",
    )

    # Run the agent in a thread to avoid blocking the event loop
    try:
        full_response = await asyncio.get_event_loop().run_in_executor(
            None, _run_chat_agent, system_prompt, text
        )
    except Exception as e:
        await websocket.send(json.dumps({
            "type": "chat_error",
            "data": {"chat_id": chat_id, "error": str(e)},
        }))
        return

    # Send response back to client
    await websocket.send(json.dumps({
        "type": "chat_response",
        "data": {"chat_id": chat_id, "text": full_response or "(No response)"},
    }))

    # Store response in history
    if full_response:
        session.history.append({"role": "assistant", "text": full_response})


def _run_chat_agent(system_prompt: str, user_text: str) -> str:
    """Run the chat agent synchronously (called via run_in_executor).

    Since claude_agent_sdk.query() is async, we need to run it in a new event loop.
    We collect all output and send it as a single response (no streaming to avoid
    cross-thread WebSocket issues).
    """
    import asyncio as _asyncio

    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    from research_agent.config import CHAT_MODEL, CHAT_MAX_TURNS

    mcp_server_script = str(Path(__file__).resolve().parent.parent / "research_agent" / "mcp_server.py")
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [mcp_server_script],
    }

    options = ClaudeAgentOptions(
        model=CHAT_MODEL,
        system_prompt=system_prompt,
        tools=[],
        allowed_tools=[
            "mcp__research-graph__get_graph_summary",
            "mcp__research-graph__get_neighborhood",
            "mcp__research-graph__query_graph",
        ],
        mcp_servers={"research-graph": mcp_server_config},
        max_turns=CHAT_MAX_TURNS,
        permission_mode="bypassPermissions",
    )

    result_parts = []

    async def _run():
        async for message in query(prompt=user_text, options=options):
            if isinstance(message, ResultMessage):
                if hasattr(message, "result") and message.result:
                    result_parts.append(message.result)
            elif hasattr(message, "content"):
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        result_parts.append(block.text)

    _asyncio.run(_run())
    return "\n".join(result_parts)


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
            msg_data = msg.get("data", {})

            # Chat messages need special handling (async, per-client)
            if msg_type == "chat_message":
                await handle_chat_message(msg_data, websocket)
                continue

            if msg_type == "chat_start":
                result = handle_chat_start(msg_data)
                await websocket.send(json.dumps({"type": "chat_ready", "data": result}))
                continue

            if msg_type == "chat_end":
                result = handle_chat_end(msg_data)
                continue

            handler = HANDLERS.get(msg_type)
            if handler:
                result = handler(msg_data)
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
    if dev:
        print("Dev mode: allowing CORS from Vite dev server")

    # Allow all origins — this is a localhost-only server
    server = await ws_serve(
        ws_handler,
        "localhost",
        PORT,
        process_request=http_handler if not dev else None,
        origins=None,
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
