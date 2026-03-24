"""Lead agent and research orchestration for Phase 1 (Walking Skeleton).

Uses claude-agent-sdk's query() function with:
- A stdio MCP server for graph tools (shared across lead + subagents)
- AgentDefinition for researcher subagents
- WebSearch and WebFetch as built-in tools
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from research_agent.config import (
    LEAD_MODEL,
    RESEARCHER_MODEL,
    MAX_TURNS,
)
from research_agent.graph.store import snapshot_graph
from research_agent.prompts import LEAD_AGENT, RESEARCHER_AGENT_DESCRIPTION

# Path to the standalone MCP server script
MCP_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "mcp_server.py")


def build_options(session_id: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with stdio MCP server and researcher subagents."""
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [MCP_SERVER_SCRIPT],
    }

    return ClaudeAgentOptions(
        model=LEAD_MODEL,
        system_prompt=LEAD_AGENT.format(session_id=session_id),
        tools=["WebSearch", "WebFetch", "Agent"],
        allowed_tools=[
            "WebSearch",
            "WebFetch",
            "Agent",
            "mcp__research-graph__add_node",
            "mcp__research-graph__add_edge",
            "mcp__research-graph__update_node",
            "mcp__research-graph__get_graph_summary",
            "mcp__research-graph__get_neighborhood",
        ],
        mcp_servers={"research-graph": mcp_server_config},
        agents={
            "researcher": AgentDefinition(
                description=RESEARCHER_AGENT_DESCRIPTION,
                prompt="",  # prompt is passed at spawn time via the Agent tool
                model=RESEARCHER_MODEL,
                tools=["WebSearch", "WebFetch"],
                mcpServers=["research-graph"],
            ),
        },
        max_turns=MAX_TURNS,
        permission_mode="bypassPermissions",
    )


async def run_research(question: str, session_id: str) -> None:
    """Run a research session by sending the question to the lead agent."""
    options = build_options(session_id)

    async for message in query(prompt=question, options=options):
        if isinstance(message, ResultMessage):
            print("\n--- Research Complete ---")
            if hasattr(message, "result") and message.result:
                print(message.result)
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    print(block.text, end="", flush=True)


def main() -> None:
    """Entry point — run the lead agent with a research question."""
    session_id = uuid.uuid4().hex[:8]

    # Snapshot existing graph before this session modifies it
    snapshot_graph(session_id)

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Enter your research question: ").strip()
        if not question:
            print("No question provided.")
            return

    print(f"Starting research session {session_id}")
    print(f"Query: {question}\n")

    asyncio.run(run_research(question, session_id))


if __name__ == "__main__":
    main()
