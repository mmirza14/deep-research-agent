import { useEffect } from "react";

const STATUS_COLORS = {
  running: { bg: "rgba(163,113,247,0.2)", fg: "#a371f7" },
  paused: { bg: "rgba(163,113,247,0.15)", fg: "#a371f7" },
  complete: { bg: "rgba(35,134,54,0.2)", fg: "#238636" },
  error: { bg: "rgba(147,0,10,0.2)", fg: "#93000a" },
  unknown: { bg: "rgba(125,125,125,0.2)", fg: "#7d7d7d" },
};

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60_000) return "just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 604_800_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export default function SessionPanel({
  sessions,
  activeSessionId,
  visible,
  onToggle,
  onSelectSession,
  onNewResearch,
  onRefreshSessions,
}) {
  useEffect(() => {
    if (visible) onRefreshSessions();
  }, [visible, onRefreshSessions]);

  if (!visible) return null;

  const sorted = [...sessions].sort((a, b) => {
    const ta = a.created_at || "";
    const tb = b.created_at || "";
    return tb.localeCompare(ta);
  });

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div>
          <div style={styles.title}>Research Sessions</div>
          <div style={styles.subtitle}>
            {sessions.length} session{sessions.length !== 1 ? "s" : ""}
          </div>
        </div>
        <button onClick={onToggle} style={styles.closeBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
            close
          </span>
        </button>
      </div>

      <button style={styles.newBtn} onClick={onNewResearch}>
        <span className="material-symbols-outlined" style={{ fontSize: 16, marginRight: 6 }}>
          add_circle
        </span>
        New Research
      </button>

      <div style={styles.body}>
        {sorted.length === 0 && (
          <div style={styles.empty}>
            No research sessions yet. Start one above or from the home screen.
          </div>
        )}

        {sorted.map((s) => {
          const isActive = s.session_id === activeSessionId;
          const colors = STATUS_COLORS[s.status] || STATUS_COLORS.unknown;
          return (
            <button
              key={s.session_id}
              style={{
                ...styles.card,
                borderColor: isActive ? "var(--primary)" : "var(--ghost-border)",
                background: isActive ? "var(--surface-high)" : "var(--surface-container)",
              }}
              onClick={() => onSelectSession(s.session_id)}
            >
              <div style={styles.cardQuestion}>
                {s.question || `Session ${s.session_id}`}
              </div>
              <div style={styles.cardMeta}>
                <span
                  style={{
                    ...styles.statusBadge,
                    background: colors.bg,
                    color: colors.fg,
                    animation: s.status === "running" ? "pulse 1.5s ease-in-out infinite" : "none",
                  }}
                >
                  {s.status}
                </span>
                <span style={styles.statText}>{s.node_count} nodes</span>
                {s.created_at && (
                  <span style={styles.statText}>{formatDate(s.created_at)}</span>
                )}
              </div>
              {(s.has_lit_review || s.has_insights) && (
                <div style={styles.docRow}>
                  {s.has_lit_review && <span style={styles.docBadge}>Lit Review</span>}
                  {s.has_insights && <span style={styles.docBadge}>Insights</span>}
                </div>
              )}
            </button>
          );
        })}
      </div>
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
  newBtn: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    margin: "0 16px 12px",
    padding: "8px 14px",
    background: "var(--tertiary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    letterSpacing: "0.02em",
    transition: "filter 0.15s ease",
  },
  body: {
    flex: 1,
    overflowY: "auto",
    padding: "0 16px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  empty: {
    padding: 20,
    fontSize: 13,
    color: "var(--text-tertiary)",
    fontStyle: "italic",
    lineHeight: 1.5,
    textAlign: "center",
  },
  card: {
    width: "100%",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    padding: "12px 14px",
    cursor: "pointer",
    textAlign: "left",
    fontFamily: "inherit",
    transition: "border-color 0.15s ease, background 0.15s ease",
  },
  cardQuestion: {
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 6,
    overflow: "hidden",
    textOverflow: "ellipsis",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    lineHeight: 1.4,
  },
  cardMeta: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 11,
  },
  statusBadge: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 10,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  statText: {
    color: "var(--text-tertiary)",
    fontWeight: 500,
  },
  docRow: {
    display: "flex",
    gap: 6,
    marginTop: 6,
  },
  docBadge: {
    color: "var(--text-tertiary)",
    fontSize: 10,
    fontWeight: 500,
    padding: "2px 6px",
    background: "var(--surface-high)",
    borderRadius: 3,
  },
};
