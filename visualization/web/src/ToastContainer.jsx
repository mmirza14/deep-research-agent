import { useEffect, useRef } from "react";

/**
 * Toast notification stack — top-right, max 3 visible.
 *
 * Props:
 *   toasts: [{ id, level, message, detail? }]
 *   onDismiss: (id) => void
 */

const LEVEL_CONFIG = {
  success: {
    border: "var(--claim-green)",
    icon: "check_circle",
    iconColor: "var(--claim-green)",
    autoDismiss: 3000,
  },
  warning: {
    border: "var(--question-amber)",
    icon: "warning",
    iconColor: "var(--question-amber)",
    autoDismiss: 5000,
  },
  error: {
    border: "var(--error-container)",
    icon: "error",
    iconColor: "#f85149",
    autoDismiss: null, // sticky
  },
  info: {
    border: "var(--primary)",
    icon: "info",
    iconColor: "var(--primary)",
    autoDismiss: 4000,
  },
};

export default function ToastContainer({ toasts, onDismiss }) {
  return (
    <div style={styles.container}>
      {toasts.slice(0, 3).map((toast) => (
        <Toast key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function Toast({ toast, onDismiss }) {
  const { id, level, message, detail } = toast;
  const config = LEVEL_CONFIG[level] || LEVEL_CONFIG.info;
  const timerRef = useRef(null);
  const nodeRef = useRef(null);

  // Auto-dismiss timer
  useEffect(() => {
    if (config.autoDismiss) {
      timerRef.current = setTimeout(() => onDismiss(id), config.autoDismiss);
    }
    return () => clearTimeout(timerRef.current);
  }, [id, config.autoDismiss, onDismiss]);

  // Slide-in animation on mount
  useEffect(() => {
    const el = nodeRef.current;
    if (el) {
      el.style.transform = "translateX(120%)";
      el.style.opacity = "0";
      requestAnimationFrame(() => {
        el.style.transition = "transform 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.3s ease";
        el.style.transform = "translateX(0)";
        el.style.opacity = "1";
      });
    }
  }, []);

  return (
    <div
      ref={nodeRef}
      style={{ ...styles.toast, borderLeft: `3px solid ${config.border}` }}
    >
      <span
        className="material-symbols-outlined"
        style={{ fontSize: 18, color: config.iconColor, flexShrink: 0 }}
      >
        {config.icon}
      </span>
      <div style={styles.content}>
        <span style={styles.message}>{message}</span>
        {detail && <span style={styles.detail}>{detail}</span>}
      </div>
      <button style={styles.closeBtn} onClick={() => onDismiss(id)}>
        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
          close
        </span>
      </button>
    </div>
  );
}

const styles = {
  container: {
    position: "fixed",
    top: 52, // below header (40px + 12px gap)
    right: 16,
    zIndex: 500,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    pointerEvents: "none",
    maxWidth: 360,
  },
  toast: {
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
    padding: "10px 12px",
    background: "rgba(38, 42, 49, 0.92)",
    backdropFilter: "blur(12px)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
    pointerEvents: "auto",
    minWidth: 260,
  },
  content: {
    display: "flex",
    flexDirection: "column",
    gap: 2,
    flex: 1,
    minWidth: 0,
  },
  message: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text-primary)",
    lineHeight: "1.4",
  },
  detail: {
    fontSize: 11,
    color: "var(--text-tertiary)",
    lineHeight: "1.3",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "var(--text-muted)",
    cursor: "pointer",
    padding: 2,
    borderRadius: 4,
    display: "flex",
    alignItems: "center",
    flexShrink: 0,
    transition: "color 0.15s ease",
  },
};
