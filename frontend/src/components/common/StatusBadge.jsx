"use client";

import React from "react";

export default function StatusBadge({ flag }) {
  if (!flag) return <span style={{ color: "var(--text-muted)" }}>-</span>;

  switch (flag) {
    case "WITHIN_RANGE":
      return <span className="badge badge-within">WITHIN RANGE</span>;
    case "OUTLIER":
      return <span className="badge badge-outlier">OUTLIER</span>;
    case "ABOVE_RANGE":
      return <span className="badge badge-above">ABOVE RANGE</span>;
    case "BELOW_RANGE":
      return <span className="badge badge-below">BELOW RANGE</span>;
    case "INVALID":
      return <span className="badge badge-invalid">INVALID</span>;
    default:
      return <span className="badge badge-unvalidated">{String(flag).toUpperCase()}</span>;
  }
}
