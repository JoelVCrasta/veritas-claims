"use client";

import React, { useState, useEffect } from "react";
import Sidebar from "../components/layout/Sidebar";
import Header from "../components/layout/Header";

import OverviewView from "../components/views/OverviewView";
import ReportsView from "../components/views/ReportsView";
import LabTestsView from "../components/views/LabTestsView";
import MedicationsView from "../components/views/MedicationsView";
import DischargesView from "../components/views/DischargesView";
import FlaggedView from "../components/views/FlaggedView";
import ScorecardView from "../components/views/ScorecardView";
import DeadLetterView from "../components/views/DeadLetterView";
import SearchResultsView from "../components/views/SearchResultsView";
import ConfigsView from "../components/views/ConfigsView";

import RecordModal from "../components/modals/RecordModal";
import FullReportModal from "../components/modals/FullReportModal";

const API_BASE = "http://localhost:8000";

export default function App() {
  const [activeTab, setActiveTab] = useState("overview");

  // Ingested Data Collections
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [labTests, setLabTests] = useState([]);
  const [medications, setMedications] = useState([]);
  const [discharges, setDischarges] = useState([]);
  const [flagged, setFlagged] = useState([]);
  const [clinics, setClinics] = useState([]);
  const [deadLetters, setDeadLetters] = useState([]);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  // Modals
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [selectedBundle, setSelectedBundle] = useState(null);

  useEffect(() => {
    fetchAllData();
    // Live interval polling to stream new file events into the UI
    const interval = setInterval(() => {
      fetchAllData();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  async function fetchAllData() {
    try {
      const [
        statsRes,
        runsRes,
        docsRes,
        labsRes,
        medsRes,
        dischargesRes,
        flaggedRes,
        clinicsRes,
        dlqRes,
      ] = await Promise.all([
        fetch(`${API_BASE}/api/stats`).then((r) => r.json()).catch(() => null),
        fetch(`${API_BASE}/api/runs`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/documents`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/records?record_type=lab_test&limit=500`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/records?record_type=medication&limit=500`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/records?record_type=discharge_summary&limit=200`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/flagged?limit=500`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/clinics`).then((r) => r.json()).catch(() => []),
        fetch(`${API_BASE}/api/dead_letters`).then((r) => r.json()).catch(() => []),
      ]);

      if (statsRes) setStats(statsRes);
      if (runsRes) setRuns(runsRes);
      if (docsRes) setDocuments(docsRes);
      if (labsRes) setLabTests(labsRes);
      if (medsRes) setMedications(medsRes);
      if (dischargesRes) setDischarges(dischargesRes);
      if (flaggedRes) setFlagged(flaggedRes);
      if (clinicsRes) setClinics(clinicsRes);
      if (dlqRes) setDeadLetters(dlqRes);
    } catch (err) {
      console.error("Failed to load pipeline data:", err);
    }
  }

  async function handleUploadFile(file) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/stream/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (res.ok && data.status === "SUCCESS") {
        await fetchAllData();
      } else {
        alert("Streaming ingestion error: " + (data.detail || data.message || "Failed to process file"));
      }
    } catch (err) {
      alert("Failed to stream report file: " + err.message);
    }
  }

  async function handleSearch(e) {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) {
      setIsSearching(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(searchQuery)}&limit=200`);
      const data = await res.json();
      setSearchResults(data);
      setIsSearching(true);
    } catch (err) {
      alert("Search request failed: " + err.message);
    }
  }

  function clearSearch() {
    setSearchQuery("");
    setIsSearching(false);
    setSearchResults([]);
  }

  async function openReportModal(item) {
    const docId = item.document_id || item.id;
    if (!docId) return;

    try {
      const res = await fetch(`${API_BASE}/api/document/${encodeURIComponent(docId)}`);
      if (res.ok) {
        const bundle = await res.json();
        setSelectedBundle(bundle);
      } else {
        setSelectedBundle({
          document_id: docId,
          summary: item,
          lab_tests: item.record_type === "lab_test" ? [item] : [],
          medications: item.record_type === "medication" ? [item] : [],
          raw_json: null,
        });
      }
    } catch (err) {
      console.error("Failed to fetch full document:", err);
    }
  }

  return (
    <div className="app-layout">
      {/* SIDEBAR NAVIGATION */}
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        isSearching={isSearching}
        onClearSearch={clearSearch}
        documentsCount={documents.length}
        labTestsCount={labTests.length}
        medicationsCount={medications.length}
        dischargesCount={discharges.length}
        flaggedCount={flagged.length}
        deadLettersCount={deadLetters.length}
        onUploadFile={handleUploadFile}
        onRefresh={fetchAllData}
      />

      {/* MAIN CONTENT AREA */}
      <div className="main-content">
        <Header
          activeTab={activeTab}
          isSearching={isSearching}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSearchSubmit={handleSearch}
          onClearSearch={clearSearch}
        />

        <main className="page-container">
          {/* SEARCH RESULTS VIEW */}
          {isSearching && (
            <SearchResultsView
              searchResults={searchResults}
              onSelectRecord={setSelectedRecord}
            />
          )}

          {/* MAIN TABS */}
          {!isSearching && activeTab === "overview" && (
            <OverviewView stats={stats} runs={runs} />
          )}

          {!isSearching && activeTab === "documents" && (
            <ReportsView
              documents={documents}
              onSelectDocument={openReportModal}
            />
          )}

          {!isSearching && activeTab === "lab_tests" && (
            <LabTestsView
              labTests={labTests}
              onSelectRecord={setSelectedRecord}
            />
          )}

          {!isSearching && activeTab === "medications" && (
            <MedicationsView
              medications={medications}
              onSelectRecord={setSelectedRecord}
            />
          )}

          {!isSearching && activeTab === "discharges" && (
            <DischargesView
              discharges={discharges}
              onSelectRecord={setSelectedRecord}
            />
          )}

          {!isSearching && activeTab === "flagged" && (
            <FlaggedView
              flagged={flagged}
              onSelectRecord={setSelectedRecord}
            />
          )}

          {!isSearching && activeTab === "clinics" && (
            <ScorecardView clinics={clinics} />
          )}

          {!isSearching && activeTab === "dlq" && (
            <DeadLetterView deadLetters={deadLetters} />
          )}

          {!isSearching && activeTab === "configs" && (
            <ConfigsView />
          )}
        </main>
      </div>

      {/* SPECIFIC RECORD DETAILS MODAL */}
      <RecordModal
        record={selectedRecord}
        onClose={() => setSelectedRecord(null)}
        onOpenReport={(docId) => openReportModal({ document_id: docId })}
      />

      {/* FULL PATIENT REPORT MODAL */}
      <FullReportModal
        bundle={selectedBundle}
        onClose={() => setSelectedBundle(null)}
        onSelectRecord={setSelectedRecord}
      />
    </div>
  );
}
