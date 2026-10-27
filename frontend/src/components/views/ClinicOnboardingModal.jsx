"use client";

import React, { useState } from "react";
import { CheckCircle2, AlertCircle, RefreshCw, X, Layers, Code, Check } from "lucide-react";

const API_BASE = "http://localhost:8000";

const DEFAULT_SAMPLE_JSON = JSON.stringify(
  {
    header: {
      doc_id: "[DOC-ID-REDACTED]",
      facility: "Metropolis Clinical Labs",
      source_system: "METROPOLIS_CARE",
    },
    sections: [
      {
        classifier: "lab_report",
        data: {
          demographics: {
            patient_name: "[PATIENT NAME REDACTED]",
            patient_age: "[AGE REDACTED]",
            sex: "[GENDER REDACTED]",
            mrn: "[MRN-REDACTED]",
          },
          investigations: [
            {
              parameter: "Hemoglobin",
              observed_value: "13.5",
              uom: "g/dL",
              reference_interval: "12.0 - 15.0",
            },
            {
              parameter: "S. Potassium",
              observed_value: "4.2",
              uom: "mmol/L",
              reference_interval: "3.5 - 5.0",
            },
            {
              parameter: "S. Creatinine",
              observed_value: "1.1",
              uom: "mg/dL",
              reference_interval: "0.7 - 1.3",
            },
          ],
        },
      },
    ],
  },
  null,
  2
);

