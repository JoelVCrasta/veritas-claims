"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import PaginationBar from "../common/Pagination";

export default function DeadLetterView({ deadLetters }) {
  const [dlqPage, setDlqPage] = useState(1);
  const [dlqSize, setDlqSize] = useState(10);

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
              <th>Record ID</th>
              <th>Source File</th>
              <th>Facility</th>
              <th>Issue Type</th>
              <th>Details / Error Message</th>
              <th>Logged Time</th>
            </tr>
          </thead>
          <tbody>
            {deadLetters.length === 0 ? (
              <tr><td colSpan="6" className="text-center">No dead-letter entries recorded.</td></tr>
            ) : (
              paginate(deadLetters, dlqPage, dlqSize).map((d) => (
                <tr key={d.id}>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{d.id}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>{d.file_path}</td>
                  <td>
                    <span className={`badge ${d.error_type === "DUPLICATE" ? "badge-above" : "badge-invalid"}`}>
                      {d.error_type}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>{d.error_message}</td>
                  <td>{new Date(d.created_at).toLocaleString()}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {deadLetters.length > 0 && (
        <PaginationBar
          currentPage={dlqPage}
          totalItems={deadLetters.length}
          pageSize={dlqSize}
          onPageChange={setDlqPage}
          onPageSizeChange={setDlqSize}
        />
      )}
    </div>
  );
}
