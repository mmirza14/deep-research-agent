"""Lead agent and research orchestration.

Phase 1: Walking skeleton — researchers search and write to graph.
Phase 2: Socratic review — Critic/Defender review findings before synthesis,
         then review synthesis before presenting to user.

Uses claude-agent-sdk's query() function with:
- A stdio MCP server for graph tools (shared across lead + subagents)
- AgentDefinition for researcher subagents
- WebSearch and WebFetch as built-in tools

Socratic review runs as a separate orchestration step outside the lead agent loop.
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
from research_agent.prompts import RESEARCHER_AGENT_DESCRIPTION
from research_agent.socratic.review import (
    run_findings_review,
    run_synthesis_review,
    get_session_findings,
    format_findings_for_review,
)

# Path to the standalone MCP server script
MCP_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "mcp_server.py")


# ---------------------------------------------------------------------------
# Lead agent prompt — updated for Phase 2 flow
# ---------------------------------------------------------------------------

LEAD_AGENT_PHASE2 = """\
You are the Lead Research Agent. You coordinate a multi-agent research system that builds a persistent knowledge graph.

Session ID: {session_id}

Your job:
1. Take the user's research question.
2. Call get_graph_summary to understand what's already known.
3. Decompose the question into 3-5 sub-topics suitable for parallel investigation.
4. For each sub-topic, spawn a "researcher" subagent using the Agent tool with a clear prompt describing what to investigate.
5. After all researchers complete, call get_graph_summary and STOP. Output your findings summary — do NOT present a final synthesis yet. The findings will be reviewed by a Socratic review process before you synthesize.

You have graph tools available (prefixed with mcp__research-graph__):
- add_node: Add nodes (concept, claim, source, question, direction, decision)
- add_edge: Link nodes with typed relationships
- update_node: Adjust confidence or description
- get_graph_summary: See current graph state
- get_neighborhood: Explore around a node

Before dispatching researchers, create a "question" node for the main research question, then "question" nodes for each sub-topic, linked via subtopic_of edges. Always pass session_id="{session_id}" when creating nodes/edges.

When spawning researcher subagents, give each one a focused prompt like:
"Research [specific sub-topic]. Search for high-quality sources, create source nodes, extract claims, and link them in the graph. Use session_id={session_id} and subagent=researcher-N for provenance."

After all researchers report back:
- Call get_graph_summary to see the full state
- Present a brief overview of what was found across sub-topics
- Note any contradictions or low-confidence areas
- STOP here — your findings summary is your final output for this phase
"""

SYNTHESIS_PROMPT = """\
You are the Lead Research Agent performing synthesis after Socratic review.

Session ID: {session_id}

The research findings have been through adversarial review. Some findings were retained, some were modified (confidence adjusted, descriptions refined), and some were challenged.

Socratic Review Summary:
{review_summary}

Current graph state (post-review):
{graph_summary}

Your task:
1. Synthesize the reviewed findings into a coherent analysis.
2. Create "decision" or "concept" nodes for your key conclusions, linked to supporting evidence via add_node and add_edge.
3. Present a structured synthesis to the user covering:
   - Key findings (noting which survived review intact vs which were modified)
   - Contradictions or tensions in the evidence
   - Confidence assessment (what we're most/least sure about)
   - Gaps identified during review
4. Output your synthesis as your final response.
"""


def build_options(session_id: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with stdio MCP server and researcher subagents."""
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [MCP_SERVER_SCRIPT],
    }

    return ClaudeAgentOptions(
        model=LEAD_MODEL,
        system_prompt=LEAD_AGENT_PHASE2.format(session_id=session_id),
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


def build_synthesis_options(
    session_id: str,
    review_summary: str,
    graph_summary: str,
) -> ClaudeAgentOptions:
    """Build options for the synthesis phase (post-Socratic review)."""
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [MCP_SERVER_SCRIPT],
    }

    return ClaudeAgentOptions(
        model=LEAD_MODEL,
        system_prompt=SYNTHESIS_PROMPT.format(
            session_id=session_id,
            review_summary=review_summary,
            graph_summary=graph_summary,
        ),
        tools=[],
        allowed_tools=[
            "mcp__research-graph__add_node",
            "mcp__research-graph__add_edge",
            "mcp__research-graph__update_node",
            "mcp__research-graph__get_graph_summary",
            "mcp__research-graph__get_neighborhood",
        ],
        mcp_servers={"research-graph": mcp_server_config},
        max_turns=MAX_TURNS,
        permission_mode="bypassPermissions",
    )


