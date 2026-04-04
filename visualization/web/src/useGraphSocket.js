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
  const [activeSessionId, setActiveSessionIdState] = useState(null);
  const [workspaceSessionIds, setWorkspaceSessionIdsState] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [agentPhase, setAgentPhase] = useState(null);
  const [documentContent, setDocumentContent] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [activities, setActivities] = useState([]);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const toastIdRef = useRef(0);
  const activityIdRef = useRef(0);

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
        } else if (msg.type === "sessions_list") {
          setSessions(msg.data.sessions || []);
        } else if (msg.type === "agent_phase") {
          setAgentPhase(msg.data);
        } else if (msg.type === "research_started") {
          setActiveSessionIdState(msg.data.session_id);
        } else if (msg.type === "document_content") {
          setDocumentContent(msg.data);
        } else if (msg.type === "notification") {
          const d = msg.data;
          toastIdRef.current += 1;
          setToasts((prev) => [
            ...prev.slice(-2), // keep max 3 (2 existing + 1 new)
            { id: toastIdRef.current, level: d.level, message: d.message, detail: d.detail },
          ]);
        } else if (msg.type === "operation_result") {
          const d = msg.data;
          toastIdRef.current += 1;
          const level = d.success ? "success" : "error";
          const opLabel = (d.operation || "").replace(/_/g, " ");
          const message = d.success ? opLabel : `${opLabel} failed`;
          setToasts((prev) => [
            ...prev.slice(-2),
            { id: toastIdRef.current, level, message, detail: d.detail },
          ]);
        } else if (msg.type === "activity") {
          activityIdRef.current += 1;
          const entry = { id: activityIdRef.current, ...msg.data };
          setActivities((prev) => [...prev.slice(-199), entry]); // cap at 200
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

  const setActiveSession = useCallback(
    (sessionId) => {
      setActiveSessionIdState(sessionId);
      setWorkspaceSessionIdsState([]);
      send("set_active_session", { session_id: sessionId });
    },
    [send]
  );

  const setWorkspace = useCallback(
    (sessionIds) => {
      setWorkspaceSessionIdsState(sessionIds);
      setActiveSessionIdState(null);
      send("set_workspace", { session_ids: sessionIds });
    },
    [send]
  );

  const listSessions = useCallback(
    () => send("list_sessions", {}),
    [send]
  );

  const startNewResearch = useCallback(
    (question) => send("start_new_research", { question }),
    [send]
  );

  const getDocument = useCallback(
    (sessionId, docType) => send("get_document", { session_id: sessionId, doc_type: docType }),
    [send]
  );

  const dismissToast = useCallback(
    (id) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    []
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
    // Session management (Phase 0)
    activeSessionId,
    workspaceSessionIds,
    sessions,
    agentPhase,
    documentContent,
    setActiveSession,
    setWorkspace,
    listSessions,
    startNewResearch,
    getDocument,
    // Activity feed (Phase 2A)
    activities,
    // Toast notifications (Phase 6A)
    toasts,
    dismissToast,
  };
}
