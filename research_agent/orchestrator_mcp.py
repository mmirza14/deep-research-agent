#!/usr/bin/env python3
"""MCP orchestration server for Claude Code integration.

Exposes tools for session management, research question refinement,
live status, and document retrieval. Registered with Claude Code as
an MCP server so users can say "research X" in conversation.

Usage:
    python3 research_agent/orchestrator_mcp.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
VIS_SERVER = PROJECT_ROOT / "visualization" / "server.py"

WS_PORT = 8420

mcp = FastMCP("research-orchestrator")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / f"session_{session_id}"


def _is_server_running() -> bool:
    """Check if the visualization server is listening on its port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", WS_PORT)) == 0


def _ensure_server() -> None:
    """Start the visualization server if it's not already running."""
    if _is_server_running():
        return
    log_path = DATA_DIR / "server.log"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "w")
    subprocess.Popen(
        [sys.executable, "-m", "visualization.server"],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    # Give it a moment to start
    import time
    time.sleep(2)


def _list_sessions() -> list[dict]:
    """Scan data/sessions/ and return metadata for each session."""
    if not SESSIONS_DIR.exists():
        return []
    sessions = []
    for sd in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if not sd.is_dir() or not sd.name.startswith("session_"):
            continue
        sid = sd.name.removeprefix("session_")
        graph_path = sd / "graph.json"
        state_path = sd / "state.json"
        pending_path = sd / "pending_research.json"

        node_count = edge_count = 0
        if graph_path.exists():
            try:
                g = json.loads(graph_path.read_text())
                node_count = len(g.get("nodes", []))
                edge_count = len(g.get("edges", []))
            except (json.JSONDecodeError, OSError):
                pass

        status = "unknown"
        phase = detail = None
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
                phase = state.get("phase")
                detail = state.get("detail")
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

        question = ""
        if pending_path.exists():
            try:
                pending = json.loads(pending_path.read_text())
                question = pending.get("research_question", "")
            except (json.JSONDecodeError, OSError):
                pass

        has_lit_review = (sd / "literature_review.md").exists()
        has_insights = (sd / "insights_report.md").exists()

        created_at = datetime.fromtimestamp(
            sd.stat().st_ctime, tz=timezone.utc
        ).isoformat()

        sessions.append({
            "session_id": sid,
            "question": question,
            "status": status,
            "phase": phase,
            "detail": detail,
            "created_at": created_at,
            "node_count": node_count,
            "edge_count": edge_count,
            "has_lit_review": has_lit_review,
            "has_insights": has_insights,
        })
    return sessions


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def refine_research_question(topic: str) -> dict:
    """Take a vague topic and return a refined, scoped research question.

    Returns a structured result with the original topic, refined question,
    scope boundaries, exclusions, and suggested sub-questions.
    """
    import asyncio
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
    from research_agent.config import REFINEMENT_MODEL
    from research_agent.prompts import QUESTION_REFINEMENT_PROMPT

    options = ClaudeAgentOptions(
        model=REFINEMENT_MODEL,
        system_prompt=QUESTION_REFINEMENT_PROMPT,
        tools=[],
        allowed_tools=[],
        max_turns=1,
        permission_mode="bypassPermissions",
    )

    result_text = []

    async def _run():
        async for message in query(prompt=topic, options=options):
            if isinstance(message, ResultMessage):
                if hasattr(message, "result") and message.result:
                    result_text.append(message.result)
            elif hasattr(message, "content"):
                for block in getattr(message, "content", []):
                    if hasattr(block, "text"):
                        result_text.append(block.text)

    asyncio.run(_run())
    raw = "\n".join(result_text)

    # Try to parse as JSON if the model returned structured output
    try:
        # Find JSON block in the response
        if "```json" in raw:
            json_str = raw.split("```json")[1].split("```")[0].strip()
        elif raw.strip().startswith("{"):
            json_str = raw.strip()
        else:
            json_str = None

        if json_str:
            parsed = json.loads(json_str)
            parsed["original"] = topic
            return parsed
    except (json.JSONDecodeError, IndexError):
        pass

    # Fallback: return the raw text as the refined question
    return {
        "original": topic,
        "refined": raw.strip(),
        "scope": "",
        "exclusions": [],
        "suggested_sub_questions": [],
    }


@mcp.tool()
def start_research(question: str, session_name: str = "") -> dict:
    """Start a new research session.

    Starts the visualization server if not running, creates a session,
    spawns the research agent, and opens the browser.

    Returns the session_id and URL to watch progress.
    """
    _ensure_server()

    session_id = uuid.uuid4().hex[:8]
    session_dir = _session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)

    # Initialize empty session graph
    (session_dir / "graph.json").write_text(
        json.dumps({"nodes": [], "edges": []}, indent=2)
    )

    # Write pending research metadata
    pending = {
        "research_question": question,
        "session_name": session_name or None,
        "origin_node_id": None,
        "origin_label": None,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (session_dir / "pending_research.json").write_text(
        json.dumps(pending, indent=2)
    )

    # Spawn research agent
    log_path = session_dir / "agent.log"
    log_file = open(log_path, "w")
    subprocess.Popen(
        [sys.executable, "-m", "research_agent.agent", question, "--session", session_id],
        cwd=str(PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    url = f"http://localhost:{WS_PORT}"
    webbrowser.open(url)

    return {
        "session_id": session_id,
        "question": question,
        "url": url,
    }


@mcp.tool()
def get_session_status(session_id: str) -> dict:
    """Get the current status of a research session.

    Returns the current phase, detail message, node/edge counts,
    start time, and elapsed time.
    """
    sd = _session_dir(session_id)
    if not sd.exists():
        return {"error": f"Session {session_id} not found"}

    state_path = sd / "state.json"
    graph_path = sd / "graph.json"
    pending_path = sd / "pending_research.json"

    phase = "unknown"
    detail = ""
    started_at = None

    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            phase = state.get("phase", "unknown")
            detail = state.get("detail", "")
            started_at = state.get("updated_at")
        except (json.JSONDecodeError, OSError):
            pass

    if pending_path.exists():
        try:
            pending = json.loads(pending_path.read_text())
            if not started_at:
                started_at = pending.get("created_at")
        except (json.JSONDecodeError, OSError):
            pass

    node_count = edge_count = 0
    if graph_path.exists():
        try:
            g = json.loads(graph_path.read_text())
            node_count = len(g.get("nodes", []))
            edge_count = len(g.get("edges", []))
        except (json.JSONDecodeError, OSError):
            pass

    elapsed = ""
    if started_at:
        try:
            start = datetime.fromisoformat(started_at)
            delta = datetime.now(timezone.utc) - start
            minutes = int(delta.total_seconds() / 60)
            elapsed = f"{minutes}m" if minutes > 0 else f"{int(delta.total_seconds())}s"
        except (ValueError, TypeError):
            pass

    return {
        "session_id": session_id,
        "phase": phase,
        "detail": detail,
        "node_count": node_count,
        "edge_count": edge_count,
        "started_at": started_at,
        "elapsed": elapsed,
    }


@mcp.tool()
def list_sessions() -> dict:
    """List all research sessions with their status and metadata."""
    return {"sessions": _list_sessions()}


@mcp.tool()
def get_document(session_id: str, doc_type: str) -> dict:
    """Retrieve a document from a research session.

    doc_type can be: literature_review, insights, transcript_findings,
    transcript_synthesis, changelog_findings, changelog_synthesis
    """
    sd = _session_dir(session_id)
    if not sd.exists():
        return {"error": f"Session {session_id} not found"}

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
        return {"error": f"Unknown doc_type: {doc_type}. Valid: {', '.join(doc_map.keys())}"}

    doc_path = sd / filename
    if not doc_path.exists():
        return {"error": f"Document not found: {filename}"}

    content = doc_path.read_text()
    return {
        "session_id": session_id,
        "doc_type": doc_type,
        "title": doc_type.replace("_", " ").title(),
        "content": content,
    }


@mcp.tool()
def resume_session(session_id: str) -> dict:
    """Resume a paused research session (proceed from analysis mode to synthesis)."""
    sd = _session_dir(session_id)
    state_path = sd / "state.json"

    if not state_path.exists():
        return {"error": "No active session state found"}

    try:
        state = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"error": "Could not read session state"}

    if state.get("phase") != "awaiting_user_input":
        return {"error": f"Session not paused (phase={state.get('phase')})"}

    state["phase"] = "resume_synthesis"
    state["resumed_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2))
    return {"ok": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
