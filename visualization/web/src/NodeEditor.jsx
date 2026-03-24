import { useCallback, useEffect, useState } from "react";

const RELATIONSHIPS = [
  "supports",
  "contradicts",
  "subtopic_of",
  "cites",
  "example_of",
  "leads_to",
  "authored_by",
  "challenged_by",
  "replaces",
  "related_to",
];

export default function NodeEditor({
  node,
  allNodes,
  onClose,
  onUpdate,
  onDelete,
  onFlag,
  onAddEdge,
}) {
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [confidence, setConfidence] = useState(0.5);
  const [dirty, setDirty] = useState(false);

  // Edge creation state
  const [showEdgeForm, setShowEdgeForm] = useState(false);
  const [edgeTarget, setEdgeTarget] = useState("");
  const [edgeRelationship, setEdgeRelationship] = useState("related_to");

  useEffect(() => {
    if (node) {
      setLabel(node.label || "");
      setDescription(node.description || "");
      setConfidence(node.confidence ?? 0.5);
      setDirty(false);
      setShowEdgeForm(false);
    }
  }, [node]);

  const handleSave = useCallback(() => {
    onUpdate({ id: node.id, label, description, confidence });
    setDirty(false);
  }, [node, label, description, confidence, onUpdate]);

  const handleAddEdge = useCallback(() => {
    if (edgeTarget && edgeTarget !== node.id) {
      onAddEdge({
        source: node.id,
        target: edgeTarget,
        relationship: edgeRelationship,
      });
      setShowEdgeForm(false);
      setEdgeTarget("");
    }
  }, [node, edgeTarget, edgeRelationship, onAddEdge]);

  if (!node) return null;

  const otherNodes = allNodes.filter((n) => n.id !== node.id);

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <span style={styles.typeTag}>{node.type}</span>
        <button onClick={onClose} style={styles.closeBtn}>
          &times;
        </button>
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Label</label>
        <input
          style={styles.input}
          value={label}
          onChange={(e) => {
            setLabel(e.target.value);
            setDirty(true);
          }}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>Description</label>
        <textarea
          style={{ ...styles.input, height: 80, resize: "vertical" }}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            setDirty(true);
          }}
        />
      </div>

      <div style={styles.field}>
        <label style={styles.label}>
          Confidence: {confidence.toFixed(2)}
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={confidence}
          onChange={(e) => {
            setConfidence(parseFloat(e.target.value));
            setDirty(true);
          }}
          style={{ width: "100%" }}
        />
      </div>

      {node.metadata?.url && (
        <div style={styles.field}>
          <label style={styles.label}>URL</label>
          <a
            href={node.metadata.url}
            target="_blank"
            rel="noopener noreferrer"
            style={styles.link}
          >
            {node.metadata.url}
          </a>
        </div>
      )}

      <div style={styles.field}>
        <label style={styles.label}>ID</label>
        <span style={styles.mono}>{node.id}</span>
      </div>

      {node.provenance?.session_id && (
        <div style={styles.field}>
          <label style={styles.label}>Session</label>
          <span style={styles.mono}>{node.provenance.session_id}</span>
        </div>
      )}

      {dirty && (
        <button onClick={handleSave} style={styles.primaryBtn}>
          Save changes
        </button>
      )}

      <div style={styles.divider} />

      {/* Edge creation */}
      {!showEdgeForm ? (
        <button
          onClick={() => setShowEdgeForm(true)}
          style={styles.secondaryBtn}
        >
          + Add edge from this node
        </button>
      ) : (
        <div style={styles.edgeForm}>
          <label style={styles.label}>Target node</label>
          <select
            style={styles.select}
            value={edgeTarget}
            onChange={(e) => setEdgeTarget(e.target.value)}
          >
            <option value="">Select a node...</option>
            {otherNodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label} ({n.type})
              </option>
            ))}
          </select>
          <label style={{ ...styles.label, marginTop: 8 }}>Relationship</label>
          <select
            style={styles.select}
            value={edgeRelationship}
            onChange={(e) => setEdgeRelationship(e.target.value)}
          >
            {RELATIONSHIPS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={handleAddEdge} style={styles.primaryBtn}>
              Add edge
            </button>
            <button
              onClick={() => setShowEdgeForm(false)}
              style={styles.secondaryBtn}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div style={styles.divider} />

      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => onFlag({ id: node.id })}
          style={styles.warnBtn}
        >
          Flag for re-investigation
        </button>
        <button
          onClick={() => {
            if (confirm(`Delete "${node.label}"?`)) {
              onDelete({ id: node.id });
              onClose();
            }
          }}
          style={styles.dangerBtn}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

const styles = {
  panel: {
    position: "fixed",
    top: 0,
    right: 0,
    width: 360,
    height: "100vh",
    background: "#161b22",
    borderLeft: "1px solid #30363d",
    padding: 20,
    overflowY: "auto",
    zIndex: 100,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  typeTag: {
    background: "#21262d",
    padding: "4px 10px",
    borderRadius: 12,
    fontSize: 12,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    color: "#8b949e",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "#8b949e",
    fontSize: 24,
    cursor: "pointer",
    lineHeight: 1,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  label: {
    fontSize: 12,
    color: "#8b949e",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  input: {
    background: "#0d1117",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "8px 10px",
    color: "#c9d1d9",
    fontSize: 14,
    outline: "none",
    fontFamily: "inherit",
  },
  select: {
    background: "#0d1117",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "8px 10px",
    color: "#c9d1d9",
    fontSize: 13,
    outline: "none",
  },
  link: {
    color: "#58a6ff",
    fontSize: 13,
    wordBreak: "break-all",
  },
  mono: {
    fontFamily: "monospace",
    fontSize: 12,
    color: "#8b949e",
  },
  divider: {
    borderTop: "1px solid #21262d",
    margin: "4px 0",
  },
  primaryBtn: {
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  secondaryBtn: {
    background: "#21262d",
    color: "#c9d1d9",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 13,
  },
  warnBtn: {
    background: "#462c10",
    color: "#e3b341",
    border: "1px solid #5a3e1b",
    borderRadius: 6,
    padding: "8px 12px",
    cursor: "pointer",
    fontSize: 12,
    flex: 1,
  },
  dangerBtn: {
    background: "#3d1214",
    color: "#ff7b72",
    border: "1px solid #5a1e21",
    borderRadius: 6,
    padding: "8px 12px",
    cursor: "pointer",
    fontSize: 12,
  },
  edgeForm: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
};
