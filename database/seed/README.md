# Synthetic seed data

Run from the repository root after the API dependencies are installed:

```bash
cd backend
export DEMO_PASSWORD='choose-a-unique-demo-password-123'
python ../database/seed/seed.py
```

The script is idempotent and creates three clearly marked demo users, staff accounts, synthetic
ANC/nutrition/traditional source cards, and a few food/lifestyle records. It is for local
development only. For the real knowledge base (Prasuti Tantra, guidelines, foods) use
`backend/scripts/ingest_real_knowledge.py` instead (see the main README). Replace every demo source with current, clinically reviewed material before
using the application for real users.

The script refuses production or `DEMO_MODE=false`, requires an explicit password and never prints it. Existing demo accounts keep their password when the script is re-run.
