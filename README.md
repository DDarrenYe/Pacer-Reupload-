# Run Analytics

Upload a GPX or CSV run and get pace splits, fatigue trends and a predicted race time. It handles outdoor GPS runs and treadmill sessions with no GPS.

- **Live API:** https://run-analytics-api.onrender.com ([interactive docs](https://run-analytics-api.onrender.com/docs), [health check](https://run-analytics-api.onrender.com/health))
  - It runs on Render's free tier, which sleeps when idle, so the first request can take 30–60 s.
- **Status:** Week 2 of 6 is done. Runs are saved per user (Supabase Postgres + Storage, Supabase Auth) and the API is live. Week 3 (splits, fatigue, best efforts) is next. See the [project plan](docs/PROJECT_PLAN.md).

## API

| Method | Path | Auth | What it does |
|---|---|---|---|
| POST | `/uploads/parse` | – | Parse a GPX/CSV file and return a summary. Nothing is saved. |
| POST | `/runs` | ✔ | Upload a file and save it as a run (409 if you've uploaded it before) |
| GET | `/runs` | ✔ | Your runs, newest first |
| GET | `/runs/{id}` | ✔ | One of your runs |
| DELETE | `/runs/{id}` | ✔ | Delete a run and its stored file |
| GET | `/health` | – | Liveness check |

Authenticated routes need a Supabase access token: `Authorization: Bearer <token>`.

## Setup

### 1. Supabase
1. **Database URL:** click **Connect** at the top of the project, choose the **Session pooler** string, and put your database password in it.
2. **Keys:** go to **Project Settings → API Keys** and copy the project URL, the publishable key and the secret key.
3. **Storage:** create a **private** bucket called `raw-uploads`.
4. **Test user:** under **Authentication → Users → Add user**, create one with an email and password.

### 2. Run locally
Keep the project somewhere iCloud doesn't sync, such as `~/Projects`, not Desktop or Documents. iCloud can offload files, which makes Python time out while importing.
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then fill in the values from step 1
alembic upgrade head        # creates the tables in Supabase
uvicorn app.main:app --reload --reload-dir app
```
The server keeps that Terminal tab busy, so run other commands in a second tab (**Cmd + T**). Activate `.venv` in the new tab first.

Get a token with `python scripts/get_token.py`. Then open http://localhost:8000/docs, click **Authorize**, paste the token, and try `POST /runs`. Tokens last about an hour.

### 3. Deploy to Render
On Render, go to **New → Blueprint**, pick this repo and branch, and fill in `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and, for legacy projects only, `SUPABASE_JWT_SECRET`. `render.yaml` takes care of the rest, and migrations run automatically on every start.

## Tests and lint
```bash
cd backend
pytest -q                                   # SQLite in memory, fake storage
TEST_DATABASE_URL=postgresql://... pytest   # optional: run against Postgres
ruff check . && ruff format --check .
```
CI runs lint, applies the migrations to a real Postgres 16, checks they match the models, then runs the tests against Postgres.

## Supported files

- **GPX:** activity exports from a watch or app (the file needs timestamps). Paused points (speed under 0.5 m/s, or a gap of more than 60 s) count toward elapsed time but not moving time. GPS spikes that imply a speed over 12 m/s are dropped.
- **CSV:** one row per lap or interval of a single run. It needs a distance column (`distance_m`, `distance_km`, `miles`, or `distance`, which is read as km when every value is 50 or less) and a time column (`time`, `duration`, and so on, in seconds or `mm:ss` / `hh:mm:ss`). An `avg_hr` column is optional. CSVs have no date, so pass `started_at` when you upload. See `backend/tests/data/treadmill.csv`.

## Security notes
- User ids come only from the verified JWT. Both the newer asymmetric (ES256 via JWKS) and legacy HS256 Supabase tokens are supported.
- Row level security is enabled on `runs`, so Supabase's public REST API can't read it. Only this API can.
- Raw files go in a private bucket under `{user_id}/{sha256}`. The secret key never leaves the server.

## Layout
```
backend/app/parsing/   GPX + CSV parsers, haversine
backend/app/routes/    API routes (uploads, runs)
backend/app/models/    SQLAlchemy tables
backend/app/schemas/   Pydantic request/response models
backend/app/auth.py    Supabase JWT verification
backend/app/storage.py Supabase Storage client
backend/alembic/       database migrations
backend/scripts/       get_token.py dev helper
backend/tests/         pytest + sample files
render.yaml            Render deploy blueprint
docs/PROJECT_PLAN.md   six-week plan
```
