import { Handle, Position } from "@xyflow/react";
import { memo } from "react";

const SHAPE_CLIPS = {
  direction: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)", // diamond
  question: "polygon(50% 0%, 100% 100%, 0% 100%)",           // triangle
};

function GraphNode({ data }) {
  const { color, dotSize, labelOpacity, type, selected, isNew } = data;
  const clipPath = SHAPE_CLIPS[type] || null;

  return (
    <div
      style={{
        position: "relative",
        width: dotSize,
        height: dotSize,
        transition: "transform 0.15s ease, opacity 0.3s ease",
        animation: isNew ? "nodeArrival 0.3s ease-out" : "none",
      }}
    >
      {/* Selected glow ring */}
      {selected && (
        <div
          style={{
            position: "absolute",
            inset: -4,
            borderRadius: clipPath ? 0 : "50%",
            clipPath: clipPath || undefined,
            background: "transparent",
            boxShadow: `0 0 15px rgba(175, 198, 255, 0.4)`,
            pointerEvents: "none",
          }}
        />
      )}

      {/* The dot/shape */}
      <div
        style={{
          width: dotSize,
          height: dotSize,
          borderRadius: clipPath ? 0 : "50%",
          clipPath: clipPath || undefined,
          background: color,
          border: clipPath ? "none" : `1.5px solid rgba(255,255,255,0.15)`,
          boxShadow: selected
            ? `0 0 ${dotSize}px ${color}88`
            : `0 0 ${dotSize / 2}px ${color}44`,
          transition: "box-shadow 0.15s ease, transform 0.15s ease",
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
          fontWeight: 500,
          color: "var(--text-secondary, #c2c6d6)",
          opacity: labelOpacity,
          transition: "opacity 0.2s linear",
          pointerEvents: "none",
          textShadow: "0 1px 4px rgba(0,0,0,0.9)",
          maxWidth: 160,
          overflow: "hidden",
          textOverflow: "ellipsis",
          letterSpacing: "0.01em",
        }}
      >
        {data.label}
      </div>

      {/* Handles for edge connections */}
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
