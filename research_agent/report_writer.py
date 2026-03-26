"""Report Writer — produces structured documents from the knowledge graph.

Generates two documents at mode boundaries:
- Literature Review (after Mode 1 + Stage 1 Socratic review)
- Key Insights & Discussion (after Mode 2 + Stage 2 Socratic review)

Follows the same orchestration pattern as socratic/review.py:
build context → build ClaudeAgentOptions → run agent → collect output → save to disk.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

logger = logging.getLogger(__name__)

# Limits for system prompt context to avoid timeout on large graphs
MAX_FINDINGS_IN_PROMPT = 30  # Show top-N findings; rest available via MCP tools
MAX_CHANGELOG_OUTCOMES_IN_PROMPT = 20
COLLECT_OUTPUT_MAX_RETRIES = 2
COLLECT_OUTPUT_TIMEOUT = 600  # seconds per attempt

from research_agent.config import (
    REPORT_WRITER_MODEL,
    REPORT_WRITER_MAX_TURNS,
    SESSIONS_DIR,
)
from research_agent.prompts import (
    REPORT_WRITER_LIT_REVIEW,
    REPORT_WRITER_INSIGHTS,
)
from research_agent.socratic.review import (
    get_session_findings,
    format_findings_for_review,
)

# Path to the standalone MCP server script
MCP_SERVER_SCRIPT = str(Path(__file__).resolve().parent / "mcp_server.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_changelog(session_id: str, stage: str) -> dict | None:
    """Load a changelog JSON file from the session directory."""
    path = SESSIONS_DIR / f"session_{session_id}" / f"changelog_{stage}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _format_changelog_for_report(changelog_data: dict | None) -> str:
    """Convert changelog outcomes into readable text for the report writer."""
    if not changelog_data:
        return "(No review changelog available.)"

    outcomes = changelog_data.get("outcomes", [])
    if not outcomes:
        return "(No challenges were raised during review.)"

    lines = []
    for o in outcomes:
        label = o.get("node_label", o.get("node_id", "unknown"))
        outcome = o.get("outcome", "unknown")
        orig_conf = o.get("original_confidence")
        final_conf = o.get("final_confidence")
        change = o.get("change_description", "")
        grounds = o.get("challenge_summary", o.get("grounds", ""))

        conf_delta = ""
        if orig_conf is not None and final_conf is not None:
            conf_delta = f" (confidence: {orig_conf:.2f} → {final_conf:.2f})"

        line = f"- **{label}** — {outcome}{conf_delta}"
        if grounds:
            line += f"\n  Challenge: {grounds}"
        if change:
            line += f"\n  Change: {change}"
        lines.append(line)

    return "\n".join(lines)


async def _collect_output(options: ClaudeAgentOptions, prompt: str) -> str:
    """Run an agent and collect all text output, with timeout and retry."""
    for attempt in range(1, COLLECT_OUTPUT_MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                _run_query(prompt, options), timeout=COLLECT_OUTPUT_TIMEOUT
            )
        except (asyncio.TimeoutError, Exception) as exc:
            logger.warning(
                "Report writer attempt %d/%d failed: %s",
                attempt, COLLECT_OUTPUT_MAX_RETRIES, exc,
            )
            if attempt == COLLECT_OUTPUT_MAX_RETRIES:
                raise
    return ""  # unreachable, satisfies type checker


async def _run_query(prompt: str, options: ClaudeAgentOptions) -> str:
    """Run query and collect results as a single coroutine (wrappable by wait_for)."""
    result_text: list[str] = []
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


def _truncate_findings(findings_text: str, total_count: int, max_items: int = MAX_FINDINGS_IN_PROMPT) -> str:
    """Keep only the first *max_items* findings; append explicit instructions for the rest."""
    entries = findings_text.split("\n- [")
    if len(entries) <= max_items + 1:  # first split element may be empty or header
        return findings_text
    kept = "\n- [".join(entries[: max_items + 1])
    omitted = len(entries) - max_items - 1
    return kept + (
        f"\n\n⚠ IMPORTANT: Only {max_items} of {total_count} findings are shown above. "
        f"{omitted} findings were omitted to stay within context limits. "
        f"You MUST use get_graph_summary to see the full node list, then use "
        f"get_neighborhood on nodes not shown above to retrieve their details. "
        f"The literature review must cover ALL findings, not just the ones listed here."
    )


def _truncate_changelog(changelog_text: str, max_items: int = MAX_CHANGELOG_OUTCOMES_IN_PROMPT) -> str:
    """Keep only the first *max_items* changelog entries."""
    entries = changelog_text.split("\n- **")
    if len(entries) <= max_items + 1:
        return changelog_text
    kept = "\n- **".join(entries[: max_items + 1])
    omitted = len(entries) - max_items - 1
    return kept + f"\n\n({omitted} additional changelog entries omitted.)"


def _build_report_options(system_prompt: str) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the report writer — read-only graph access."""
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": [MCP_SERVER_SCRIPT],
    }

    return ClaudeAgentOptions(
        model=REPORT_WRITER_MODEL,
        system_prompt=system_prompt,
        tools=[],
        allowed_tools=[
            "mcp__research-graph__get_graph_summary",
            "mcp__research-graph__get_session_findings",
            "mcp__research-graph__get_neighborhood",
        ],
        mcp_servers={"research-graph": mcp_server_config},
        max_turns=REPORT_WRITER_MAX_TURNS,
        permission_mode="bypassPermissions",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def write_literature_review(session_id: str, question: str) -> Path:
    """Generate a literature review from the post-review knowledge graph."""
    findings = get_session_findings(session_id)
    findings_text = format_findings_for_review(findings)

    changelog_data = _load_changelog(session_id, "findings")
    changelog_text = _format_changelog_for_report(changelog_data)

    review_summary = ""
    if changelog_data:
        rounds = changelog_data.get("total_rounds", "?")
        reason = changelog_data.get("termination_reason", "unknown")
        review_summary = f"Stage 1: {rounds} rounds, terminated: {reason}."

    system_prompt = REPORT_WRITER_LIT_REVIEW.format(
        session_id=session_id,
        research_question=question,
        findings_text=_truncate_findings(findings_text, len(findings)),
        review_summary=review_summary,
        changelog_text=_truncate_changelog(changelog_text),
    )

    options = _build_report_options(system_prompt)
    output = await _collect_output(
        options, "Write the literature review document."
    )

    session_dir = SESSIONS_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / "literature_review.md"
    output_path.write_text(output, encoding="utf-8")

    return output_path


async def write_insights_report(
    session_id: str, question: str, synthesis_output: str
) -> Path:
    """Generate a key insights & discussion document from synthesis + review."""
    findings = get_session_findings(session_id)
    findings_text = format_findings_for_review(findings)

    changelog_findings = _load_changelog(session_id, "findings")
    changelog_synthesis = _load_changelog(session_id, "synthesis")

    # Combine both changelogs into a single readable block
    parts = []
    if changelog_findings:
        parts.append("#### Stage 1 — Findings Review")
        parts.append(_format_changelog_for_report(changelog_findings))
    if changelog_synthesis:
        parts.append("\n#### Stage 2 — Synthesis Review")
        parts.append(_format_changelog_for_report(changelog_synthesis))
    changelog_text = "\n".join(parts) if parts else "(No review changelogs available.)"

    review_parts = []
    if changelog_findings:
        r = changelog_findings.get("total_rounds", "?")
        t = changelog_findings.get("termination_reason", "unknown")
        review_parts.append(f"Stage 1 (Findings): {r} rounds, terminated: {t}.")
    if changelog_synthesis:
        r = changelog_synthesis.get("total_rounds", "?")
        t = changelog_synthesis.get("termination_reason", "unknown")
        review_parts.append(f"Stage 2 (Synthesis): {r} rounds, terminated: {t}.")
    review_summary = " ".join(review_parts) if review_parts else "No review data."

    system_prompt = REPORT_WRITER_INSIGHTS.format(
        session_id=session_id,
        research_question=question,
        findings_text=findings_text,
        synthesis_text=synthesis_output,
        review_summary=review_summary,
        changelog_text=changelog_text,
    )

    options = _build_report_options(system_prompt)
    output = await _collect_output(
        options, "Write the key insights and discussion document."
    )

    session_dir = SESSIONS_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / "insights_and_discussion.md"
    output_path.write_text(output, encoding="utf-8")

    return output_path
