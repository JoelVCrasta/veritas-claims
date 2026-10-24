"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import StatusBadge from "../common/StatusBadge";
import PaginationBar from "../common/Pagination";

export default function SearchResultsView({ searchResults, onSelectRecord }) {
  const [searchPage, setSearchPage] = useState(1);
  const [searchSize, setSearchSize] = useState(15);

  const paginate = (items, page, size) => {
    const start = (page - 1) * size;
    return items.slice(start, start + size);
  };

  return (
    <div className="card">
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Record Type</th>
              <th>Patient Name</th>
              <th>Patient ID</th>
              <th>Claim #</th>
              <th>Test / Medicine / Diagnosis</th>
              <th>Result</th>
              <th>Status Flag</th>
              <th>Facility</th>
            </tr>
          </thead>
          <tbody>
            {searchResults.length === 0 ? (
              <tr>
                <td colSpan="8" className="text-center" style={{ padding: "3rem" }}>
                  No records matched your search query.
                </td>
              </tr>
            ) : (
              paginate(searchResults, searchPage, searchSize).map((r) => (
                <tr key={r.id} className="clickable-row" onClick={() => onSelectRecord(r)}>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem", fontWeight: 500 }}>
                    {r.record_type === "lab_test"
                      ? "Lab Test"
                      : r.record_type === "medication"
                      ? "Prescription"
                      : "Discharge Summary"}
                  </td>
                  <td style={{ fontWeight: 600 }}><DataCell value={r.patient_name} /></td>
                  <td><DataCell value={r.uhid} mono={true} /></td>
                  <td><DataCell value={r.claim_no} mono={true} /></td>
                  <td style={r.record_type === "discharge_summary" ? {} : { fontWeight: 600 }}>
                    {r.record_type === "lab_test"
                      ? (r.test_name_canonical || "-")
                      : r.record_type === "medication"
                      ? (r.medicine || "-")
                      : (r.diagnosis || "Discharge Summary")}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                    {r.record_type === "lab_test"
                      ? (r.result_value !== null ? `${r.result_value} ${r.unit_canonical || ""}` : (r.result_text || "-"))
                      : r.record_type === "medication"
                      ? (r.dose ? `${r.dose} ${r.frequency}` : "-")
                      : (r.admission_date || "-")}
                  </td>
                  <td><StatusBadge flag={r.test_analytics} /></td>
                  <td><DataCell value={r.source_system} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {searchResults.length > 0 && (
        <PaginationBar
          currentPage={searchPage}
          totalItems={searchResults.length}
          pageSize={searchSize}
          onPageChange={setSearchPage}
          onPageSizeChange={setSearchSize}
        />
      )}
    </div>
  );
}
