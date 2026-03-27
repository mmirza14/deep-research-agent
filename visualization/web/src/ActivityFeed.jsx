import { useEffect, useRef, useState } from "react";

const TYPE_COLORS = {
  concept: "var(--node-concept)",
  claim: "var(--node-claim)",
  source: "var(--node-source)",
  question: "var(--node-question)",
  direction: "var(--node-direction)",
  decision: "var(--node-decision)",
};

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

export default function ActivityFeed({ activities }) {
  const [expanded, setExpanded] = useState(false);
  const scrollRef = useRef(null);

  // Auto-scroll to bottom when new activities arrive
  useEffect(() => {
    if (expanded && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activities.length, expanded]);

  return (
    <div style={{ ...styles.container, height: expanded ? 200 : 32 }}>
      <button
        style={styles.bar}
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="material-symbols-outlined" style={styles.chevron}>
          {expanded ? "expand_more" : "expand_less"}
        </span>
        <span style={styles.barLabel}>Activity</span>
        {activities.length > 0 && (
          <span style={styles.barCount}>{activities.length}</span>
        )}
      </button>
      {expanded && (
        <div ref={scrollRef} style={styles.list}>
          {activities.length === 0 && (
            <div style={styles.empty}>No activity yet.</div>
          )}
          {activities.map((a) => (
            <div key={a.id} style={styles.entry}>
              <div
                style={{
                  ...styles.entryBorder,
                  background: TYPE_COLORS[a.node_type] || "var(--text-tertiary)",
                }}
              />
              <span style={styles.time}>{formatTime(a.timestamp)}</span>
              <span style={styles.action}>{a.action}</span>
              <span style={styles.detail}>{a.detail}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    background: "var(--surface-low)",
    borderTop: "1px solid var(--ghost-border)",
    display: "flex",
    flexDirection: "column",
    transition: "height 0.2s ease",
    zIndex: 30,
    overflow: "hidden",
  },
  bar: {
    height: 32,
    minHeight: 32,
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "0 12px",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontFamily: "inherit",
  },
  chevron: {
    fontSize: 16,
    color: "var(--text-tertiary)",
  },
  barLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  barCount: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-muted)",
    background: "var(--surface-high)",
    padding: "1px 6px",
    borderRadius: 8,
  },
  list: {
    flex: 1,
    overflowY: "auto",
    padding: "0 12px 8px",
  },
  empty: {
    fontSize: 12,
    color: "var(--text-tertiary)",
    fontStyle: "italic",
    padding: "8px 0",
  },
  entry: {
    display: "flex",
    alignItems: "baseline",
    gap: 8,
    padding: "3px 0",
    fontSize: 12,
    lineHeight: 1.4,
  },
  entryBorder: {
    width: 3,
    minWidth: 3,
    height: 14,
    borderRadius: 1,
    alignSelf: "center",
  },
  time: {
    color: "var(--text-muted)",
    fontFamily: "monospace",
    fontSize: 10,
    flexShrink: 0,
  },
  action: {
    color: "var(--text-secondary)",
    fontWeight: 600,
    flexShrink: 0,
  },
  detail: {
    color: "var(--text-tertiary)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
};
