import { memo, useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
} from "@xyflow/react";

/**
 * Edge that only shows its label on hover.
 */
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
      {/* Invisible fat hit area for hover detection */}
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
      {/* Label — only on hover */}
      {hovered && data?.relationship && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "none",
              fontSize: 10,
              color: "#c9d1d9",
              background: "rgba(22, 27, 34, 0.92)",
              border: "1px solid #30363d",
              borderRadius: 4,
              padding: "2px 6px",
              whiteSpace: "nowrap",
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
