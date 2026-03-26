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

const TYPE_COLORS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#c1c7d0",
  question: "#d29922",
  direction: "#8a58dd",
  decision: "#93000a",
};

export default function NodeEditor({
  node,
  allNodes,
  onClose,
  onUpdate,
  onDelete,
  onFlag,
  onAddEdge,
  onResearchThis,
}) {
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [confidence, setConfidence] = useState(0.5);
  const [dirty, setDirty] = useState(false);
  const [showEdgeForm, setShowEdgeForm] = useState(false);
  const [edgeTarget, setEdgeTarget] = useState("");
  const [edgeRelationship, setEdgeRelationship] = useState("related_to");
  const [researchStarted, setResearchStarted] = useState(false);

  useEffect(() => {
    if (node) {
      setLabel(node.label || "");
      setDescription(node.description || "");
      setConfidence(node.confidence ?? 0.5);
      setDirty(false);
      setShowEdgeForm(false);
      setResearchStarted(false);
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
  const typeColor = TYPE_COLORS[node.type] || TYPE_COLORS.concept;

  return (
    <div style={styles.panel}>
      {/* Node Identity */}
      <div style={styles.section}>
        <div style={styles.sectionLabel}>NODE IDENTITY</div>
        <span
          style={{
            ...styles.typeTag,
            background: typeColor,
            color: node.type === "source" ? "#10141a" : "#fff",
          }}
        >
          {node.type}
        </span>
        <input
          style={styles.labelInput}
          value={label}
          onChange={(e) => {
            setLabel(e.target.value);
            setDirty(true);
          }}
        />
      </div>

      {/* Description */}
      <div style={styles.section}>
        <div style={styles.sectionLabel}>DESCRIPTION</div>
        <textarea
          style={styles.textarea}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            setDirty(true);
          }}
        />
      </div>

      {/* Confidence */}
      <div style={styles.section}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={styles.sectionLabel}>CONFIDENCE SCORE</div>
          <span style={styles.confidenceValue}>{confidence.toFixed(2)}</span>
        </div>
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
          style={styles.slider}
        />
      </div>

      {/* URL */}
      {node.metadata?.url && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>URL</div>
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

      {/* Provenance */}
      <div style={styles.provenanceCard}>
        <div style={styles.sectionLabel}>PROVENANCE</div>
        <div style={styles.provenanceRow}>
          <span style={styles.provenanceKey}>SESSION ID</span>
          <span style={styles.provenanceMono}>
            {node.provenance?.session_id || "—"}
          </span>
        </div>
        <div style={styles.provenanceRow}>
          <span style={styles.provenanceKey}>LAST MODIFIED</span>
          <span style={styles.provenanceMono}>
            {node.provenance?.timestamp || "—"}
          </span>
        </div>
      </div>

      {/* Save */}
      {dirty && (
        <button onClick={handleSave} style={styles.primaryBtn}>
          Save Changes
        </button>
      )}

      {/* Research This */}
      {(node.type === "direction" || node.type === "question") && onResearchThis && (
        <button
          onClick={() => {
            onResearchThis({
              node_id: node.id,
              label: node.label,
              description: node.description || node.label,
            });
            setResearchStarted(true);
            setTimeout(() => setResearchStarted(false), 5000);
          }}
          style={researchStarted ? styles.researchBtnDone : styles.researchBtn}
          disabled={researchStarted}
        >
          {researchStarted ? "Research session started" : "Research This"}
        </button>
      )}

      {/* Add Edge */}
      {!showEdgeForm ? (
        <button
          onClick={() => setShowEdgeForm(true)}
          style={styles.addEdgeBtn}
        >
          + ADD EDGE
        </button>
      ) : (
        <div style={styles.edgeForm}>
          <div style={styles.sectionLabel}>TARGET NODE</div>
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
          <div style={{ ...styles.sectionLabel, marginTop: 8 }}>RELATIONSHIP</div>
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
          <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
            <button onClick={handleAddEdge} style={styles.primaryBtn}>
              Add Edge
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

      {/* Danger zone */}
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button
          onClick={() => onFlag({ id: node.id })}
          style={styles.flagBtn}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
            flag
          </span>
          FLAG
        </button>
        <button
          onClick={() => {
            if (confirm(`Delete "${node.label}"?`)) {
              onDelete({ id: node.id });
              onClose();
            }
          }}
          style={styles.deleteBtn}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
            delete
          </span>
          DELETE
        </button>
      </div>

      {/* Footer */}
      <div style={styles.footer}>
        <span>IN: {countEdgesTo(allNodes, node.id)} OUT: {countEdgesFrom(allNodes, node.id)}</span>
      </div>
    </div>
  );
}

function countEdgesTo(allNodes, nodeId) {
  return 0; // Placeholder — edges aren't passed to editor; this is cosmetic
}
function countEdgesFrom(allNodes, nodeId) {
  return 0;
}

const styles = {
  panel: {
    flex: 1,
    padding: "16px 20px",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  section: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  sectionLabel: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  typeTag: {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    alignSelf: "flex-start",
  },
  labelInput: {
    background: "var(--surface-lowest)",
    border: "none",
    borderRadius: 4,
    padding: "10px 12px",
    color: "var(--text-primary)",
    fontSize: 16,
    fontWeight: 700,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
    transition: "background 0.15s ease",
  },
  textarea: {
    background: "var(--surface-lowest)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    padding: "10px 12px",
    color: "var(--text-secondary)",
    fontSize: 14,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
    minHeight: 80,
    resize: "vertical",
    lineHeight: 1.6,
  },
  confidenceValue: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--primary)",
  },
  slider: {
    width: "100%",
    accentColor: "var(--primary)",
  },
  link: {
    color: "var(--primary)",
    fontSize: 13,
    wordBreak: "break-all",
    textDecoration: "none",
  },
  provenanceCard: {
    background: "var(--surface-high)",
    borderRadius: 8,
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  provenanceRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  provenanceKey: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
  },
  provenanceMono: {
    fontFamily: "monospace",
    fontSize: 11,
    color: "var(--text-secondary)",
  },
  primaryBtn: {
    background: "var(--primary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    letterSpacing: "0.02em",
    transition: "filter 0.15s ease",
  },
  secondaryBtn: {
    background: "var(--surface-high)",
    color: "var(--text-secondary)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 4,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 12,
  },
  addEdgeBtn: {
    background: "var(--primary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "10px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    width: "100%",
    transition: "filter 0.15s ease",
  },
  researchBtn: {
    background: "var(--tertiary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "10px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    width: "100%",
    transition: "filter 0.15s ease",
  },
  researchBtnDone: {
    background: "var(--claim-green)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "10px 14px",
    cursor: "default",
    fontSize: 12,
    fontWeight: 600,
    width: "100%",
  },
  flagBtn: {
    background: "var(--surface-high)",
    color: "var(--text-secondary)",
    border: "1px solid rgba(66, 71, 84, 0.3)",
    borderRadius: 4,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "background 0.15s ease",
  },
  deleteBtn: {
    background: "var(--surface-high)",
    color: "#ffb4ab",
    border: "1px solid rgba(147, 0, 10, 0.3)",
    borderRadius: 4,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "background 0.15s ease",
  },
  select: {
    background: "var(--surface-lowest)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 4,
    padding: "8px 10px",
    color: "var(--text-secondary)",
    fontSize: 13,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
  },
  edgeForm: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    background: "var(--surface-high)",
    borderRadius: 8,
    padding: 14,
  },
  footer: {
    marginTop: "auto",
    paddingTop: 12,
    fontSize: 10,
    color: "var(--text-muted)",
    letterSpacing: "0.05em",
    display: "flex",
    justifyContent: "space-between",
  },
};
