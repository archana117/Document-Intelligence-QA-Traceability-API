Document Intelligence QA Traceability API 

This project implements a modular, production-ready document ingestion and parsing pipeline in Python. It parses structured engineering or regulatory manuals (specifically the CardioTrack CT-200 upper-arm blood pressure monitor PDF manuals) into a logical section hierarchy tree. It also exposes a FastAPI backend that persists the extracted tree, manages document versions, pins selections, generates QA test-case ideas via LLM integration (Gemini), and detects when existing test cases become stale as manuals change.

## Folder Structure

```
project/
├── app/
│   ├── config.py         # App directories, parameters, and API configuration
│   ├── database.py       # SQLite connection and SQLAlchemy session pool
│   ├── repository.py     # Database CRUD (versioning, matching, diffing, selections, staleness)
│   ├── routes.py         # FastAPI endpoints for ingestion, browsing, selections, diffs, and LLM
│   └── main.py           # Application entrypoint
├── models/
│   ├── db_models.py      # SQLAlchemy schemas (Document, Node, Selection, Generation)
│   └── schemas.py        # Pydantic serialization models for requests/responses
├── parser/
│   ├── pdf_loader.py       # PyMuPDF engine extracting text spans, positions, fonts, and sizes
│   ├── layout_detector.py  # Spatial heuristics classifying blocks (Title, Heading, Table, List, Paragraph)
│   ├── reading_order.py    # Geometric re-sorting sorting vertical/horizontal block flows
│   ├── heading_detector.py # Heading level resolution, parsing section numbers (1.1, 2.1.1.1)
│   ├── hierarchy_builder.py# Document skeleton assembly establishing parent-child-sibling relationships
│   ├── paragraph_assigner.py # Contextual linking of paragraphs, lists, and tables to headings
│   ├── table_extractor.py  # pdfplumber table extraction exporting tabular grids as JSON structures
│   ├── image_extractor.py  # Image locator and proximity caption association
│   ├── hashing.py          # SHA256 content hashing for change detection
│   └── validator.py        # Pipeline validator detecting broken structures, gaps, and orphans
├── tests/
│   ├── conftest.py       # In-memory SQLite session and TestClient fixtures
│   ├── test_parser.py    # Unit tests for heading levels, tree builds, list detections, validator
│   ├── test_api.py       # Integration tests for Ingest, Browse, Diff, Selections, Staleness
├── requirements.txt      # Python dependencies
├── ARCHITECTURE.md       # Technical architecture explanation
└── README.md             # This document
```

---

## Installation & Setup

1. **Prerequisites**: Python 3.10+ (tested on Python 3.13)
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Variables**:
   To enable live LLM generation with Gemini, set the environment variable:
   * **Windows (PowerShell)**:
     ```powershell
     $env:GEMINI_API_KEY="your-gemini-api-key-here"
     ```
   * **Windows (CMD)**:
     ```cmd
     set GEMINI_API_KEY=your-gemini-api-key-here
     ```
   If `GEMINI_API_KEY` is not set, the API runs in **Offline Mock Mode**, returning realistic, content-aware test cases dynamically generated for the selected sections.

---

## Running the API Server

Start the local server using Uvicorn:
```bash
python app/main.py
```
The server will start at `http://127.0.0.1:8000`. 
Interactive documentation is available at:
* Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## E2E Ingestion and Staleness Flow

You can trigger the entire flow (v1 ingestion -> selection -> QA generation -> v2 ingestion -> staleness detection) using curl or python.

### Step 1: Ingest Version 1 of the manual
```bash
curl -X POST "http://127.0.0.1:8000/api/documents/ingest?filepath=c:/Users/vyshn/Downloads/AffineSurge/ct200_manual.pdf&version=1&document_name=CardioTrack-CT-200"
```
Response:
```json
{
  "status": "success",
  "document_id": 1,
  "document_name": "CardioTrack-CT-200",
  "version": 1,
  "total_nodes": 28,
  "orphans_detected": 0,
  "validation_report": {
    "is_valid": true,
    "errors": []
  }
}
```

### Step 2: Create a Selection pinned to Version 1
Submit a POST to create a named selection for the Battery Life section (`sec_2_1_1_1`):
```bash
curl -X POST "http://127.0.0.1:8000/api/selections" \
     -H "Content-Type: application/json" \
     -d '{"name": "CardioTrack-CT-200", "document_id": 1, "version": 1, "node_ids": ["sec_2_1_1_1"]}'
```
Response:
```json
{
  "id": "e2a22f77-9fc5-4235-866b-a25e79ff5780",
  "name": "CardioTrack-CT-200",
  "document_id": 1,
  "version": 1,
  "node_ids": ["sec_2_1_1_1"],
  "created_at": "2026-07-17T12:00:00"
}
```

### Step 3: Generate QA Test Cases
```bash
curl -X POST "http://127.0.0.1:8000/api/selections/e2a22f77-9fc5-4235-866b-a25e79ff5780/generate-qa"
```
Response returns 2 test cases verifying the original 300 cycles rating and 15% low battery icon trigger.

### Step 4: Ingest Version 2 of the manual
Version 2 is ingested. This version changes the estimated battery cycles to 250, and shifts the low battery capacity warning from 15% to 10%.
```bash
curl -X POST "http://127.0.0.1:8000/api/documents/ingest?filepath=c:/Users/vyshn/Downloads/AffineSurge/ct200_manual_v2.pdf&version=2&document_name=CardioTrack-CT-200"
```

### Step 5: Check Selection Staleness
```bash
curl -X GET "http://127.0.0.1:8000/api/selections/e2a22f77-9fc5-4235-866b-a25e79ff5780/qa-status"
```
Response:
```json
{
  "selection_id": "e2a22f77-9fc5-4235-866b-a25e79ff5780",
  "selection_name": "CardioTrack-CT-200",
  "document_version": 1,
  "is_stale": true,
  "generations": [
    {
      "node_id": "sec_2_1_1_1",
      "node_heading": "2.1.1.1 Battery Life Under Typical Use",
      "content_hash": "...",
      "is_stale": true,
      "test_cases": [...]
    }
  ]
}
```
The selection QA is correctly flagged as `is_stale: true` because the text inside section `2.1.1.1` was modified in version 2!

### Step 6: Diff Section Node across Versions
To see exactly what changed in the manual for the battery section:
```bash
curl -X GET "http://127.0.0.1:8000/api/nodes/sec_2_1_1_1/diff?document_name=CardioTrack-CT-200&v1=1&v2=2"
```

---

## Testing

Execute all 10 unit and integration tests using pytest:
```bash
python -m pytest -v tests/
```
All tests should pass, showing output like:
`10 passed in X.XXs`
