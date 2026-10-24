"use client";

import React from "react";

export default function DataCell({ value, mono = false }) {
  if (value === null || value === undefined || value === "") {
    return <span style={{ color: "var(--text-muted)" }}>-</span>;
  }

  const str = String(value).trim();
  if (
    (str.startsWith("[") && str.endsWith("]")) ||
    str.toUpperCase().includes("REDACTED")
  ) {
    return <span className="badge badge-redacted">Redacted</span>;
  }

  return (
    <span style={mono ? { fontFamily: "var(--font-mono)" } : undefined}>
      {str}
    </span>
  );
}
