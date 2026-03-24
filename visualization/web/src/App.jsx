import { useCallback, useState } from "react";
import GraphView from "./GraphView";
import NodeEditor from "./NodeEditor";
import AddNodeDialog from "./AddNodeDialog";
import AnalysisBanner from "./AnalysisBanner";
import useGraphSocket from "./useGraphSocket";

export default function App() {
  const {
    graph,
    connected,
    sessionState,
    addNode,
    updateNode,
    addEdge,
    deleteNode,
    flagNode,
    resumeSession,
  } = useGraphSocket();

  const [selectedNode, setSelectedNode] = useState(null);
  const [showAddDialog, setShowAddDialog] = useState(false);

  const handleNodeSelect = useCallback(
    (nodeData) => {
      setSelectedNode(nodeData);
    },
    []
  );

  const handleEdgeConnect = useCallback(
    (connection) => {
      addEdge({
        source: connection.source,
        target: connection.target,
        relationship: "related_to",
      });
    },
    [addEdge]
  );

  return (
    <>
      {/* Toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <span style={styles.title}>Research Mind Map</span>
          <span style={styles.stats}>
            {graph.nodes.length} nodes, {graph.edges.length} edges
          </span>
        </div>
        <div style={styles.toolbarRight}>
          <button
            style={styles.addBtn}
            onClick={() => setShowAddDialog(true)}
          >
            + Add Node
          </button>
          <span
            style={{
              ...styles.connIndicator,
              background: connected ? "#238636" : "#f85149",
            }}
            title={connected ? "Connected" : "Disconnected"}
          />
        </div>
      </div>

      {/* Analysis mode banner (Phase 4) */}
      {sessionState?.phase === "awaiting_user_input" && (
        <AnalysisBanner
          sessionId={sessionState.session_id}
          pausedAt={sessionState.paused_at}
          onResume={() => resumeSession(sessionState.session_id)}
        />
      )}

      {/* Graph */}
      <GraphView
        graph={graph}
        onNodeSelect={handleNodeSelect}
        onEdgeConnect={handleEdgeConnect}
      />

      {/* Node detail/editor panel */}
      {selectedNode && (
        <NodeEditor
          node={selectedNode}
          allNodes={graph.nodes}
          onClose={() => setSelectedNode(null)}
          onUpdate={updateNode}
          onDelete={deleteNode}
          onFlag={flagNode}
          onAddEdge={addEdge}
        />
      )}

      {/* Add node dialog */}
      {showAddDialog && (
        <AddNodeDialog
          onAdd={addNode}
          onClose={() => setShowAddDialog(false)}
        />
      )}

      {/* Legend */}
      <div style={styles.legend}>
        {Object.entries(LEGEND_ITEMS).map(([type, color]) => (
          <div key={type} style={styles.legendItem}>
            <span
              style={{ ...styles.legendDot, background: color }}
            />
            <span>{type}</span>
          </div>
        ))}
      </div>
    </>
  );
}

const LEGEND_ITEMS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#8b949e",
  question: "#d29922",
  direction: "#a371f7",
  decision: "#f85149",
};

const styles = {
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 20px",
    background: "#161b22",
    borderBottom: "1px solid #30363d",
    zIndex: 50,
  },
  toolbarLeft: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  toolbarRight: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  title: {
    fontSize: 15,
    fontWeight: 600,
    color: "#c9d1d9",
  },
  stats: {
    fontSize: 13,
    color: "#8b949e",
  },
  addBtn: {
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  connIndicator: {
    width: 10,
    height: 10,
    borderRadius: "50%",
    display: "inline-block",
  },
  legend: {
    position: "fixed",
    bottom: 16,
    left: 16,
    display: "flex",
    gap: 12,
    background: "rgba(22, 27, 34, 0.9)",
    border: "1px solid #30363d",
    borderRadius: 8,
    padding: "8px 14px",
    zIndex: 50,
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 5,
    fontSize: 11,
    color: "#8b949e",
    textTransform: "capitalize",
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
  },
};
