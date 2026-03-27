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
from research_agent.config import session_graph_path
from research_agent.graph.store import load_graph
from research_agent.socratic.review import (
    get_session_findings,
    format_findings_for_review,
    load_socratic_scores,
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


def _score_finding(node: dict, degree: int, socratic_score: float) -> float:
    """Composite relevance score: confidence + connectivity + Socratic outcome."""
    confidence = node.get("confidence", 0.5)
    connectivity = min(degree / 10, 1.0)  # normalize, cap at 10 edges
    return (0.4 * confidence) + (0.3 * connectivity) + (0.3 * socratic_score)


def _rank_findings(
    findings: list[dict], session_id: str
) -> list[dict]:
    """Return findings sorted by composite relevance score (descending)."""
    sgp = session_graph_path(session_id)
    graph = load_graph(sgp) if sgp.exists() else load_graph()
    socratic_scores = load_socratic_scores(session_id)

    scored = []
    for node in findings:
        degree = graph.node_degree(node["id"])
        soc_score = socratic_scores.get(node["id"], 0.7)  # default: unchallenged
        score = _score_finding(node, degree, soc_score)
        scored.append((score, node))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [node for _, node in scored]


def _truncate_findings(
    findings_text: str,
    total_count: int,
    max_items: int = MAX_FINDINGS_IN_PROMPT,
    ranked_ids: list[str] | None = None,
) -> str:
    """Keep the top *max_items* findings by relevance rank.

    If *ranked_ids* is provided, reorders the entries to match the ranked order
    before truncating. Otherwise falls back to positional truncation.
    """
    entries = findings_text.split("\n- [")
    # First element is usually empty or a header line
    header = entries[0] if entries else ""
    items = entries[1:] if len(entries) > 1 else []

    if len(items) <= max_items:
        return findings_text

    if ranked_ids:
        # Build a map from node_id → entry text
        id_to_entry: dict[str, str] = {}
        for item in items:
            # Each item starts with the 12-char hex id after "- ["
            nid = item[:12] if len(item) >= 12 else ""
            id_to_entry[nid] = item

        # Reorder by ranked_ids, keeping only those present in the text
        ordered = []
        for nid in ranked_ids:
            if nid in id_to_entry:
                ordered.append(id_to_entry.pop(nid))
        # Append any remaining items not in ranked_ids
        ordered.extend(id_to_entry.values())
        items = ordered

    kept = header + "\n- [".join([""] + items[:max_items])
    omitted = len(items) - max_items
    return kept + (
        f"\n\n⚠ IMPORTANT: Only {max_items} of {total_count} findings are shown above "
        f"(ranked by relevance — most important first). "
        f"{omitted} findings were omitted to stay within context limits. "
        f"You MUST use get_graph_summary to see the full node list, then use "
        f"get_neighborhood on nodes not shown above to retrieve their details. "
        f"The literature review must cover ALL findings, not just the ones listed here."
    )


def _truncate_changelog(
    changelog_text: str,
    changelog_data: dict | None = None,
    max_items: int = MAX_CHANGELOG_OUTCOMES_IN_PROMPT,
) -> str:
    """Keep the top *max_items* changelog entries, ranked by impact.

    Entries where outcome is conceded/modified or confidence changed most rank higher.
    """
    entries = changelog_text.split("\n- **")
    header = entries[0] if entries else ""
    items = entries[1:] if len(entries) > 1 else []

    if len(items) <= max_items:
        return changelog_text

    # Rank by impact if changelog data is available
    if changelog_data:
        outcomes = changelog_data.get("outcomes", [])
        # Score: larger confidence delta + non-retained outcomes rank higher
        outcome_weights = {
            "removed": 3.0, "modified": 2.0, "synthesis_modified": 2.0,
            "retained": 0.5, "retained_unchallenged": 0.1,
            "synthesis_retained": 0.5, "secondary_adjustment": 1.0,
        }
        scored_outcomes = []
        for o in outcomes:
            delta = abs(o.get("original_confidence", 0) - o.get("final_confidence", 0))
            weight = outcome_weights.get(o.get("outcome", ""), 0.5)
            scored_outcomes.append((delta + weight, o.get("node_label", "")))

        scored_outcomes.sort(key=lambda x: x[0], reverse=True)
        # Build a priority order of node labels
        priority_labels = [label.lower() for _, label in scored_outcomes]

        # Sort items by matching priority label
        def _item_priority(item: str) -> float:
            item_lower = item.lower()
            for i, label in enumerate(priority_labels):
                if label and label in item_lower:
                    return i
            return len(priority_labels)

        items.sort(key=_item_priority)

    kept = header + "\n- **".join([""] + items[:max_items])
    omitted = len(items) - max_items
    return kept + f"\n\n({omitted} additional changelog entries omitted — highest-impact shown above.)"


def _build_report_options(system_prompt: str, session_id: str = "") -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions for the report writer — read-only graph access."""
    mcp_args = [MCP_SERVER_SCRIPT]
    if session_id:
        mcp_args.extend(["--session", session_id])
    mcp_server_config = {
        "type": "stdio",
        "command": "python3",
        "args": mcp_args,
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
    ranked_findings = _rank_findings(findings, session_id)
    ranked_ids = [n["id"] for n in ranked_findings]
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
        findings_text=_truncate_findings(findings_text, len(findings), ranked_ids=ranked_ids),
        review_summary=review_summary,
        changelog_text=_truncate_changelog(changelog_text, changelog_data=changelog_data),
    )

    options = _build_report_options(system_prompt, session_id=session_id)
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
    # Rank-truncate the combined changelog
    combined_changelog_data = None
    if changelog_findings or changelog_synthesis:
        combined_outcomes = []
        if changelog_findings:
            combined_outcomes.extend(changelog_findings.get("outcomes", []))
        if changelog_synthesis:
            combined_outcomes.extend(changelog_synthesis.get("outcomes", []))
        combined_changelog_data = {"outcomes": combined_outcomes}
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

    options = _build_report_options(system_prompt, session_id=session_id)
    output = await _collect_output(
        options, "Write the key insights and discussion document."
    )

    session_dir = SESSIONS_DIR / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / "insights_and_discussion.md"
    output_path.write_text(output, encoding="utf-8")

    return output_path
