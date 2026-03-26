import { useCallback, useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8420";
const RECONNECT_DELAY = 2000;

/**
 * Hook that maintains a WebSocket connection to the graph server.
 * Returns the current graph state and mutation functions.
 */
export default function useGraphSocket() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [connected, setConnected] = useState(false);
  const [sessionState, setSessionState] = useState(null);
  const [chatState, setChatState] = useState(null); // { chatId, messages: [{role, text}], waiting }
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      clearTimeout(reconnectTimer.current);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "graph_update") {
          setGraph(msg.data);
        } else if (msg.type === "session_state") {
          setSessionState(msg.data);
        } else if (msg.type === "chat_ready") {
          setChatState((prev) => ({
            chatId: msg.data.chat_id,
            messages: prev?.messages || [],
            waiting: false,
          }));
        } else if (msg.type === "chat_response") {
          setChatState((prev) => prev ? {
            ...prev,
            messages: [...prev.messages, { role: "assistant", text: msg.data.text }],
            waiting: false,
          } : prev);
        } else if (msg.type === "chat_error") {
          setChatState((prev) => prev ? {
            ...prev,
            messages: [...prev.messages, { role: "assistant", text: `Error: ${msg.data.error}` }],
            waiting: false,
          } : prev);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((type, data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  }, []);

  const addNode = useCallback(
    (data) => send("add_node", data),
    [send]
  );

  const updateNode = useCallback(
    (data) => send("update_node", data),
    [send]
  );

  const addEdge = useCallback(
    (data) => send("add_edge", data),
    [send]
  );

  const deleteNode = useCallback(
    (data) => send("delete_node", data),
    [send]
  );

  const flagNode = useCallback(
    (data) => send("flag_node", data),
    [send]
  );

  const resumeSession = useCallback(
    (sessionId) => send("resume_session", { session_id: sessionId }),
    [send]
  );

  const startResearch = useCallback(
    (data) => send("start_research", data),
    [send]
  );

  const startChat = useCallback(
    (nodeId) => {
      setChatState({ chatId: null, messages: [], waiting: false });
      send("chat_start", { node_id: nodeId });
    },
    [send]
  );

  const sendChatMessage = useCallback(
    (chatId, text) => {
      setChatState((prev) => prev ? {
        ...prev,
        messages: [...prev.messages, { role: "user", text }],
        waiting: true,
      } : prev);
      send("chat_message", { chat_id: chatId, text });
    },
    [send]
  );

  const endChat = useCallback(
    (chatId) => {
      send("chat_end", { chat_id: chatId });
      setChatState(null);
    },
    [send]
  );

  return {
    graph,
    connected,
    sessionState,
    addNode,
    updateNode,
    addEdge,
    deleteNode,
    flagNode,
    resumeSession,
    startResearch,
    chatState,
    startChat,
    sendChatMessage,
    endChat,
  };
}
