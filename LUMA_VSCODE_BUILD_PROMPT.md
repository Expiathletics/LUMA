# LUMA VS CODE BUILD PROMPT
## Copy everything below this line and paste into Claude Code (VS Code)

---

You are a senior full-stack AI engineer helping me build LUMA — Learning Universal Machine Architecture.

LUMA is a multi-tenant supervised learning platform that ingests any industry's historical form data, trains field-prediction models from it, deploys a confidence-scored auto-fill interface on top of existing workflows, and continuously retrains from every correction. The system gets smarter the more it's used.

**First vertical: Funeral homes.**
Pain: families fill out 15-30 forms per case. Funeral homes have years of completed records = training data already exists.

**The AI Factory Loop (runs continuously):**
1. DATA IN → gather, clean, normalize, integrate
2. LEARN → supervised learning builds algorithm
3. BUILD → software created from algorithm
4. EXPERIMENT → shadow mode, measure accuracy
5. PRODUCT → live deployment
6. RESTART → new data flows in, loop repeats, system improves

---

## TECH STACK

- Frontend: Next.js (React) + TypeScript
- Backend: FastAPI (Python)
- Database: PostgreSQL via Supabase
- ML Structured Fields: XGBoost (Gradient Boosted Trees)
- ML Text Fields: Fine-tuned Llama 3 (local inference)
- OCR: AWS Textract
- File Storage: AWS S3
- Hosting MVP: Vercel (frontend) + Railway (backend)
- Auth: Supabase Auth

---

## PHASE 0 — SCHEMA DESIGN
**Goal:** Define the data skeleton for funeral home vertical

Build `funeral_home_schema.json` containing:
- Every form type: death_certificate, burial_permit, ssa_notification, va_benefits, insurance_assignment, cemetery_authorization, obituary, service_preferences, disposition_authorization
- Every field per form: field_name, data_type, validation_rule, required (true/false)
- State variations: flag fields that differ by state (e.g. California vs Texas death cert format)
- Seed fields (what staff enters first): deceased_name, dob, dod, next_of_kin_name, relationship
- Predicted fields (everything LUMA fills): all remaining 20-30 fields per case

Output: `/luma/schema/funeral_home_schema.json`

---

## PHASE 1 — DATA INGESTION PIPELINE
**Goal:** Take their historical paper/PDF files and turn them into structured training data

### Step 1 — Document Intake
```python
# Accept scanned PDFs, digital exports (CSV/Excel/JSON), CRM exports
# Store raw files in S3
def upload_document(file, customer_id):
    s3.put_object(
        Bucket="luma-raw",
        Key=f"{customer_id}/{doc_id}.pdf",
        Body=file
    )
    return doc_id
```

### Step 2 — OCR (AWS Textract)
```python
def extract_text(doc_id, customer_id):
    response = textract.analyze_document(
        Document={'S3Object': {'Bucket': 'luma-raw', 'Key': f'{customer_id}/{doc_id}.pdf'}},
        FeatureTypes=['FORMS', 'TABLES']
    )
    # Returns: raw text + key-value pairs + bounding boxes
    return parse_textract_response(response)
```

### Step 3 — Field Extraction via Named Entity Recognition (NER)
```python
import spacy
nlp = spacy.load("en_core_web_lg")

def extract_fields(raw_text):
    doc = nlp(raw_text)
    fields = {}
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            fields["deceased_name"] = ent.text
        elif ent.label_ == "DATE":
            fields["date_of_birth"] = ent.text
        # Map all entity types to schema fields
    return fields
```

### Step 4 — Normalization
```python
def normalize_fields(raw_fields):
    normalized = {}
    # Dates: "March 15" / "3-15-42" / "03/15/1942" → "1942-03-15"
    normalized["dob"] = parse_date(raw_fields.get("date_of_birth"))
    # Names: "JOHN SMITH" / "Smith, John" → "John Smith"
    normalized["deceased_name"] = normalize_name(raw_fields.get("deceased_name"))
    # SSN: "123456789" / "123-45-6789" → "XXX-XX-6789" (masked)
    normalized["ssn_last4"] = extract_last4(raw_fields.get("ssn"))
    return normalized
```

### Step 5 — Store in PostgreSQL
```sql
CREATE TABLE cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,
    fields JSONB NOT NULL,
    raw_doc_id TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    corrected_at TIMESTAMP,
    correction_fields JSONB
);
```

```python
def store_case(customer_id, normalized_fields, raw_doc_id):
    db.execute("""
        INSERT INTO cases (customer_id, fields, raw_doc_id)
        VALUES (%s, %s, %s)
    """, [customer_id, json.dumps(normalized_fields), raw_doc_id])
```

**Output:** Every historical case is now a structured JSON record. 500 cases = 500 training records.

---

## PHASE 2 — ML MODEL TRAINING
**Goal:** Build the brain that predicts field values from partial input

