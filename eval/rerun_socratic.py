#!/usr/bin/env python3
"""Re-run Socratic review on an existing session to test Critic MCP access.

Saves new transcripts/changelogs to eval/rerun_<session_id>/ so the
original session artifacts are preserved for comparison.

Usage:
    python eval/rerun_socratic.py <session_id>
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.config import SESSIONS_DIR
from research_agent.graph.store import load_graph, save_graph
from research_agent.socratic.review import (
    run_findings_review,
    get_session_findings,
)


async def rerun(session_id: str):
    eval_dir = PROJECT_ROOT / "eval" / f"rerun_{session_id}"
    eval_dir.mkdir(parents=True, exist_ok=True)

    # Copy original transcripts/changelogs as baseline
    session_dir = SESSIONS_DIR / f"session_{session_id}"
    for fname in ["transcript_findings.md", "changelog_findings.json"]:
        src = session_dir / fname
        if src.exists():
            shutil.copy2(src, eval_dir / f"baseline_{fname}")
            print(f"Baseline saved: {eval_dir / f'baseline_{fname}'}")

    # Restore graph to pre-socratic state by reverting confidence changes
    # from the original review (so the new Critic reviews the same findings)
    graph = load_graph()
    original_changelog = session_dir / "changelog_findings.json"
    if original_changelog.exists():
        cl = json.loads(original_changelog.read_text())
        reverted = 0
        for outcome in cl.get("outcomes", []):
            node_id = outcome.get("node_id")
            orig_conf = outcome.get("original_confidence")
            if node_id and orig_conf is not None:
                for n in graph.nodes:
                    if n["id"] == node_id:
                        n["confidence"] = orig_conf
                        n.pop("withdrawn", None)
                        # Remove Socratic revision annotations
                        desc = n.get("description", "")
                        if "[Socratic revision:" in desc:
                            n["description"] = desc[:desc.index("[Socratic revision:")]
                        reverted += 1
                        break
        save_graph(graph)
        print(f"Reverted {reverted} nodes to pre-review confidence levels")

    # Check findings
    findings = get_session_findings(session_id)
    print(f"\nFindings available for review: {len(findings)}")
    if not findings:
        print("No findings — aborting.")
        return

    # Run the improved Socratic review (Critic now has MCP access)
    print("\n" + "=" * 60)
    print("RUNNING IMPROVED SOCRATIC REVIEW (Stage 1 — Findings)")
    print("Critic now has MCP access to: get_graph_summary, get_neighborhood, query_graph")
    print("=" * 60 + "\n")

    transcript, changelog = await run_findings_review(session_id)

    # Save new artifacts to eval dir (don't overwrite session originals)
    new_transcript_path = eval_dir / "improved_transcript_findings.md"
    new_changelog_path = eval_dir / "improved_changelog_findings.json"

    # Copy from session dir to eval dir
    session_transcript = session_dir / "transcript_findings.md"
    session_changelog = session_dir / "changelog_findings.json"
    if session_transcript.exists():
        shutil.copy2(session_transcript, new_transcript_path)
    if session_changelog.exists():
        shutil.copy2(session_changelog, new_changelog_path)

    print(f"\nNew transcript: {new_transcript_path}")
    print(f"New changelog: {new_changelog_path}")

    # Quick comparison
    stats = changelog.summary_stats()
    print(f"\nReview complete: {changelog.total_rounds} rounds, "
          f"terminated: {changelog.termination_reason}")
    print(f"Outcomes: {json.dumps(stats)}")

    # Count tool references in new transcript
    if new_transcript_path.exists():
        text = new_transcript_path.read_text()
        tool_refs = (
            text.count("get_neighborhood")
            + text.count("query_graph")
            + text.count("get_graph_summary")
        )
        print(f"\nTool references in new transcript: {tool_refs}")
    else:
        print("\nWARNING: new transcript not found")

    # Restore original graph state (put the original review results back)
    original_changelog_data = eval_dir / "baseline_changelog_findings.json"
    if original_changelog_data.exists():
        cl = json.loads(original_changelog_data.read_text())
        graph = load_graph()
        for outcome in cl.get("outcomes", []):
            node_id = outcome.get("node_id")
            final_conf = outcome.get("final_confidence")
            if node_id and final_conf is not None:
                for n in graph.nodes:
                    if n["id"] == node_id:
                        n["confidence"] = final_conf
                        if final_conf < 0.15:
                            n["withdrawn"] = True
                        break
        save_graph(graph)
        print("\nGraph restored to post-original-review state")

    # Restore original session artifacts
    for fname in ["transcript_findings.md", "changelog_findings.json"]:
        baseline = eval_dir / f"baseline_{fname}"
        if baseline.exists():
            shutil.copy2(baseline, session_dir / fname)
    print("Original session artifacts restored")


def main():
    if len(sys.argv) < 2:
        print("Usage: python eval/rerun_socratic.py <session_id>")
        sys.exit(1)

    session_id = sys.argv[1]
    asyncio.run(rerun(session_id))


if __name__ == "__main__":
    main()
