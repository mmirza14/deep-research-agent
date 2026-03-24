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
