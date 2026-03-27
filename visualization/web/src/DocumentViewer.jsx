import Markdown from "react-markdown";

export default function DocumentViewer({ document, onClose }) {
  if (!document) {
    return (
      <div style={styles.empty}>
        <span className="material-symbols-outlined" style={{ fontSize: 32, color: "var(--text-muted)" }}>
          description
        </span>
        <div style={styles.emptyText}>
          Select a document from the session panel or analysis banner to view it here.
        </div>
      </div>
    );
  }

  if (document.error) {
    return (
      <div style={styles.empty}>
        <div style={{ ...styles.emptyText, color: "var(--error-container)" }}>
          {document.error}
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.title}>{document.title}</div>
        <button onClick={onClose} style={styles.closeBtn}>
          <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
            close
          </span>
        </button>
      </div>
      <div style={styles.content}>
        <Markdown>{document.content}</Markdown>
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    flex: 1,
    overflow: "hidden",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 16px",
    borderBottom: "1px solid var(--ghost-border)",
    flexShrink: 0,
  },
  title: {
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text-primary)",
    textTransform: "capitalize",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "var(--text-tertiary)",
    cursor: "pointer",
    padding: 2,
    borderRadius: 4,
    display: "flex",
    alignItems: "center",
  },
  content: {
    flex: 1,
    overflowY: "auto",
    padding: "12px 16px",
    fontSize: 13,
    lineHeight: 1.6,
    color: "var(--text-secondary)",
  },
  empty: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: 24,
  },
  emptyText: {
    fontSize: 12,
    color: "var(--text-tertiary)",
    textAlign: "center",
    lineHeight: 1.5,
  },
};
