"use client";

import React from "react";
import {
  Activity,
  FileText,
  FlaskConical,
  Pill,
  ClipboardList,
  AlertTriangle,
  Building2,
  ShieldAlert,
  Sliders,
  Play,
  RefreshCw,
} from "lucide-react";

export default function Sidebar({
  activeTab,
  onTabChange,
  isSearching,
  onClearSearch,
  documentsCount = 0,
  labTestsCount = 0,
  medicationsCount = 0,
  dischargesCount = 0,
  flaggedCount = 0,
  deadLettersCount = 0,
  pipelineStatus,
  isProcessing,
  onRunPipeline,
  onRefresh,
}) {
  const handleNavClick = (tab) => {
    onTabChange(tab);
    if (isSearching) {
      onClearSearch();
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-wrapper">
          <div className="brand-logo">V</div>
          <div className="brand-info">
            <span className="brand-title">Veritas Claims</span>
            <span className="brand-subtitle">Console</span>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-title">Operations</div>
        <button
          className={`sidebar-link ${activeTab === "overview" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("overview")}
        >
          <span className="sidebar-link-icon">
            <Activity size={18} />
          </span>
          <span>Dashboard</span>
        </button>
        <button
          className={`sidebar-link ${activeTab === "documents" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("documents")}
        >
          <span className="sidebar-link-icon">
            <FileText size={18} />
          </span>
          <span>Patient Reports</span>
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "#94a3b8",
            }}
          >
            {documentsCount}
          </span>
        </button>

        <div className="nav-section-title">Clinical Findings</div>
        <button
          className={`sidebar-link ${activeTab === "lab_tests" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("lab_tests")}
        >
          <span className="sidebar-link-icon">
            <FlaskConical size={18} />
          </span>
          <span>Lab Tests</span>
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "#94a3b8",
            }}
          >
            {labTestsCount}
          </span>
        </button>
        <button
          className={`sidebar-link ${activeTab === "medications" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("medications")}
        >
          <span className="sidebar-link-icon">
            <Pill size={18} />
          </span>
          <span>Prescriptions</span>
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "#94a3b8",
            }}
          >
            {medicationsCount}
          </span>
        </button>
        <button
          className={`sidebar-link ${activeTab === "discharges" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("discharges")}
        >
          <span className="sidebar-link-icon">
            <ClipboardList size={18} />
          </span>
          <span>Discharge Summaries</span>
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "#94a3b8",
            }}
          >
            {dischargesCount}
          </span>
        </button>
        <button
          className={`sidebar-link ${activeTab === "flagged" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("flagged")}
        >
          <span className="sidebar-link-icon">
            <AlertTriangle size={18} />
          </span>
          <span>Flagged Issues</span>
          <span
            style={{
              marginLeft: "auto",
              fontFamily: "var(--font-mono)",
              fontSize: "0.8rem",
              color: "#f87171",
            }}
          >
            {flaggedCount}
          </span>
        </button>

        <div className="nav-section-title">Monitoring</div>
        <button
          className={`sidebar-link ${activeTab === "clinics" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("clinics")}
        >
          <span className="sidebar-link-icon">
            <Building2 size={18} />
          </span>
          <span>Clinic Scorecard</span>
        </button>
        <button
          className={`sidebar-link ${activeTab === "dlq" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("dlq")}
        >
          <span className="sidebar-link-icon">
            <ShieldAlert size={18} />
          </span>
          <span>Dead-Letter Queue</span>
          {deadLettersCount > 0 && (
            <span
              style={{
                marginLeft: "auto",
                fontFamily: "var(--font-mono)",
                fontSize: "0.8rem",
                color: "#fbbf24",
              }}
            >
              {deadLettersCount}
            </span>
          )}
        </button>

        <div className="nav-section-title">System & Config</div>
        <button
          className={`sidebar-link ${activeTab === "configs" && !isSearching ? "active" : ""}`}
          onClick={() => handleNavClick("configs")}
        >
          <span className="sidebar-link-icon">
            <Sliders size={18} />
          </span>
          <span>Configurations</span>
        </button>
      </nav>

      <div className="sidebar-footer">
        <button
          onClick={onRunPipeline}
          disabled={isProcessing}
          className="btn btn-primary"
          style={{ width: "100%" }}
        >
          <Play size={15} />
          <span>{isProcessing ? "Running..." : "Run Pipeline"}</span>
        </button>
        <button
          onClick={onRefresh}
          className="btn btn-secondary"
          style={{
            width: "100%",
            background: "#1e293b",
            color: "#f8fafc",
            borderColor: "#334155",
          }}
        >
          <RefreshCw size={14} />
          <span>Refresh Data</span>
        </button>
      </div>
    </aside>
  );
}
