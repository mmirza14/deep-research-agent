from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_PATH = DATA_DIR / "graph.json"
SNAPSHOTS_DIR = DATA_DIR / "graph_snapshots"
SESSIONS_DIR = DATA_DIR / "sessions"

# AgentDefinition.model accepts 'sonnet' | 'opus' | 'haiku'
LEAD_MODEL = "sonnet"
RESEARCHER_MODEL = "sonnet"

MAX_RESEARCHER_SUBAGENTS = 3
MAX_SEARCH_RESULTS_PER_SUBTOPIC = 5
MAX_TURNS = 30

# Socratic review
CRITIC_MODEL = "sonnet"
DEFENDER_MODEL = "sonnet"
MAX_SOCRATIC_ROUNDS = 5
CONFIDENCE_ESCALATION_THRESHOLD = 0.4  # Defender confidence below this triggers extra rounds
SOCRATIC_MAX_TURNS_PER_ROUND = 10  # Max turns per critic/defender agent call

# Report writer
REPORT_WRITER_MODEL = "sonnet"
REPORT_WRITER_MAX_TURNS = 25

# Collaborative analysis (Phase 4)
PAUSE_POLL_INTERVAL = 1.0  # seconds between state.json checks during analysis pause

# Direction finding (Phase 5)
DIRECTION_MODEL = "sonnet"
DIRECTION_MAX_TURNS = 20

# Single-node chat (Phase 5)
CHAT_MODEL = "haiku"
CHAT_MAX_TURNS = 5

# Visualization server
WS_PORT = 8420
WS_POLL_INTERVAL = 0.5  # seconds between graph.json change checks
