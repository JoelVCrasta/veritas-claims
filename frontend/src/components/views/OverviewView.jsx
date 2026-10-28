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
          <div className="stat-desc">Duplicates and format errors</div>
        </div>
      </div>

      {/* Audit Table */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Pipeline Audit</h3>
          <span className="badge badge-unvalidated" style={{ fontFamily: "var(--font-mono)" }}>
            {runs.length} events logged
          </span>
        </div>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>File Name</th>
                <th>Timestamp</th>
                <th>Status</th>
                <th>Records Loaded</th>
                <th>Flagged</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center" style={{ padding: "2rem", color: "var(--text-muted)" }}>
                    No streaming file events recorded yet. Drop JSON files into sample_data/ to begin ingestion.
                  </td>
                </tr>
              ) : (
                paginate(runs, runsPage, runsSize).map((r) => (
                  <tr key={r.run_id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600, fontSize: "0.85rem" }}>
                      {r.run_id}
                    </td>
                    <td>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>
                        {r.file_name || "raw_payload.json"}
                      </span>
                    </td>
                    <td style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                      {new Date(r.start_time).toLocaleString()}
                    </td>
                    <td>
                      <span className={`badge ${
                        r.status === "COMPLETED"
                          ? "badge-success"
                          : (r.status === "DUPLICATE" || r.status === "DUPLICATE_SUPPRESSED")
                          ? "badge-above"
                          : "badge-outlier"
                      }`}>
                        {r.status === "DUPLICATE_SUPPRESSED" ? "DUPLICATE" : r.status}
                      </span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "0.85rem" }}>
                      {r.records_loaded}
                    </td>
                    <td style={{
                      fontFamily: "var(--font-mono)",
                      fontWeight: 600,
                      fontSize: "0.85rem",
                      color: r.records_flagged > 0 ? "var(--text-amber)" : "var(--text-muted)",
                    }}>
                      {r.records_flagged}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                      {r.duration_ms ? `${Number(r.duration_ms).toFixed(1)} ms` : "< 1 ms"}
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
