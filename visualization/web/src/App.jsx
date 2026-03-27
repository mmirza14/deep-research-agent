import { useCallback, useEffect, useRef, useState } from "react";
import ActivityFeed from "./ActivityFeed";
import GraphView from "./GraphView";
import NodeEditor from "./NodeEditor";
import NodeChat from "./NodeChat";
import AddNodeDialog from "./AddNodeDialog";
import AnalysisBanner from "./AnalysisBanner";
import DirectionsPanel from "./DirectionsPanel";
import HomeScreen from "./HomeScreen";
import PhaseTimeline from "./PhaseTimeline";
import SessionPanel from "./SessionPanel";
import ToastContainer from "./ToastContainer";
import useGraphSocket from "./useGraphSocket";

const SIDEBAR_ICONS = [
  { icon: "sync", label: "Status", action: null },
  { icon: "help_outline", label: "Help", action: null },
  { icon: "send", label: "Directions", action: "directions" },
  { icon: "history", label: "History", action: "history" },
];

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
    startResearch,
    chatState,
    startChat,
    sendChatMessage,
    endChat,
    agentPhase,
    sessions,
    activeSessionId,
    setActiveSession,
    listSessions,
    startNewResearch,
    activities,
    toasts,
    dismissToast,
  } = useGraphSocket();

  const [selectedNode, setSelectedNode] = useState(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showDirections, setShowDirections] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [rightTab, setRightTab] = useState("editor");
  const [showHome, setShowHome] = useState(true);
  const graphRef = useRef(null);

  // Exit home screen when graph gets populated
  useEffect(() => {
    if (graph.nodes.length > 0 && showHome) {
      setShowHome(false);
    }
  }, [graph.nodes.length, showHome]);

  const handleNodeSelect = useCallback((nodeData) => {
    setSelectedNode(nodeData);
  }, []);

  const handleDirectionSelect = useCallback(
    (nodeId) => {
      const nodeData = graph.nodes.find((n) => n.id === nodeId);
      if (nodeData) {
        setSelectedNode(nodeData);
        graphRef.current?.panToNode(nodeId);
      }
    },
    [graph]
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

  const bannerPhases = ["awaiting_user_input", "synthesizing", "socratic_review_2", "writing_insights", "complete"];
  const hasBanner =
    sessionState?.phase === "awaiting_user_input" ||
    (agentPhase?.phase && bannerPhases.includes(agentPhase.phase));

  return (
    <>
      {/* Header Bar */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.brandName}>Kinetic Intellect</span>
          <span style={styles.stats}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
              auto_awesome
            </span>
            Nodes: {graph.nodes.length}
          </span>
          <span style={styles.stats}>
            <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
              hub
            </span>
            Edges: {graph.edges.length}
          </span>
        </div>
        <div style={styles.headerRight}>
          <div style={styles.agentStatus}>
            <span
              style={{
                ...styles.statusDot,
                background: !connected
                  ? "var(--error-container)"
                  : agentPhase?.phase === "complete"
                  ? "var(--claim-green)"
                  : agentPhase?.phase === "error"
                  ? "var(--error-container)"
                  : agentPhase?.phase && agentPhase.phase !== "awaiting_user_input"
                  ? "var(--node-direction)"
                  : "var(--claim-green)",
                boxShadow: !connected
                  ? "0 0 8px rgba(147,0,10,0.4)"
                  : agentPhase?.phase && !["complete", "error", "awaiting_user_input"].includes(agentPhase.phase)
                  ? "0 0 8px rgba(163,113,247,0.6)"
                  : "0 0 8px rgba(35,134,54,0.6)",
                animation: agentPhase?.phase && !["complete", "error", "awaiting_user_input"].includes(agentPhase.phase)
                  ? "pulse 1.5s ease-in-out infinite"
                  : "none",
              }}
            />
            <span style={styles.statusLabel}>
              {!connected
                ? "OFFLINE"
                : agentPhase?.detail
                ? agentPhase.detail
                : "ACTIVE"}
            </span>
            {agentPhase?.node_count > 0 && connected && (
              <span style={{ ...styles.statusLabel, color: "var(--text-tertiary)", marginLeft: 4 }}>
                ({agentPhase.node_count}n / {agentPhase.edge_count}e)
              </span>
            )}
          </div>
          <button style={styles.newResearchBtn} onClick={() => setShowHome(true)}>
            <span className="material-symbols-outlined" style={{ fontSize: 16, marginRight: 4 }}>
              add_circle
            </span>
            New Research
          </button>
          <button style={styles.addNodeBtn} onClick={() => setShowAddDialog(true)}>
            + Add Node
          </button>
          <button style={styles.directionsBtn} onClick={() => setShowDirections((v) => !v)}>
            <span className="material-symbols-outlined" style={{ fontSize: 16, marginRight: 4 }}>
              send
            </span>
            Directions
          </button>
          <div style={styles.avatar} />
        </div>
      </div>

      {/* Analysis banner — shown during review + post-proceed phases */}
      {hasBanner && (
        <AnalysisBanner
          sessionId={sessionState?.session_id || agentPhase?.session_id}
          pausedAt={sessionState?.paused_at}
          agentPhase={agentPhase}
          hasLitReview={!!sessionState?.lit_review_path}
          onResume={() => resumeSession(sessionState?.session_id)}
          onViewDocument={(sid, docType) => {
            // TODO: wire to document viewer in Phase 4A
          }}
        />
      )}

      <div style={styles.body}>
        {showHome && graph.nodes.length === 0 ? (
          <HomeScreen
            sessions={sessions}
            onStartResearch={(q) => {
              startNewResearch(q);
              setShowHome(false);
            }}
            onSelectSession={(sid) => {
              setActiveSession(sid);
              setShowHome(false);
            }}
            onRefreshSessions={listSessions}
          />
        ) : (
        <>
        {/* Left Sidebar (collapsed) */}
        <div style={styles.sidebar}>
          <div style={styles.sidebarIcons}>
            {SIDEBAR_ICONS.map(({ icon, label, action }) => (
              <button
                key={icon}
                style={{
                  ...styles.sidebarIcon,
                  color:
                    action === "directions" && showDirections
                      ? "var(--primary)"
                      : action === "history" && showSessions
                      ? "var(--primary)"
                      : icon === "sync"
                      ? connected
                        ? "var(--claim-green)"
                        : "var(--error-container)"
                      : "var(--text-tertiary)",
                }}
                title={label}
                onClick={
                  action === "directions"
                    ? () => setShowDirections((v) => !v)
                    : action === "history"
                    ? () => setShowSessions((v) => !v)
                    : undefined
                }
              >
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                  {icon}
                </span>
              </button>
            ))}
          </div>
          <PhaseTimeline agentPhase={agentPhase} />
        </div>

        {/* Directions Panel */}
        <DirectionsPanel
          graph={graph}
          onSelectNode={handleDirectionSelect}
          onResearchThis={startResearch}
          visible={showDirections}
          onToggle={() => setShowDirections((v) => !v)}
        />

        {/* Session Panel */}
        <SessionPanel
          sessions={sessions}
          activeSessionId={activeSessionId}
          visible={showSessions}
          onToggle={() => setShowSessions((v) => !v)}
          onSelectSession={(sid) => {
            setActiveSession(sid);
            setShowSessions(false);
            setShowHome(false);
          }}
          onNewResearch={() => {
            setShowSessions(false);
            setShowHome(true);
          }}
          onRefreshSessions={listSessions}
        />

        {/* Graph Canvas */}
        <div
          style={{
            ...styles.canvas,
            marginLeft: (showDirections || showSessions) ? 320 + 56 : 56,
            marginRight: selectedNode ? 360 : 0,
          }}
        >
          <GraphView
            ref={graphRef}
            graph={graph}
            onNodeSelect={handleNodeSelect}
            onEdgeConnect={handleEdgeConnect}
            selectedNodeId={selectedNode?.id}
          />

          {/* Legend (bottom-left) */}
          <div className="glass-panel" style={styles.legend}>
            <div style={styles.legendTitle}>ONTOLOGY LEGEND</div>
            {Object.entries(LEGEND_ITEMS).map(([type, { color, shape }]) => (
              <div key={type} style={styles.legendItem}>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    display: "inline-block",
                    background: color,
                    borderRadius: shape === "circle" ? "50%" : 0,
                    clipPath:
                      shape === "diamond"
                        ? "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)"
                        : shape === "triangle"
                        ? "polygon(50% 0%, 100% 100%, 0% 100%)"
                        : undefined,
                  }}
                />
                <span>{type}</span>
              </div>
            ))}
          </div>

          {/* Activity Feed (bottom drawer) */}
          <ActivityFeed activities={activities} />
        </div>

        {/* Right Panel */}
        {selectedNode && (
          <div style={styles.rightPanel}>
            <div style={styles.rightPanelHeader}>
              <span style={styles.panelTitle}>Analysis Panel</span>
              <button
                onClick={() => {
                  setSelectedNode(null);
                  setRightTab("editor");
                  if (chatState?.chatId) endChat(chatState.chatId);
                }}
                style={styles.panelCloseBtn}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
                  close
                </span>
              </button>
            </div>
            <div style={styles.tabBar}>
              <button
                style={rightTab === "editor" ? styles.tabActive : styles.tabInactive}
                onClick={() => setRightTab("editor")}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 6 }}>
                  tune
                </span>
                EDITOR
              </button>
              <button
                style={rightTab === "chat" ? styles.tabActive : styles.tabInactive}
                onClick={() => setRightTab("chat")}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 6 }}>
                  chat
                </span>
                CHAT
              </button>
            </div>
            <div style={styles.rightPanelContent}>
              {rightTab === "editor" ? (
                <NodeEditor
                  node={selectedNode}
                  allNodes={graph.nodes}
                  onClose={() => {
                    setSelectedNode(null);
                    setRightTab("editor");
                  }}
                  onUpdate={updateNode}
                  onDelete={deleteNode}
                  onFlag={flagNode}
                  onAddEdge={addEdge}
                  onResearchThis={startResearch}
                />
              ) : (
                <NodeChat
                  node={selectedNode}
                  chatState={chatState}
                  onStartChat={startChat}
                  onSendMessage={sendChatMessage}
                  onEndChat={endChat}
                />
              )}
            </div>
          </div>
        )}
        </>
        )}
      </div>

      {/* Add node dialog */}
      {showAddDialog && (
        <AddNodeDialog
          onAdd={addNode}
          onClose={() => setShowAddDialog(false)}
        />
      )}

      {/* Toast notifications */}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}

