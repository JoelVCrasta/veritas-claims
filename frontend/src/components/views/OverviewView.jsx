"use client";

import React, { useState } from "react";
import { FlaskConical, FileText, AlertTriangle, ShieldAlert } from "lucide-react";
import PaginationBar from "../common/Pagination";

export default function OverviewView({ stats, runs }) {
  const [runsPage, setRunsPage] = useState(1);
  const [runsSize, setRunsSize] = useState(10);

  const paginate = (items, page, size) => {
    const start = (page - 1) * size;
    return items.slice(start, start + size);
  };

  return (
    <div>
      {/* KPI Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Total Records</span>
            <span className="stat-icon"><FlaskConical size={16} /></span>
          </div>
          <div className="stat-value">{stats ? stats.total_records.toLocaleString() : "-"}</div>
          <div className="stat-desc">Standardised records found</div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Patient Reports</span>
            <span className="stat-icon"><FileText size={16} /></span>
          </div>
          <div className="stat-value">{stats ? stats.total_documents.toLocaleString() : "-"}</div>
          <div className="stat-desc">Distinct patient claims</div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Flagged Records</span>
            <span className="stat-icon"><AlertTriangle size={16} /></span>
          </div>
          <div className="stat-value text-amber">{stats ? stats.flagged_records.toLocaleString() : "-"}</div>
          <div className="stat-desc">Outliers and abnormal clinical values</div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Outliers</span>
            <span className="stat-icon"><AlertTriangle size={16} /></span>
          </div>
          <div className="stat-value text-red">{stats ? stats.outlier_records.toLocaleString() : "-"}</div>
          <div className="stat-desc">Extreme implausible results</div>
        </div>

        <div className="stat-card">
          <div className="stat-header">
            <span className="stat-label">Dead Letters</span>
            <span className="stat-icon"><ShieldAlert size={16} /></span>
          </div>
          <div className="stat-value">{stats ? stats.dead_letter_count.toLocaleString() : "-"}</div>
          <div className="stat-desc">Suppressed duplicates and format errors</div>
        </div>
      </div>

      {/* Execution Runs Table */}
      <div className="card">
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Execution ID</th>
                <th>Run Timestamp</th>
                <th>Status</th>
                <th>Files Scanned</th>
                <th>Processed</th>
                <th>Duplicates Suppressed</th>
                <th>Records Stored</th>
                <th>Flagged</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr><td colSpan="8" className="text-center">No pipeline executions recorded yet.</td></tr>
              ) : (
                paginate(runs, runsPage, runsSize).map((r) => (
                  <tr key={r.run_id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{r.run_id}</td>
                    <td>{new Date(r.start_time).toLocaleString()}</td>
                    <td>
                      <span className={`badge ${r.status === "COMPLETED" ? "badge-success" : "badge-outlier"}`}>
                        {r.status}
                      </span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{r.files_scanned}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{r.files_processed}</td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>{r.duplicates_suppressed}</td>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{r.records_loaded}</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: r.records_flagged > 0 ? "var(--text-amber)" : "inherit" }}>
                      {r.records_flagged}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {runs.length > 0 && (
          <PaginationBar
            currentPage={runsPage}
            totalItems={runs.length}
            pageSize={runsSize}
            onPageChange={setRunsPage}
            onPageSizeChange={setRunsSize}
          />
        )}
      </div>
    </div>
  );
}
