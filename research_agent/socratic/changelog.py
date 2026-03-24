"""Structured changelog for Socratic review outcomes.

Records what was challenged, on what grounds, and what happened.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

from research_agent.config import SESSIONS_DIR


@dataclass
class ChallengeOutcome:
    """A single challenge and its resolution."""

    node_id: str
    node_label: str
    grounds: str  # credibility, accuracy, completeness, confidence, logic, framing
    challenge_summary: str
    outcome: str  # retained, modified, removed
    change_description: str  # what changed (empty if retained)
    original_confidence: float
    final_confidence: float
    round_number: int


@dataclass
class Changelog:
    """Full changelog for one Socratic review stage."""

    session_id: str
    stage: str  # "findings" or "synthesis"
    total_rounds: int = 0
    termination_reason: str = ""  # "max_rounds", "no_further_objections", "all_resolved"
    outcomes: list[ChallengeOutcome] = field(default_factory=list)

    def add_outcome(self, outcome: ChallengeOutcome) -> None:
        self.outcomes.append(outcome)

    def summary_stats(self) -> dict:
        """Return counts of retained/modified/removed."""
        stats = {"retained": 0, "modified": 0, "removed": 0}
        for o in self.outcomes:
            if o.outcome in stats:
                stats[o.outcome] += 1
        return stats

    def save(self) -> Path:
        """Save changelog as JSON to the session directory."""
        session_dir = SESSIONS_DIR / f"session_{self.session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"changelog_{self.stage}.json"
        path.write_text(json.dumps(asdict(self), indent=2))
        return path
