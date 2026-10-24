"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import PaginationBar from "../common/Pagination";

export default function MedicationsView({ medications, onSelectRecord }) {
  const [medsPage, setMedsPage] = useState(1);
  const [medsSize, setMedsSize] = useState(15);

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
              <th>Medication (Generic)</th>
              <th>Reported Name</th>
              <th>Form</th>
              <th>Dosage</th>
              <th>Frequency</th>
              <th>Patient Name</th>
              <th>Claim #</th>
              <th>Facility</th>
            </tr>
          </thead>
          <tbody>
            {medications.length === 0 ? (
              <tr><td colSpan="8" className="text-center">No prescription records available.</td></tr>
            ) : (
              paginate(medications, medsPage, medsSize).map((m) => (
                <tr key={m.id} className="clickable-row" onClick={() => onSelectRecord(m)}>
                  <td style={{ fontWeight: 600 }}>{m.medicine || "-"}</td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {m.medication_medicine || m.discharge_medications_medicine || "-"}
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
                    {m.medicine_type || "-"}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{m.dose || "-"}</td>
                  <td>{m.frequency || "-"}</td>
                  <td><DataCell value={m.patient_name} /></td>
                  <td><DataCell value={m.claim_no} mono={true} /></td>
                  <td><DataCell value={m.source_system} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {medications.length > 0 && (
        <PaginationBar
          currentPage={medsPage}
          totalItems={medications.length}
          pageSize={medsSize}
          onPageChange={setMedsPage}
          onPageSizeChange={setMedsSize}
        />
      )}
    </div>
  );
}
