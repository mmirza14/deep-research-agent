"""Format and persist full Socratic review transcripts as markdown."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from research_agent.config import SESSIONS_DIR


@dataclass
class TranscriptEntry:
    """One turn in the Critic/Defender exchange."""

    round_number: int
    role: str  # "critic" or "defender"
    content: str


@dataclass
class Transcript:
    """Full transcript of a Socratic review stage."""

    session_id: str
    stage: str  # "findings" or "synthesis"
    entries: list[TranscriptEntry] = field(default_factory=list)

    def add_entry(self, round_number: int, role: str, content: str) -> None:
        self.entries.append(TranscriptEntry(
            round_number=round_number,
            role=role,
            content=content,
        ))

    def to_markdown(self) -> str:
        """Render transcript as readable markdown."""
        lines = [
            f"# Socratic Review Transcript — {self.stage.title()}",
            f"Session: {self.session_id}",
            f"Rounds: {max((e.round_number for e in self.entries), default=0)}",
            "",
            "---",
            "",
        ]
        for entry in self.entries:
            header = "Critic" if entry.role == "critic" else "Defender"
            lines.append(f"## Round {entry.round_number} — {header}")
            lines.append("")
            lines.append(entry.content)
            lines.append("")
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def save(self) -> Path:
        """Save transcript as markdown to the session directory."""
        session_dir = SESSIONS_DIR / f"session_{self.session_id}"
        session_dir.mkdir(parents=True, exist_ok=True)
        path = session_dir / f"transcript_{self.stage}.md"
        path.write_text(self.to_markdown())
        return path
