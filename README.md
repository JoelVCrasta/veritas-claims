# Veritas Claims - Medical Data Standardisation

A pipeline that ingests raw JSON medical reports from various clinics, standardises them into a clean canonical schema, validates clinical values against medical reference ranges, and provides an operations dashboard for monitoring and record inspection.

---

## Architecture Summary

The system is structured into four sequential stages:

1. **Ingestion & Deduplication**
   - Scans incoming medical report JSON files.
   - Detects and suppresses duplicate reports using configurable criteria (Document ID, Content Hash, and Claim Number).
   - Drops corrupt or unparseable files into a dead-letter log without failing the batch.

2. **Standardisation Engine**
   - Normalises test names to canonical names using exact alias lookups and fuzzy string matching.
   - Converts raw strings and mixed text to clean numeric values.
   - Conerts differing units and scales values mathematically.
   - Standardises demographics.
   - Resolves brand-name medications to their generic equivalents.

3. **Clinical Validation**
   - Validates numeric test values against biological reference ranges.
   - Assigns a clinical status flag: `WITHIN_RANGE`, `ABOVE_RANGE`, `BELOW_RANGE`, `OUTLIER`, or `INVALID`.
   - Distinguishes out-of-range readings from extreme outliers.

4. **Storage & Operations**
   - Stores transformed records into an SQLite database.
   - Exposes REST endpoints via FastAPI (`http://localhost:8000`).
   - Uses a Next.js web dashboard (`http://localhost:3000`) for teams to monitor ingestion stats, flagged anomalies, inspect patient reports, and manage configurations.

---

## Setup Instructions

### 1. Prerequisites
- Python 3.14+
- Node 24.11+

### 2. Backend Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Pipeline
Execute ingestion, standardisation, and database storage over the sample files:
```bash
python -m src.pipeline --input sample_data --db data/veritas.db
```

### 4. Run Unit Tests
Run the standardisation and validation tests:
```bash
python -m unittest discover tests
```

### 5. Start the Application

**Start the Backend API:**
```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
```

**Start the Web Dashboard:**
```bash
cd frontend
npm install
npm run dev
```

---

## Key Design Decisions

1. **AI Clinic Onboarding & Zero-Code Schema Mapping**:
   - New clinics can be onboarded in seconds through the Clinic Adapters.
   - Provide any raw clinic JSON report and onboard it. The engine uses Groq Qwen model (`qwen3.8-27b`) to automatically infer document envelopes, demographic paths, observation lists, and canonical database mappings.
   - Operators can review the live canonical 78-column database preview and save the adapter profile directly to configurations without touching any code.

2. **Fast Rule-Based Processing**:
   - Uses dictionary alias lookups with fuzzy matching rather than heavy runtime LLM calls.
   - Processes 400+ clinical records in under 0.5 seconds.

3. **Graceful Multi-Value Handling**:
   - In real-world clinic JSONs, OCR engines occasionally combine entire test panels into comma-separated strings.
   - The parser safely extracts the primary metric and range to prevent pipeline failure, while preserving the complete raw string for compliance and auditing.

4. **Audit Trail Preservation**:
   - Alongside normalised values, original unedited strings (`test_name_original`, `result_text`, `range_text`, `unit_original`) and source metadata are stored with each record.

5. **Configurable Deduplication**:
   - Deduplication rules (Document ID, Content Hash, Claim Number) can be toggled on or off independently to match different operational policies.

---

## Known Limitations

1. **Multi-Parameter Panel Merging**:
   - When a clinic's extractor collapses a huge parameter panel may merge into a single row, the pipeline extracts the primary metric and retains the full raw text. Automatically splitting these into discrete records requires a some human confirmation to avoid misaligning values.
2. **Local Storage Backend**:
   - Currently uses SQLite for local execution. For high-concurrency production workloads the database layer should be swapped for a cloud solution like Cloud SQL.
3. **Fuzzy Match Threshold**:
   - Test names with substantial typographical corruption below the similarity threshold (85%) fall back to UNMAPPED status and are routed to the unmapped/review queue rather than risking an incorrect match.
