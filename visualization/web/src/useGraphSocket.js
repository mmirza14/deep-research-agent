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

  return {
    graph,
    connected,
    addNode,
    updateNode,
    addEdge,
    deleteNode,
    flagNode,
  };
}