### Step 1 — Prepare Training Data
```python
def prepare_training_data(customer_id):
    cases = db.query("SELECT fields FROM cases WHERE customer_id = %s", [customer_id])

    X = []  # Input features (seed fields staff enters first)
    y = {}  # Target labels (one per predicted field)

    for case in cases:
        fields = case["fields"]
        # Seed fields (input)
        x_row = [
            fields.get("deceased_name", ""),
            fields.get("dob", ""),
            fields.get("dod", ""),
            fields.get("next_of_kin_name", ""),
            fields.get("relationship", "")
        ]
        X.append(x_row)
        # Predicted fields (targets) — one model per field
        for field_name in PREDICTED_FIELDS:
            if field_name not in y:
                y[field_name] = []
            y[field_name].append(fields.get(field_name, ""))

    return X, y
```

### Step 2 — Train XGBoost (Structured Fields)
```python
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder
import pickle

def train_field_models(X, y, customer_id):
    models = {}
    encoders = {}

    for field_name, labels in y.items():
        # Encode string labels to integers
        le = LabelEncoder()
        y_encoded = le.fit_transform(labels)
        encoders[field_name] = le

        # Train one model per field
        model = XGBClassifier(n_estimators=100, max_depth=4)
        model.fit(X, y_encoded)
        models[field_name] = model

        # Save model
        with open(f"models/{customer_id}/{field_name}.pkl", "wb") as f:
            pickle.dump({"model": model, "encoder": le}, f)

    return models, encoders
```

### Step 3 — Fine-tune Llama 3 (Free-text Fields)
```python
# For fields like: obituary_draft, special_instructions, service_notes
# Fine-tune on {input: seed_fields, output: text_field} pairs
# Runs locally on M5 Max via Ollama — $0 inference cost

def prepare_llm_training_data(cases):
    training_pairs = []
    for case in cases:
        training_pairs.append({
            "instruction": f"Write a brief obituary for {case['deceased_name']}, born {case['dob']}, passed {case['dod']}.",
            "output": case.get("obituary_draft", "")
        })
    return training_pairs

# Fine-tune using Ollama or HuggingFace transformers
# ollama create luma-funeral --modelfile Modelfile
```

### Step 4 — Confidence Scoring
```python
def predict_with_confidence(seed_fields, models, encoders, customer_id):
    predictions = {}

    for field_name, model in models.items():
        # Get probability distribution across all possible values
        proba = model.predict_proba([seed_fields])[0]
        max_confidence = max(proba)
        predicted_class = proba.argmax()
        predicted_value = encoders[field_name].inverse_transform([predicted_class])[0]

        predictions[field_name] = {
            "value": predicted_value,
            "confidence": round(max_confidence * 100),
            "status": "green" if max_confidence > 0.90 else ("yellow" if max_confidence > 0.70 else "red")
        }

    return predictions
```

### Step 5 — Automated Retraining Pipeline
```python
# Runs nightly via cron job
def retrain_pipeline(customer_id):
    # Pull all corrections made today
    corrections = db.query("""
        SELECT fields, correction_fields FROM cases
        WHERE customer_id = %s
        AND corrected_at > NOW() - INTERVAL '24 hours'
    """, [customer_id])

    if len(corrections) == 0:
        return  # Nothing new to learn

    # Add corrections to training data
    for correction in corrections:
        append_to_training_set(customer_id, correction)

    # Retrain all models
    X, y = prepare_training_data(customer_id)
    train_field_models(X, y, customer_id)

    # Log retraining event
    log_model_update(customer_id, len(corrections))
```

---

## PHASE 3 — APPLICATION LAYER
**Goal:** Build the 3 screens staff actually uses

### Screen 1 — Staff Intake Form (Next.js)
```typescript
// Staff enters 5 seed fields
// System immediately predicts remaining 25+ fields
// Color coded by confidence

export default function IntakeForm() {
  const [seedFields, setSeedFields] = useState({})
  const [predictions, setPredictions] = useState({})

  const handleSeedChange = async (field, value) => {
    setSeedFields(prev => ({...prev, [field]: value}))
    // Trigger prediction on every keystroke
    const preds = await fetch('/api/predict', {
      method: 'POST',
      body: JSON.stringify({...seedFields, [field]: value})
    }).then(r => r.json())
    setPredictions(preds)
  }

  return (
    <form>
      {/* Seed fields - staff enters these */}
      <SeedField label="Deceased Name" onChange={handleSeedChange} />
      <SeedField label="Date of Birth" onChange={handleSeedChange} />
      <SeedField label="Date of Death" onChange={handleSeedChange} />
      <SeedField label="Next of Kin" onChange={handleSeedChange} />
      <SeedField label="Relationship" onChange={handleSeedChange} />

      {/* Predicted fields - LUMA fills these */}
      {Object.entries(predictions).map(([field, pred]) => (
        <PredictedField
          key={field}
          label={field}
          value={pred.value}
          confidence={pred.confidence}
          status={pred.status}  // green / yellow / red
          onCorrect={(newValue) => handleCorrection(field, newValue)}
        />
      ))}
    </form>
  )
}
```