async def _collect_agent_output(options: ClaudeAgentOptions, prompt: str) -> str:
    """Run an agent and collect all text output."""
    result_text = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            if hasattr(message, "result") and message.result:
                result_text.append(message.result)
                print(message.result, end="", flush=True)
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    result_text.append(block.text)
                    print(block.text, end="", flush=True)
    return "\n".join(result_text)


async def run_research(question: str, session_id: str) -> None:
    """Run a full research session: research → Socratic review → synthesis → Socratic review."""

    # -----------------------------------------------------------------------
    # Step 1: Research phase — researchers investigate and populate the graph
    # -----------------------------------------------------------------------
    print("=" * 60)
    print("PHASE: Research")
    print("=" * 60)

    options = build_options(session_id)
    findings_output = await _collect_agent_output(options, question)

    # -----------------------------------------------------------------------
    # Step 2: Stage 1 Socratic Review — Critic/Defender review findings
    # -----------------------------------------------------------------------
    findings = get_session_findings(session_id)
    if findings:
        print("\n\n" + "=" * 60)
        print(f"PHASE: Socratic Review — Stage 1 (Findings)")
        print(f"Reviewing {len(findings)} findings...")
        print("=" * 60 + "\n")

        transcript_1, changelog_1 = await run_findings_review(session_id)

        stats = changelog_1.summary_stats()
        review_summary = (
            f"Stage 1 (Findings Review): {changelog_1.total_rounds} rounds, "
            f"terminated: {changelog_1.termination_reason}. "
            f"Outcomes: {stats['retained']} retained, {stats['modified']} modified, "
            f"{stats['removed']} removed."
        )
        print(f"\n{review_summary}")
        print(f"Transcript saved: {transcript_1.save()}")
        print(f"Changelog saved: {changelog_1.save()}")
    else:
        review_summary = "No findings to review."
        print("\nNo researcher findings found — skipping Socratic review.")

    # -----------------------------------------------------------------------
    # Step 3: Synthesis — lead agent synthesizes reviewed findings
    # -----------------------------------------------------------------------
    print("\n\n" + "=" * 60)
    print("PHASE: Synthesis (post-review)")
    print("=" * 60 + "\n")

    from research_agent.graph.summarizer import summarize_graph
    from research_agent.graph.store import load_graph

    graph = load_graph()
    graph_summary = summarize_graph(graph)

    synth_options = build_synthesis_options(session_id, review_summary, graph_summary)
    synthesis_output = await _collect_agent_output(
        synth_options,
        "Synthesize the reviewed findings into a coherent analysis.",
    )

    # -----------------------------------------------------------------------
    # Step 4: Stage 2 Socratic Review — Critic/Defender review synthesis
    # -----------------------------------------------------------------------
    if synthesis_output.strip():
        print("\n\n" + "=" * 60)
        print("PHASE: Socratic Review — Stage 2 (Synthesis)")
        print("=" * 60 + "\n")

        transcript_2, changelog_2 = await run_synthesis_review(
            session_id, synthesis_output
        )

        stats_2 = changelog_2.summary_stats()
        print(
            f"\nStage 2 complete: {changelog_2.total_rounds} rounds, "
            f"terminated: {changelog_2.termination_reason}. "
            f"Outcomes: {stats_2['retained']} retained, {stats_2['modified']} modified, "
            f"{stats_2['removed']} removed."
        )
        print(f"Transcript saved: {transcript_2.save()}")
        print(f"Changelog saved: {changelog_2.save()}")

    print("\n\n" + "=" * 60)
    print("Research session complete.")
    print("=" * 60)


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
