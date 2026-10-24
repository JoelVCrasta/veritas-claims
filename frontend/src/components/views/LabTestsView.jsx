"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import StatusBadge from "../common/StatusBadge";
import PaginationBar from "../common/Pagination";

export default function LabTestsView({ labTests, onSelectRecord }) {
  const [labFilter, setLabFilter] = useState("ALL");
  const [labsPage, setLabsPage] = useState(1);
  const [labsSize, setLabsSize] = useState(15);

  const filteredLabTests =
    labFilter === "ALL"
      ? labTests
      : labTests.filter((r) => r.test_analytics === labFilter);

  const paginate = (items, page, size) => {
    const start = (page - 1) * size;
    return items.slice(start, start + size);
  };

  return (
    <div className="card">
      <div className="table-toolbar">
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <label htmlFor="lab-filter" style={{ fontSize: "0.825rem", color: "var(--text-muted)" }}>
            Filter by Status:
          </label>
          <select
            id="lab-filter"
            className="select-input"
            value={labFilter}
            onChange={(e) => {
              setLabFilter(e.target.value);
              setLabsPage(1);
            }}
          >
            <option value="ALL">All Statuses</option>
            <option value="WITHIN_RANGE">Within Range</option>
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
              <th>Test Name</th>
              <th>Reported As</th>
              <th>Result</th>
              <th>Unit</th>
              <th>Normal Range</th>
              <th>Clinical Status</th>
              <th>Patient Name</th>
              <th>Claim #</th>
              <th>Facility</th>
            </tr>
          </thead>
          <tbody>
            {filteredLabTests.length === 0 ? (
              <tr><td colSpan="9" className="text-center">No lab test records match this filter.</td></tr>
            ) : (
              paginate(filteredLabTests, labsPage, labsSize).map((t) => (
                <tr key={t.id} className="clickable-row" onClick={() => onSelectRecord(t)}>
                  <td style={{ fontWeight: 600 }}>{t.test_name_canonical || "-"}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{t.test_name_original || "-"}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                    {t.result_value !== null ? t.result_value : (t.result_text || "-")}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.unit_canonical || "-"}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.range_text || "-"}</td>
                  <td><StatusBadge flag={t.test_analytics} /></td>
                  <td><DataCell value={t.patient_name} /></td>
                  <td><DataCell value={t.claim_no} mono={true} /></td>
                  <td><DataCell value={t.source_system} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {filteredLabTests.length > 0 && (
        <PaginationBar
          currentPage={labsPage}
          totalItems={filteredLabTests.length}
          pageSize={labsSize}
          onPageChange={setLabsPage}
          onPageSizeChange={setLabsSize}
        />
      )}
    </div>
  );
}
