import { useCallback, useEffect, useRef, useState } from "react";

const TYPE_COLORS = {
  concept: "#1f6feb",
  claim: "#238636",
  source: "#c1c7d0",
  question: "#d29922",
  direction: "#8a58dd",
  decision: "#93000a",
};

export default function NodeChat({ node, chatState, onStartChat, onSendMessage, onEndChat }) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (node?.id) {
      onStartChat(node.id);
    }
    return () => {
      if (chatState?.chatId) {
        onEndChat(chatState.chatId);
      }
    };
  }, [node?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatState?.messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || !chatState?.chatId) return;
    onSendMessage(chatState.chatId, text);
    setInput("");
  }, [input, chatState?.chatId, onSendMessage]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  if (!node) return null;

  const isConnecting = !chatState?.chatId;
  const isWaiting = chatState?.waiting;
  const typeColor = TYPE_COLORS[node.type] || TYPE_COLORS.concept;

  return (
    <div style={styles.container}>
      {/* Chat header */}
      <div style={styles.header}>
        <span style={styles.nodeLabel}>{node.label}</span>
        <span
          style={{
            ...styles.typeTag,
            background: typeColor,
            color: node.type === "source" ? "#10141a" : "#fff",
          }}
        >
          {node.type}
        </span>
      </div>

      {/* Messages */}
      <div style={styles.messages}>
        {isConnecting && (
          <div style={styles.systemMsg}>Connecting...</div>
        )}

        {chatState?.messages?.map((msg, i) => (
          <div key={i} style={styles.msgWrapper}>
            <div style={styles.msgLabel}>
              {msg.role === "user" ? "YOU" : "ASSISTANT"}
            </div>
            <div
              style={
                msg.role === "user" ? styles.userBubble : styles.assistantBubble
              }
            >
              <div style={styles.msgText}>{msg.text}</div>
            </div>
          </div>
        ))}

        {isWaiting && (
          <div style={styles.systemMsg}>Thinking...</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div style={styles.inputArea}>
        <textarea
          style={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isConnecting ? "Connecting..." : "Ask a question about this node..."}
          disabled={isConnecting || isWaiting}
          rows={2}
        />
        <button
          onClick={handleSend}
          style={{
            ...styles.sendBtn,
            opacity: isConnecting || isWaiting || !input.trim() ? 0.4 : 1,
          }}
          disabled={isConnecting || isWaiting || !input.trim()}
        >
          <span className="material-symbols-outlined" style={{ fontSize: 18 }}>
            send
          </span>
        </button>
      </div>
      <div style={styles.inputHint}>
        <span className="material-symbols-outlined" style={{ fontSize: 11 }}>
          keyboard_return
        </span>
        ENTER to send
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    padding: "0 16px 12px",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "12px 0",
    marginBottom: 4,
  },
  nodeLabel: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text-primary)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
  },
  typeTag: {
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 9,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    flexShrink: 0,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 14,
    paddingBottom: 8,
  },
  msgWrapper: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  msgLabel: {
    fontSize: 9,
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
  },
  userBubble: {
    alignSelf: "flex-end",
    background: "rgba(31, 111, 235, 0.15)",
    borderRadius: "12px 12px 4px 12px",
    padding: "10px 14px",
    maxWidth: "90%",
  },
  assistantBubble: {
    alignSelf: "flex-start",
    background: "var(--surface-high)",
    borderRadius: "12px 12px 12px 4px",
    padding: "10px 14px",
    maxWidth: "90%",
  },
  msgText: {
    fontSize: 13,
    color: "var(--text-secondary)",
    lineHeight: 1.6,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
  },
  systemMsg: {
    textAlign: "center",
    fontSize: 12,
    color: "var(--text-muted)",
    fontStyle: "italic",
    padding: 12,
  },
  inputArea: {
    display: "flex",
    gap: 8,
    paddingTop: 10,
    marginTop: "auto",
  },
  input: {
    flex: 1,
    background: "var(--surface-lowest)",
    border: "1px solid var(--ghost-border)",
    borderRadius: 8,
    padding: "10px 12px",
    color: "var(--text-secondary)",
    fontSize: 13,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
    resize: "none",
    lineHeight: 1.5,
    transition: "background 0.15s ease, border-color 0.15s ease",
  },
  sendBtn: {
    background: "var(--claim-green)",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    padding: "8px 12px",
    cursor: "pointer",
    alignSelf: "flex-end",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    transition: "opacity 0.15s ease",
  },
  inputHint: {
    fontSize: 9,
    color: "var(--text-muted)",
    letterSpacing: "0.05em",
    textAlign: "right",
    paddingTop: 4,
    display: "flex",
    alignItems: "center",
    justifyContent: "flex-end",
    gap: 4,
  },
};