const LEGEND_ITEMS = {
  concept: { color: "var(--node-concept)", shape: "circle" },
  claim: { color: "var(--node-claim)", shape: "circle" },
  source: { color: "var(--node-source)", shape: "circle" },
  question: { color: "var(--node-question)", shape: "triangle" },
  direction: { color: "var(--node-direction)", shape: "diamond" },
  decision: { color: "var(--node-decision)", shape: "circle" },
};

const styles = {
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    height: 40,
    padding: "0 16px",
    background: "var(--surface-base)",
    borderBottom: "1px solid var(--ghost-border)",
    zIndex: 50,
    flexShrink: 0,
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  headerRight: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  brandName: {
    fontSize: 14,
    fontWeight: 700,
    color: "var(--text-primary)",
    letterSpacing: "-0.02em",
  },
  stats: {
    fontSize: 12,
    color: "var(--text-tertiary)",
    display: "flex",
    alignItems: "center",
    fontWeight: 500,
    letterSpacing: "0.02em",
  },
  agentStatus: {
    display: "flex",
    alignItems: "center",
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
  },
  statusLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  newResearchBtn: {
    background: "var(--tertiary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.02em",
    display: "flex",
    alignItems: "center",
    transition: "filter 0.15s ease",
  },
  addNodeBtn: {
    background: "var(--primary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.02em",
    transition: "filter 0.15s ease",
  },
  directionsBtn: {
    background: "var(--tertiary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.02em",
    display: "flex",
    alignItems: "center",
    transition: "filter 0.15s ease",
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: "50%",
    background: "var(--surface-high)",
    border: "1px solid var(--ghost-border)",
  },
  body: {
    display: "flex",
    flex: 1,
    position: "relative",
    overflow: "hidden",
  },
  sidebar: {
    width: 56,
    background: "var(--surface-low)",
    borderRight: "1px solid var(--ghost-border)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    zIndex: 40,
    flexShrink: 0,
    justifyContent: "space-between",
    overflow: "hidden",
  },
  sidebarIcons: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: 16,
    gap: 24,
  },
  sidebarIcon: {
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: 8,
    borderRadius: 8,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "background 0.15s ease, color 0.15s ease",
  },
  canvas: {
    flex: 1,
    position: "relative",
    transition: "margin 0.2s ease",
    overflow: "hidden",
  },
  rightPanel: {
    width: 360,
    background: "var(--surface-container)",
    borderLeft: "1px solid var(--ghost-border)",
    boxShadow: "-20px 0 40px rgba(0, 0, 0, 0.4)",
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
    zIndex: 40,
  },
  rightPanelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "12px 16px",
  },
  panelTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  panelCloseBtn: {
    background: "none",
    border: "none",
    color: "var(--text-tertiary)",
    cursor: "pointer",
    padding: 4,
    borderRadius: 4,
    display: "flex",
    alignItems: "center",
    transition: "color 0.15s ease",
  },
  tabBar: {
    display: "flex",
    gap: 0,
    padding: "0 16px",
  },
  tabActive: {
    background: "none",
    border: "none",
    borderBottom: "2px solid var(--primary)",
    color: "var(--text-primary)",
    padding: "8px 16px",
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
    letterSpacing: "0.05em",
    display: "flex",
    alignItems: "center",
  },
  tabInactive: {
    background: "none",
    border: "none",
    borderBottom: "2px solid transparent",
    color: "var(--text-tertiary)",
    padding: "8px 16px",
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
    letterSpacing: "0.05em",
    display: "flex",
    alignItems: "center",
  },
  rightPanelContent: {
    flex: 1,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  legend: {
    position: "absolute",
    bottom: 24,
    left: 24,
    borderRadius: 12,
    padding: "12px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    zIndex: 30,
    width: 192,
  },
  legendTitle: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.15em",
    marginBottom: 4,
    textTransform: "uppercase",
  },
  legendItem: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 11,
    fontWeight: 500,
    color: "var(--text-secondary)",
    textTransform: "capitalize",
  },
};
