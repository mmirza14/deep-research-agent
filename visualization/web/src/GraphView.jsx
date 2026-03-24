import { useCallback, useEffect, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useOnViewportChange,
  MarkerType,
} from "@xyflow/react";
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  forceX,
  forceY,
} from "d3-force";
import "@xyflow/react/dist/style.css";

import GraphNode from "./GraphNode";
import HoverEdge from "./HoverEdge";

// Register custom node/edge types
const nodeTypes = { graphNode: GraphNode };
const edgeTypes = { hoverEdge: HoverEdge };

// Node type → dot colour
const TYPE_COLORS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#8b949e",
  question: "#d29922",
  direction: "#a371f7",
  decision: "#f85149",
};

const EDGE_COLORS = {
  supports: "#2ea043",
  contradicts: "#f85149",
  subtopic_of: "#388bfd",
  cites: "#8b949e",
  challenged_by: "#d29922",
  default: "#30363d",
};

// Dot size range (scaled by degree)
const DOT_MIN = 6;
const DOT_MAX = 18;

// Zoom thresholds for label fading
const ZOOM_HIDE = 0.35; // fully hidden below this
const ZOOM_SHOW = 0.7; // fully visible above this

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function labelOpacityForZoom(zoom) {
  if (zoom >= ZOOM_SHOW) return 1;
  if (zoom <= ZOOM_HIDE) return 0;
  return (zoom - ZOOM_HIDE) / (ZOOM_SHOW - ZOOM_HIDE);
}

// ---------------------------------------------------------------------------
// Force layout
// ---------------------------------------------------------------------------

function computeForceLayout(graphNodes, graphEdges) {
  if (graphNodes.length === 0) return new Map();

  const nodeIds = new Set(graphNodes.map((n) => n.id));

  const simNodes = graphNodes.map((n) => ({
    id: n.id,
    x: Math.random() * 800 - 400,
    y: Math.random() * 800 - 400,
  }));

  const simLinks = graphEdges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ source: e.source, target: e.target }));

  const sim = forceSimulation(simNodes)
    .force(
      "link",
      forceLink(simLinks)
        .id((d) => d.id)
        .distance(80)
        .strength(1)
    )
    .force("charge", forceManyBody().strength(-350))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide().radius(30))
    .force("x", forceX(0).strength(0.04))
    .force("y", forceY(0).strength(0.04))
    .stop();

  const ticks = Math.min(300, Math.max(120, graphNodes.length * 2));
  sim.tick(ticks);

  const positions = new Map();
  for (const n of simNodes) {
    positions.set(n.id, { x: n.x, y: n.y });
  }
  return positions;
}

// ---------------------------------------------------------------------------
// Build React Flow elements
// ---------------------------------------------------------------------------

function computeDegrees(edges, nodeIds) {
  const deg = new Map();
  for (const id of nodeIds) deg.set(id, 0);
  for (const e of edges) {
    if (nodeIds.has(e.source)) deg.set(e.source, deg.get(e.source) + 1);
    if (nodeIds.has(e.target)) deg.set(e.target, deg.get(e.target) + 1);
  }
  return deg;
}

function toFlowElements(graphData, positionMap, labelOpacity) {
  const nodeIds = new Set(graphData.nodes.map((n) => n.id));
  const degrees = computeDegrees(graphData.edges, nodeIds);

  const maxDeg = Math.max(1, ...degrees.values());

  const flowNodes = graphData.nodes.map((n) => {
    const pos = positionMap.get(n.id) || { x: 0, y: 0 };
    const deg = degrees.get(n.id) || 0;
    const dotSize = DOT_MIN + ((deg / maxDeg) * (DOT_MAX - DOT_MIN));
    const color = TYPE_COLORS[n.type] || TYPE_COLORS.concept;

    return {
      id: n.id,
      type: "graphNode",
      position: pos,
      data: {
        label: n.label,
        color,
        dotSize,
        labelOpacity,
        ...n,
      },
      // Minimal wrapper — no default chrome
      style: {
        background: "transparent",
        border: "none",
        padding: 0,
        width: "auto",
        height: "auto",
      },
    };
  });

  const flowEdges = graphData.edges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({
      id: e.id,
      type: "hoverEdge",
      source: e.source,
      target: e.target,
      animated:
        e.relationship === "contradicts" || e.relationship === "challenged_by",
      style: {
        stroke: EDGE_COLORS[e.relationship] || EDGE_COLORS.default,
        strokeWidth: 1,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 10,
        height: 10,
        color: EDGE_COLORS[e.relationship] || EDGE_COLORS.default,
      },
      data: { relationship: e.relationship, ...e },
    }));

  return { flowNodes, flowEdges };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function ViewportTracker({ onZoomChange }) {
  useOnViewportChange({
    onChange: useCallback(
      (vp) => onZoomChange(vp.zoom),
      [onZoomChange]
    ),
  });
  return null;
}

export default function GraphView({ graph, onNodeSelect, onEdgeConnect }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [zoom, setZoom] = useState(1);

  const draggedRef = useRef(new Map());
  const lastStructureRef = useRef("");
  const forcePositionsRef = useRef(new Map());

  const labelOpacity = labelOpacityForZoom(zoom);

  useEffect(() => {
    const structureKey = `${graph.nodes.length}-${graph.edges.length}`;

    if (structureKey !== lastStructureRef.current) {
      lastStructureRef.current = structureKey;
      forcePositionsRef.current = computeForceLayout(graph.nodes, graph.edges);
    }

    const mergedPositions = new Map(forcePositionsRef.current);
    for (const [id, pos] of draggedRef.current) {
      mergedPositions.set(id, pos);
    }

    const { flowNodes, flowEdges } = toFlowElements(
      graph,
      mergedPositions,
      labelOpacity
    );

    setNodes((prev) => {
      const prevMap = new Map(prev.map((n) => [n.id, n]));
      return flowNodes.map((fn) => {
        const existing = prevMap.get(fn.id);
        if (existing) {
          // Keep position, update data (label opacity, etc.)
          return { ...fn, position: existing.position };
        }
        return fn;
      });
    });
    setEdges(flowEdges);
  }, [graph, labelOpacity, setNodes, setEdges]);

  const onNodeDragStop = useCallback((_event, node) => {
    draggedRef.current.set(node.id, node.position);
  }, []);

  const onNodeClick = useCallback(
    (_event, node) => onNodeSelect?.(node.data),
    [onNodeSelect]
  );

  const onConnect = useCallback(
    (connection) => onEdgeConnect?.(connection),
    [onEdgeConnect]
  );

  const onPaneClick = useCallback(() => onNodeSelect?.(null), [onNodeSelect]);

  return (
    <div style={{ flex: 1, background: "#0d1117" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onNodeDragStop={onNodeDragStop}
        onConnect={onConnect}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.5 }}
        minZoom={0.1}
        maxZoom={4}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ type: "hoverEdge" }}
      >
        <ViewportTracker onZoomChange={setZoom} />
        <Background color="#21262d" gap={20} />
        <Controls
          style={{
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: 8,
          }}
        />
        <MiniMap
          nodeColor={(n) => n.data?.color || "#1f6feb"}
          style={{
            background: "#161b22",
            border: "1px solid #30363d",
            borderRadius: 8,
          }}
          maskColor="rgba(13, 17, 23, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
