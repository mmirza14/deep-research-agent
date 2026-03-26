import { useCallback, useEffect, useImperativeHandle, useRef, useState, forwardRef } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  useOnViewportChange,
  useReactFlow,
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

const nodeTypes = { graphNode: GraphNode };
const edgeTypes = { hoverEdge: HoverEdge };

// Stitch palette — node type colours
const TYPE_COLORS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#c1c7d0",
  question: "#d29922",
  direction: "#8a58dd",
  decision: "#93000a",
};

// Stitch palette — edge relationship colours
const EDGE_COLORS = {
  supports: "#238636",
  contradicts: "#93000a",
  subtopic_of: "#1f6feb",
  cites: "#424754",
  challenged_by: "#d29922",
  leads_to: "#8a58dd",
  default: "#424754",
};

const DOT_MIN = 6;
const DOT_MAX = 18;
const ZOOM_HIDE = 0.35;
const ZOOM_SHOW = 0.7;

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

function toFlowElements(graphData, positionMap, labelOpacity, selectedNodeId) {
  const nodeIds = new Set(graphData.nodes.map((n) => n.id));
  const degrees = computeDegrees(graphData.edges, nodeIds);

  const maxDeg = Math.max(1, ...degrees.values());

  const flowNodes = graphData.nodes.map((n) => {
    const pos = positionMap.get(n.id) || { x: 0, y: 0 };
    const deg = degrees.get(n.id) || 0;
    const sizeMultiplier = (n.type === "direction" || n.type === "question") ? 1.3 : 1.0;
    const dotSize = (DOT_MIN + ((deg / maxDeg) * (DOT_MAX - DOT_MIN))) * sizeMultiplier;
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
        selected: n.id === selectedNodeId,
        ...n,
      },
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
    .map((e) => {
      const edgeColor = EDGE_COLORS[e.relationship] || EDGE_COLORS.default;
      return {
        id: e.id,
        type: "hoverEdge",
        source: e.source,
        target: e.target,
        animated:
          e.relationship === "contradicts" || e.relationship === "challenged_by",
        style: {
          stroke: edgeColor,
          strokeWidth: 1,
          strokeOpacity: 0.6,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 10,
          height: 10,
          color: edgeColor,
        },
        data: { relationship: e.relationship, ...e },
      };
    });

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

function PanHelper({ panRef }) {
  const { setCenter, getNodes } = useReactFlow();
  useImperativeHandle(panRef, () => ({
    panToNode(nodeId) {
      const rfNode = getNodes().find((n) => n.id === nodeId);
      if (rfNode) {
        setCenter(rfNode.position.x, rfNode.position.y, { zoom: 1.2, duration: 400 });
      }
    },
  }));
  return null;
}

const GraphView = forwardRef(function GraphView({ graph, onNodeSelect, onEdgeConnect, selectedNodeId }, ref) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [zoom, setZoom] = useState(1);

  const draggedRef = useRef(new Map());
  const lastStructureRef = useRef("");
  const forcePositionsRef = useRef(new Map());
  const panRef = useRef(null);

  useImperativeHandle(ref, () => ({
    panToNode(nodeId) {
      panRef.current?.panToNode(nodeId);
    },
  }));

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
      labelOpacity,
      selectedNodeId
    );

    setNodes((prev) => {
      const prevMap = new Map(prev.map((n) => [n.id, n]));
      return flowNodes.map((fn) => {
        const existing = prevMap.get(fn.id);
        if (existing) {
          return { ...fn, position: existing.position };
        }
        return fn;
      });
    });
    setEdges(flowEdges);
  }, [graph, labelOpacity, selectedNodeId, setNodes, setEdges]);

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
    <div style={canvasStyle}>
      {/* Dot grid background layer */}
      <div style={dotGridStyle} />
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
        <PanHelper panRef={panRef} />
        <Controls
          style={{
            background: "var(--surface-high)",
            border: "1px solid var(--ghost-border)",
            borderRadius: 8,
          }}
        />
        <MiniMap
          nodeColor={(n) => n.data?.color || "#1f6feb"}
          style={{
            background: "rgba(38, 42, 49, 0.7)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid var(--ghost-border)",
            borderRadius: 12,
          }}
          maskColor="rgba(16, 20, 26, 0.7)"
        />
      </ReactFlow>
    </div>
  );
});

const canvasStyle = {
  width: "100%",
  height: "100%",
  position: "relative",
  background: "var(--surface-base)",
};

const dotGridStyle = {
  position: "absolute",
  inset: 0,
  backgroundImage: "radial-gradient(#424754 1px, transparent 1px)",
  backgroundSize: "40px 40px",
  opacity: 0.15,
  pointerEvents: "none",
  zIndex: 0,
};

export default GraphView;
