# LUMA — 7 Core Scripts

## Setup Order

```bash
# 1. Python 3.11+ required
python --version

# 2. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 4. Set up credentials
cp .env.example .env
# Fill in .env with your AWS + Supabase credentials

# 5. Set up database (run migrations)
alembic upgrade head

# 6. Place test PDFs in the input folder
mkdir -p luma/data/incoming_pdfs
# Copy PDFs here

# 7. Run pipeline in order
python -m luma.pipeline.ocr_processor
python -m luma.pipeline.field_extractor
python -m luma.pipeline.normalize_and_store
python -m luma.ml.train_model

# 8. Start API server (dev)
uvicorn luma.api.predict:app --reload --port 8000

# 9. Test it
curl http://localhost:8000/health

# 10. Set nightly retrain cron
# crontab -e
# 0 2 * * * cd /path/to/project && .venv/bin/python -m luma.ml.retrain
```

## The 7 Scripts

| Script | File | Purpose |
|--------|------|---------|
| 1 | `luma/pipeline/ocr_processor.py` | PDF → raw text via AWS Textract |
| 2 | `luma/pipeline/field_extractor.py` | Raw text → structured fields |
| 3 | `luma/pipeline/normalize_and_store.py` | Clean data → PostgreSQL |
| 4 | `luma/ml/train_model.py` | Train AI models |
| 5 | `luma/api/predict.py` | FastAPI prediction server |
| 6 | `luma/api/correct.py` | Capture staff corrections |
| 7 | `luma/ml/retrain.py` | Nightly retrain loop (cron) |

## Services Needed
- **AWS** — S3 storage + Textract OCR (~$6-12/month per customer)
- **Supabase** — PostgreSQL database (free tier to start)
- **Railway** — Backend hosting (~$5-20/month)
- **Vercel** — Frontend hosting (free tier)
