"""Direction Finding (L3) — Phase 5 orchestration.

Standalone entry point that examines the knowledge graph for structural gaps
and proposes new research directions. No Socratic review — the user is the
Socratic partner.

Usage:
    python -m research_agent.direction                     # full graph
    python -m research_agent.direction --session abc123    # focus on session
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from research_agent.config import (
    DIRECTION_MODEL,
    DIRECTION_MAX_TURNS,
    GRAPH_PATH,
    session_graph_path,
)
from research_agent.graph.analysis import analyze_graph_structure
from research_agent.graph.store import load_graph, load_workspace, snapshot_graph
from research_agent.graph.summarizer import summarize_graph
from research_agent.prompts import DIRECTION_AGENT_PROMPT

MCP_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "mcp_server.py")


def _summarize_session_subgraph(graph, session_id: str) -> str:
    """Filter graph to a session's nodes + 1-hop neighbors and summarize."""
    session_node_ids = {
        n["id"] for n in graph.nodes
        if n.get("provenance", {}).get("session_id") == session_id
        and not n.get("withdrawn")
    }
    if not session_node_ids:
        return f"No nodes found for session {session_id}."

    # Expand to 1-hop neighbors
    neighbor_ids = set(session_node_ids)
    for e in graph.edges:
        if e["source"] in session_node_ids:
            neighbor_ids.add(e["target"])
        if e["target"] in session_node_ids:
            neighbor_ids.add(e["source"])

    # Summarize
    nodes = [n for n in graph.nodes if n["id"] in neighbor_ids and not n.get("withdrawn")]
    from collections import Counter
    type_counts = Counter(n["type"] for n in nodes)

    lines = [
        f"Session {session_id}: {len(session_node_ids)} direct nodes, "
        f"{len(neighbor_ids) - len(session_node_ids)} neighbors.",
        "Types: " + ", ".join(f"{c} {t}" for t, c in type_counts.most_common()),
        "",
        "Key session nodes:",
    ]
    for n in nodes:
        if n["id"] in session_node_ids and n["type"] in ("concept", "question", "decision", "direction"):
            lines.append(f"  - [{n['id']}] {n['label']} ({n['type']}, conf={n.get('confidence', 0):.2f})")

    return "\n".join(lines)


def build_direction_options(session_id: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the Direction agent."""
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [MCP_SERVER_SCRIPT, "--session", session_id],
    }

    return ClaudeAgentOptions(
        model=DIRECTION_MODEL,
        tools=[],
        allowed_tools=[
            "mcp__research-graph__add_node",
            "mcp__research-graph__add_edge",
            "mcp__research-graph__update_node",
            "mcp__research-graph__get_graph_summary",
            "mcp__research-graph__get_neighborhood",
            "mcp__research-graph__query_graph",
        ],
        mcp_servers={"research-graph": mcp_server_config},
        max_turns=DIRECTION_MAX_TURNS,
        permission_mode="bypassPermissions",
    )


async def run_direction_finding(
    session_id: str | None = None,
    session_ids: list[str] | None = None,
) -> None:
    """Run direction finding on the knowledge graph.

    If session_ids is provided, loads a workspace composite of those sessions.
    Otherwise falls back to a single session graph or the global graph.
    """
    dir_session_id = f"dir-{uuid.uuid4().hex[:8]}"

    # Snapshot before modifications
    snapshot_graph(dir_session_id)

    # Load graph: workspace composite > single session > global
    if session_ids:
        graph = load_workspace(session_ids)
    elif session_id:
        sgp = session_graph_path(session_id)
        graph = load_graph(sgp) if sgp.exists() else load_graph()
    else:
        graph = load_graph()
    # Ensure direction session directory + graph.json exist
    from research_agent.config import SESSIONS_DIR
    dir_session_dir = SESSIONS_DIR / f"session_{dir_session_id}"
    dir_session_dir.mkdir(parents=True, exist_ok=True)
    dir_graph_path = session_graph_path(dir_session_id)
    if not dir_graph_path.exists():
        import json as _json
        dir_graph_path.write_text(_json.dumps({"nodes": [], "edges": []}, indent=2))

    print(f"Loaded graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges\n")

    print("=" * 60)
    print("PHASE: Structural Analysis")
    print("=" * 60 + "\n")

    analysis_report = analyze_graph_structure(graph, session_id)
    print(analysis_report)

    graph_summary = summarize_graph(graph)

    # Optional session context
    session_context_block = ""
    if session_id:
        session_context = _summarize_session_subgraph(graph, session_id)
        session_context_block = f"\n## Session Focus\n{session_context}\n"

    # Build system prompt
    system_prompt = DIRECTION_AGENT_PROMPT.format(
        session_id=dir_session_id,
        session_context_block=session_context_block,
        analysis_report=analysis_report,
        graph_summary=graph_summary,
    )

    # Run direction agent
    print("\n" + "=" * 60)
    print("PHASE: Direction Finding")
    print("=" * 60 + "\n")

    options = build_direction_options(dir_session_id)
    # Inject the system prompt
    options = ClaudeAgentOptions(
        model=options.model,
        system_prompt=system_prompt,
        tools=options.tools,
        allowed_tools=options.allowed_tools,
        mcp_servers=options.mcp_servers,
        max_turns=options.max_turns,
        permission_mode=options.permission_mode,
    )

    result_text = []
    async for message in query(
        prompt="Analyze the graph structure and propose research directions.",
        options=options,
    ):
        if isinstance(message, ResultMessage):
            if hasattr(message, "result") and message.result:
                result_text.append(message.result)
                print(message.result, end="", flush=True)
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    result_text.append(block.text)
                    print(block.text, end="", flush=True)

    print("\n\n" + "=" * 60)
    print(f"Direction finding complete. Session: {dir_session_id}")
    print("=" * 60)


def main() -> None:
    """Entry point — parse args and run direction finding."""
    session_id = None
    args = sys.argv[1:]
    if "--session" in args:
        idx = args.index("--session")
        if idx + 1 < len(args):
            session_id = args[idx + 1]

    if session_id:
        print(f"Direction finding focused on session: {session_id}")
    else:
        print("Direction finding on full graph")

    asyncio.run(run_direction_finding(session_id))


if __name__ == "__main__":
    main()
