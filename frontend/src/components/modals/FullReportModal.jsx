"use client";

import React, { useState } from "react";
import { X, Copy, Check, FileCode, FlaskConical, Pill, ChevronDown, ChevronRight } from "lucide-react";
import DataCell from "../common/DataCell";
import StatusBadge from "../common/StatusBadge";
import PaginationBar from "../common/Pagination";

export default function FullReportModal({ bundle, onClose, onSelectRecord }) {
  const [modalTab, setModalTab] = useState("processed");
  const [copied, setCopied] = useState(false);
  const [isLabCollapsed, setIsLabCollapsed] = useState(false);
  const [isMedCollapsed, setIsMedCollapsed] = useState(false);

  const [modalLabsPage, setModalLabsPage] = useState(1);
  const [modalLabsSize, setModalLabsSize] = useState(10);
  const [modalMedsPage, setModalMedsPage] = useState(1);
  const [modalMedsSize, setModalMedsSize] = useState(10);

  if (!bundle) return null;

  const handleCopyJson = (data) => {
    if (!data) return;
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const paginate = (items, page, size) => {
    if (!items) return [];
    const start = (page - 1) * size;
    return items.slice(start, start + size);
  };

  const labTests = bundle.lab_tests || [];
  const medications = bundle.medications || [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <h3 className="modal-title">
              Report: {bundle.summary?.claim_no || bundle.document_id}
            </h3>
            <div className="modal-meta">
              <span className="modal-meta-item">
                <span className="modal-meta-label">Patient:</span>
                <span className="modal-meta-value"><DataCell value={bundle.summary?.patient_name} /></span>
              </span>
              <span className="modal-meta-dot">•</span>
              <span className="modal-meta-item">
                <span className="modal-meta-label">ID:</span>
                <span className="modal-meta-value"><DataCell value={bundle.summary?.uhid} mono={true} /></span>
              </span>
              <span className="modal-meta-dot">•</span>
              <span className="modal-meta-item">
                <span className="modal-meta-label">Facility:</span>
                <span className="modal-meta-value"><DataCell value={bundle.summary?.source_system || bundle.summary?.hospital_name} /></span>
              </span>
              <span className="modal-meta-dot">•</span>
              <span className="modal-meta-item">
                <span className="modal-meta-label">Doc ID:</span>
                <span className="modal-meta-value" style={{ fontFamily: "var(--font-mono)" }}>{bundle.document_id}</span>
              </span>
            </div>
          </div>
          <div className="modal-header-actions">
            <button className="btn-close" onClick={onClose} aria-label="Close modal">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="modal-tabs">
          <button
            className={`modal-tab ${modalTab === "processed" ? "active" : ""}`}
            onClick={() => setModalTab("processed")}
          >
            Standardised Medical Report
          </button>
          <button
            className={`modal-tab ${modalTab === "original" ? "active" : ""}`}
            onClick={() => setModalTab("original")}
          >
            Original Source JSON
          </button>
        </div>

        {/* Modal Body */}
        <div className="modal-body">
          {/* TAB 1: PROCESSED REPORT */}
          {modalTab === "processed" && (
            <div>
              {/* Top Demographic & Admission Info Strip */}
              <div className="info-strip">
                <div className="info-item">
                  <span className="info-label">Patient Age</span>
                  <span className="info-value"><DataCell value={bundle.summary?.age} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Gender</span>
                  <span className="info-value"><DataCell value={bundle.summary?.gender} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Attending Doctor</span>
                  <span className="info-value"><DataCell value={bundle.summary?.doctor_name} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Admission Date</span>
                  <span className="info-value"><DataCell value={bundle.summary?.admission_date} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Discharge Date</span>
                  <span className="info-value"><DataCell value={bundle.summary?.discharge_date} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Ward / Department</span>
                  <span className="info-value"><DataCell value={bundle.summary?.ward} /></span>
                </div>
              </div>

              {/* Diagnosis & Clinical Notes */}
              {(bundle.summary?.diagnosis || bundle.summary?.brief_history || bundle.summary?.post_discharge_advice) && (
                <div className="clinical-notes-card">
                  <div className="clinical-notes-title">Clinical Notes & Diagnosis</div>
                  {bundle.summary?.diagnosis && (
                    <div className="clinical-note-row">
                      <span className="clinical-note-label">Primary Diagnosis:</span>
                      <span className="clinical-note-text">{bundle.summary.diagnosis}</span>
                    </div>
                  )}
                  {bundle.summary?.brief_history && (
                    <div className="clinical-note-row">
                      <span className="clinical-note-label">Brief History:</span>
                      <span className="clinical-note-text">{bundle.summary.brief_history}</span>
                    </div>
                  )}
                  {bundle.summary?.post_discharge_advice && (
                    <div className="clinical-note-row">
                      <span className="clinical-note-label">Post-Discharge Advice:</span>
                      <span className="clinical-note-text">{bundle.summary.post_discharge_advice}</span>
                    </div>
                  )}
                </div>
              )}

              {/* COLLAPSIBLE LAB RESULTS SECTION */}
              <div style={{ marginBottom: "1.5rem" }}>
                <div
                  className="collapsible-trigger"
                  onClick={() => setIsLabCollapsed(!isLabCollapsed)}
                >
                  <div className="collapsible-trigger-title">
                    <FlaskConical size={18} color="var(--primary)" />
                    <span>Lab Tests</span>
                  </div>
                  <div className="collapsible-trigger-meta">
                    <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {labTests.length} observations
                    </span>
                    {isLabCollapsed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
                  </div>
                </div>

                {!isLabCollapsed && (
                  <div>
                    {labTests.length === 0 ? (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "0.5rem 1rem" }}>
                        No lab tests recorded in this report.
                      </p>
                    ) : (
                      <div style={{ border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
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
                              </tr>
                            </thead>
                            <tbody>
                              {paginate(labTests, modalLabsPage, modalLabsSize).map((t) => (
                                <tr
                                  key={t.id}
                                  className={onSelectRecord ? "clickable-row" : ""}
                                  onClick={() => onSelectRecord && onSelectRecord(t)}
                                >
                                  <td style={{ fontWeight: 600 }}>{t.test_name_canonical}</td>
                                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{t.test_name_original}</td>
                                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700 }}>
                                    {t.result_value !== null ? t.result_value : (t.result_text || "-")}
                                  </td>
                                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.unit_canonical || "-"}</td>
                                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.range_text || "-"}</td>
                                  <td><StatusBadge flag={t.test_analytics} /></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {labTests.length > modalLabsSize && (
                          <PaginationBar
                            currentPage={modalLabsPage}
                            totalItems={labTests.length}
                            pageSize={modalLabsSize}
                            onPageChange={setModalLabsPage}
                            onPageSizeChange={setModalLabsSize}
                          />
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* COLLAPSIBLE PRESCRIPTIONS SECTION */}
              <div>
                <div
                  className="collapsible-trigger"
                  onClick={() => setIsMedCollapsed(!isMedCollapsed)}
                >
                  <div className="collapsible-trigger-title">
                    <Pill size={18} color="var(--primary)" />
                    <span>Prescriptions & Medications</span>
                  </div>
                  <div className="collapsible-trigger-meta">
                    <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {medications.length} medications
                    </span>
                    {isMedCollapsed ? <ChevronRight size={18} /> : <ChevronDown size={18} />}
                  </div>
                </div>

                {!isMedCollapsed && (
                  <div>
                    {medications.length === 0 ? (
                      <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", padding: "0.5rem 1rem" }}>
                        No discharge medications recorded in this report.
                      </p>
                    ) : (
                      <div style={{ border: "1px solid var(--border-color)", borderRadius: "var(--radius-md)", overflow: "hidden" }}>
                        <div className="table-container">
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Medication (Generic)</th>
                                <th>Reported Name</th>
                                <th>Form</th>
                                <th>Dosage</th>
                                <th>Frequency</th>
                              </tr>
                            </thead>
                            <tbody>
                              {paginate(medications, modalMedsPage, modalMedsSize).map((m) => (
                                <tr
                                  key={m.id}
                                  className={onSelectRecord ? "clickable-row" : ""}
                                  onClick={() => onSelectRecord && onSelectRecord(m)}
                                >
                                  <td style={{ fontWeight: 600 }}>{m.medicine}</td>
                                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                                    {m.medication_medicine || m.discharge_medications_medicine}
                                  </td>
                                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                                    {m.medicine_type || "-"}
                                  </td>
                                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{m.dose || "-"}</td>
                                  <td>{m.frequency || "-"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        {medications.length > modalMedsSize && (
                          <PaginationBar
                            currentPage={modalMedsPage}
                            totalItems={medications.length}
                            pageSize={modalMedsSize}
                            onPageChange={setModalMedsPage}
                            onPageSizeChange={setModalMedsSize}
                          />
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: ORIGINAL REPORT (RAW JSON) */}
          {modalTab === "original" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                  Source File: <code style={{ fontFamily: "var(--font-mono)" }}>{bundle.summary?.file_gcs_path || "N/A"}</code>
                </span>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => handleCopyJson(bundle.raw_json)}
                  disabled={!bundle.raw_json}
                >
                  {copied ? <Check size={14} color="#16a34a" /> : <Copy size={14} />}
                  <span>{copied ? "Copied!" : "Copy JSON"}</span>
                </button>
              </div>
              {bundle.raw_json ? (
                <pre className="json-viewer">
                  {JSON.stringify(bundle.raw_json, null, 2)}
                </pre>
              ) : (
                <div className="empty-state">
                  <FileCode size={36} className="empty-icon" />
                  <div className="empty-title">Original Payload Unavailable</div>
                  <div className="empty-desc">Source file could not be read directly from local storage.</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
