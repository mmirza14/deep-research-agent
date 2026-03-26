import { useCallback, useState } from "react";

const NODE_TYPES = ["question", "concept", "direction", "claim", "decision"];

const TYPE_COLORS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#c1c7d0",
  question: "#d29922",
  direction: "#8a58dd",
  decision: "#93000a",
};

export default function AddNodeDialog({ onAdd, onClose }) {
  const [label, setLabel] = useState("");
  const [type, setType] = useState("question");
  const [description, setDescription] = useState("");

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      if (!label.trim()) return;
      onAdd({ label: label.trim(), type, description: description.trim() });
      onClose();
    },
    [label, type, description, onAdd, onClose]
  );

  return (
    <div style={styles.overlay} onClick={onClose}>
      <form
        className="glass-panel"
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h3 style={styles.title}>Add Node</h3>

        <div style={styles.field}>
          <label style={styles.label}>LABEL</label>
          <input
            style={styles.input}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. What causes hallucination in LLMs?"
            autoFocus
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>TYPE</label>
          <div style={styles.typeGrid}>
            {NODE_TYPES.map((t) => {
              const isActive = type === t;
              const color = TYPE_COLORS[t];
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => setType(t)}
                  style={{
                    ...styles.typeBtn,
                    ...(isActive
                      ? {
                          background: color,
                          color: t === "source" ? "#10141a" : "#fff",
                          borderColor: color,
                        }
                      : {}),
                  }}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>DESCRIPTION (OPTIONAL)</label>
          <textarea
            style={{ ...styles.input, minHeight: 60, resize: "vertical" }}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="A brief description..."
          />
        </div>

        <div style={styles.actions}>
          <button type="button" onClick={onClose} style={styles.cancelBtn}>
            Cancel
          </button>
          <button
            type="submit"
            style={{
              ...styles.submitBtn,
              opacity: label.trim() ? 1 : 0.4,
            }}
            disabled={!label.trim()}
          >
            Add to Graph
          </button>
        </div>
      </form>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0, 0, 0, 0.5)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 200,
  },
  dialog: {
    borderRadius: 12,
    padding: 24,
    width: 420,
    maxWidth: "90vw",
    display: "flex",
    flexDirection: "column",
    gap: 18,
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text-primary)",
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  label: {
    fontSize: 10,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  input: {
    background: "var(--surface-lowest)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 6,
    padding: "10px 12px",
    color: "var(--text-secondary)",
    fontSize: 14,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
    lineHeight: 1.5,
    transition: "background 0.15s ease, border-color 0.15s ease",
  },
  typeGrid: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
  },
  typeBtn: {
    background: "var(--surface-high)",
    color: "var(--text-tertiary)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 4,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.03em",
    transition: "all 0.15s ease",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 8,
    marginTop: 4,
  },
  cancelBtn: {
    background: "transparent",
    color: "var(--text-tertiary)",
    border: "none",
    borderRadius: 4,
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  submitBtn: {
    background: "var(--primary-container)",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    padding: "8px 20px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    transition: "filter 0.15s ease, opacity 0.15s ease",
  },
};
