# Design decisions and lessons

This file records why the project is built the way it is: the choices I made, what each one costs, and the bugs I hit along the way. The newest week comes first. Code links point to the file where each decision lives.

---

## Week 2: storage, auth and deployment

### One Supabase project for the database, auth and file storage
- **Decision:** Supabase provides Postgres, user accounts and file storage. The API runs on Render.
- **Why:** It's one free project instead of three separate services. Render's free Postgres is deleted after 30 days; Supabase's isn't.
- **Trade-off:** The app is tied to Supabase's auth tokens and storage API. Both sit behind small modules (`auth.py`, `storage.py`), so swapping them out would touch two files.

### Row level security on, with no policies
- **Decision:** The first migration enables row level security (RLS) on `runs` and adds no policies.
- **Why:** Supabase automatically exposes every table in the `public` schema through a REST API. The key for that API is public, because it ships in the frontend. With RLS on and no policies, that route can't read or write anything. My API connects as the database owner, which bypasses RLS, and filters by user itself.
- **Trade-off:** All data access has to go through my API. If the frontend ever queried Supabase directly, I'd need per-user policies such as `user_id = auth.uid()`.
- **Code:** [`alembic/versions/0001_create_runs.py`](../backend/alembic/versions/0001_create_runs.py)

### The user id comes only from the verified token
- **Decision:** Every `/runs` route takes the user id from the verified Supabase token, never from the request.
  - Newer projects sign tokens with ES256, so the public key is fetched from Supabase's JWKS endpoint.
  - Older projects use a shared HS256 secret, and that's supported too.
  - The audience (`authenticated`) and the expiry are both checked.
- **Why:** If the client could send its own user id, anyone could read anyone's runs.
- **Detail:** Another user's run returns **404**, not 403, so you can't tell whether a run id exists.
- **Code:** [`backend/app/auth.py`](../backend/app/auth.py). Tests include a forged ES256 token and expired and wrong-audience tokens.

### Duplicate uploads detected by content hash
- **Decision:** Each upload is hashed with SHA-256, and there's a unique constraint on `(user_id, file_hash)`. Uploading the same file twice returns **409** with the existing run's id.
- **Why:** People re-upload the same export all the time, and duplicate runs would skew every trend.
- **Edge case:** Two identical uploads at the same moment both pass the first check, but the database constraint lets only one insert through. The loser gets a 409. The stored file is named after the hash, so both requests wrote the same object, and it's deliberately **not** deleted.
- **Code:** [`backend/app/routes/runs.py`](../backend/app/routes/runs.py)

### Raw files kept in private storage
- **Decision:** The original file is stored in a private bucket at `{user_id}/{sha256}.{ext}`. The database stores only the key. The service key that can write to storage stays on the server.
- **Why:** When the analytics change, every run can be re-processed from its original file. Keeping files out of the database keeps it small.
- **Code:** [`backend/app/storage.py`](../backend/app/storage.py)

### Tests that don't need the cloud
- **Decision:** The database session and the storage client are FastAPI dependencies. Tests swap in an in-memory SQLite database and a fake storage class.
- **Why:** The whole suite runs in about 2 seconds with no Supabase account, and CI needs no secrets.
- **Safety net:** CI also starts a real Postgres 16. It applies the migrations, runs `alembic check` to confirm they match the models, rolls them back, then runs the tests against Postgres. That catches anything that behaves differently between SQLite and Postgres.
- **Code:** [`backend/tests/conftest.py`](../backend/tests/conftest.py), [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

### Deployment
- **Decision:** `render.yaml` defines the service. Migrations run as part of the start command, and every push redeploys.
- **Why:** Render's free tier has no pre-deploy step. The migrations are idempotent, so running them on every start is safe.
- **Connection:** Render only has IPv4, and Supabase's direct database connection is IPv6-only, so the API uses Supabase's **Session pooler** connection string.
- **Trade-off:** The free tier sleeps after about 15 minutes idle, so the first request takes 30–60 s. That's fine for a portfolio project; real users would need an always-on instance.

---

## Week 1: parsing

### Distance from GPS points
- Distance between points uses the **haversine** formula. It's vectorised with numpy, so a 10,000-point run needs no Python loop.
- **Code:** [`backend/app/parsing/geo.py`](../backend/app/parsing/geo.py)

### Cleaning GPS data
- **GPS spikes:** a point that implies a speed over **12 m/s** (faster than any human sprinter) is dropped. Without this, one glitch can add hundreds of metres to a run.
- **Pauses:** a point counts as stopped when speed is below **0.5 m/s**, or when there's a gap of more than **60 s** (watch auto-pause). The summary reports **moving time** as well as **elapsed time**, and pace uses moving time, so traffic lights don't make a run look slower.
- **Why 60 s and not 10 s:** some watches use "smart recording" and only write a point every few seconds. A 10 s threshold would count real running as paused.
- **Code:** [`backend/app/parsing/gpx_parser.py`](../backend/app/parsing/gpx_parser.py)

### A sample run with known answers
- The tests use a synthetic GPX: 3 km at exactly 5:00/km, with a 60 s stop and one GPS spike planted in it. Because the correct answers are known (3000 m, 900 s moving, 960 s elapsed), the tests prove the numbers are right, not just that the code runs.
- **Code:** [`backend/tests/data/generate_samples.py`](../backend/tests/data/generate_samples.py)

### A lenient CSV parser with precise errors
- It accepts many column names (`distance_km`, `miles`, `Distance KM`, …) and time formats (`90`, `1:30`, `1:00:00`).
- A plain `distance` column is read as km when every value is 50 or less, and as metres otherwise.
- Errors name the row as it appears in a spreadsheet: "Couldn't read 'abc' in column 'distance_m' (row 3)".
- **Code:** [`backend/app/parsing/csv_parser.py`](../backend/app/parsing/csv_parser.py)

### Parsing kept separate from the web layer
- Parsers take bytes and return DataFrames, and know nothing about HTTP. They raise a `ParseError` with a user-facing message, and the route turns it into a 422. This keeps the core logic testable without a web server.

---

## Bugs and fixes

| Symptom | Cause | Fix | Found by |
|---|---|---|---|
| Upload returned a bare **500** when storage was unreachable | httpx network errors weren't wrapped, so they skipped the storage error handler | Wrap them in `StorageError` → clear **503**, with no database row saved, plus a test | Smoke test with storage pointed at a dead port |
| An upload would block the whole server while it saved | Synchronous database and HTTP calls inside `async def` routes | Made the routes plain `def`, so FastAPI runs them in its thread pool | Reviewing my own diff |
| Login failed with `PGRST125` | `SUPABASE_URL` was pasted from Supabase's Data API page with `/rest/v1` on the end, so the login request went to the database REST API | Settings normalise the URL to the project base, with a test | Setting up locally |
| Python startup timed out (`Errno 60`) on macOS | The project was in an iCloud-synced Desktop folder, and offloaded files timed out when read | Moved the project to `~/Projects`; noted in the README | Setting up locally |

---

## Open questions
- **Treadmill runs:** a GPX export of an indoor run has no usable distance, because it has no GPS. For now, treadmill runs come in as CSV laps. Importing the original watch file (FIT or TCX), which records distance every second, is a stretch goal.
- **Fatigue (Week 3):** how should pace drop-off be measured? A plain slope of pace against distance is easy to explain, but it's thrown off by hills and pauses. Options include using only moving splits, or correcting for elevation.
