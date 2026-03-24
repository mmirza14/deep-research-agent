import { useCallback, useState } from "react";

const NODE_TYPES = ["question", "concept", "direction", "claim", "decision"];

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
        style={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        onSubmit={handleSubmit}
      >
        <h3 style={styles.title}>Add Node</h3>

        <div style={styles.field}>
          <label style={styles.label}>Label</label>
          <input
            style={styles.input}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. What causes hallucination in LLMs?"
            autoFocus
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Type</label>
          <div style={styles.typeGrid}>
            {NODE_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setType(t)}
                style={{
                  ...styles.typeBtn,
                  ...(type === t ? styles.typeBtnActive : {}),
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Description (optional)</label>
          <textarea
            style={{ ...styles.input, height: 60, resize: "vertical" }}
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
            style={styles.submitBtn}
            disabled={!label.trim()}
          >
            Add to graph
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
    background: "rgba(0,0,0,0.6)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 200,
  },
  dialog: {
    background: "#161b22",
    border: "1px solid #30363d",
    borderRadius: 12,
    padding: 24,
    width: 420,
    maxWidth: "90vw",
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  title: {
    fontSize: 18,
    color: "#c9d1d9",
    fontWeight: 600,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
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
  typeGrid: {
    display: "flex",
    gap: 6,
    flexWrap: "wrap",
  },
  typeBtn: {
    background: "#21262d",
    color: "#8b949e",
    border: "1px solid #30363d",
    borderRadius: 16,
    padding: "5px 12px",
    cursor: "pointer",
    fontSize: 12,
    textTransform: "capitalize",
  },
  typeBtnActive: {
    background: "#1f6feb",
    color: "#fff",
    borderColor: "#388bfd",
  },
  actions: {
    display: "flex",
    justifyContent: "flex-end",
    gap: 8,
    marginTop: 4,
  },
  cancelBtn: {
    background: "#21262d",
    color: "#c9d1d9",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 13,
  },
  submitBtn: {
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "8px 16px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
};
