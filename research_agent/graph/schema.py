from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    CONCEPT = "concept"
    CLAIM = "claim"
    SOURCE = "source"
    QUESTION = "question"
    DIRECTION = "direction"
    DECISION = "decision"


class SourceType(str, Enum):
    ACADEMIC = "academic"
    INDUSTRY = "industry"
    BLOG = "blog"
    BOOK = "book"
    GOVERNMENT = "government"
    OTHER = "other"


class Relationship(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUBTOPIC_OF = "subtopic_of"
    CITES = "cites"
    EXAMPLE_OF = "example_of"
    LEADS_TO = "leads_to"
    AUTHORED_BY = "authored_by"
    CHALLENGED_BY = "challenged_by"
    REPLACES = "replaces"
    RELATED_TO = "related_to"


class ResearchMode(str, Enum):
    SURVEY = "survey"
    ANALYSIS = "analysis"
    DIRECTION = "direction"


@dataclass
class Provenance:
    session_id: str
    subagent: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    mode: str = ResearchMode.SURVEY.value


@dataclass
class NodeMetadata:
    url: str | None = None
    source_type: str | None = None
    user_added: bool = False


@dataclass
class Node:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    label: str = ""
    type: str = NodeType.CONCEPT.value
    description: str = ""
    confidence: float = 0.5
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    source: str = ""
    target: str = ""
    relationship: str = Relationship.RELATED_TO.value
    weight: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class Graph:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)

    def add_node(self, node: Node) -> str:
        self.nodes.append(asdict(node))
        return node.id

    def add_edge(self, edge: Edge) -> str:
        self.edges.append(asdict(edge))
        return edge.id

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        for n in self.nodes:
            if n["id"] == node_id:
                return n
        return None

    def update_node(self, node_id: str, updates: dict[str, Any]) -> bool:
        for n in self.nodes:
            if n["id"] == node_id:
                n.update(updates)
                return True
        return False

    def get_neighborhood(self, node_id: str, depth: int = 1) -> dict:
        visited_nodes: set[str] = {node_id}
        frontier: set[str] = {node_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for e in self.edges:
                if e["source"] in frontier:
                    next_frontier.add(e["target"])
                if e["target"] in frontier:
                    next_frontier.add(e["source"])
            next_frontier -= visited_nodes
            visited_nodes |= next_frontier
            frontier = next_frontier

        result_nodes = [n for n in self.nodes if n["id"] in visited_nodes]
        result_edges = [
            e for e in self.edges
            if e["source"] in visited_nodes and e["target"] in visited_nodes
        ]
        return {"nodes": result_nodes, "edges": result_edges}
