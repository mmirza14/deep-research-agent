# Deep Research Agent

Multi-agent research system that builds a persistent knowledge graph through structured literature survey, adversarial Socratic review, and an interactive mind map.

## How it works

1. **Lead agent** takes a research question, decomposes it into sub-topics, and creates a question structure in the knowledge graph
2. **Researcher subagents** (3-5 in parallel) search the web, extract claims, and write findings as nodes/edges to a shared graph via an MCP server
3. **Lead agent** reviews the populated graph and synthesizes a structured research report

Built on `claude-agent-sdk` with a standalone MCP stdio server for shared graph access across agent processes.

## Setup

```bash
cd deep-research
pip install -e .
```

Requires a Claude Code CLI session with Max plan (for Agent SDK auth).

## Usage

### Run the research agent

```bash
# Interactive mode
python -m research_agent.agent

# Single query
python -m research_agent.agent "What are the current approaches to LLM evaluation?"
```

### View the mind map

In a separate terminal:

```bash
python visualization/server.py
```

Then open http://localhost:8420. Click **Refresh** to reload after the agent updates the graph.

## Project structure

```
deep-research/
├── research_agent/
│   ├── agent.py          # Lead agent orchestration via query()
│   ├── prompts.py        # System prompts for all roles
│   ├── config.py         # Model, paths, thresholds
│   ├── mcp_server.py     # Standalone MCP stdio server for graph tools
│   ├── graph/
│   │   ├── schema.py     # Node, Edge, Graph dataclasses
│   │   ├── store.py      # Load/save/snapshot graph JSON
│   │   ├── tools.py      # SDK MCP tool definitions (kept for reference)
│   │   └── summarizer.py # Graph → text for agent context
│   └── socratic/         # Phase 2: Critic/Defender review (not yet implemented)
├── visualization/
│   ├── server.py         # HTTP server for mind map
│   └── web/public/       # D3 force-graph visualization
├── data/
│   ├── graph.json        # Persistent knowledge graph
│   └── graph_snapshots/  # Per-session backups
└── pyproject.toml
```

## Build phases

- [x] **Phase 1: Walking Skeleton** — agent loop, parallel researchers, graph tools, static mind map
- [ ] **Phase 2: Socratic Review** — Critic/Defender adversarial review of findings
- [ ] **Phase 3: Interactive Mind Map** — React + WebSocket, live updates, user edits
- [ ] **Phase 4: Collaborative Analysis (L2)** — human-in-the-loop analysis mode
- [ ] **Phase 5: Direction Finding (L3)** — graph gap detection, novel direction proposals
- [ ] **Phase 6: Instrumentation** — token tracking, cost attribution per taxonomy
- [ ] **Phase 7: Native macOS App** — Swift/SwiftUI mind map
