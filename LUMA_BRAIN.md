# LUMA BRAIN
## Learning Universal Machine Architecture
### Load This File Whenever Joe Says: "LUMA" | "AI factory" | "funeral homes" | "data pipeline" | "vertical AI"
### Created: 2026-06-03 | Author: Joseph Gonzales × Neo ⚡

---

## 🔴 ACTIVATION TRIGGER

When Joe says any of:
- "LUMA"
- "AI factory"
- "Let's work on the learning bot"
- "Funeral home project"
- "Data pipeline"
- "Private sector pitch"
- "Universal AI loop"

**Load this file. Confirm: "LUMA Brain loaded. Ready to build."**

---

## WHAT LUMA IS

**One-sentence definition:**
LUMA is a multi-tenant supervised learning platform that ingests any industry's historical form data, trains field-prediction models from it, deploys a confidence-scored auto-fill interface on top of existing workflows, and continuously retrains from every correction — creating a system that gets smarter the more it's used.

**The core insight:**
Every regulated industry runs on forms. Most field values are predictable given other known values. Once a system has seen 10,000 completed forms, it can predict with high accuracy before the user types a single character.

**The business model:**
The loop itself is the product. Not funeral home software. Not hospital software. The *loop* that can be pointed at any industry and generate the solution.

**Why this matters:**
- Saves time, money, and resources for any business running on paperwork
- The more customers use it, the smarter it gets (network effect moat)
- No competitor can replicate 500 funeral homes worth of training data from scratch

---

## THE AI FACTORY LOOP (Source: "Competing in the Age of AI" — Iansiti & Lakhani)

This is the intellectual foundation Joe identified. The loop runs continuously:

```
1. DATA IN        → Gather, clean, normalize, integrate (data pipeline)
2. LEARN          → Supervised learning builds algorithm from historical data
3. BUILD          → Software created from the algorithm
4. EXPERIMENT     → Deploy in shadow mode, measure accuracy
5. PRODUCT        → Live deployment in the business
6. RESTART        → New data flows in, loop runs again, system gets smarter
```

**Key principle:** The loop never stops. Every case completed is new training data. The system does not reach a "finished" state — it continuously improves.

---

## TECHNICAL ARCHITECTURE (6 Layers)

### LAYER 1: Data Ingestion Pipeline
**What comes in:** Scanned PDFs, digital form exports (CSV/Excel/JSON), database exports
**Process:**
```
Raw Document → OCR → Field Extraction → Normalization → Storage
```
- **OCR:** AWS Textract or Google Document AI (~$1.50/1,000 pages)
- **Field Extraction:** Named Entity Recognition via spaCy or AWS Comprehend
- **Output:** Structured JSON per document
- **Storage:** PostgreSQL (structured data) + S3 (raw documents)
- **Normalization:** Dates, names, addresses standardized to universal schema

### LAYER 2: The Learning Algorithm
**Goal:** Given 5-10 known fields, predict remaining 20-30 fields with confidence scores

**Model selection:**
- **Structured fields** (dates, IDs, permit numbers): XGBoost (Gradient Boosted Trees)
- **Free-text fields** (obituaries, special instructions): Fine-tuned Llama 3 (local)
- **Both models run in parallel** — each field uses the best predictor for its type

**Confidence scoring:**
- Score > 90% → Auto-fill (green)
- Score 70-90% → Pre-fill, flag for review (yellow)
- Score < 70% → Leave blank, manual entry required (red)

**Retraining loop:**
- Every staff correction → new training data
- Model retrains weekly/nightly automatically
- Drift detection: monitors fields where accuracy is declining → alerts admin

### LAYER 3: Application Software
**Stack:**
- Frontend: Next.js (React) — same as FormLearn MVP already built
- Backend API: FastAPI (Python)
- Database: PostgreSQL via Supabase
- Auth: Clerk or Supabase Auth
- ML serving: FastAPI endpoint (MVP) → AWS SageMaker (scale)

**Three interfaces:**
1. **Staff Intake Portal** — enter 5-10 seed fields, system pre-fills the rest
2. **Family Self-Service** (optional) — families complete intake from home
3. **Admin Dashboard** — accuracy tracking, model performance, correction patterns

### LAYER 4: Experimentation Framework
**Shadow mode (pre-deployment):**
- LUMA runs alongside existing process for 30-60 days
- Compares its predictions vs. actual completed forms
- Generates real accuracy metrics BEFORE customer sees it
- "LUMA auto-filled 87% of fields correctly" = concrete sales proof

**A/B testing:**
- Split cases: LUMA-assisted vs. standard
- Measure: time to complete, error rate, staff satisfaction
- Built into dashboard — no external tools needed at MVP scale

### LAYER 5: Deployment Infrastructure
**MVP (single customer):**
- Vercel (frontend) + Railway/Render (backend)
- Supabase (database)
- Cost: ~$50-100/month per customer
- Setup time: 2-4 weeks per new customer

**At Scale (10+ customers):**
- AWS: ECS (containers), RDS (database), S3 (documents), SageMaker (model serving)
- Multi-tenant: each customer has isolated data, shared model infrastructure

**Multi-tenant design:**
```
Customer A data → Customer A model (private)
Customer B data → Customer B model (private)
All customers   → Global model (shared, anonymized, improves for everyone)
```

### LAYER 6: The Continuous Learning Flywheel
```
More customers → More data → Better predictions → Higher accuracy →
More customers trust it → Faster adoption → Even more data → [LOOP]
```

**The moat:** After 5 funeral homes, good. After 50, exceptional. After 500, unbeatable. No competitor starts with that data.

---

