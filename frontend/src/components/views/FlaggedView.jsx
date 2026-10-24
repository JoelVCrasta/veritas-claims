"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import StatusBadge from "../common/StatusBadge";
import PaginationBar from "../common/Pagination";

export default function FlaggedView({ flagged, onSelectRecord }) {
  const [flagFilter, setFlagFilter] = useState("ALL");
  const [flaggedPage, setFlaggedPage] = useState(1);
  const [flaggedSize, setFlaggedSize] = useState(15);

  const filteredFlagged =
    flagFilter === "ALL"
      ? flagged
      : flagged.filter((r) => r.test_analytics === flagFilter);

  const paginate = (items, page, size) => {
    const start = (page - 1) * size;
    return items.slice(start, start + size);
  };

  return (
    <div className="card">
      <div className="table-toolbar">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label htmlFor="flag-select" style={{ fontSize: "0.825rem", color: "var(--text-muted)" }}>
            Filter by Flag:
          </label>
          <select
            id="flag-select"
            className="select-input"
            value={flagFilter}
            onChange={(e) => {
              setFlagFilter(e.target.value);
              setFlaggedPage(1);
            }}
          >
            <option value="ALL">All Flags</option>
            <option value="OUTLIER">Outliers Only</option>
            <option value="ABOVE_RANGE">Above Range</option>
            <option value="BELOW_RANGE">Below Range</option>
            <option value="INVALID">Invalid Values</option>
          </select>
        </div>
      </div>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Status Flag</th>
              <th>Test Name</th>
              <th>Reported As</th>
              <th>Result</th>
              <th>Unit</th>
              <th>Normal Range</th>
              <th>Patient ID</th>
              <th>Facility</th>
            </tr>
          </thead>
          <tbody>
            {filteredFlagged.length === 0 ? (
              <tr><td colSpan="8" className="text-center">No records match this filter.</td></tr>
            ) : (
              paginate(filteredFlagged, flaggedPage, flaggedSize).map((r) => (
                <tr key={r.id} className="clickable-row" onClick={() => onSelectRecord(r)}>
                  <td><StatusBadge flag={r.test_analytics} /></td>
                  <td style={{ fontWeight: 600 }}>{r.test_name_canonical || "-"}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{r.test_name_original || "-"}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                    {r.result_value !== null ? r.result_value : (r.result_text || "-")}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{r.unit_canonical || "-"}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{r.range_text || "-"}</td>
                  <td><DataCell value={r.uhid} mono={true} /></td>
                  <td><DataCell value={r.source_system} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {filteredFlagged.length > 0 && (
        <PaginationBar
          currentPage={flaggedPage}
          totalItems={filteredFlagged.length}
          pageSize={flaggedSize}
          onPageChange={setFlaggedPage}
          onPageSizeChange={setFlaggedSize}
        />
      )}
    </div>
  );
}
