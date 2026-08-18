# SessionOps AI

AI assisted SME session scheduling for the Ops and Curriculum team of a B2C learning company.

Guiding principle: AI recommends, Ops decides, Calendar executes, the system observes and reacts.

## What it does

Ops selects a date range, syncs session and SME data, and generates a draft schedule. Every session gets an AI recommended SME with an explainable score. Ops reviews each session and can approve, edit, or reject the recommendation. Editing never approves anything by itself: a manually selected SME sits in a pending approval state until Ops explicitly approves it, at which point a real Google Calendar invite is created and sent. RSVP responses are picked up automatically, and a decline starts a replacement workflow with the same human approval step.

## Architecture

Three layers.

**Frontend.** Next.js (App Router) and TypeScript, Tailwind CSS, a small internal component library. Talks to the backend only through a typed REST client.

**Backend.** FastAPI (Python). Owns the scheduling engine, all workflow state transitions, and the integration adapters for Google Calendar, Google Sheets, and OpenAI. Each adapter has a mock implementation (deterministic, no external calls) and a live implementation behind the same interface, selected by an environment variable, so the engine code never changes when switching modes.

**Data.** SQLite locally, mirroring the schema intended for Supabase or Postgres in production. Source data (sessions, SMEs, performance, history, preferences, calendar busy blocks) is separate from operational state (assignments, RSVP status, activity log), so re-syncing source data never touches in-progress reviews.

Request flow: the frontend calls the backend API. The backend's matching engine reads source data from SQLite and produces a ranked, explainable recommendation per session, using the Calendar adapter to check availability and the OpenAI adapter for a small semantic scoring nudge only. Once Ops approves a session, the backend calls the Calendar adapter to create a real event and send an invite, then persists the result back to SQLite. A background poller checks Calendar for RSVP changes and updates state the same way a manual recheck would.

The matching engine is fully deterministic: hard constraints (expertise, availability, capacity, timezone, location) eliminate candidates first, then soft scoring (expertise fit, performance history, rolling four week fairness, preferences) ranks what is left, with a fixed tie break order. OpenAI is only ever consulted for a small, bounded semantic nudge and never decides eligibility.

## Assignment state machine

An AI recommendation starts in Pending Review. From there:

Approving it directly sends the Calendar invite and moves it to Approved, then Confirmed once the SME accepts.

Editing it to a different, constraint valid SME moves it to Edited, Pending Approval. No invite is sent yet. Ops must then explicitly click Approve and Send Invite to move it to Approved.

Editing it to a SME who only fails on daily capacity, with a required reason given, moves it to Exception, Pending Approval. Same rule: still needs an explicit approval before any invite goes out.

Editing it to a SME who fails any other hard constraint (inactive, missing expertise, wrong level, calendar conflict, offline location mismatch) is blocked outright. There is no override for these. Ops has to choose someone else.

Rejecting a recommendation asks the engine for the next best alternative and returns to Pending Review.

Once approved, an RSVP of accepted confirms the session, tentative surfaces a review flag without reassigning, and declined clears the SME and reruns matching for a replacement, up to three replacement attempts before the session becomes a critical unfilled exception.

## Tech stack

Frontend: Next.js, TypeScript, Tailwind CSS, Lucide icons.

Backend: FastAPI, SQLAlchemy, Google API client, OpenAI SDK.

Data: SQLite for development, schema compatible with Supabase and Postgres.

Auth: Google OAuth for Calendar and Sheets access, fixed demo credentials for the Ops login screen.

## Repository layout

`backend` holds the FastAPI app, matching engine, adapters, and models.

`frontend` holds the Next.js app.

`scripts` holds the deterministic synthetic data generator and validator.

`data` holds the generated synthetic dataset, standing in for the Google Sheets tabs.

## Running locally

Backend:

```
cd backend
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --port 8000
```

It seeds itself from the bundled synthetic dataset on first run. No external credentials are required in mock mode.

Frontend:

```
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open `http://localhost:3000`. Demo login: Ops ID `ops`, password `sessionops`.

## Mock mode versus live mode

Set `INTEGRATION_MODE=live` in `backend/.env` along with Google OAuth credentials, a Sheets spreadsheet ID, and an OpenAI key to switch from simulated adapters to the real APIs. The scheduling engine itself does not change between modes, only where the data and the calendar invites come from. A `DEMO_MODE` flag can redirect every real Calendar invite to a single test inbox, useful while the SME pool is still synthetic.

## Regenerating the synthetic dataset

```
python scripts/generate_synthetic_data.py
python scripts/validate_synthetic_data.py
```

Both are deterministic with a fixed seed, so reruns produce identical output. The generator intentionally builds in edge cases: no qualified SME, qualified but unavailable, an exact scoring tie, a fairness tradeoff, a timezone exclusion, a capacity limit, an offline location mismatch, and a scenario with no possible replacement.

## Status

The full mock mode workflow is built and verified end to end, including the session review drawer, the approval flow, exceptions, and insights. Live mode has been verified against a real Google account: real Sheets sync, real Calendar invites, and real RSVP detection all work. Not yet done: writing the draft back to a Sheets tab, and a committed automated test suite. Verification so far has been manual and scripted rather than a rerunnable test file.
