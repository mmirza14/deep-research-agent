"""WebSocket server for real-time mind map sync.

Supports per-session graphs. Each client can view a single session or a
workspace composite of multiple sessions. Watches the active session's
graph.json for agent-side changes and broadcasts to all connected browser
clients.

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
import shutil
import sys
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import websockets
from websockets.asyncio.server import serve as ws_serve

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
GRAPH_PATH = DATA_DIR / "graph.json"  # legacy global graph
DIST_DIR = Path(__file__).resolve().parent / "web" / "dist"

PORT = 8420
POLL_INTERVAL = 0.5  # seconds between graph.json checks

# Track connected clients and their active session
clients: set[websockets.asyncio.server.ServerConnection] = set()

# Global active session ID (simple v1: shared across all clients)
_active_session_id: str | None = None
_workspace_session_ids: list[str] = []

# Last known hash for change detection
_last_graph_hash: str = ""

# Spawned agent processes: session_id -> (Popen, spawn_time)
_spawned_processes: dict[str, tuple] = {}

# Notification queue for async broadcast (filled by sync handlers, flushed by ws_handler)
_pending_notifications: list[dict] = []


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _session_graph_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"session_{session_id}" / "graph.json"


def _active_graph_path() -> Path:
    """Return the graph path for the currently active view."""
    if _workspace_session_ids:
        return Path("")  # workspace mode — no single file
    if _active_session_id:
        return _session_graph_path(_active_session_id)
    return GRAPH_PATH  # legacy fallback


def _list_sessions() -> list[dict]:
    """Scan data/sessions/ and return metadata for each session."""
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for session_dir in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if not session_dir.is_dir() or not session_dir.name.startswith("session_"):
            continue
        sid = session_dir.name.removeprefix("session_")
        graph_path = session_dir / "graph.json"
        state_path = session_dir / "state.json"
        pending_path = session_dir / "pending_research.json"

        # Count nodes
        node_count = 0
        edge_count = 0
        if graph_path.exists():
            try:
                g = json.loads(graph_path.read_text())
                node_count = len(g.get("nodes", []))
                edge_count = len(g.get("edges", []))
            except (json.JSONDecodeError, OSError):
                pass

        # Read status
        status = "unknown"
        phase = None
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                phase = state.get("phase")
                if phase == "awaiting_user_input":
                    status = "paused"
                elif phase == "complete":
                    status = "complete"
                elif phase == "error":
                    status = "error"
                else:
                    status = "running"
            except (json.JSONDecodeError, OSError):
                pass
        elif pending_path.exists():
            status = "running"

        # Read research question
        question = ""
        if pending_path.exists():
            try:
                pending = json.loads(pending_path.read_text())
                question = pending.get("research_question", "")
            except (json.JSONDecodeError, OSError):
                pass

        # Check for documents
        has_lit_review = (session_dir / "literature_review.md").exists()
        has_insights = (session_dir / "insights_report.md").exists()

        created_at = datetime.fromtimestamp(
            session_dir.stat().st_ctime, tz=timezone.utc
        ).isoformat()

        sessions.append({
            "session_id": sid,
            "question": question,
            "status": status,
            "phase": phase,
            "created_at": created_at,
            "node_count": node_count,
            "edge_count": edge_count,
            "has_lit_review": has_lit_review,
            "has_insights": has_insights,
        })
    return sessions


# ---------------------------------------------------------------------------
# Migration — split global graph.json into per-session graphs
# ---------------------------------------------------------------------------

def _migrate_global_graph() -> None:
    """If a global graph.json exists, split it into per-session graphs."""
    if not GRAPH_PATH.exists():
        return
    # Don't migrate if sessions already exist
    if SESSIONS_DIR.exists() and any(SESSIONS_DIR.iterdir()):
        return

    try:
        data = json.loads(GRAPH_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    if not nodes:
        return

    # Group nodes by provenance.session_id
    session_nodes: dict[str, list] = {}
    for node in nodes:
        sid = node.get("provenance", {}).get("session_id", "unknown")
        session_nodes.setdefault(sid, []).append(node)

    # Group edges — assign to session of source node
    node_session: dict[str, str] = {}
    for node in nodes:
        sid = node.get("provenance", {}).get("session_id", "unknown")
        node_session[node["id"]] = sid

    session_edges: dict[str, list] = {}
    for edge in edges:
        sid = node_session.get(edge.get("source"), "unknown")
        session_edges.setdefault(sid, []).append(edge)

    # Write per-session graphs
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    for sid, snodes in session_nodes.items():
        session_dir = SESSIONS_DIR / f"session_{sid}"
        session_dir.mkdir(parents=True, exist_ok=True)
        graph_data = {
            "nodes": snodes,
            "edges": session_edges.get(sid, []),
        }
        (session_dir / "graph.json").write_text(json.dumps(graph_data, indent=2))

    # Move original to legacy
    shutil.move(str(GRAPH_PATH), str(DATA_DIR / "graph_legacy.json"))
    print(f"Migrated global graph.json → {len(session_nodes)} per-session graphs")


# ---------------------------------------------------------------------------
# Graph I/O (session-aware)
# ---------------------------------------------------------------------------

def _load_graph() -> dict:
    """Load the graph for the active view (session, workspace, or legacy)."""
    if _workspace_session_ids:
        return _load_workspace(_workspace_session_ids)
    path = _active_graph_path()
    if not path.exists():
        return {"nodes": [], "edges": []}
    return json.loads(path.read_text())


def _load_workspace(session_ids: list[str]) -> dict:
    """Merge multiple session graphs into one composite."""
    seen_node_ids: set[str] = set()
    seen_edge_ids: set[str] = set()
    merged_nodes = []
    merged_edges = []
    for sid in session_ids:
        path = _session_graph_path(sid)
        if not path.exists():
            continue
        try:
            g = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for node in g.get("nodes", []):
            if node["id"] not in seen_node_ids:
                seen_node_ids.add(node["id"])
                merged_nodes.append(node)
        for edge in g.get("edges", []):
            if edge["id"] not in seen_edge_ids:
                seen_edge_ids.add(edge["id"])
                merged_edges.append(edge)
    return {"nodes": merged_nodes, "edges": merged_edges}


def _save_graph(data: dict) -> None:
    """Save to the active session's graph (not workspace mode)."""
    if _workspace_session_ids:
        return  # workspace is read-only composite
    path = _active_graph_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _graph_hash() -> str:
    if _workspace_session_ids:
        # Hash all workspace session graphs together
        h = hashlib.md5()
        for sid in _workspace_session_ids:
            p = _session_graph_path(sid)
            if p.exists():
                h.update(p.read_bytes())
        return h.hexdigest()
    path = _active_graph_path()
    if not path.exists():
        return ""
    return hashlib.md5(path.read_bytes()).hexdigest()


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

    _queue_notification("info", "Synthesis resumed", "Agent is processing your feedback.")

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
    session_dir = SESSIONS_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Initialize empty session graph
    (session_dir / "graph.json").write_text(json.dumps({"nodes": [], "edges": []}, indent=2))

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
    proc = subprocess.Popen(
        ["python3", "-m", "research_agent.agent", description, "--session", session_id],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Track for watchdog
    _spawned_processes[session_id] = (proc, datetime.now(timezone.utc))

    _queue_notification(
        "success",
        "Research session started",
        f"Exploring direction: {label[:60]}{'...' if len(label) > 60 else ''}",
    )

    print(f"Started research session {session_id} from node {node_id}: {label}")
    return {"ok": True, "session_id": session_id}


def handle_set_active_session(data: dict) -> dict:
    """Switch the active session for all clients."""
    global _active_session_id, _workspace_session_ids
    sid = data.get("session_id")
    if not sid:
        return {"error": "session_id required"}
    _active_session_id = sid
    _workspace_session_ids = []  # exit workspace mode
    return {"ok": True, "session_id": sid}


def handle_set_workspace(data: dict) -> dict:
    """Set workspace mode with multiple sessions."""
    global _workspace_session_ids, _active_session_id
    sids = data.get("session_ids", [])
    if not sids:
        return {"error": "session_ids required"}
    _workspace_session_ids = sids
    _active_session_id = None  # workspace mode
    return {"ok": True, "session_ids": sids}


def handle_list_sessions(data: dict) -> dict:
    """Return all sessions with metadata."""
    return {"sessions": _list_sessions()}


def handle_start_new_research(data: dict) -> dict:
    """Start a new research session from a question string (web UI home screen)."""
    import subprocess

    question = data.get("question", "").strip()
    if not question:
        return {"error": "question required"}

    session_id = uuid.uuid4().hex[:8]
    session_dir = SESSIONS_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Initialize empty session graph
    (session_dir / "graph.json").write_text(json.dumps({"nodes": [], "edges": []}, indent=2))

    # Write pending research metadata
    pending = {
        "research_question": question,
        "origin_node_id": None,
        "origin_label": None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (session_dir / "pending_research.json").write_text(json.dumps(pending, indent=2))

    # Spawn research agent
    log_path = session_dir / "agent.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        ["python3", "-m", "research_agent.agent", question, "--session", session_id],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Track for watchdog
    _spawned_processes[session_id] = (proc, datetime.now(timezone.utc))

    _queue_notification(
        "success",
        "Research session started",
        f"Researching: {question[:80]}{'...' if len(question) > 80 else ''}",
    )

    print(f"Started new research session {session_id}: {question}")
    return {"ok": True, "session_id": session_id, "question": question}


def handle_get_document(data: dict) -> dict:
    """Return a document's content from a session directory."""
    sid = data.get("session_id")
    doc_type = data.get("doc_type", "")
    if not sid or not doc_type:
        return {"error": "session_id and doc_type required"}

    doc_map = {
        "literature_review": "literature_review.md",
        "insights": "insights_report.md",
        "transcript_findings": "transcript_findings.md",
        "transcript_synthesis": "transcript_synthesis.md",
        "changelog_findings": "changelog_findings.md",
        "changelog_synthesis": "changelog_synthesis.md",
    }
    filename = doc_map.get(doc_type)
    if not filename:
        return {"error": f"Unknown doc_type: {doc_type}"}

    doc_path = SESSIONS_DIR / f"session_{sid}" / filename
    if not doc_path.exists():
        return {"error": f"Document not found: {filename}"}

    content = doc_path.read_text()
    return {
        "session_id": sid,
        "doc_type": doc_type,
        "title": doc_type.replace("_", " ").title(),
        "content": content,
    }


HANDLERS = {
    "add_node": handle_add_node,
    "update_node": handle_update_node,
    "add_edge": handle_add_edge,
    "delete_node": handle_delete_node,
    "flag_node": handle_flag_node,
    "resume_session": handle_resume_session,
    "start_research": handle_start_research,
    "set_active_session": handle_set_active_session,
    "set_workspace": handle_set_workspace,
    "list_sessions": handle_list_sessions,
    "start_new_research": handle_start_new_research,
    "get_document": handle_get_document,
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
    mcp_args = [mcp_server_script]
    if _active_session_id:
        mcp_args.extend(["--session", _active_session_id])
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": mcp_args,
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
# Session state broadcasting (Phase 4: Analysis Mode + Phase 1C: Live Phase)
# ---------------------------------------------------------------------------

_last_session_state: dict | None = None
_last_phase_per_session: dict[str, str] = {}  # session_id -> last known phase+detail hash

# Activity feed (Phase 2A): track previous graph snapshot for diffing
_last_graph_nodes: dict[str, dict] = {}  # node_id -> node dict (snapshot for diff)


NODE_TYPE_LABELS = {
    "concept": "discovered concept",
    "claim": "added claim",
    "source": "added source",
    "question": "raised question",
    "direction": "proposed direction",
    "decision": "recorded decision",
}


def _diff_graph_activities(graph: dict) -> list[dict]:
    """Compare current graph against last snapshot. Return activity entries for new/modified nodes."""
    activities = []
    now = datetime.now(timezone.utc).isoformat()
    current_nodes = {n["id"]: n for n in graph.get("nodes", [])}

    for nid, node in current_nodes.items():
        prev = _last_graph_nodes.get(nid)
        node_type = node.get("type", "concept")
        label = node.get("label", "Untitled")
        session_id = node.get("provenance", {}).get("session_id", "")

        if prev is None:
            # New node
            action_verb = NODE_TYPE_LABELS.get(node_type, f"added {node_type}")
            activities.append({
                "timestamp": node.get("provenance", {}).get("timestamp", now),
                "action": action_verb,
                "detail": label,
                "node_id": nid,
                "node_type": node_type,
                "session_id": session_id,
            })
        else:
            # Check for confidence change
            old_conf = prev.get("confidence")
            new_conf = node.get("confidence")
            if old_conf is not None and new_conf is not None and old_conf != new_conf:
                direction = "raised" if new_conf > old_conf else "lowered"
                activities.append({
                    "timestamp": now,
                    "action": f"confidence {direction}",
                    "detail": f"{label}: {old_conf:.2f} → {new_conf:.2f}",
                    "node_id": nid,
                    "node_type": node_type,
                    "session_id": session_id,
                })
            # Check for flagging
            if node.get("flagged") and not prev.get("flagged"):
                activities.append({
                    "timestamp": now,
                    "action": "flagged",
                    "detail": label,
                    "node_id": nid,
                    "node_type": node_type,
                    "session_id": session_id,
                })
            # Check for withdrawal
            if node.get("withdrawn") and not prev.get("withdrawn"):
                activities.append({
                    "timestamp": now,
                    "action": "withdrawn",
                    "detail": label,
                    "node_id": nid,
                    "node_type": node_type,
                    "session_id": session_id,
                })

    _last_graph_nodes.clear()
    _last_graph_nodes.update(current_nodes)
    return activities


async def broadcast_activities(graph: dict) -> None:
    """Diff the graph and broadcast activity entries to all clients."""
    activities = _diff_graph_activities(graph)
    if not activities or not clients:
        return
    for activity in activities:
        payload = json.dumps({"type": "activity", "data": activity})
        await asyncio.gather(
            *(c.send(payload) for c in clients),
            return_exceptions=True,
        )


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


def _scan_session_phases() -> dict[str, dict]:
    """Read state.json from all sessions and return {session_id: state_dict}."""
    result = {}
    sessions_dir = DATA_DIR / "sessions"
    if not sessions_dir.exists():
        return result
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir() or not session_dir.name.startswith("session_"):
            continue
        state_path = session_dir / "state.json"
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                sid = session_dir.name.removeprefix("session_")
                result[sid] = state
            except (json.JSONDecodeError, OSError):
                continue
    return result


async def broadcast_session_state() -> None:
    """Broadcast active session state (awaiting_user_input) to all connected clients."""
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


async def broadcast_phase_changes() -> None:
    """Detect phase changes in any session and broadcast agent_phase messages."""
    global _last_phase_per_session
    current_phases = _scan_session_phases()
    for sid, state in current_phases.items():
        phase = state.get("phase", "")
        detail = state.get("detail", "")
        key = f"{phase}:{detail}"
        if _last_phase_per_session.get(sid) != key:
            _last_phase_per_session[sid] = key
            # Count nodes for the phase message
            graph_path = _session_graph_path(sid)
            node_count = 0
            edge_count = 0
            if graph_path.exists():
                try:
                    g = json.loads(graph_path.read_text())
                    node_count = len(g.get("nodes", []))
                    edge_count = len(g.get("edges", []))
                except (json.JSONDecodeError, OSError):
                    pass
            phase_data = {
                "session_id": sid,
                "phase": phase,
                "detail": detail,
                "node_count": node_count,
                "edge_count": edge_count,
                "started_at": state.get("updated_at"),
            }
            payload = json.dumps({"type": "agent_phase", "data": phase_data})
            if clients:
                await asyncio.gather(
                    *(c.send(payload) for c in clients),
                    return_exceptions=True,
                )
            # Emit an activity entry for the phase transition
            activity_detail = detail if detail else phase.replace("_", " ").title()
            activity_payload = json.dumps({
                "type": "activity",
                "data": {
                    "timestamp": state.get("updated_at", datetime.now(timezone.utc).isoformat()),
                    "action": "phase transition",
                    "detail": activity_detail,
                    "node_type": "direction",
                    "session_id": sid,
                },
            })
            if clients:
                await asyncio.gather(
                    *(c.send(activity_payload) for c in clients),
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

                # Some handlers return data directly to the sender
                if msg_type == "list_sessions":
                    await websocket.send(json.dumps({
                        "type": "sessions_list", "data": result,
                    }))
                    continue
                if msg_type == "get_document":
                    await websocket.send(json.dumps({
                        "type": "document_content", "data": result,
                    }))
                    continue
                if msg_type == "start_new_research":
                    # Notify all clients
                    if result.get("ok"):
                        payload = json.dumps({
                            "type": "research_started",
                            "data": {"session_id": result["session_id"], "question": result["question"]},
                        })
                        await asyncio.gather(
                            *(c.send(payload) for c in clients),
                            return_exceptions=True,
                        )
                    else:
                        await websocket.send(json.dumps({"type": "error", "data": result}))
                    await broadcast_notifications()
                    continue
                if msg_type in ("set_active_session", "set_workspace"):
                    # After switching sessions, broadcast the new graph
                    await broadcast_graph()
                    continue

                # Send operation result to the originating client
                success = result is not None and result is not False
                op_label = msg_type.replace("_", " ")
                detail = ""
                if msg_type == "add_node" and isinstance(result, dict):
                    detail = result.get("label", "")
                elif msg_type == "delete_node":
                    detail = data.get("id", "")[:8]
                elif msg_type == "flag_node":
                    detail = data.get("id", "")[:8]
                elif msg_type == "add_edge":
                    detail = data.get("relationship", "")
                await websocket.send(json.dumps({
                    "type": "operation_result",
                    "data": {
                        "operation": msg_type,
                        "success": success,
                        "detail": detail if success else f"{op_label} failed",
                    },
                }))

                # Default: broadcast updated graph to ALL clients
                await broadcast_graph()

                # Flush any notifications queued by the handler
                await broadcast_notifications()
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
# Toast notifications (Phase 6A)
# ---------------------------------------------------------------------------

def _queue_notification(level: str, message: str, detail: str | None = None) -> None:
    """Queue a notification for broadcast on the next poll cycle.

    Called from synchronous handlers — the async poll loop flushes these.
    """
    _pending_notifications.append({
        "level": level,
        "message": message,
        "detail": detail,
    })


async def broadcast_notifications() -> None:
    """Flush any queued notifications to all connected clients."""
    while _pending_notifications:
        notif = _pending_notifications.pop(0)
        payload = json.dumps({"type": "notification", "data": notif})
        if clients:
            await asyncio.gather(
                *(c.send(payload) for c in clients),
                return_exceptions=True,
            )


async def check_spawned_processes() -> None:
    """Watchdog: check if any spawned agent processes have died unexpectedly."""
    dead = []
    for sid, (proc, spawn_time) in _spawned_processes.items():
        retcode = proc.poll()
        if retcode is not None:
            elapsed = (datetime.now(timezone.utc) - spawn_time).total_seconds()
            if retcode == 0:
                _queue_notification(
                    "success",
                    "Research complete",
                    f"Session {sid[:8]} finished successfully.",
                )
            else:
                _queue_notification(
                    "error",
                    "Agent process crashed",
                    f"Session {sid[:8]} exited with code {retcode} after {int(elapsed)}s.",
                )
            dead.append(sid)
    for sid in dead:
        del _spawned_processes[sid]


# ---------------------------------------------------------------------------
# File watcher — polls graph.json for agent-side changes
# ---------------------------------------------------------------------------

async def watch_graph() -> None:
    global _last_graph_hash
    _last_graph_hash = _graph_hash()
    # Initialize activity diff baseline
    _diff_graph_activities(_load_graph())
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        current = _graph_hash()
        if current != _last_graph_hash:
            graph = _load_graph()
            await broadcast_activities(graph)
            await broadcast_graph()
        await broadcast_session_state()
        await broadcast_phase_changes()
        await check_spawned_processes()
        await broadcast_notifications()


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
    # Run migration on startup (idempotent)
    _migrate_global_graph()

    # Auto-select the most recent session if none is active
    global _active_session_id
    if not _active_session_id:
        sessions = _list_sessions()
        if sessions:
            _active_session_id = sessions[0]["session_id"]

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
        url = f"http://localhost:{PORT}"
        print(f"Mind map UI:      {url}")
        webbrowser.open(url)
    elif dev:
        print("Run 'npm run dev' in visualization/web/ for the React UI")

    # Start file watcher
    asyncio.create_task(watch_graph())

    await server.serve_forever()


if __name__ == "__main__":
    dev_mode = "--dev" in sys.argv
    asyncio.run(main(dev=dev_mode))
