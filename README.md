# SessionOps AI

AI-assisted SME session scheduling for a B2C learning company's Ops/Curriculum team.

> AI recommends. Ops decides. Calendar executes. The system observes and reacts.

## What's here

- **`backend/`** — FastAPI service: deterministic matching engine, scheduling
  workflow (draft → review → approve → invite → RSVP → reassignment →
  finalize), and mock-mode adapters for Google Calendar, Google Sheets, and
  OpenAI that are swappable for the real APIs without touching the engine.
- **`frontend/`** — Next.js + TypeScript + Tailwind app implementing the full
  Ops workflow: Overview, Schedule (Review List / Calendar), Session Drawer,
  Exceptions, Insights, SMEs, Settings.
- **`scripts/`** — deterministic synthetic dataset generator (seed=42) and
  validator, standing in for the Google Sheets ingestion tabs.
- **`data/generated/`** — the generated dataset (100 SMEs, 50 sessions, 500
  performance records, 400 assignment-history records, 100 preference
  records, ~538 calendar events) plus `synthetic_scenarios.json` describing
  13 engineered edge cases.

## Quick start (mock mode — no external credentials needed)

**Backend**
```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # or source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8000
```
On first run it auto-seeds the database from `data/generated/`. To use a
freshly regenerated dataset, call `POST /sync` (also wired to the "Sync
Data" button in the UI).

**Frontend**
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```
Open http://localhost:3000, sign in with Ops ID `ops` / password
`sessionops` (demo credentials, configurable via backend `.env`).

**First-time demo flow:** Sync Data → Generate Draft → open a session →
Approve → simulate an RSVP response from the drawer's demo control → watch
declines trigger the reassignment workflow.

## Regenerating the synthetic dataset

```bash
python scripts/generate_synthetic_data.py   # writes data/generated/*.json + *.csv
python scripts/validate_synthetic_data.py   # structural + edge-case checks
```
Both are deterministic (fixed seed) — reruns produce identical output.

## Mock vs. live mode

Set `INTEGRATION_MODE=live` in `backend/.env` plus the Google OAuth,
Sheets, and OpenAI credentials to switch from simulated adapters to the
real APIs. The scheduling engine (hard constraints, scoring, fairness,
tie-breaking) is identical in both modes — only the data-source adapters in
`backend/app/services/*_adapter.py` change. See `backend/.env.example`.

## Status

Phases 1–4 of the build plan (design system, full frontend on real data,
deterministic matching engine, all core interaction states) are complete
and verified end-to-end, including the primary demo loop: AI recommendation
→ approve → calendar invite → RSVP decline → automatic reassignment →
replacement invite → confirmation. Google Calendar/Sheets/OpenAI live
integrations are stubbed with clear extension points (Phases 8–10) but not
yet wired to real credentials.
