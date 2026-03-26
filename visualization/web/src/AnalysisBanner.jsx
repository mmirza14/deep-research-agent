import { useState } from "react";

export default function AnalysisBanner({ sessionId, pausedAt, onResume }) {
  const [confirming, setConfirming] = useState(false);

  const elapsed = pausedAt
    ? Math.round((Date.now() - new Date(pausedAt).getTime()) / 60000)
    : null;

  return (
    <div style={styles.banner}>
      <div style={styles.bannerLeft}>
        <span className="material-symbols-outlined" style={{ fontSize: 18, color: "#fff" }}>
          science
        </span>
        <span style={styles.bannerText}>
          ANALYSIS MODE: AGENT PAUSED FOR USER REVIEW
        </span>
        {elapsed !== null && (
          <span style={styles.elapsed}>({elapsed}m ago)</span>
        )}
      </div>
      <div style={styles.bannerRight}>
        {!confirming ? (
          <button
            style={styles.proceedBtn}
            onClick={() => setConfirming(true)}
          >
            PROCEED TO SYNTHESIS
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
    height: 40,
    padding: "0 16px",
    background: "#a371f7",
    zIndex: 50,
    flexShrink: 0,
  },
  bannerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  bannerRight: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  bannerText: {
    color: "#fff",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.05em",
  },
  elapsed: {
    color: "rgba(255, 255, 255, 0.7)",
    fontSize: 11,
  },
  proceedBtn: {
    background: "transparent",
    color: "#fff",
    border: "1px solid rgba(255, 255, 255, 0.6)",
    borderRadius: 4,
    padding: "5px 16px",
    cursor: "pointer",
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.05em",
    transition: "background 0.15s ease",
  },
  confirmText: {
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
  },
  confirmBtn: {
    background: "#fff",
    color: "#a371f7",
    border: "none",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 700,
  },
  cancelBtn: {
    background: "transparent",
    color: "rgba(255, 255, 255, 0.8)",
    border: "none",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 11,
  },
};
