import { Handle, Position } from "@xyflow/react";
import { memo } from "react";

/**
 * igraph-style node: small colored dot with label beside it.
 * Label opacity is controlled by the zoom level passed via data.
 */
function GraphNode({ data }) {
  const { color, dotSize, labelOpacity } = data;

  return (
    <div
      style={{
        position: "relative",
        width: dotSize,
        height: dotSize,
      }}
    >
      {/* The dot */}
      <div
        style={{
          width: dotSize,
          height: dotSize,
          borderRadius: "50%",
          background: color,
          border: `1.5px solid rgba(255,255,255,0.15)`,
          boxShadow: `0 0 ${dotSize / 2}px ${color}44`,
        }}
      />

      {/* Label beside the dot */}
      <div
        style={{
          position: "absolute",
          left: dotSize + 6,
          top: "50%",
          transform: "translateY(-50%)",
          whiteSpace: "nowrap",
          fontSize: 11,
          color: "#c9d1d9",
          opacity: labelOpacity,
          transition: "opacity 0.15s ease",
          pointerEvents: "none",
          textShadow: "0 1px 3px rgba(0,0,0,0.8)",
          maxWidth: 160,
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
      >
        {data.label}
      </div>

      {/* Handles for edge connections — invisible, centered on the dot */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ opacity: 0, left: dotSize / 2, top: dotSize / 2 }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{ opacity: 0, left: dotSize / 2, top: dotSize / 2 }}
      />
    </div>
  );
}

export default memo(GraphNode);
