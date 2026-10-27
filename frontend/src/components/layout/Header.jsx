"use client";

import React from "react";
import { Search, X } from "lucide-react";

export default function Header({
  activeTab,
  isSearching,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
  onClearSearch,
}) {
  const getPageTitle = () => {
    if (isSearching) return "Search Results";
    switch (activeTab) {
      case "overview":
        return "Pipeline Operations Overview";
      case "documents":
        return "Patient Reports";
      case "lab_tests":
        return "Lab Tests";
      case "medications":
        return "Prescriptions & Medications";
      case "discharges":
        return "Discharge Summaries";
      case "flagged":
        return "Flagged Issues";
      case "clinics":
        return "Facility Quality Scorecard";
      case "dlq":
        return "Dead-Letter Queue";
      case "configs":
        return "Configurations";
      default:
        return "Operations Console";
    }
  };

  const getPageSubtitle = () => {
    if (isSearching) {
      return `Showing records matching "${searchQuery}"`;
    }
    switch (activeTab) {
      case "overview":
        return "Pipeline metrics, throughput statistics, and execution history";
      case "documents":
        return "Ingested patient report bundles and document submissions";
      case "lab_tests":
        return "Standardised laboratory test results with units and reference ranges";
      case "medications":
        return "Extracted prescription medications resolved to generic drug names";
      case "discharges":
        return "Standardised patient discharge summaries, diagnoses, and clinical notes";
      case "flagged":
        return "Clinical anomalies, extreme outliers, and out-of-range results";
      case "clinics":
        return "Per-facility ingestion statistics, outlier rates, and quality scorecards";
      case "dlq":
        return "Suppressed duplicate reports and rejected ingestion errors";
      case "configs":
        return "Manage clinic adapters, deduplication rules, and reference dictionaries";
      default:
        return "Clinical standardisation, range validation, and record lineage";
    }
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <h1 className="page-title">{getPageTitle()}</h1>
        <span className="page-subtitle">{getPageSubtitle()}</span>
      </div>

      <div className="topbar-right">
        <form onSubmit={onSearchSubmit} className="search-bar">
          <input
            type="text"
            className="search-input"
            placeholder="Search patient, claim #, test, medicine..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <button type="submit" className="btn btn-primary btn-sm">
            <Search size={14} />
            <span>Search</span>
          </button>
          {isSearching && (
            <button type="button" onClick={onClearSearch} className="btn btn-secondary btn-sm">
              <X size={14} />
              <span>Clear</span>
            </button>
          )}
        </form>
      </div>
    </header>
  );
}
