"""Resume a research session from the Literature Review phase onward.

Usage:
    python3 resume_session.py <session_id> "<research_question>"

Skips: Research (Phase 1), Validation (Phase 1.5), Socratic Review Stage 1 (Phase 2)
Runs:  Literature Review → Interactive Pause (Phase 2.5) → Synthesis (Phase 3) →
       Socratic Review Stage 2 (Phase 4) → Insights Report
"""

import asyncio
import json
import sys
from pathlib import Path

from research_agent.config import SESSIONS_DIR
from research_agent.agent import (
    _wait_for_user_input,
    _collect_user_feedback,
    _collect_agent_output,
    build_collaborative_synthesis_options,
)
from research_agent.graph.store import load_graph
from research_agent.graph.summarizer import summarize_graph
from research_agent.report_writer import write_literature_review, write_insights_report
from research_agent.socratic.review import run_synthesis_review


async def resume(session_id: str, question: str) -> None:
    print(f"Resuming session {session_id}")
    print(f"Query: {question}\n")

    # Reconstruct review_summary from existing changelog
    changelog_path = SESSIONS_DIR / f"session_{session_id}" / "changelog_findings.json"
    review_summary = "Stage 1 review completed (resumed session)."
    if changelog_path.exists():
        cl = json.loads(changelog_path.read_text())
        rounds = cl.get("total_rounds", "?")
        reason = cl.get("termination_reason", "unknown")
        review_summary = f"Stage 1 (Findings Review): {rounds} rounds, terminated: {reason}."
    print(f"Prior review: {review_summary}\n")

    # --- Literature Review (non-fatal) ---
    print("=" * 60)
    print("PHASE: Report — Literature Review")
    print("=" * 60 + "\n")

    lit_review_path = None
    try:
        lit_review_path = await write_literature_review(session_id, question)
        print(f"\nLiterature review saved: {lit_review_path}")
    except Exception as e:
        print(f"\nLiterature review failed (non-fatal): {e}")
        print("Continuing to interactive pause...\n")

    # --- Interactive Pause (Phase 2.5) ---
    await _wait_for_user_input(session_id, question, lit_review_path or Path())
    user_feedback = _collect_user_feedback(session_id)

    # --- Synthesis (Phase 3) ---
    print("\n\n" + "=" * 60)
    print("PHASE: Collaborative Synthesis (post-review + user feedback)")
    print("=" * 60 + "\n")

    graph = load_graph()
    graph_summary = summarize_graph(graph)

    synth_options = build_collaborative_synthesis_options(
        session_id, review_summary, graph_summary, user_feedback
    )
    synthesis_output = await _collect_agent_output(
        synth_options,
        "Synthesize the reviewed findings into a coherent analysis, incorporating user feedback.",
    )

    # --- Stage 2 Socratic Review (Phase 4) ---
    if synthesis_output.strip():
        print("\n\n" + "=" * 60)
        print("PHASE: Socratic Review — Stage 2 (Synthesis)")
        print("=" * 60 + "\n")

        transcript_2, changelog_2 = await run_synthesis_review(
            session_id, synthesis_output
        )

        stats_2 = changelog_2.summary_stats()
        stats_2_str = ", ".join(f"{v} {k}" for k, v in stats_2.items())
        print(
            f"\nStage 2 complete: {changelog_2.total_rounds} rounds, "
            f"terminated: {changelog_2.termination_reason}. "
            f"Outcomes: {stats_2_str}."
        )
        print(f"Transcript saved: {transcript_2.save()}")
        print(f"Changelog saved: {changelog_2.save()}")

        # --- Insights Report ---
        print("\n\n" + "=" * 60)
        print("PHASE: Report — Insights & Discussion")
        print("=" * 60 + "\n")

        try:
            insights_path = await write_insights_report(
                session_id, question, synthesis_output
            )
            print(f"\nInsights report saved: {insights_path}")
        except Exception as e:
            print(f"\nInsights report failed (non-fatal): {e}")

    print("\n\n" + "=" * 60)
    print("Research session complete.")
    print("=" * 60)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 resume_session.py <session_id> \"<research_question>\"")
        sys.exit(1)

    session_id = sys.argv[1]
    question = " ".join(sys.argv[2:])
    asyncio.run(resume(session_id, question))


if __name__ == "__main__":
    main()
