import { memo, useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
} from "@xyflow/react";

function HoverEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  data,
  markerEnd,
}) {
  const [hovered, setHovered] = useState(false);

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });

  return (
    <>
      {/* Invisible fat hit area */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={14}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{ cursor: "pointer" }}
      />
      {/* Visible edge */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          ...style,
          strokeWidth: hovered ? 2.5 : style?.strokeWidth ?? 1,
          transition: "stroke-width 0.15s ease",
        }}
        markerEnd={markerEnd}
      />
      {/* Glass-panel label on hover */}
      {hovered && data?.relationship && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "none",
              fontSize: 10,
              fontWeight: 500,
              color: "#dfe2eb",
              background: "rgba(38, 42, 49, 0.7)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1px solid rgba(66, 71, 84, 0.15)",
              borderRadius: 6,
              padding: "3px 8px",
              whiteSpace: "nowrap",
              letterSpacing: "0.02em",
            }}
          >
            {data.relationship}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export default memo(HoverEdge);
