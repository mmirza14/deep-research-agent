import { useState } from "react";

export default function AnalysisBanner({ sessionId, pausedAt, onResume }) {
  const [confirming, setConfirming] = useState(false);

  const elapsed = pausedAt
    ? Math.round((Date.now() - new Date(pausedAt).getTime()) / 60000)
    : null;

  return (
    <div style={styles.banner}>
      <div style={styles.bannerLeft}>
        <span style={styles.modeTag}>ANALYSIS MODE</span>
        <span style={styles.bannerText}>
          Agent paused. Review the graph, add questions, flag nodes, then
          proceed.
        </span>
        {elapsed !== null && (
          <span style={styles.elapsed}>Paused {elapsed}m ago</span>
        )}
      </div>
      <div style={styles.bannerRight}>
        {!confirming ? (
          <button
            style={styles.proceedBtn}
            onClick={() => setConfirming(true)}
          >
            Proceed to Synthesis
          </button>
        ) : (
          <>
            <span style={styles.confirmText}>Are you sure?</span>
            <button style={styles.confirmBtn} onClick={onResume}>
              Yes, proceed
            </button>
            <button
              style={styles.cancelBtn}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
}

const styles = {
  banner: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 20px",
    background: "linear-gradient(90deg, #2d1b4e 0%, #1b2838 100%)",
    borderBottom: "1px solid #6e40c9",
    zIndex: 50,
  },
  bannerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  bannerRight: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  modeTag: {
    background: "#6e40c9",
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    padding: "3px 8px",
    borderRadius: 4,
    letterSpacing: "0.05em",
  },
  bannerText: {
    color: "#c9d1d9",
    fontSize: 13,
  },
  elapsed: {
    color: "#8b949e",
    fontSize: 12,
  },
  proceedBtn: {
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "7px 16px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
  },
  confirmText: {
    color: "#d29922",
    fontSize: 13,
    fontWeight: 500,
  },
  confirmBtn: {
    background: "#238636",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  cancelBtn: {
    background: "transparent",
    color: "#8b949e",
    border: "1px solid #30363d",
    borderRadius: 6,
    padding: "6px 14px",
    cursor: "pointer",
    fontSize: 13,
  },
};
