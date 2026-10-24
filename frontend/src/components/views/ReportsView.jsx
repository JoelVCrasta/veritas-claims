"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import PaginationBar from "../common/Pagination";

export default function ReportsView({ documents, onSelectDocument }) {
  const [docsPage, setDocsPage] = useState(1);
  const [docsSize, setDocsSize] = useState(10);

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
              <th>Patient Name</th>
              <th>Patient ID</th>
              <th>Claim #</th>
              <th>Hospital / Clinic</th>
              <th>Primary Diagnosis</th>
              <th>Lab Tests</th>
              <th>Prescriptions</th>
              <th>Clinical Flags</th>
              <th>Ingested Date</th>
            </tr>
          </thead>
          <tbody>
            {documents.length === 0 ? (
              <tr><td colSpan="9" className="text-center">No reports ingested yet.</td></tr>
            ) : (
              paginate(documents, docsPage, docsSize).map((doc) => (
                <tr
                  key={doc.document_id}
                  className="clickable-row"
                  onClick={() => onSelectDocument(doc)}
                >
                  <td style={{ fontWeight: 600 }}><DataCell value={doc.patient_name} /></td>
                  <td><DataCell value={doc.uhid} mono={true} /></td>
                  <td><DataCell value={doc.claim_no} mono={true} /></td>
                  <td><DataCell value={doc.source_system || doc.hospital_name} /></td>
                  <td style={{ maxWidth: "250px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <DataCell value={doc.primary_diagnosis} />
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>
                    {doc.lab_count}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>
                    {doc.med_count}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", color: doc.flag_count > 0 ? "var(--text-amber)" : "inherit", fontWeight: doc.flag_count > 0 ? 600 : 400 }}>
                    {doc.flag_count}
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    {new Date(doc.processed_at).toLocaleDateString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {documents.length > 0 && (
        <PaginationBar
          currentPage={docsPage}
          totalItems={documents.length}
          pageSize={docsSize}
          onPageChange={setDocsPage}
          onPageSizeChange={setDocsSize}
        />
      )}
    </div>
  );
}
