import { useMemo, useState } from "react";

export default function DirectionsPanel({ graph, onSelectNode, onResearchThis, visible, onToggle }) {
  const groups = useMemo(() => {
    const directions = [];
    const questions = [];

    for (const node of graph.nodes) {
      if (node.withdrawn) continue;
      if (node.type === "direction") directions.push(node);
      else if (node.type === "question") questions.push(node);
    }

    const byRecency = (a, b) => {
      const ta = a.provenance?.timestamp || "";
      const tb = b.provenance?.timestamp || "";
      return tb.localeCompare(ta);
    };
    directions.sort(byRecency);
    questions.sort(byRecency);

    return { directions, questions };
  }, [graph]);

  const total = groups.directions.length + groups.questions.length;

  // Panel is rendered inside the flex body in App.jsx — no collapsed tab needed here,
  // the sidebar icon handles toggling
  if (!visible) return null;

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div>
          <div style={styles.title}>Directions Panel</div>
          <div style={styles.subtitle}>
            {groups.directions.length} directions, {groups.questions.length} questions
          </div>
        </div>
        <button onClick={onToggle} style={styles.closeBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
            close
          </span>
        </button>
      </div>

      <div style={styles.body}>
        {total === 0 && (
          <div style={styles.empty}>
            No direction or question nodes yet. Run direction finding to generate proposals.
          </div>
        )}

        {groups.questions.length > 0 && (
          <Section
            title="Open Questions"
            color="#d29922"
            nodes={groups.questions}
            onSelect={onSelectNode}
            onResearchThis={onResearchThis}
          />
        )}

        {groups.directions.length > 0 && (
          <Section
            title="Proposed Directions"
            color="#8a58dd"
            nodes={groups.directions}
            onSelect={onSelectNode}
            onResearchThis={onResearchThis}
          />
        )}
      </div>
    </div>
  );
}

function Section({ title, color, nodes, onSelect, onResearchThis }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div style={styles.section}>
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={{ ...styles.sectionHeader, borderLeftColor: color }}
      >
        <span style={{ color, fontWeight: 700 }}>{title.toUpperCase()}</span>
        <span className="material-symbols-outlined" style={{ fontSize: 16, color: "var(--text-tertiary)" }}>
          {collapsed ? "expand_more" : "expand_less"}
        </span>
      </button>
      {!collapsed &&
        nodes.map((node) => (
          <NodeItem key={node.id} node={node} onSelect={onSelect} onResearchThis={onResearchThis} />
        ))}
    </div>
  );
}

function NodeItem({ node, onSelect, onResearchThis }) {
  const [started, setStarted] = useState(false);
  const desc = node.description || "";
  const snippet = desc.length > 80 ? desc.slice(0, 80) + "\u2026" : desc;
  const session = node.provenance?.session_id || "unknown";
  const sessionShort = session.length > 8 ? session.slice(0, 8) : session;

  return (
    <div style={styles.item}>
      <button
        onClick={() => onSelect(node.id)}
        style={styles.itemClickArea}
      >
        <div style={styles.itemLabel}>{node.label}</div>
        {snippet && <div style={styles.itemDesc}>{snippet}</div>}
        <div style={styles.itemMeta}>
          <span style={styles.confBadge}>
            {(node.confidence ?? 0.5).toFixed(2)}
          </span>
          <span style={styles.sessionBadge}>{sessionShort}</span>
        </div>
      </button>
      {onResearchThis && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onResearchThis({
              node_id: node.id,
              label: node.label,
              description: node.description || node.label,
            });
            setStarted(true);
            setTimeout(() => setStarted(false), 5000);
          }}
          style={started ? styles.researchBtnDone : styles.researchBtn}
          disabled={started}
        >
          {started ? "Started" : "Research This"}
        </button>
      )}
    </div>
  );
}

const styles = {
  panel: {
    width: 320,
    background: "var(--surface-low)",
    borderRight: "1px solid var(--ghost-border)",
    boxShadow: "20px 0 40px rgba(0, 0, 0, 0.4)",
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
    zIndex: 35,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    padding: "16px 16px 12px",
  },
  title: {
    fontSize: 16,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  subtitle: {
    fontSize: 10,
    fontWeight: 500,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    marginTop: 2,
    textTransform: "uppercase",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "var(--text-tertiary)",
    cursor: "pointer",
    padding: 4,
    borderRadius: 4,
  },
  body: {
    flex: 1,
    overflowY: "auto",
  },
  empty: {
    padding: 20,
    fontSize: 13,
    color: "var(--text-tertiary)",
    fontStyle: "italic",
    lineHeight: 1.5,
  },
  section: {
    marginBottom: 4,
  },
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    width: "100%",
    padding: "10px 16px",
    background: "none",
    border: "none",
    borderLeft: "2px solid",
    color: "var(--text-secondary)",
    fontSize: 10,
    fontWeight: 600,
    cursor: "pointer",
    textAlign: "left",
    letterSpacing: "0.05em",
  },
  item: {
    width: "100%",
    padding: "12px 16px 12px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    transition: "background 0.15s ease",
  },
  itemClickArea: {
    display: "block",
    width: "100%",
    background: "none",
    border: "none",
    cursor: "pointer",
    textAlign: "left",
    color: "var(--text-primary)",
    padding: 0,
  },
  itemLabel: {
    fontSize: 14,
    fontWeight: 600,
    marginBottom: 3,
    lineHeight: 1.3,
  },
  itemDesc: {
    fontSize: 11,
    color: "var(--text-tertiary)",
    lineHeight: 1.4,
    marginBottom: 6,
  },
  itemMeta: {
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  confBadge: {
    fontSize: 10,
    background: "var(--surface-high)",
    padding: "2px 8px",
    borderRadius: 4,
    color: "var(--text-secondary)",
    fontWeight: 500,
  },
  sessionBadge: {
    fontSize: 10,
    color: "var(--text-muted)",
    fontFamily: "monospace",
  },
  researchBtn: {
    background: "var(--tertiary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.02em",
    width: "100%",
    transition: "filter 0.15s ease",
  },
  researchBtnDone: {
    background: "var(--claim-green)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "default",
    fontSize: 11,
    fontWeight: 600,
    width: "100%",
  },
};
