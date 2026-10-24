"use client";

import React, { useState } from "react";
import DataCell from "../common/DataCell";
import PaginationBar from "../common/Pagination";

export default function DischargesView({ discharges, onSelectRecord }) {
  const [dischargesPage, setDischargesPage] = useState(1);
  const [dischargesSize, setDischargesSize] = useState(10);

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
              <th>Facility</th>
              <th>Primary Diagnosis</th>
              <th>Admission Date</th>
              <th>Discharge Date</th>
              <th>Ward / Dept</th>
            </tr>
          </thead>
          <tbody>
            {discharges.length === 0 ? (
              <tr><td colSpan="8" className="text-center">No discharge summary records available.</td></tr>
            ) : (
              paginate(discharges, dischargesPage, dischargesSize).map((d) => (
                <tr key={d.id} className="clickable-row" onClick={() => onSelectRecord(d)}>
                  <td style={{ fontWeight: 600 }}><DataCell value={d.patient_name} /></td>
                  <td><DataCell value={d.uhid} mono={true} /></td>
                  <td><DataCell value={d.claim_no} mono={true} /></td>
                  <td><DataCell value={d.source_system || d.hospital_name} /></td>
                  <td style={{ maxWidth: "280px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    <DataCell value={d.diagnosis} />
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                    <DataCell value={d.admission_date} />
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                    <DataCell value={d.discharge_date} />
                  </td>
                  <td><DataCell value={d.ward} /></td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {discharges.length > 0 && (
        <PaginationBar
          currentPage={dischargesPage}
          totalItems={discharges.length}
          pageSize={dischargesSize}
          onPageChange={setDischargesPage}
          onPageSizeChange={setDischargesSize}
        />
      )}
    </div>
  );
}