### Screen 2 — Document Generator
```python
# FastAPI endpoint — generates all forms as pre-filled PDFs
@app.post("/api/generate")
def generate_documents(case_id: str):
    case = db.get_case(case_id)
    documents = []

    for form_type in FUNERAL_HOME_FORMS:
        pdf = fill_pdf_template(
            template=f"templates/{form_type}.pdf",
            fields=case.fields
        )
        s3_url = upload_to_s3(pdf, f"{case_id}/{form_type}.pdf")
        documents.append({"form": form_type, "url": s3_url})

    return {"documents": documents}
```

### Screen 3 — Admin Dashboard
```typescript
// Shows accuracy metrics, cases processed, model performance
export default function Dashboard() {
  return (
    <div>
      <MetricCard title="Field Accuracy This Week" value="87%" trend="+3%" />
      <MetricCard title="Cases Processed" value="142" />
      <MetricCard title="Avg Time Saved Per Case" value="67 min" />
      <AccuracyByFieldChart />   {/* Which fields are most accurate */}
      <CorrectionPatternChart /> {/* Which fields get corrected most */}
    </div>
  )
}
```

### FastAPI Backend Endpoints
```python
@app.post("/api/predict")      # seed fields → predictions + confidence scores
@app.post("/api/correct")      # staff correction → adds to training queue
@app.post("/api/generate")     # generate PDF documents from completed case
@app.get("/api/accuracy")      # dashboard metrics
@app.post("/api/ingest")       # upload historical documents for training
@app.get("/api/cases")         # list all cases for a customer
```

---

## PHASE 4 — SHADOW MODE / EXPERIMENTATION
**Goal:** Run LUMA alongside existing process for 30-60 days before replacing it

```python
# Shadow mode: LUMA predicts but does NOT replace staff workflow
# Staff completes forms normally
# LUMA simultaneously predicts all fields
# System compares LUMA output vs actual completed form at end of each case

def shadow_mode_compare(case_id, luma_predictions, actual_fields):
    correct = 0
    total = 0

    for field, actual_value in actual_fields.items():
        if field in luma_predictions:
            total += 1
            if luma_predictions[field]["value"] == actual_value:
                correct += 1

    accuracy = correct / total if total > 0 else 0

    db.execute("""
        INSERT INTO shadow_results (case_id, accuracy, correct_count, total_fields, created_at)
        VALUES (%s, %s, %s, %s, NOW())
    """, [case_id, accuracy, correct, total])

    return accuracy
```

**Dashboard shows daily:**
- "LUMA was right on 87 of 100 fields today"
- "Week over week: +4% accuracy"
- "Ready to go live when accuracy hits 80%+"

**A/B split (optional):**
- 50% of new cases → LUMA-assisted intake
- 50% → standard intake
- Measure: time per case, error rate, staff satisfaction

---

## PHASE 5 — PRODUCTION DEPLOYMENT
**Goal:** LUMA becomes the primary intake tool

### Deployment Checklist
```
✅ Shadow mode accuracy > 80% sustained for 2+ weeks
✅ Staff trained on new intake form (30-min session)
✅ Data Processing Agreement signed
✅ All historical data migrated and models trained
✅ Rollback plan ready (can revert to paper in 10 min)
✅ Monitoring alerts set up (accuracy drop > 5% triggers alert)
```

### Infrastructure (MVP)
```
Frontend → Vercel (free tier → $20/mo at scale)
Backend  → Railway ($5-20/mo)
Database → Supabase ($25/mo)
Storage  → AWS S3 (~$5/mo at funeral home volume)
OCR      → AWS Textract (~$15/mo for 10,000 pages)
Total    → ~$70-80/mo per customer
```

### Multi-Tenant Architecture
```python
# Every customer has isolated data
# Shared model infrastructure
# Global model trained on anonymized aggregate data

class CustomerIsolation:
    # Customer A data NEVER touches Customer B model
    def get_model(self, customer_id, field_name):
        return load_model(f"models/{customer_id}/{field_name}.pkl")

    # Global model improves accuracy for all new customers
    def get_global_model(self, field_name):
        return load_model(f"models/global/{field_name}.pkl")
```

---

## BUILD SEQUENCE SUMMARY

| Phase | What | Est. Time |
|-------|------|-----------|
| 0 | Schema design — funeral home field map | 2 weeks |
| 1 | Data pipeline — OCR + extraction + normalization + storage | 3 weeks |
| 2 | ML models — XGBoost + Llama3 + confidence scoring + retraining | 3 weeks |
| 3 | Application — intake form + doc generator + dashboard + API | 4 weeks |
| 4 | Shadow mode — 30-60 days alongside existing process | 4-8 weeks |
| 5 | Production launch at Funeral Home #1 | 1 week |
| **Total** | **MVP live** | **~17 weeks** |

---

## YOUR TASK

Build LUMA Phase by Phase starting with Phase 0.

Begin by:
1. Creating the project structure
2. Building `funeral_home_schema.json` with all form types and field definitions
3. Setting up the Next.js + FastAPI project scaffold
4. Building the Supabase database schema (cases table + shadow_results table + corrections table)

Ask me before moving to the next phase. I will review each phase before you proceed.

---

*LUMA Build Prompt v1.0 | Joseph Gonzales × Neo ⚡*
*"The loop is the product. The data is the moat. The intelligence is the result."*
