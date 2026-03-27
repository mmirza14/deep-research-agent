import { useState, useEffect } from "react";

/**
 * Phase-aware banner that:
 * 1. During awaiting_user_input: shows guidance + lit review link + proceed button
 * 2. After proceeding: shows live phase progress (synthesizing → socratic → writing → complete)
 * 3. On complete: shows success message, then fades out after 10s
 */

const POST_PROCEED_PHASES = [
  "synthesizing",
  "socratic_review_2",
  "writing_insights",
  "complete",
];

const PHASE_CONFIG = {
  awaiting_user_input: {
    bg: "#a371f7",
    icon: "science",
    label: null, // custom render
  },
  synthesizing: {
    bg: "#1f6feb",
    icon: "sync",
    label: "Synthesizing: analyzing your feedback...",
    animate: true,
  },
  socratic_review_2: {
    bg: "#1f6feb",
    icon: "psychology",
    label: "Socratic Review: Stage 2...",
    animate: true,
  },
  writing_insights: {
    bg: "#1f6feb",
    icon: "edit_note",
    label: "Writing insights report...",
    animate: true,
  },
  complete: {
    bg: "#238636",
    icon: "check_circle",
    label: "Research complete. View insights report.",
    animate: false,
  },
};

export default function AnalysisBanner({
  sessionId,
  pausedAt,
  agentPhase,
  hasLitReview,
  onResume,
  onViewDocument,
}) {
  const [confirming, setConfirming] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [fadingOut, setFadingOut] = useState(false);

  const phase = agentPhase?.phase;

  // Auto-dismiss complete banner after 10s
  useEffect(() => {
    if (phase === "complete") {
      const fadeTimer = setTimeout(() => setFadingOut(true), 8000);
      const dismissTimer = setTimeout(() => setDismissed(true), 10000);
      return () => {
        clearTimeout(fadeTimer);
        clearTimeout(dismissTimer);
      };
    } else {
      setDismissed(false);
      setFadingOut(false);
    }
  }, [phase]);

  // Reset confirmation state when phase changes away from awaiting
  useEffect(() => {
    if (phase !== "awaiting_user_input") {
      setConfirming(false);
    }
  }, [phase]);

  if (dismissed) return null;

  const config = PHASE_CONFIG[phase];
  if (!config) return null;

  const elapsed = pausedAt
    ? Math.round((Date.now() - new Date(pausedAt).getTime()) / 60000)
    : null;

  // Awaiting user input — full guidance banner
  if (phase === "awaiting_user_input") {
    return (
      <div style={{ ...styles.banner, background: config.bg }}>
        <div style={styles.bannerContent}>
          <div style={styles.bannerRow}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, color: "#fff" }}>
              {config.icon}
            </span>
            <span style={styles.bannerHeadline}>
              Review the mind map below. Flag uncertain claims, add questions, adjust confidence.
            </span>
            {elapsed !== null && (
              <span style={styles.elapsed}>({elapsed}m ago)</span>
            )}
          </div>
          <div style={styles.bannerRow}>
            <span style={styles.bannerSubtext}>
              When ready, click Proceed. The agent will synthesize using your feedback.
            </span>
          </div>
        </div>
        <div style={styles.bannerRight}>
          {hasLitReview && (
            <button
              style={styles.litReviewBtn}
              onClick={() => onViewDocument?.(sessionId, "literature_review")}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
                description
              </span>
              View Literature Review
            </button>
          )}
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

  // Post-proceed phases — progress indicator
  return (
    <div
      style={{
        ...styles.banner,
        background: config.bg,
        opacity: fadingOut ? 0 : 1,
        transition: "opacity 2s ease",
      }}
    >
      <div style={styles.bannerLeft}>
        <span
          className="material-symbols-outlined"
          style={{
            fontSize: 18,
            color: "#fff",
            animation: config.animate ? "spin 1.5s linear infinite" : "none",
          }}
        >
          {config.icon}
        </span>
        <span style={styles.bannerText}>{config.label}</span>
        {agentPhase?.detail && config.animate && (
          <span style={styles.elapsed}>{agentPhase.detail}</span>
        )}
      </div>
      <div style={styles.bannerRight}>
        {phase === "complete" && (
          <button
            style={styles.litReviewBtn}
            onClick={() => onViewDocument?.(sessionId, "insights")}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14, marginRight: 4 }}>
              insights
            </span>
            View Insights
          </button>
        )}
        {config.animate && (
          <div style={styles.progressDots}>
            <span style={{ ...styles.dot, animationDelay: "0s" }} />
            <span style={{ ...styles.dot, animationDelay: "0.2s" }} />
            <span style={{ ...styles.dot, animationDelay: "0.4s" }} />
          </div>
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
    minHeight: 40,
    padding: "8px 16px",
    zIndex: 50,
    flexShrink: 0,
  },
  bannerContent: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    flex: 1,
  },
  bannerRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
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
    flexShrink: 0,
  },
  bannerHeadline: {
    color: "#fff",
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: "0.02em",
  },
  bannerSubtext: {
    color: "rgba(255, 255, 255, 0.75)",
    fontSize: 11,
    fontWeight: 500,
    marginLeft: 28, // align with text after icon
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
    whiteSpace: "nowrap",
  },
  litReviewBtn: {
    background: "rgba(255, 255, 255, 0.15)",
    color: "#fff",
    border: "1px solid rgba(255, 255, 255, 0.3)",
    borderRadius: 4,
    padding: "5px 14px",
    cursor: "pointer",
    fontSize: 10,
    fontWeight: 600,
    letterSpacing: "0.03em",
    display: "flex",
    alignItems: "center",
    whiteSpace: "nowrap",
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
  progressDots: {
    display: "flex",
    gap: 4,
    alignItems: "center",
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "rgba(255, 255, 255, 0.8)",
    animation: "dotPulse 1.2s ease-in-out infinite",
  },
};
