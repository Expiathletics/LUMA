# LUMA — Learning Universal Machine Architecture
## Funeral Home Form Automation Platform
## Version 0.1.0 — Phase 0 + Phase 1 Complete

---

## WHAT THIS IS

LUMA ingests funeral home historical case documents, extracts all form fields automatically, 
and stores them as training data. Over time it learns to predict fields before staff types them.

**The AI Factory Loop:**
```
Upload Document → OCR → Extract Fields → Normalize → Store → Train Model → Predict → Repeat
```

---

## PROJECT STRUCTURE

```
LUMA/
├── backend/
│   ├── main.py              ← FastAPI entry point
│   ├── requirements.txt     ← Python dependencies
│   ├── pipeline/
│   │   ├── ingest.py        ← Step 1: Save uploaded file
│   │   ├── ocr.py           ← Step 2: Extract text from document
│   │   ├── extractor.py     ← Step 3: Identify field types
│   │   ├── normalizer.py    ← Step 4: Standardize values
│   │   ├── storage.py       ← Step 5: Save to database
│   │   └── pipeline.py      ← Orchestrates all 5 steps
│   └── api/
│       └── routes.py        ← REST API endpoints
├── frontend/
│   ├── package.json
│   └── app/
│       ├── layout.tsx
│       ├── globals.css
│       └── page.tsx         ← Main dashboard UI
├── database/
│   └── schema.sql           ← Supabase database schema
├── data/cases/              ← JSON case records (auto-created)
├── uploads/                 ← Uploaded documents (auto-created)
├── libs/
│   ├── unstructured/        ← PDF/doc extraction library
│   ├── langchain/           ← AI agent framework
│   └── docassemble/         ← Form automation engine
├── LUMA_BRAIN.md            ← Full architecture specification
├── LUMA_VSCODE_BUILD_PROMPT.md ← VS Code build prompt
└── .env.example             ← Environment variables template
```

---

## HOW TO RUN

### Backend (Python/FastAPI)

```bash
cd backend

# Install dependencies
pip install fastapi uvicorn python-multipart unstructured python-dotenv

# Optional: install spaCy for better NER
pip install spacy
python -m spacy download en_core_web_sm

# Start the API server
python main.py
# or
uvicorn main:app --reload --port 8000
```

API will be live at: http://localhost:8000
Interactive docs at: http://localhost:8000/docs

### Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Dashboard will be live at: http://localhost:3000

---

## API ENDPOINTS

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/ingest?customer_id=X | Upload document, run pipeline |
| GET | /api/cases | List all processed cases |
| GET | /api/cases/{id} | Get single case with all fields |
| GET | /api/stats | Dashboard statistics |
| GET | /api/health | Health check |

---

## WHAT'S BUILT (Phase 0 + 1)

✅ Project scaffold (backend + frontend + database)
✅ Data ingestion (accepts PDF, PNG, JPG, TIFF, CSV)
✅ OCR pipeline (text + key-value extraction via Unstructured)
✅ Field extraction (pattern matching + spaCy NER)
✅ Normalization (dates, names, phones, SSN, disposition)
✅ Storage (SQLite for MVP, schema ready for Supabase)
✅ Training data accumulation (every case = new training records)
✅ REST API (FastAPI with auto-docs)
✅ Dashboard UI (Next.js with drag-and-drop upload)

## WHAT'S NEXT (Phase 2+)

🔲 ML model training (XGBoost for structured field prediction)
🔲 Confidence scoring (green/yellow/red per field)
🔲 Intake form with auto-fill (staff enters 5 fields, LUMA fills 25)
🔲 PDF generation (auto-populated death certificates, permits, etc.)
🔲 Shadow mode (compare LUMA predictions vs actual)
🔲 Automated retraining (nightly, from corrections)
🔲 Multi-tenant (customer data isolation)

---

*LUMA v0.1.0 | Joseph Gonzales × Neo ⚡ | June 4, 2026*
