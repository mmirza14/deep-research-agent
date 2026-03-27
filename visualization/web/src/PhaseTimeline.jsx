const PHASES = [
  { key: "researching", label: "Survey" },
  { key: "validating", label: "Validation" },
  { key: "socratic_review_1", label: "Socratic Review 1" },
  { key: "writing_literature_review", label: "Literature Review" },
  { key: "awaiting_user_input", label: "Your Review" },
  { key: "synthesizing", label: "Synthesis" },
  { key: "socratic_review_2", label: "Socratic Review 2" },
  { key: "writing_insights", label: "Insights Report" },
  { key: "complete", label: "Complete" },
];

function phaseIndex(phase) {
  if (!phase) return -1;
  const idx = PHASES.findIndex((p) => p.key === phase);
  return idx >= 0 ? idx : -1;
}

export default function PhaseTimeline({ agentPhase }) {
  const currentPhase = agentPhase?.phase || null;
  const currentIdx = phaseIndex(currentPhase);
  const isError = currentPhase === "error";

  // Don't render if no phase data
  if (!currentPhase) return null;

  return (
    <div style={styles.container}>
      <div style={styles.title}>PIPELINE</div>
      {PHASES.map((p, i) => {
        const isDone = i < currentIdx;
        const isCurrent = i === currentIdx;
        const isFuture = i > currentIdx;

        let icon, iconColor;
        if (isError && isCurrent) {
          icon = "error";
          iconColor = "var(--error-container)";
        } else if (isDone) {
          icon = "check_circle";
          iconColor = "var(--claim-green)";
        } else if (isCurrent) {
          icon = "arrow_forward";
          iconColor = "var(--node-direction)";
        } else {
          icon = "radio_button_unchecked";
          iconColor = "var(--text-muted)";
        }

        return (
          <div key={p.key} style={styles.step}>
            <div style={styles.iconCol}>
              <span
                className="material-symbols-outlined"
                style={{
                  fontSize: 16,
                  color: iconColor,
                  animation: isCurrent && !isError ? "pulse 1.5s ease-in-out infinite" : "none",
                }}
              >
                {icon}
              </span>
              {i < PHASES.length - 1 && (
                <div
                  style={{
                    ...styles.line,
                    background: isDone ? "var(--claim-green)" : "var(--ghost-border)",
                  }}
                />
              )}
            </div>
            <div
              style={{
                ...styles.label,
                color: isCurrent
                  ? "var(--text-primary)"
                  : isDone
                  ? "var(--text-secondary)"
                  : "var(--text-muted)",
                fontWeight: isCurrent ? 600 : 400,
              }}
            >
              {p.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

const styles = {
  container: {
    padding: "12px 8px",
    borderTop: "1px solid var(--ghost-border)",
    marginTop: "auto",
  },
  title: {
    fontSize: 9,
    fontWeight: 600,
    color: "var(--text-muted)",
    letterSpacing: "0.15em",
    marginBottom: 8,
    textAlign: "center",
  },
  step: {
    display: "flex",
    alignItems: "flex-start",
    gap: 6,
    minHeight: 24,
  },
  iconCol: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    width: 16,
    flexShrink: 0,
  },
  line: {
    width: 1.5,
    height: 8,
    borderRadius: 1,
  },
  label: {
    fontSize: 11,
    lineHeight: "16px",
    paddingTop: 0,
  },
};
