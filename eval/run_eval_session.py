#!/usr/bin/env python3
"""Run a fresh research session for end-to-end evaluation.

Uses a focused sub-question derived from the existing graph to test:
- Researcher cross-awareness (should link to existing nodes, not duplicate)
- Semantic dedup in add_node
- Thematic summary quality
- Ranked truncation in report

Saves all artifacts under eval/eval_session_<id>/ and runs proxy metrics.

Usage:
    python eval/run_eval_session.py
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from research_agent.graph.store import snapshot_graph
from research_agent.agent import run_research


# A question that deliberately overlaps with existing graph content
# to test cross-awareness and dedup
EVAL_QUESTION = (
    "What are the cost barriers and regulatory hurdles for scaling "
    "bio-based polymer alternatives to replace synthetic acrylates "
    "in personal care products by 2030?"
)


async def main():
    session_id = "eval_" + uuid.uuid4().hex[:6]

    print(f"Starting evaluation session: {session_id}")
    print(f"Question: {EVAL_QUESTION}")
    print(f"\nThis question overlaps with existing graph content to test:")
    print("  - Researcher cross-awareness (should link, not duplicate)")
    print("  - Semantic dedup in add_node")
    print("  - Thematic summary quality")
    print()

    # Snapshot before
    snapshot_graph(session_id)

    await run_research(EVAL_QUESTION, session_id)

    # Run proxy metrics
    print("\n\n" + "=" * 60)
    print("POST-SESSION METRICS")
    print("=" * 60 + "\n")

    from eval.proxy_metrics import compute_all_metrics
    metrics = compute_all_metrics(session_id)
    print(json.dumps(metrics, indent=2))

    # Save metrics
    eval_dir = PROJECT_ROOT / "eval"
    metrics_path = eval_dir / f"metrics_{session_id}.json"
    metrics_path.write_text(json.dumps(metrics, indent=2))
    print(f"\nMetrics saved: {metrics_path}")


if __name__ == "__main__":
    asyncio.run(main())
