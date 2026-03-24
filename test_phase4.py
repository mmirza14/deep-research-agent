"""Phase 4 integration test — simulate analysis mode using an existing session.

Writes a state.json to trigger the pause, then polls for resume (same as the
real pipeline). Run alongside the WebSocket server + React UI to test the full
flow: banner appears → user edits graph → clicks Proceed → diff is computed.

Usage:
    python test_phase4.py [session_id]

Defaults to session_a7a98575 if no session ID is provided.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from research_agent.config import SESSIONS_DIR, PAUSE_POLL_INTERVAL
from research_agent.graph.store import diff_graph_since, snapshot_graph
from research_agent.prompts import format_user_feedback


async def test_analysis_mode(session_id: str) -> None:
    session_dir = SESSIONS_DIR / f"session_{session_id}"
    if not session_dir.exists():
        print(f"Session {session_id} not found at {session_dir}")
        return

    # Take a fresh snapshot so diff_graph_since has a baseline
    snap = snapshot_graph(session_id)
    print(f"Snapshot saved: {snap}")

    # Write state.json to trigger analysis mode
    state_path = session_dir / "state.json"
    state = {
        "phase": "awaiting_user_input",
        "session_id": session_id,
        "research_question": "(test — using existing session data)",
        "lit_review_path": str(session_dir / "literature_review.md"),
        "paused_at": datetime.now(timezone.utc).isoformat(),
    }
    state_path.write_text(json.dumps(state, indent=2))

    print()
    print("=" * 60)
    print("ANALYSIS MODE — Test")
    print("=" * 60)
    print(f"Session: {session_id}")
    print(f"State file: {state_path}")
    print()
    print("The WebSocket server should now broadcast this state.")
    print("Open the mind map UI and you should see the purple banner.")
    print()
    print("Try these actions:")
    print("  1. Add a question node")
    print("  2. Flag a claim node")
    print("  3. Edit a node's confidence")
    print("  4. Click 'Proceed to Synthesis'")
    print()
    print("Waiting for resume signal...")
    print("=" * 60)

    # Poll for resume — same logic as agent.py
    while True:
        await asyncio.sleep(PAUSE_POLL_INTERVAL)
        try:
            current = json.loads(state_path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        if current.get("phase") == "resume_synthesis":
            print("\n** Resume signal received! **\n")
            break

    # Compute diff
    print("Computing graph diff since snapshot...")
    diff = diff_graph_since(session_id)

    print(f"\nResults:")
    print(f"  User-added nodes:    {len(diff['user_added_nodes'])}")
    print(f"  Flagged nodes:       {len(diff['flagged_nodes'])}")
    print(f"  Modified nodes:      {len(diff['user_modified_nodes'])}")
    print(f"  Deleted node IDs:    {len(diff['user_deleted_node_ids'])}")
    print(f"  User-added edges:    {len(diff['user_added_edges'])}")

    feedback_text = format_user_feedback(diff)
    print(f"\nFormatted feedback for synthesis prompt:")
    print("-" * 40)
    print(feedback_text)
    print("-" * 40)

    # Clean up state file
    state_path.unlink()
    print(f"\nCleaned up {state_path}")
    print("Phase 4 test complete.")


if __name__ == "__main__":
    sid = sys.argv[1] if len(sys.argv) > 1 else "a7a98575"
    asyncio.run(test_analysis_mode(sid))
