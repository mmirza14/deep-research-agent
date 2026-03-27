import { useEffect, useState } from "react";

export default function HomeScreen({ sessions, onStartResearch, onSelectSession, onRefreshSessions }) {
  const [question, setQuestion] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    onRefreshSessions();
  }, [onRefreshSessions]);

  const handleStart = () => {
    const q = question.trim();
    if (!q || starting) return;
    setStarting(true);
    onStartResearch(q);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleStart();
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <span
          className="material-symbols-outlined"
          style={styles.icon}
        >
          hub
        </span>
        <h1 style={styles.headline}>What would you like to research?</h1>
        <div style={styles.inputRow}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="e.g. impact of social media on teenage mental health"
            style={styles.input}
            autoFocus
          />
          <button
            style={{
              ...styles.startBtn,
              opacity: question.trim() && !starting ? 1 : 0.5,
            }}
            onClick={handleStart}
            disabled={!question.trim() || starting}
          >
            {starting ? "Starting..." : "Start Research"}
          </button>
        </div>

        {sessions.length > 0 && (
          <div style={styles.sessionsSection}>
            <div style={styles.sessionsTitle}>RECENT SESSIONS</div>
            <div style={styles.sessionsList}>
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  style={styles.sessionCard}
                  onClick={() => onSelectSession(s.session_id)}
                >
                  <div style={styles.sessionQuestion}>
                    {s.question || `Session ${s.session_id}`}
                  </div>
                  <div style={styles.sessionMeta}>
                    <span
                      style={{
                        ...styles.statusBadge,
                        background:
                          s.status === "running"
                            ? "rgba(163,113,247,0.2)"
                            : s.status === "paused"
                            ? "rgba(163,113,247,0.15)"
                            : s.status === "complete"
                            ? "rgba(35,134,54,0.2)"
                            : "rgba(147,0,10,0.2)",
                        color:
                          s.status === "running"
                            ? "#a371f7"
                            : s.status === "paused"
                            ? "#a371f7"
                            : s.status === "complete"
                            ? "#238636"
                            : "#93000a",
                      }}
                    >
                      {s.status}
                    </span>
                    <span style={styles.sessionStats}>
                      {s.node_count} nodes
                    </span>
                    {s.has_lit_review && (
                      <span style={styles.docBadge}>Lit Review</span>
                    )}
                    {s.has_insights && (
                      <span style={styles.docBadge}>Insights</span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  container: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--surface-base)",
  },
  content: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    maxWidth: 640,
    width: "100%",
    padding: "0 24px",
  },
  icon: {
    fontSize: 64,
    color: "var(--text-tertiary)",
    marginBottom: 16,
  },
  headline: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text-primary)",
    marginBottom: 24,
    textAlign: "center",
    letterSpacing: "-0.02em",
  },
  inputRow: {
    display: "flex",
    gap: 8,
    width: "100%",
    maxWidth: 560,
  },
  input: {
    flex: 1,
    height: 48,
    background: "var(--surface-container)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    padding: "0 16px",
    fontSize: 15,
    color: "var(--text-primary)",
    outline: "none",
    fontFamily: "inherit",
  },
  startBtn: {
    height: 48,
    padding: "0 24px",
    background: "var(--primary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    whiteSpace: "nowrap",
    transition: "opacity 0.15s ease",
  },
  sessionsSection: {
    marginTop: 48,
    width: "100%",
    maxWidth: 560,
  },
  sessionsTitle: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.15em",
    marginBottom: 12,
    textTransform: "uppercase",
  },
  sessionsList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  sessionCard: {
    background: "var(--surface-container)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    padding: "12px 16px",
    cursor: "pointer",
    textAlign: "left",
    transition: "border-color 0.15s ease",
    fontFamily: "inherit",
  },
  sessionQuestion: {
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text-primary)",
    marginBottom: 6,
    overflow: "hidden",
    textOverflow: "ellipsis",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
  },
  sessionMeta: {
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
  sessionStats: {
    color: "var(--text-tertiary)",
    fontWeight: 500,
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
