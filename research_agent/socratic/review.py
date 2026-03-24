"""Orchestrate multi-round Critic/Defender Socratic review.

Supports two stages:
- Stage 1 (findings): Reviews raw researcher findings before synthesis.
- Stage 2 (synthesis): Reviews the lead agent's synthesis before presenting to user.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    ClaudeAgentOptions,
    ResultMessage,
    query,
)

from research_agent.config import (
    CRITIC_MODEL,
    DEFENDER_MODEL,
    MAX_SOCRATIC_ROUNDS,
    CONFIDENCE_ESCALATION_THRESHOLD,
    SOCRATIC_MAX_TURNS_PER_ROUND,
)
from research_agent.graph.store import load_graph, save_graph
from research_agent.prompts import (
    CRITIC_FINDINGS,
    DEFENDER_FINDINGS,
    CRITIC_SYNTHESIS,
    DEFENDER_SYNTHESIS,
)
from research_agent.socratic.changelog import Changelog, ChallengeOutcome
from research_agent.socratic.transcript import Transcript


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def get_session_findings(session_id: str) -> list[dict]:
    """Return all nodes added by researchers in this session."""
    graph = load_graph()
    return [
        n for n in graph.nodes
        if n.get("provenance", {}).get("session_id") == session_id
        and n.get("provenance", {}).get("subagent", "").startswith("researcher")
    ]


def format_findings_for_review(nodes: list[dict]) -> str:
    """Format graph nodes into readable text for the Critic/Defender."""
    # Filter out withdrawn nodes
    nodes = [n for n in nodes if not n.get("withdrawn", False)]
    if not nodes:
        return "(No findings to review.)"
    lines = []
    for n in nodes:
        entry = (
            f"- [{n['id']}] **{n['label']}** ({n['type']}, conf={n.get('confidence', 0.5):.2f})\n"
            f"  Description: {n.get('description', 'N/A')}\n"
            f"  Source: {n.get('metadata', {}).get('url', 'N/A')} "
            f"({n.get('metadata', {}).get('source_type', 'N/A')})"
        )
        # Surface validation flags
        meta = n.get("metadata", {})
        if meta.get("needs_source"):
            entry += "\n  ⚠ UNSOURCED QUANTITATIVE CLAIM — confidence capped at 0.50"
        if meta.get("potential_coi"):
            entry += "\n  ⚠ POTENTIAL COI — source domain appears in claim"
        lines.append(entry)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent interaction
# ---------------------------------------------------------------------------

async def _run_agent(system_prompt: str, model: str) -> str:
    """Run a single-turn agent call and collect the text response."""
    options = ClaudeAgentOptions(
        model=model,
        system_prompt=system_prompt,
        tools=[],
        allowed_tools=[],
        max_turns=SOCRATIC_MAX_TURNS_PER_ROUND,
        permission_mode="bypassPermissions",
    )

    result_text = []
    async for message in query(prompt="Begin your review.", options=options):
        if isinstance(message, ResultMessage):
            if hasattr(message, "result") and message.result:
                result_text.append(message.result)
        elif hasattr(message, "content"):
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    result_text.append(block.text)

    return "\n".join(result_text)


# ---------------------------------------------------------------------------
# Outcome parsing
# ---------------------------------------------------------------------------

def _parse_defender_json(defender_text: str, findings: list[dict]) -> list[dict] | None:
    """Try to extract structured JSON outcomes from the Defender's response.

    The Defender is instructed to emit a ```json [...] ``` block after its
    natural language response.  Returns parsed outcomes or None if no valid
    JSON block is found.
    """
    node_map = {n["id"]: n for n in findings}

    json_match = re.search(r"```json\s*(\[.*?\])\s*```", defender_text, re.DOTALL)
    if not json_match:
        return None

    try:
        raw = json.loads(json_match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(raw, list):
        return None

    outcomes = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        node_id = entry.get("node_id", "")
        if node_id not in node_map:
            continue
        response = entry.get("response", "").upper().strip()
        if response not in ("DEFEND", "CONCEDE", "PARTIALLY CONCEDE"):
            continue

        outcomes.append({
            "node_id": node_id,
            "node_label": node_map[node_id].get("label", ""),
            "response": response,
            "reasoning": entry.get("change_description", ""),
            "post_confidence": entry.get("confidence"),
            "proposed_change": entry.get("change_description", ""),
            "secondary_updates": entry.get("secondary_updates", []),
        })

    return outcomes if outcomes else None


def _parse_defender_response(defender_text: str, findings: list[dict]) -> list[dict]:
    """Extract per-node outcomes from the Defender's structured response.

    Tries JSON parsing first (preferred); falls back to regex extraction
    from markdown if no valid JSON block is found.

    Returns a list of dicts with keys:
    - node_id, node_label, response (DEFEND/CONCEDE/PARTIALLY CONCEDE),
      reasoning, post_confidence, proposed_change, secondary_updates
    """
    # Try structured JSON first
    json_outcomes = _parse_defender_json(defender_text, findings)
    if json_outcomes is not None:
        return json_outcomes

    # Fall back to regex parsing
    outcomes = []
    node_map = {n["id"]: n for n in findings}

    # Split into per-challenge blocks on horizontal rules, ### headers,
    # or bold challenge headers like **Challenge 1**.
    blocks = re.split(
        r"\n---+\n|\n(?=###\s)|\n(?=\*\*Challenge\s+\d+\*\*)",
        defender_text,
    )

    for block in blocks:
        if not block.strip():
            continue

        # Look for a 12-char hex node ID anywhere in the block.
        # Handles: **Node:** [id] label,  ### C13 — [id] label,  [id] bare
        id_match = re.search(r"\[?([a-f0-9]{12})\]?", block)
        if not id_match:
            continue
        node_id = id_match.group(1)
        if node_id not in node_map:
            continue

        # Must have an explicit Response line to count as a parsed outcome
        response_match = re.search(
            r"\*{0,2}Response:?\*{0,2}\s*(DEFEND|CONCEDE|PARTIALLY CONCEDE)",
            block, re.IGNORECASE
        )
        if not response_match:
            continue
        response = response_match.group(1).upper()

        # Extract confidence — handles bold markers and varied labels
        conf_match = re.search(
            r"\*{0,2}(?:Post-challenge confidence|confidence):?\*{0,2}\s*(\d+\.?\d*|\.\d+)",
            block, re.IGNORECASE
        )
        post_confidence = None
        if conf_match:
            try:
                post_confidence = float(conf_match.group(1))
            except ValueError:
                pass

        # Extract proposed change — runs until next field, divider, or end
        change_match = re.search(
            r"\*{0,2}Proposed change:?\*{0,2}\s*(.+?)(?=\n\s*[-*]?\s*\*{0,2}(?:Node|Response|Reasoning|Post-challenge)|(?:\n---|\n###|\Z))",
            block, re.IGNORECASE | re.DOTALL
        )
        proposed_change = change_match.group(1).strip() if change_match else ""

        # Extract reasoning — runs until Post-challenge or Proposed change
        reasoning_match = re.search(
            r"\*{0,2}Reasoning:?\*{0,2}\s*(.+?)(?=\n\s*[-*]?\s*\*{0,2}(?:Post-challenge|Proposed)|(?:\n---|\n###|\Z))",
            block, re.IGNORECASE | re.DOTALL
        )
        reasoning = reasoning_match.group(1).strip() if reasoning_match else block.strip()[:200]

        outcomes.append({
            "node_id": node_id,
            "node_label": node_map[node_id].get("label", ""),
            "response": response,
            "reasoning": reasoning,
            "post_confidence": post_confidence,
            "proposed_change": proposed_change,
            "secondary_updates": [],
        })

    # Deduplicate by node_id — keep the last occurrence per node
    # (the model sometimes echoes its response, producing duplicates)
    seen: dict[str, int] = {}
    for i, o in enumerate(outcomes):
        seen[o["node_id"]] = i
    outcomes = [outcomes[i] for i in sorted(seen.values())]

    return outcomes


def _apply_graph_mutations(
    outcomes: list[dict],
    changelog: Changelog,
    findings: list[dict],
    round_number: int,
) -> list[dict]:
    """Apply concessions to the graph and record in changelog.

    Returns a list of mutation records: [{node_id, field, old, new}].
    """
    graph = load_graph()
    node_map = {n["id"]: n for n in graph.nodes}
    findings_map = {n["id"]: n for n in findings}
    mutations: list[dict] = []

    for outcome in outcomes:
        node_id = outcome["node_id"]
        node = node_map.get(node_id)
        if not node:
            continue

        original_conf = node.get("confidence", 0.5)
        response = outcome["response"]

        if response == "DEFEND":
            final_conf = outcome.get("post_confidence") or original_conf
            changelog.add_outcome(ChallengeOutcome(
                node_id=node_id,
                node_label=outcome["node_label"],
                grounds="",
                challenge_summary=outcome["reasoning"][:200],
                outcome="retained",
                change_description="",
                original_confidence=original_conf,
                final_confidence=final_conf,
                round_number=round_number,
            ))
        elif response in ("CONCEDE", "PARTIALLY CONCEDE"):
            new_conf = outcome.get("post_confidence") or max(original_conf - 0.2, 0.0)
            change_desc = outcome.get("proposed_change", "")

            # Apply to graph
            node["confidence"] = new_conf
            mutations.append({"node_id": node_id, "field": "confidence",
                              "old": original_conf, "new": new_conf})
            if change_desc and len(change_desc) > 10:
                # Append caveat to description rather than replacing
                existing = node.get("description", "")
                node["description"] = f"{existing} [Socratic revision: {change_desc}]"
                mutations.append({"node_id": node_id, "field": "description",
                                  "old": "(appended)", "new": "(revised)"})

            # Soft-delete if confidence drops very low
            if new_conf < 0.15:
                node["withdrawn"] = True

            outcome_label = "removed" if new_conf < 0.15 else "modified"
            changelog.add_outcome(ChallengeOutcome(
                node_id=node_id,
                node_label=outcome["node_label"],
                grounds="",
                challenge_summary=outcome["reasoning"][:200],
                outcome=outcome_label,
                change_description=change_desc,
                original_confidence=original_conf,
                final_confidence=new_conf,
                round_number=round_number,
            ))

        # --- Process secondary confidence updates ---
        for sec in outcome.get("secondary_updates", []):
            sec_id = sec.get("node_id", "")
            sec_node = node_map.get(sec_id)
            if not sec_node:
                continue
            sec_conf = sec.get("confidence")
            if sec_conf is None:
                continue
            sec_original = sec_node.get("confidence", 0.5)
            sec_node["confidence"] = sec_conf
            mutations.append({"node_id": sec_id, "field": "confidence",
                              "old": sec_original, "new": sec_conf})
            if sec_conf < 0.15:
                sec_node["withdrawn"] = True
            changelog.add_outcome(ChallengeOutcome(
                node_id=sec_id,
                node_label=sec_node.get("label", ""),
                grounds="",
                challenge_summary=f"Secondary update from [{node_id}] review",
                outcome="secondary_adjustment",
                change_description="",
                original_confidence=sec_original,
                final_confidence=sec_conf,
                round_number=round_number,
            ))

    save_graph(graph)

    # --- Validation pass: verify writes landed ---
    if mutations:
        import sys
        verified = load_graph()
        v_map = {n["id"]: n for n in verified.nodes}
        for m in mutations:
            if m["field"] != "confidence":
                continue
            v_node = v_map.get(m["node_id"])
            if v_node and abs(v_node.get("confidence", -1) - m["new"]) > 0.001:
                print(
                    f"WARNING: confidence drift on [{m['node_id']}]: "
                    f"expected {m['new']}, got {v_node.get('confidence')}",
                    file=sys.stderr,
                )

    return mutations


# ---------------------------------------------------------------------------
# Main review orchestration
# ---------------------------------------------------------------------------

async def run_findings_review(session_id: str) -> tuple[Transcript, Changelog]:
    """Run Stage 1: Findings Review.

    Multi-round Critic/Defender exchange on researcher findings.
    Returns (transcript, changelog).
    """
    findings = get_session_findings(session_id)
    if not findings:
        # Nothing to review
        transcript = Transcript(session_id=session_id, stage="findings")
        changelog = Changelog(session_id=session_id, stage="findings",
                              termination_reason="no_findings")
        return transcript, changelog

    findings_text = format_findings_for_review(findings)
    transcript = Transcript(session_id=session_id, stage="findings")
    changelog = Changelog(session_id=session_id, stage="findings")

    last_critic_message = ""
    last_defender_message = ""
    mutation_summaries: list[str] = []

    for round_num in range(1, MAX_SOCRATIC_ROUNDS + 1):
        # --- Critic turn ---
        critic_prompt = CRITIC_FINDINGS.format(
            session_id=session_id,
            round_number=round_num,
            max_rounds=MAX_SOCRATIC_ROUNDS,
            findings_text=findings_text,
        )
        # After round 1, include the Defender's prior response and applied mutations
        if last_critic_message:
            critic_prompt += (
                f"\n\nThe Defender's response from the previous round:\n\n"
                f"{last_defender_message}\n\n"
            )
            if mutation_summaries:
                critic_prompt += (
                    "Changes applied to the graph in previous rounds:\n\n"
                    + "\n".join(mutation_summaries)
                    + "\n\n"
                )
            critic_prompt += "Continue your review. Raise new challenges or follow up on unresolved ones."

        critic_response = await _run_agent(critic_prompt, CRITIC_MODEL)
        transcript.add_entry(round_num, "critic", critic_response)

        # Check for early termination
        if "NO FURTHER OBJECTIONS" in critic_response.upper():
            changelog.termination_reason = "no_further_objections"
            changelog.total_rounds = round_num
            break

        # --- Defender turn ---
        defender_prompt = DEFENDER_FINDINGS.format(
            session_id=session_id,
            round_number=round_num,
            max_rounds=MAX_SOCRATIC_ROUNDS,
            findings_text=findings_text,
            critic_message=critic_response,
            confidence_threshold=CONFIDENCE_ESCALATION_THRESHOLD,
        )

        defender_response = await _run_agent(defender_prompt, DEFENDER_MODEL)
        transcript.add_entry(round_num, "defender", defender_response)

        # Parse outcomes and apply mutations
        outcomes = _parse_defender_response(defender_response, findings)
        round_mutations = _apply_graph_mutations(outcomes, changelog, findings, round_num)

        # Build mutation summary for next round's Critic context
        if round_mutations:
            summary_lines = [f"### Round {round_num} applied changes"]
            for m in round_mutations:
                if m["field"] == "confidence":
                    summary_lines.append(
                        f"- [{m['node_id']}] confidence: {m['old']:.2f} → {m['new']:.2f}"
                    )
                else:
                    summary_lines.append(f"- [{m['node_id']}] {m['field']} updated")
            mutation_summaries.append("\n".join(summary_lines))

        # Check for confidence escalation — if any finding drops below threshold,
        # the Critic gets an extra round on that finding (handled by continuing the loop)
        low_conf_findings = [
            o for o in outcomes
            if o.get("post_confidence") is not None
            and o["post_confidence"] < CONFIDENCE_ESCALATION_THRESHOLD
        ]
        if low_conf_findings and round_num == MAX_SOCRATIC_ROUNDS:
            # Extend by one round for low-confidence escalation
            # (We don't modify MAX_SOCRATIC_ROUNDS — just note it)
            changelog.termination_reason = "max_rounds_with_escalation"

        last_critic_message = critic_response
        last_defender_message = defender_response

        # Refresh findings text with updated graph state
        findings = get_session_findings(session_id)
        findings_text = format_findings_for_review(findings)

    else:
        changelog.termination_reason = "max_rounds"
        changelog.total_rounds = MAX_SOCRATIC_ROUNDS

    # Persist
    transcript.save()
    changelog.save()

    return transcript, changelog


async def run_synthesis_review(
    session_id: str,
    synthesis_text: str,
) -> tuple[Transcript, Changelog]:
    """Run Stage 2: Synthesis Review.

    Multi-round Critic/Defender exchange on the lead agent's synthesis.
    Returns (transcript, changelog).
    """
    findings = get_session_findings(session_id)
    findings_text = format_findings_for_review(findings)

    transcript = Transcript(session_id=session_id, stage="synthesis")
    changelog = Changelog(session_id=session_id, stage="synthesis")

    last_defender_message = ""

    for round_num in range(1, MAX_SOCRATIC_ROUNDS + 1):
        # --- Critic turn ---
        critic_prompt = CRITIC_SYNTHESIS.format(
            session_id=session_id,
            round_number=round_num,
            max_rounds=MAX_SOCRATIC_ROUNDS,
            synthesis_text=synthesis_text,
            findings_text=findings_text,
        )
        if last_defender_message:
            critic_prompt += (
                f"\n\nThe Defender's response from the previous round:\n\n"
                f"{last_defender_message}\n\n"
                f"Continue your review or state NO FURTHER OBJECTIONS."
            )

        critic_response = await _run_agent(critic_prompt, CRITIC_MODEL)
        transcript.add_entry(round_num, "critic", critic_response)

        if "NO FURTHER OBJECTIONS" in critic_response.upper():
            changelog.termination_reason = "no_further_objections"
            changelog.total_rounds = round_num
            break

        # --- Defender turn ---
        defender_prompt = DEFENDER_SYNTHESIS.format(
            session_id=session_id,
            round_number=round_num,
            max_rounds=MAX_SOCRATIC_ROUNDS,
            synthesis_text=synthesis_text,
            critic_message=critic_response,
        )

        defender_response = await _run_agent(defender_prompt, DEFENDER_MODEL)
        transcript.add_entry(round_num, "defender", defender_response)

        # Parse and record outcomes (no graph mutations for synthesis)
        outcomes = _parse_defender_response(defender_response, findings)
        for outcome in outcomes:
            response = outcome["response"]
            original_conf = 0.0  # synthesis challenges don't map to node confidence
            post_conf = outcome.get("post_confidence") or 0.0
            if response == "DEFEND":
                outcome_label = "synthesis_retained"
            else:
                outcome_label = "synthesis_modified"
            changelog.add_outcome(ChallengeOutcome(
                node_id=outcome.get("node_id", ""),
                node_label=outcome.get("node_label", ""),
                grounds="",
                challenge_summary=outcome.get("reasoning", "")[:200],
                outcome=outcome_label,
                change_description=outcome.get("proposed_change", ""),
                original_confidence=original_conf,
                final_confidence=post_conf,
                round_number=round_num,
            ))

        last_defender_message = defender_response
    else:
        changelog.termination_reason = "max_rounds"
        changelog.total_rounds = MAX_SOCRATIC_ROUNDS

    # Persist
    transcript.save()
    changelog.save()

    return transcript, changelog
