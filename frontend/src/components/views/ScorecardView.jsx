"use client";

import React, { useState } from "react";
import PaginationBar from "../common/Pagination";

export default function ScorecardView({ clinics }) {
  const [clinicsPage, setClinicsPage] = useState(1);
  const [clinicsSize, setClinicsSize] = useState(10);

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
              <th>Facility / Source Clinic</th>
              <th>Total Records</th>
              <th>Patient Reports</th>
              <th>Outliers</th>
              <th>Out of Range</th>
              <th>Outlier Rate</th>
              <th>Unmapped Tests</th>
              <th>Dead-Letters</th>
            </tr>
          </thead>
          <tbody>
            {clinics.length === 0 ? (
              <tr><td colSpan="8" className="text-center">No facility data available.</td></tr>
            ) : (
              paginate(clinics, clinicsPage, clinicsSize).map((c) => (
                <tr key={c.source_system}>
                  <td style={{ fontWeight: 600 }}>{c.source_system}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{c.total_records}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{c.total_documents}</td>
                  <td style={{ fontFamily: "var(--font-mono)", color: c.outlier_count > 0 ? "var(--text-red)" : "inherit", fontWeight: 600 }}>
                    {c.outlier_count}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", color: c.out_of_range_count > 0 ? "var(--text-amber)" : "inherit" }}>
                    {c.out_of_range_count}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>{c.outlier_rate}%</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{c.unmapped_tests}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{c.dead_letters}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {clinics.length > 0 && (
        <PaginationBar
          currentPage={clinicsPage}
          totalItems={clinics.length}
          pageSize={clinicsSize}
          onPageChange={setClinicsPage}
          onPageSizeChange={setClinicsSize}
        />
      )}
    </div>
  );
}
