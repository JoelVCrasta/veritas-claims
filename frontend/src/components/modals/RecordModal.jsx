"use client";

import React from "react";
import { X, ExternalLink } from "lucide-react";
import DataCell from "../common/DataCell";
import StatusBadge from "../common/StatusBadge";

export default function RecordModal({ record, onClose, onOpenReport }) {
  if (!record) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Header - Aligned, neat, no badge before title */}
        <div className="modal-header">
          <div className="modal-title-group">
            <h3 className="modal-title">{record.id}</h3>
            <div className="modal-meta">
              <span className="modal-meta-item">
                <span className="modal-meta-label">Patient:</span>
                <span className="modal-meta-value"><DataCell value={record.patient_name} /></span>
              </span>
              <span className="modal-meta-dot">•</span>
              <span className="modal-meta-item">
                <span className="modal-meta-label">Claim #:</span>
                <span className="modal-meta-value"><DataCell value={record.claim_no} mono={true} /></span>
              </span>
              <span className="modal-meta-dot">•</span>
              <span className="modal-meta-item">
                <span className="modal-meta-label">Facility:</span>
                <span className="modal-meta-value"><DataCell value={record.source_system || record.hospital_name} /></span>
              </span>
            </div>
          </div>
          <div className="modal-header-actions">
            {record.document_id && (
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  const docId = record.document_id;
                  onClose();
                  onOpenReport(docId);
                }}
              >
                <ExternalLink size={14} />
                <span>View Full Patient Report</span>
              </button>
            )}
            <button className="btn-close" onClick={onClose} aria-label="Close modal">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* LAB TEST SPECIFIC DETAILS */}
          {record.record_type === "lab_test" && (
            <div>
              <div className="details-highlight-strip">
                <div className="details-highlight-item">
                  <span className="details-highlight-label">Result</span>
                  <div className="details-highlight-value" style={{ fontFamily: "var(--font-mono)" }}>
                    {record.result_value !== null ? record.result_value : (record.result_text || "-")}
                    {record.unit_canonical ? ` ${record.unit_canonical}` : ""}
                  </div>
                </div>
                <div className="details-highlight-item">
                  <span className="details-highlight-label">Normal Range</span>
                  <div className="details-highlight-value" style={{ fontSize: "1.15rem", fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                    {record.range_text || "-"}
                  </div>
                </div>
                <div className="details-highlight-item">
                  <span className="details-highlight-label">Clinical Status</span>
                  <div style={{ marginTop: "0.2rem" }}>
                    <StatusBadge flag={record.test_analytics} />
                  </div>
                </div>
              </div>

              <div className="details-card">
                <div className="details-card-header">Investigation Details</div>
                <div className="details-card-body">
                  <div className="details-grid">
                    <div className="details-item">
                      <span className="details-label">Test Name (Canonical)</span>
                      <span className="details-value">{record.test_name_canonical || "-"}</span>
                    </div>
                    <div className="details-item">
                      <span className="details-label">Reported As</span>
                      <span className="details-value" style={{ color: "var(--text-muted)" }}>
                        {record.test_name_original || "-"}
                      </span>
                    </div>
                    <div className="details-item">
                      <span className="details-label">Unit</span>
                      <span className="details-value" style={{ fontFamily: "var(--font-mono)" }}>
                        {record.unit_canonical || "-"}
                      </span>
                    </div>
                    <div className="details-item">
                      <span className="details-label">Facility / Source</span>
                      <span className="details-value">
                        <DataCell value={record.source_system || record.hospital_name} />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* PRESCRIPTION SPECIFIC DETAILS */}
          {record.record_type === "medication" && (
            <div className="details-card">
              <div className="details-card-header">Prescription Details</div>
              <div className="details-card-body">
                <div className="details-grid">
                  <div className="details-item">
                    <span className="details-label">Medication (Generic)</span>
                    <span className="details-value" style={{ fontWeight: 600 }}>
                      {record.medicine || "-"}
                    </span>
                  </div>
                  <div className="details-item">
                    <span className="details-label">Reported Brand Name</span>
                    <span className="details-value" style={{ color: "var(--text-muted)" }}>
                      {record.medication_medicine || record.discharge_medications_medicine || "-"}
                    </span>
                  </div>
                  <div className="details-item">
                    <span className="details-label">Form</span>
                    <span className="details-value">{record.medicine_type || "-"}</span>
                  </div>
                  <div className="details-item">
                    <span className="details-label">Dosage</span>
                    <span className="details-value" style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {record.dose || "-"}
                    </span>
                  </div>
                  <div className="details-item">
                    <span className="details-label">Frequency / Schedule</span>
                    <span className="details-value">{record.frequency || "-"}</span>
                  </div>
                  <div className="details-item">
                    <span className="details-label">Facility / Source</span>
                    <span className="details-value">
                      <DataCell value={record.source_system || record.hospital_name} />
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* DISCHARGE SUMMARY SPECIFIC DETAILS */}
          {record.record_type === "discharge_summary" && (
            <div>
              <div className="info-strip">
                <div className="info-item">
                  <span className="info-label">Admission Date</span>
                  <span className="info-value"><DataCell value={record.admission_date} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Discharge Date</span>
                  <span className="info-value"><DataCell value={record.discharge_date} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Attending Doctor</span>
                  <span className="info-value"><DataCell value={record.doctor_name} /></span>
                </div>
                <div className="info-item">
                  <span className="info-label">Ward / Dept</span>
                  <span className="info-value"><DataCell value={record.ward} /></span>
                </div>
              </div>

              <div className="clinical-notes-card">
                <div className="clinical-notes-title">Clinical Diagnosis & Documentation</div>
                {record.diagnosis && (
                  <div className="clinical-note-row">
                    <span className="clinical-note-label">Primary Diagnosis:</span>
                    <span className="clinical-note-text">{record.diagnosis}</span>
                  </div>
                )}
                {record.brief_history && (
                  <div className="clinical-note-row">
                    <span className="clinical-note-label">Brief History:</span>
                    <span className="clinical-note-text">{record.brief_history}</span>
                  </div>
                )}
                {record.general_examinations && (
                  <div className="clinical-note-row">
                    <span className="clinical-note-label">Examinations:</span>
                    <span className="clinical-note-text">{record.general_examinations}</span>
                  </div>
                )}
                {record.recommendations && (
                  <div className="clinical-note-row">
                    <span className="clinical-note-label">Recommendations:</span>
                    <span className="clinical-note-text">{record.recommendations}</span>
                  </div>
                )}
                {record.post_discharge_advice && (
                  <div className="clinical-note-row">
                    <span className="clinical-note-label">Post-Discharge Advice:</span>
                    <span className="clinical-note-text">{record.post_discharge_advice}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
