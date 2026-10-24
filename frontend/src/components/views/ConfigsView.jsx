"use client";

import React, { useState, useEffect } from "react";
import {
  Plus,
  Trash2,
  CheckCircle2,
  Search,
  Shield,
  X,
} from "lucide-react";
import PaginationBar from "../common/Pagination";

const API_BASE = "http://localhost:8000";

export default function ConfigsView() {
  const [activeSubTab, setActiveSubTab] = useState("clinics");

  // Data states
  const [clinicsData, setClinicsData] = useState({});
  const [dedupChecks, setDedupChecks] = useState({});
  const [testsData, setTestsData] = useState({});
  const [rangesData, setRangesData] = useState({});
  const [medicinesData, setMedicinesData] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Search & filter
  const [filterQuery, setFilterQuery] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Modals
  const [modalType, setModalType] = useState(null); // 'clinic', 'test', 'range', 'medicine'
  const [clinicForm, setClinicForm] = useState({
    key: "",
    system_name: "",
    doc_id: "data.documentId",
    corr_id: "data.correlationId",
    meta_field: "data.metaDetails",
    resp_field: "data.responseDetails",
    name_fields: "patient_name, patientName",
    age_fields: "age, patient_age",
    gender_fields: "gender, sex",
    uhid_fields: "uhid, mrn",
  });
  const [testForm, setTestForm] = useState({
    name: "",
    unit: "",
    aliases: "",
  });
  const [rangeForm, setRangeForm] = useState({
    test_name: "",
    unit: "",
    range_low: "",
    range_high: "",
    outlier_low: "",
    outlier_high: "",
  });
  const [medForm, setMedForm] = useState({
    brand: "",
    generic: "",
  });

  useEffect(() => {
    fetchAllConfigs();
  }, []);

  useEffect(() => {
    setPage(1);
    setFilterQuery("");
  }, [activeSubTab]);

  async function fetchAllConfigs() {
    setLoading(true);
    try {
      const [clinicsRes, testsRes, rangesRes, medsRes] = await Promise.all([
        fetch(`${API_BASE}/api/configs/clinics`).then((r) => r.json()).catch(() => ({})),
        fetch(`${API_BASE}/api/configs/tests`).then((r) => r.json()).catch(() => ({})),
        fetch(`${API_BASE}/api/configs/ranges`).then((r) => r.json()).catch(() => ({})),
        fetch(`${API_BASE}/api/configs/medicines`).then((r) => r.json()).catch(() => ({})),
      ]);

      setClinicsData(clinicsRes.clinics || {});
      setDedupChecks(clinicsRes.deduplication?.checks || {});
      setTestsData(testsRes || {});
      setRangesData(rangesRes || {});
      setMedicinesData(medsRes || {});
    } catch (err) {
      console.error("Failed to load configs:", err);
    } finally {
      setLoading(false);
    }
  }

  function showFeedback(type, text) {
    setFeedback({ type, text });
    setTimeout(() => setFeedback(null), 3000);
  }

  // Deduplication Save
  async function handleSaveDedup() {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/configs/dedup`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ checks: dedupChecks }),
      });
      if (res.ok) {
        showFeedback("success", "Deduplication checks successfully updated.");
      } else {
        showFeedback("error", "Failed to update deduplication settings.");
      }
    } catch (err) {
      showFeedback("error", "Error saving: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  // Clinic Adapter Operations
  async function handleAddClinic(e) {
    e.preventDefault();
    const key = clinicForm.key.trim().toUpperCase();
    if (!key) return;
    setSaving(true);
    try {
      const parseList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
      const payload = {
        clinic_key: key,
        config: {
          system_name: clinicForm.system_name.trim() || key,
          document_id_field: clinicForm.doc_id.trim() || "data.documentId",
          correlation_id_field: clinicForm.corr_id.trim() || "data.correlationId",
          meta_details_field: clinicForm.meta_field.trim() || "data.metaDetails",
          response_details_field: clinicForm.resp_field.trim() || "data.responseDetails",
          patient_fields: {
            patient_name: parseList(clinicForm.name_fields),
            age: parseList(clinicForm.age_fields),
            gender: parseList(clinicForm.gender_fields),
            uhid: parseList(clinicForm.uhid_fields),
          },
        },
      };
      const res = await fetch(`${API_BASE}/api/configs/clinics`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setModalType(null);
        showFeedback("success", `Clinic adapter for "${key}" saved.`);
        await fetchAllConfigs();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to save clinic.");
      }
    } catch (err) {
      alert("Error saving clinic: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteClinic(key) {
    if (key === "DEFAULT") return alert("Cannot delete the DEFAULT fallback adapter.");
    if (!confirm(`Delete clinic adapter "${key}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/configs/clinics/${encodeURIComponent(key)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showFeedback("success", `Clinic adapter "${key}" removed.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  // Test Dictionary Operations
  async function handleAddTest(e) {
    e.preventDefault();
    const name = testForm.name.trim().toUpperCase();
    if (!name) return;
    setSaving(true);
    try {
      const aliases = testForm.aliases.split(",").map((s) => s.trim()).filter(Boolean);
      const payload = {
        test_name: name,
        canonical_unit: testForm.unit.trim(),
        aliases: aliases.length > 0 ? aliases : [name],
        unit_conversions: {},
      };
      const res = await fetch(`${API_BASE}/api/configs/tests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setModalType(null);
        setTestForm({ name: "", unit: "", aliases: "" });
        showFeedback("success", `Test definition "${name}" saved.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Error adding test: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteTest(name) {
    if (!confirm(`Delete test "${name}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/configs/tests/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showFeedback("success", `Test "${name}" deleted.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  // Reference Ranges Operations
  async function handleAddRange(e) {
    e.preventDefault();
    const name = rangeForm.test_name.trim().toUpperCase();
    if (!name) return;
    setSaving(true);
    try {
      const payload = {
        test_name: name,
        unit: rangeForm.unit.trim(),
        range_low: rangeForm.range_low ? parseFloat(rangeForm.range_low) : null,
        range_high: rangeForm.range_high ? parseFloat(rangeForm.range_high) : null,
        outlier_low: rangeForm.outlier_low ? parseFloat(rangeForm.outlier_low) : null,
        outlier_high: rangeForm.outlier_high ? parseFloat(rangeForm.outlier_high) : null,
      };
      const res = await fetch(`${API_BASE}/api/configs/ranges`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        setModalType(null);
        setRangeForm({ test_name: "", unit: "", range_low: "", range_high: "", outlier_low: "", outlier_high: "" });
        showFeedback("success", `Reference range for "${name}" saved.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Error adding range: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteRange(name) {
    if (!confirm(`Delete reference range for "${name}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/configs/ranges/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showFeedback("success", `Range for "${name}" deleted.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  // Medicine Mapping Operations
  async function handleAddMedicine(e) {
    e.preventDefault();
    const brand = medForm.brand.trim().toLowerCase();
    const generic = medForm.generic.trim();
    if (!brand || !generic) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/configs/medicines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ brand, generic }),
      });
      if (res.ok) {
        setModalType(null);
        setMedForm({ brand: "", generic: "" });
        showFeedback("success", `Medicine mapping "${brand}" → "${generic}" saved.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Error adding medicine: " + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteMedicine(brand) {
    if (!confirm(`Delete medicine mapping for "${brand}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/configs/medicines/${encodeURIComponent(brand)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        showFeedback("success", `Medicine mapping for "${brand}" deleted.`);
        await fetchAllConfigs();
      }
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  if (loading) {
    return (
      <div className="card text-center" style={{ padding: "3rem" }}>
        <p style={{ color: "var(--text-muted)" }}>Loading configurations...</p>
      </div>
    );
  }

  const subTabs = [
    { id: "clinics", label: "Clinic Adapters", count: Object.keys(clinicsData).length },
    { id: "dedup", label: "Deduplication", count: Object.values(dedupChecks).filter(Boolean).length },
    { id: "tests", label: "Test Dictionary", count: Object.keys(testsData).length },
    { id: "ranges", label: "Reference Ranges", count: Object.keys(rangesData).length },
    { id: "medicines", label: "Medicine Mappings", count: Object.keys(medicinesData).length },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* SUB-TABS NAVIGATION BAR */}
      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          background: "#ffffff",
          padding: "0.4rem 0.5rem",
          borderRadius: "8px",
          border: "1px solid var(--border-color)",
          overflowX: "auto",
        }}
      >
        {subTabs.map((t) => {
          const isActive = activeSubTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveSubTab(t.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: isActive ? "1px solid #1d4ed8" : "1px solid transparent",
                background: isActive ? "#2563eb" : "transparent",
                color: isActive ? "#ffffff" : "var(--text-main)",
                fontWeight: isActive ? 600 : 500,
                fontSize: "0.85rem",
                cursor: "pointer",
                transition: "all 0.15s ease",
                whiteSpace: "nowrap",
                boxShadow: isActive ? "0 2px 4px rgba(37, 99, 235, 0.25)" : "none",
              }}
            >
              <span>{t.label}</span>
              <span
                style={{
                  fontSize: "0.75rem",
                  padding: "0.1rem 0.45rem",
                  borderRadius: "10px",
                  background: isActive ? "rgba(255, 255, 255, 0.25)" : "#f1f5f9",
                  color: isActive ? "#ffffff" : "#64748b",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                }}
              >
                {t.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* FEEDBACK BANNER */}
      {feedback && (
        <div
          style={{
            padding: "0.75rem 1rem",
            borderRadius: "6px",
            background: feedback.type === "success" ? "#ecfdf5" : "#ffe4e6",
            color: feedback.type === "success" ? "#065f46" : "#9f1239",
            fontSize: "0.85rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
          }}
        >
          <CheckCircle2 size={16} />
          <span>{feedback.text}</span>
        </div>
      )}

      {/* SUB-TAB 1: CLINIC ADAPTERS */}
      {activeSubTab === "clinics" && (
        <div className="card">
          <div className="table-toolbar">
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Extracts document IDs, response details, and demographic fields from clinic JSON payloads.
            </span>
            <div style={{ marginLeft: "auto", display: "flex", gap: "0.5rem" }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => setModalType("clinic")}
                style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
              >
                <Plus size={15} />
                <span>Add Clinic</span>
              </button>
            </div>
          </div>

          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Clinic Identifier</th>
                  <th>System Name</th>
                  <th>Document ID Field</th>
                  <th>Response Details Field</th>
                  <th>Demographic Field Mapping</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(clinicsData).map(([key, cfg]) => {
                  const isDefault = key === "DEFAULT";
                  const pFields = cfg.patient_fields || {};
                  return (
                    <tr key={key}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <span style={{ fontWeight: 600, fontFamily: "var(--font-mono)" }}>{key}</span>
                          {isDefault && (
                            <span className="badge badge-unvalidated" style={{ fontSize: "0.7rem" }}>
                              <Shield size={10} style={{ marginRight: "2px" }} /> Fallback
                            </span>
                          )}
                        </div>
                      </td>
                      <td>{cfg.system_name || key}</td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {cfg.document_id_field || "data.documentId"}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                        {cfg.response_details_field || "data.responseDetails"}
                      </td>
                      <td>
                        <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                          <span>name: {Array.isArray(pFields.patient_name) ? pFields.patient_name.join(", ") : "-"}</span>
                          <span>age: {Array.isArray(pFields.age) ? pFields.age.join(", ") : "-"}</span>
                        </div>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {!isDefault ? (
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleDeleteClinic(key)}
                            title="Remove Adapter"
                            style={{ color: "#ef4444", borderColor: "#fecaca" }}
                          >
                            <Trash2 size={13} />
                          </button>
                        ) : (
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Protected</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: DEDUPLICATION */}
      {activeSubTab === "dedup" && (
        <div className="card">
          <div className="table-toolbar">
            <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
              Select which check rules to enable for detecting duplicate reports.
            </span>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleSaveDedup}
              disabled={saving}
              style={{ marginLeft: "auto" }}
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
          </div>

          <div style={{ padding: "1.25rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1rem" }}>
            {/* Document ID */}
            <div
              onClick={() => setDedupChecks({ ...dedupChecks, document_id: !dedupChecks.document_id })}
              style={{
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "1.1rem 1.25rem",
                cursor: "pointer",
                background: dedupChecks.document_id ? "rgba(37, 99, 235, 0.05)" : "#ffffff",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Document ID</span>
                <input
                  type="checkbox"
                  checked={!!dedupChecks.document_id}
                  onChange={() => {}}
                  style={{ width: "18px", height: "18px", cursor: "pointer" }}
                />
              </div>
            </div>

            {/* Content Hash */}
            <div
              onClick={() => setDedupChecks({ ...dedupChecks, content_hash: !dedupChecks.content_hash })}
              style={{
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "1.1rem 1.25rem",
                cursor: "pointer",
                background: dedupChecks.content_hash ? "rgba(37, 99, 235, 0.05)" : "#ffffff",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Content Hash</span>
                <input
                  type="checkbox"
                  checked={!!dedupChecks.content_hash}
                  onChange={() => {}}
                  style={{ width: "18px", height: "18px", cursor: "pointer" }}
                />
              </div>
            </div>

            {/* Claim Number */}
            <div
              onClick={() => setDedupChecks({ ...dedupChecks, claim_no: !dedupChecks.claim_no })}
              style={{
                border: "1px solid var(--border-color)",
                borderRadius: "8px",
                padding: "1.1rem 1.25rem",
                cursor: "pointer",
                background: dedupChecks.claim_no ? "rgba(37, 99, 235, 0.05)" : "#ffffff",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Claim Number</span>
                <input
                  type="checkbox"
                  checked={!!dedupChecks.claim_no}
                  onChange={() => {}}
                  style={{ width: "18px", height: "18px", cursor: "pointer" }}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 3: TEST DICTIONARY */}
      {activeSubTab === "tests" && (
        <div className="card">
          <div className="table-toolbar">
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <div style={{ position: "relative", width: "260px" }}>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Filter test or alias..."
                  value={filterQuery}
                  onChange={(e) => {
                    setFilterQuery(e.target.value);
                    setPage(1);
                  }}
                  style={{ width: "100%", paddingLeft: "1.75rem", fontSize: "0.8rem" }}
                />
                <Search size={13} style={{ position: "absolute", left: "9px", top: "10px", color: "var(--text-muted)" }} />
              </div>
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setModalType("test")}
              style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.35rem" }}
            >
              <Plus size={15} />
              <span>Add Test</span>
            </button>
          </div>

          {(() => {
            const allTests = Object.entries(testsData);
            const filtered = allTests.filter(([name, data]) => {
              if (!filterQuery) return true;
              const q = filterQuery.toLowerCase();
              return (
                name.toLowerCase().includes(q) ||
                (data.aliases || []).some((a) => a.toLowerCase().includes(q))
              );
            });
            const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

            return (
              <>
                <div className="table-container">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Canonical Test Name</th>
                        <th>Canonical Unit</th>
                        <th>Registered Aliases</th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginated.length === 0 ? (
                        <tr><td colSpan="4" className="text-center">No tests found matching filter.</td></tr>
                      ) : (
                        paginated.map(([name, data]) => (
                          <tr key={name}>
                            <td style={{ fontWeight: 600 }}>{name}</td>
                            <td>{data.canonical_unit || "-"}</td>
                            <td>
                              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem", maxWidth: "600px" }}>
                                {(data.aliases || []).map((a, i) => (
                                  <span key={i} className="badge badge-unvalidated" style={{ fontSize: "0.75rem" }}>
                                    {a}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDeleteTest(name)}
                                title="Remove Test"
                                style={{ color: "#ef4444", borderColor: "#fecaca" }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {filtered.length > 0 && (
                  <PaginationBar
                    currentPage={page}
                    totalItems={filtered.length}
                    pageSize={pageSize}
                    onPageChange={setPage}
                    onPageSizeChange={setPageSize}
                  />
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* SUB-TAB 4: REFERENCE RANGES */}
      {activeSubTab === "ranges" && (
        <div className="card">
          <div className="table-toolbar">
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <div style={{ position: "relative", width: "260px" }}>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Filter by test name..."
                  value={filterQuery}
                  onChange={(e) => {
                    setFilterQuery(e.target.value);
                    setPage(1);
                  }}
                  style={{ width: "100%", paddingLeft: "1.75rem", fontSize: "0.8rem" }}
                />
                <Search size={13} style={{ position: "absolute", left: "9px", top: "10px", color: "var(--text-muted)" }} />
              </div>
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setModalType("range")}
              style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.35rem" }}
            >
              <Plus size={15} />
              <span>Add Range</span>
            </button>
          </div>

          {(() => {
            const allRanges = Object.entries(rangesData);
            const filtered = allRanges.filter(([name]) =>
              !filterQuery || name.toLowerCase().includes(filterQuery.toLowerCase())
            );
            const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

            return (
              <>
                <div className="table-container">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Test Name</th>
                        <th>Unit</th>
                        <th>Normal Range</th>
                        <th>Outlier Boundaries</th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginated.length === 0 ? (
                        <tr><td colSpan="5" className="text-center">No reference ranges found.</td></tr>
                      ) : (
                        paginated.map(([name, data]) => (
                          <tr key={name}>
                            <td style={{ fontWeight: 600 }}>{name}</td>
                            <td>{data.unit || "-"}</td>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>
                              {data.range_low !== null && data.range_high !== null
                                ? `${data.range_low} – ${data.range_high}`
                                : "-"}
                            </td>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#9f1239" }}>
                              {data.outlier_low !== null && data.outlier_high !== null
                                ? `< ${data.outlier_low} or > ${data.outlier_high}`
                                : "-"}
                            </td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDeleteRange(name)}
                                title="Remove Range"
                                style={{ color: "#ef4444", borderColor: "#fecaca" }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {filtered.length > 0 && (
                  <PaginationBar
                    currentPage={page}
                    totalItems={filtered.length}
                    pageSize={pageSize}
                    onPageChange={setPage}
                    onPageSizeChange={setPageSize}
                  />
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* SUB-TAB 5: MEDICINE MAPPINGS */}
      {activeSubTab === "medicines" && (
        <div className="card">
          <div className="table-toolbar">
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <div style={{ position: "relative", width: "260px" }}>
                <input
                  type="text"
                  className="search-input"
                  placeholder="Filter brand or generic..."
                  value={filterQuery}
                  onChange={(e) => {
                    setFilterQuery(e.target.value);
                    setPage(1);
                  }}
                  style={{ width: "100%", paddingLeft: "1.75rem", fontSize: "0.8rem" }}
                />
                <Search size={13} style={{ position: "absolute", left: "9px", top: "10px", color: "var(--text-muted)" }} />
              </div>
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setModalType("medicine")}
              style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.35rem" }}
            >
              <Plus size={15} />
              <span>Add Medicine</span>
            </button>
          </div>

          {(() => {
            const allMeds = Object.entries(medicinesData);
            const filtered = allMeds.filter(([brand, generic]) => {
              if (!filterQuery) return true;
              const q = filterQuery.toLowerCase();
              return brand.toLowerCase().includes(q) || generic.toLowerCase().includes(q);
            });
            const paginated = filtered.slice((page - 1) * pageSize, page * pageSize);

            return (
              <>
                <div className="table-container">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Brand Name Variant</th>
                        <th>Generic Molecule</th>
                        <th style={{ textAlign: "right" }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {paginated.length === 0 ? (
                        <tr><td colSpan="3" className="text-center">No medicine mappings found.</td></tr>
                      ) : (
                        paginated.map(([brand, generic]) => (
                          <tr key={brand}>
                            <td style={{ fontFamily: "var(--font-mono)", fontWeight: 500 }}>{brand}</td>
                            <td style={{ fontWeight: 600 }}>{generic}</td>
                            <td style={{ textAlign: "right" }}>
                              <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => handleDeleteMedicine(brand)}
                                title="Remove Medicine"
                                style={{ color: "#ef4444", borderColor: "#fecaca" }}
                              >
                                <Trash2 size={13} />
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {filtered.length > 0 && (
                  <PaginationBar
                    currentPage={page}
                    totalItems={filtered.length}
                    pageSize={pageSize}
                    onPageChange={setPage}
                    onPageSizeChange={setPageSize}
                  />
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* MODAL: ADD CLINIC */}
      {modalType === "clinic" && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "520px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Add Clinic Adapter</h3>
              <button className="btn-close" onClick={() => setModalType(null)}>×</button>
            </div>
            <form onSubmit={handleAddClinic}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Clinic Key Identifier *
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      placeholder="e.g. APOLLO"
                      value={clinicForm.key}
                      onChange={(e) => setClinicForm({ ...clinicForm, key: e.target.value })}
                      required
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      System Name
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      placeholder="e.g. APOLLO_HOSPITALS"
                      value={clinicForm.system_name}
                      onChange={(e) => setClinicForm({ ...clinicForm, system_name: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>

                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Document ID Path
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      value={clinicForm.doc_id}
                      onChange={(e) => setClinicForm({ ...clinicForm, doc_id: e.target.value })}
                      style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Response Details Path
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      value={clinicForm.resp_field}
                      onChange={(e) => setClinicForm({ ...clinicForm, resp_field: e.target.value })}
                      style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
                    />
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Patient Name Aliases (comma-separated)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    value={clinicForm.name_fields}
                    onChange={(e) => setClinicForm({ ...clinicForm, name_fields: e.target.value })}
                    style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
                  />
                </div>

                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Age Aliases
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      value={clinicForm.age_fields}
                      onChange={(e) => setClinicForm({ ...clinicForm, age_fields: e.target.value })}
                      style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Gender Aliases
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      value={clinicForm.gender_fields}
                      onChange={(e) => setClinicForm({ ...clinicForm, gender_fields: e.target.value })}
                      style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}
                    />
                  </div>
                </div>
              </div>

              <div style={{ padding: "0.85rem 1.25rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>Save Clinic</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ADD TEST */}
      {modalType === "test" && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Add Canonical Test</h3>
              <button className="btn-close" onClick={() => setModalType(null)}>×</button>
            </div>
            <form onSubmit={handleAddTest}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Canonical Test Name *
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="e.g. LIPID PROFILE"
                    value={testForm.name}
                    onChange={(e) => setTestForm({ ...testForm, name: e.target.value })}
                    required
                    style={{ width: "100%" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Canonical Unit
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="e.g. mg/dL"
                    value={testForm.unit}
                    onChange={(e) => setTestForm({ ...testForm, unit: e.target.value })}
                    style={{ width: "100%" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Aliases (comma-separated)
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="e.g. Lipid, Lipids, Lipid Screen"
                    value={testForm.aliases}
                    onChange={(e) => setTestForm({ ...testForm, aliases: e.target.value })}
                    style={{ width: "100%" }}
                  />
                </div>
              </div>
              <div style={{ padding: "0.85rem 1.25rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>Save Test</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ADD RANGE */}
      {modalType === "range" && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Add Reference Range</h3>
              <button className="btn-close" onClick={() => setModalType(null)}>×</button>
            </div>
            <form onSubmit={handleAddRange}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Test Name *
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      placeholder="e.g. CALCIUM"
                      value={rangeForm.test_name}
                      onChange={(e) => setRangeForm({ ...rangeForm, test_name: e.target.value })}
                      required
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Unit
                    </label>
                    <input
                      type="text"
                      className="search-input"
                      placeholder="e.g. mg/dL"
                      value={rangeForm.unit}
                      onChange={(e) => setRangeForm({ ...rangeForm, unit: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>

                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Normal Range Low
                    </label>
                    <input
                      type="number"
                      step="any"
                      className="search-input"
                      placeholder="e.g. 8.5"
                      value={rangeForm.range_low}
                      onChange={(e) => setRangeForm({ ...rangeForm, range_low: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Normal Range High
                    </label>
                    <input
                      type="number"
                      step="any"
                      className="search-input"
                      placeholder="e.g. 10.5"
                      value={rangeForm.range_high}
                      onChange={(e) => setRangeForm({ ...rangeForm, range_high: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>

                <div className="grid-2">
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Outlier Threshold Low
                    </label>
                    <input
                      type="number"
                      step="any"
                      className="search-input"
                      placeholder="e.g. 4.0"
                      value={rangeForm.outlier_low}
                      onChange={(e) => setRangeForm({ ...rangeForm, outlier_low: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                  <div>
                    <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                      Outlier Threshold High
                    </label>
                    <input
                      type="number"
                      step="any"
                      className="search-input"
                      placeholder="e.g. 16.0"
                      value={rangeForm.outlier_high}
                      onChange={(e) => setRangeForm({ ...rangeForm, outlier_high: e.target.value })}
                      style={{ width: "100%" }}
                    />
                  </div>
                </div>
              </div>
              <div style={{ padding: "0.85rem 1.25rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>Save Range</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ADD MEDICINE */}
      {modalType === "medicine" && (
        <div className="modal-overlay" onClick={() => setModalType(null)}>
          <div className="modal-container" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "460px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>Add Medicine Mapping</h3>
              <button className="btn-close" onClick={() => setModalType(null)}>×</button>
            </div>
            <form onSubmit={handleAddMedicine}>
              <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Brand Name / Prescription Form *
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="e.g. tab augmentin 625"
                    value={medForm.brand}
                    onChange={(e) => setMedForm({ ...medForm, brand: e.target.value })}
                    required
                    style={{ width: "100%" }}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "0.8rem", fontWeight: 600, marginBottom: "0.2rem" }}>
                    Generic Molecule Name *
                  </label>
                  <input
                    type="text"
                    className="search-input"
                    placeholder="e.g. Amoxicillin + Clavulanic Acid"
                    value={medForm.generic}
                    onChange={(e) => setMedForm({ ...medForm, generic: e.target.value })}
                    required
                    style={{ width: "100%" }}
                  />
                </div>
              </div>
              <div style={{ padding: "0.85rem 1.25rem", borderTop: "1px solid var(--border-color)", display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setModalType(null)}>Cancel</button>
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>Save Mapping</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