export default function ClinicOnboardingModal({ isOpen, onClose, onSuccess }) {
  const [rawJson, setRawJson] = useState(DEFAULT_SAMPLE_JSON);
  const [clinicKey, setClinicKey] = useState("METROPOLIS_CARE");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [adapterConfig, setAdapterConfig] = useState(null);
  const [fieldMappings, setFieldMappings] = useState(null);
  const [showRawConfig, setShowRawConfig] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  async function handleOnboard() {
    setErrorMsg(null);
    setSuccessMsg(null);

    let parsedObj;
    try {
      parsedObj = JSON.parse(rawJson);
    } catch (err) {
      setErrorMsg("Invalid JSON template format. Please paste valid JSON.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ai/infer-mapping`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payload: parsedObj,
          clinic_name: clinicKey.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to onboard clinic schema");
      }

      const data = await res.json();
      setAdapterConfig(data.adapter_config || null);
      setFieldMappings(data.field_mappings || []);
      if (data.clinic_key) {
        setClinicKey(data.clinic_key);
      }
    } catch (err) {
      setErrorMsg(err.message || "Failed to onboard clinic schema");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveAdapter() {
    if (!adapterConfig) return;
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetch(`${API_BASE}/api/ai/apply-onboarding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_key: clinicKey.trim().toUpperCase(),
          adapter_config: adapterConfig,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save clinic adapter");
      }

      setSuccessMsg(`Clinic "${clinicKey}" adapter saved. Future incoming reports will map automatically.`);
      if (onSuccess) {
        await onSuccess();
      }
      setTimeout(() => {
        onClose();
      }, 900);
    } catch (err) {
      setErrorMsg(err.message || "Failed to save clinic adapter");
    } finally {
      setSaving(false);
    }
  }

  const getCategoryBadgeStyle = (cat) => {
    const c = String(cat || "").toLowerCase();
    if (c.includes("envelope")) {
      return { bg: "#e0f2fe", text: "#0369a1", border: "#bae6fd" };
    }
    if (c.includes("demographic") || c.includes("patient")) {
      return { bg: "#f3e8ff", text: "#7e22ce", border: "#e9d5ff" };
    }
    if (c.includes("lab") || c.includes("result") || c.includes("observation")) {
      return { bg: "#ecfdf5", text: "#047857", border: "#a7f3d0" };
    }
    if (c.includes("medication") || c.includes("prescription")) {
      return { bg: "#fef3c7", text: "#b45309", border: "#fde68a" };
    }
    return { bg: "#f1f5f9", text: "#475569", border: "#e2e8f0" };
  };

  return (
    <div
      className="modal-overlay"
      onClick={onClose}
      style={{
        zIndex: 1000,
        backgroundColor: "rgba(15, 23, 42, 0.5)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1.5rem",
      }}
    >
      <div
        className="modal-container"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "920px",
          width: "100%",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: "12px",
          backgroundColor: "#ffffff",
          boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.05)",
          border: "1px solid #e2e8f0",
          overflow: "hidden",
        }}
      >
        {/* HEADER */}
        <div
          style={{
            padding: "1.25rem 1.5rem",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700, color: "#0f172a" }}>
              Onboard Clinic
            </h3>
            <p style={{ margin: "2px 0 0 0", fontSize: "0.82rem", color: "#64748b" }}>
              Provide template JSON from a clinic to map its fields to the canonical schema.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              cursor: "pointer",
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              padding: "4px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.15s ease",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "#0f172a";
              e.currentTarget.style.background = "#f1f5f9";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "#94a3b8";
              e.currentTarget.style.background = "transparent";
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* BODY */}
        <div style={{ padding: "1.25rem 1.5rem", overflowY: "auto", display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* TOP CONTROLS */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <label style={{ fontSize: "0.82rem", fontWeight: 600, color: "#334155" }}>Clinic Identifier:</label>
              <input
                type="text"
                className="input"
                value={clinicKey}
                onChange={(e) => setClinicKey(e.target.value.toUpperCase())}
                placeholder="e.g. METROPOLIS_CARE"
                style={{
                  width: "220px",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                  textTransform: "uppercase",
                  fontSize: "0.82rem",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "0.4rem" }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setRawJson(DEFAULT_SAMPLE_JSON);
                  setClinicKey("METROPOLIS_CARE");
                  setAdapterConfig(null);
                  setFieldMappings(null);
                }}
                style={{ fontSize: "0.78rem" }}
              >
                Reset Template
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setRawJson("");
                  setAdapterConfig(null);
                  setFieldMappings(null);
                }}
                style={{ fontSize: "0.78rem" }}
              >
                Clear
              </button>
            </div>
          </div>

          {/* TEMPLATE JSON TEXTAREA */}
          <div>
            <textarea
              className="input"
              rows={6}
              value={rawJson}
              onChange={(e) => setRawJson(e.target.value)}
              placeholder="Paste raw clinic specimen/template JSON here..."
              style={{
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: "0.8rem",
                lineHeight: 1.45,
                width: "100%",
                background: "#f8fafc",
                borderColor: "#e2e8f0",
                borderRadius: "8px",
                padding: "0.75rem",
              }}
            />
          </div>

          {/* ONBOARD ACTION BUTTON */}
          <div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleOnboard}
              disabled={loading || !rawJson.trim()}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.45rem",
                padding: "0.55rem 1.4rem",
                fontWeight: 600,
                fontSize: "0.85rem",
                borderRadius: "6px",
              }}
            >
              {loading && <RefreshCw size={14} className="spin" />}
              <span>Map Clinic</span>
            </button>
          </div>

          {/* ALERTS */}
          {errorMsg && (
            <div
              style={{
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                background: "#fef2f2",
                color: "#991b1b",
                border: "1px solid #fecaca",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.82rem",
              }}
            >
              <AlertCircle size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div
              style={{
                padding: "0.75rem 1rem",
                borderRadius: "8px",
                background: "#f0fdf4",
                color: "#166534",
                border: "1px solid #bbf7d0",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: "0.82rem",
              }}
            >
              <CheckCircle2 size={16} />
              <span>{successMsg}</span>
            </div>
          )}

          {/* MAPPED SCHEMA FIELD TABLE */}
          {adapterConfig && fieldMappings && (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem", marginTop: "0.5rem" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                  paddingBottom: "0.5rem",
                  borderBottom: "1px solid #e2e8f0",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                    <Layers size={16} color="#2563eb" />
                    <span style={{ fontSize: "0.92rem", fontWeight: 700, color: "#0f172a" }}>
                      Clinic Field Mapping ({fieldMappings.length} Fields)
                    </span>
                  </div>
                  <p style={{ margin: "2px 0 0 0", fontSize: "0.78rem", color: "#64748b" }}>
                    Future incoming reports for <strong>{clinicKey}</strong> will automatically map to database columns according to these rules.
                  </p>
                </div>

                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleSaveAdapter}
                  disabled={saving}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.4rem",
                    padding: "0.45rem 1rem",
                    fontWeight: 600,
                    borderRadius: "6px",
                  }}
                >
                  {saving ? <RefreshCw size={13} className="spin" /> : <Check size={13} />}
                  <span>{saving ? "Saving..." : "Save Clinic Adapter"}</span>
                </button>
              </div>

              {/* TABLE */}
              <div
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: "8px",
                  overflow: "hidden",
                  boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
                }}
              >
                <div style={{ overflowX: "auto", maxHeight: "320px" }}>
                  <table className="table" style={{ width: "100%", fontSize: "0.8rem", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ background: "#f8fafc", textAlign: "left", borderBottom: "1px solid #e2e8f0" }}>
                        <th style={{ padding: "0.6rem 0.85rem", color: "#475569", fontWeight: 600, width: "140px" }}>
                          Category
                        </th>
                        <th style={{ padding: "0.6rem 0.85rem", color: "#475569", fontWeight: 600, width: "160px" }}>
                          Canonical DB Field
                        </th>
                        <th style={{ padding: "0.6rem 0.85rem", color: "#475569", fontWeight: 600 }}>
                          Clinic Template Path / Key
                        </th>
                        <th style={{ padding: "0.6rem 0.85rem", color: "#475569", fontWeight: 600 }}>
                          Database Description
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {fieldMappings.map((m, idx) => {
                        const style = getCategoryBadgeStyle(m.category);
                        return (
                          <tr key={idx} style={{ borderBottom: "1px solid #f1f5f9" }}>
                            <td style={{ padding: "0.6rem 0.85rem" }}>
                              <span
                                style={{
                                  fontSize: "0.72rem",
                                  padding: "2px 8px",
                                  borderRadius: "12px",
                                  fontWeight: 600,
                                  background: style.bg,
                                  color: style.text,
                                  border: `1px solid ${style.border}`,
                                  display: "inline-block",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {m.category || "General"}
                              </span>
                            </td>
                            <td style={{ padding: "0.6rem 0.85rem", fontWeight: 600, color: "#1e293b", fontFamily: "var(--font-mono)" }}>
                              {m.canonical_field}
                            </td>
                            <td style={{ padding: "0.6rem 0.85rem" }}>
                              <code
                                style={{
                                  fontSize: "0.78rem",
                                  padding: "3px 8px",
                                  borderRadius: "5px",
                                  background: "#f1f5f9",
                                  border: "1px solid #cbd5e1",
                                  color: "#0f172a",
                                  fontWeight: 600,
                                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                                }}
                              >
                                {m.clinic_path || "N/A"}
                              </code>
                            </td>
                            <td style={{ padding: "0.6rem 0.85rem", color: "#64748b", fontSize: "0.78rem" }}>
                              {m.description || "-"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* RAW CONFIG TOGGLE */}
              <div style={{ marginTop: "0.25rem" }}>
                <button
                  type="button"
                  onClick={() => setShowRawConfig(!showRawConfig)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#64748b",
                    fontSize: "0.78rem",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    padding: "0.25rem 0",
                  }}
                >
                  <Code size={13} />
                  <span>{showRawConfig ? "Hide" : "View"} Adapter JSON Config</span>
                </button>

                {showRawConfig && (
                  <pre
                    style={{
                      background: "#0f172a",
                      color: "#f8fafc",
                      borderRadius: "8px",
                      padding: "0.85rem",
                      fontSize: "0.75rem",
                      fontFamily: "var(--font-mono)",
                      overflowX: "auto",
                      maxHeight: "220px",
                      marginTop: "0.4rem",
                    }}
                  >
                    {JSON.stringify(adapterConfig, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
