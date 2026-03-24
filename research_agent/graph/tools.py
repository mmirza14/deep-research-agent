"""Graph mutation and query tools exposed to agents via SDK MCP server."""

from __future__ import annotations

import json

from claude_agent_sdk import tool, create_sdk_mcp_server

from research_agent.graph.schema import Graph, Node, Edge
from research_agent.graph.store import load_graph, save_graph
from research_agent.graph.summarizer import summarize_graph

# Module-level graph instance — loaded once, mutated in-place, saved after each write.
_graph: Graph | None = None


def _get_graph() -> Graph:
    global _graph
    if _graph is None:
        _graph = load_graph()
    return _graph


def _save() -> None:
    if _graph is not None:
        save_graph(_graph)


def _text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "add_node",
    "Add a node to the knowledge graph. Returns the new node's ID.",
    {
        "label": str,
        "type": str,
        "description": str,
        "confidence": float,
        "url": str,
        "source_type": str,
        "session_id": str,
        "subagent": str,
        "mode": str,
    },
)
async def add_node(args: dict) -> dict:
    g = _get_graph()
    node = Node(
        label=args["label"],
        type=args["type"],
        description=args["description"],
        confidence=args.get("confidence", 0.5),
        provenance={
            "session_id": args.get("session_id", ""),
            "subagent": args.get("subagent", ""),
            "mode": args.get("mode", "survey"),
        },
        metadata={
            "url": args.get("url"),
            "source_type": args.get("source_type"),
            "user_added": False,
        },
    )
    node_id = g.add_node(node)
    _save()
    return _text_result(f"Node added: {node_id}")


@tool(
    "add_edge",
    "Add an edge between two nodes in the knowledge graph. Returns the new edge's ID.",
    {
        "source_id": str,
        "target_id": str,
        "relationship": str,
        "weight": float,
        "session_id": str,
        "subagent": str,
        "mode": str,
    },
)
async def add_edge(args: dict) -> dict:
    g = _get_graph()
    edge = Edge(
        source=args["source_id"],
        target=args["target_id"],
        relationship=args["relationship"],
        weight=args.get("weight", 1.0),
        provenance={
            "session_id": args.get("session_id", ""),
            "subagent": args.get("subagent", ""),
            "mode": args.get("mode", "survey"),
        },
    )
    edge_id = g.add_edge(edge)
    _save()
    return _text_result(f"Edge added: {edge_id}")


@tool(
    "update_node",
    "Update confidence or description on an existing node.",
    {
        "node_id": str,
        "confidence": float,
        "description": str,
    },
)
async def update_node(args: dict) -> dict:
    g = _get_graph()
    updates: dict = {}
    if "confidence" in args and args["confidence"] is not None:
        updates["confidence"] = args["confidence"]
    if "description" in args and args["description"] is not None:
        updates["description"] = args["description"]
    if g.update_node(args["node_id"], updates):
        _save()
        return _text_result(f"Node {args['node_id']} updated.")
    return _text_result(f"Node {args['node_id']} not found.")


@tool(
    "get_graph_summary",
    "Get a compressed text summary of the current knowledge graph including node counts, key clusters, recent additions, and low-confidence areas.",
    {},
)
async def get_graph_summary(args: dict) -> dict:
    g = _get_graph()
    return _text_result(summarize_graph(g))


@tool(
    "get_neighborhood",
    "Get all nodes and edges within N hops of a given node.",
    {
        "node_id": str,
        "depth": int,
    },
)
async def get_neighborhood(args: dict) -> dict:
    g = _get_graph()
    subgraph = g.get_neighborhood(args["node_id"], args.get("depth", 1))
    return _text_result(json.dumps(subgraph, indent=2))


def get_all_tools() -> list:
    """Return all graph tool instances for MCP server registration."""
    return [add_node, add_edge, update_node, get_graph_summary, get_neighborhood]


def create_graph_mcp_server():
    """Create an in-process MCP server with all graph tools."""
    return create_sdk_mcp_server(
        name="research-graph",
        version="0.1.0",
        tools=get_all_tools(),
    )