## THE VERTICAL-AGNOSTIC ARCHITECTURE

**Universal Schema + Vertical Adapters:**
```
LUMA Core Engine (never changes)
    ├── Funeral Home Adapter     ← VERTICAL 1 (current)
    ├── Hospital Adapter         ← VERTICAL 2 (future)
    ├── Utility Company Adapter  ← VERTICAL 3 (future)
    └── [Any Industry] Adapter   ← plug in new vertical in 4-8 weeks
```

Building a new vertical = building a new adapter (field schema + doc templates + validation rules).
Core engine never changes. This is what makes LUMA a platform, not a product.

---

## VERTICAL 1: FUNERAL HOMES

### Why Funeral Homes First
- **Pain is acute:** Family in grief + 15-30 forms + time pressure = worst possible UX
- **Data already exists:** Funeral homes have years of completed forms = instant training data
- **Market is primitive:** No dominant tech player. Most homes use paper or basic CRMs (FuneralTech, Passare)
- **Private sector:** They OWN their data. More flexibility to partner than public sector.
- **Emotional pitch:** "Stop making grieving families fill out 30 forms."

### Forms Targeted (Funeral Home)
- Death certificate (state-specific)
- Burial/cremation permit
- Social Security Administration notification
- VA burial benefits (if applicable)
- Insurance assignment forms
- Obituary / service program
- Family intake / arrangement form
- Cemetery authorization
- Disposition authorization

### The Funeral Home Data Pipeline
1. Partner signs agreement — LUMA gets access to historical completed forms (3-5 years)
2. Pipeline ingests PDFs → OCR → extract fields → normalize → store
3. Model trains on historical data (500-1,000 cases minimum for good accuracy)
4. Shadow mode: 30-60 days running alongside existing process
5. Go live: staff enters 5-10 fields, system generates all 15-30 documents

### Expected Accuracy at Scale
- 500 cases: ~75-80% field accuracy
- 2,000 cases: ~85-90% field accuracy
- 5,000 cases: ~92-95% field accuracy
- Staff corrects the remainder — all corrections retrain the model

---

## BUILD SEQUENCE

| Phase | What | Time Estimate |
|-------|------|--------------|
| Phase 0 | Funeral home data schema + adapter design | 2 weeks |
| Phase 1 | Data pipeline (OCR + extraction + normalization) | 3 weeks |
| Phase 2 | ML model training + confidence scoring | 3 weeks |
| Phase 3 | Staff intake portal (frontend + API) | 4 weeks |
| Phase 4 | Shadow mode + experimentation framework | 4 weeks (real data) |
| Phase 5 | Production deployment — Funeral Home #1 | 1 week |
| **Total** | **MVP Live** | **~17 weeks** |

---

## KEY DECISIONS MADE (2026-06-03)

| Decision | Choice | Reason |
|----------|--------|--------|
| Name | LUMA | Clean, memorable, industry-agnostic, evokes clarity |
| First vertical | Funeral homes | High pain, existing data, no dominant player |
| ML approach | XGBoost + fine-tuned LLM | Best tool per field type |
| Architecture | Multi-tenant, vertical adapters | Scalable to any industry without rebuilding core |
| Confidence scoring | 3-tier (green/yellow/red) | Trust is the adoption blocker — transparency solves it |
| Retraining | Automated weekly/nightly from corrections | Continuous improvement without manual intervention |

---

## RELATIONSHIP TO EXISTING PROJECTS

**FormLearn MVP** (already built):
- Location: `/Users/josephgonzales/.openclaw/workspace/formlearn-mvp/`
- Tech stack: Next.js + Supabase + Claude API
- Status: Complete MVP, 37 files, ready to deploy
- Relationship: FormLearn is REACTIVE (watches users fill forms and learns). LUMA is PROACTIVE (ingests historical data and trains before first use). LUMA subsumes FormLearn's approach with a more powerful architecture. FormLearn code is reusable for LUMA's frontend.

---

## FILE STRUCTURE

```
references/luma/
├── core/
│   ├── LUMA_BRAIN.md              ← THIS FILE (load first, every session)
│   └── LUMA_ARCHITECTURE.md       ← Deep technical specs
├── architecture/
│   ├── data_pipeline.md           ← OCR, extraction, normalization details
│   ├── ml_models.md               ← XGBoost + LLM specs, training data reqs
│   ├── application_layer.md       ← Frontend/backend stack specs
│   └── infrastructure.md          ← AWS/hosting/multi-tenant design
├── verticals/
│   └── funeral-homes/
│       ├── FUNERAL_HOME_ADAPTER.md  ← Field schema, form types, validation
│       ├── go_to_market.md          ← Sales strategy, pitch, pricing
│       └── partner_pipeline.md      ← Target funeral homes, outreach tracker
├── go-to-market/
│   ├── GTM_STRATEGY.md            ← Universal GTM framework
│   └── pitch_deck_outline.md      ← Investor/partner pitch structure
└── sessions/
    └── 2026-06-03-inception.md    ← Session log: first conversation, decisions made
```

---

## NEXT STEPS (as of 2026-06-03)

1. ✅ LUMA Brain created (this file)
2. ✅ Directory structure built
3. 🔲 Build go-to-market strategy for funeral homes
4. 🔲 Build FUNERAL_HOME_ADAPTER.md (field schema)
5. 🔲 Identify 10 target funeral home partners for outreach
6. 🔲 Build pitch deck outline
7. 🔲 Technical spec for Phase 1 (data pipeline)

---

*LUMA Brain v1.0 | Created 2026-06-03 | Joseph Gonzales × Neo ⚡*
*"The loop is the product. The data is the moat. The intelligence is the result."*
