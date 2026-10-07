# Design decisions and lessons

This file records why the project is built the way it is: the choices I made, what each one costs, and the bugs I hit along the way. The newest week comes first. Code links point to the file where each decision lives.

---

## Week 4: front end

### The browser logs in with Supabase, and talks to the API for everything else
- **Decision:** The React app uses `supabase-js` only for sign-in and sign-up. Every data request goes to my API with the user's access token, and the client refreshes that token automatically.
- **Why:** The browser never touches the database, so row level security can stay "deny everything" (see Week 2), and all the rules live in one tested place.
- **Detail:** The publishable key in the bundle is meant to be public. The secret key exists only on the server.

### CORS limited to known origins
- **Decision:** The API only accepts browser requests from origins listed in `CORS_ORIGINS` (the Vercel site and `localhost:5173`), and only the methods and headers the app uses.
- **Why:** Auth tokens already stop strangers reading data, and CORS adds a second layer so other websites can't use a logged-in user's browser to call the API. Tests check one allowed and one blocked origin.

### Charts: one measure per chart, faster at the top
- **Decision:** Pace and heart rate get **separate** charts rather than one chart with two y-axes. The pace axis is reversed so that faster is higher, and the caption says so. Each chart has a single series, so there's no legend; the title names it. Colours come from CSS tokens with their own light and dark values, not an automatic inversion.
- **Why:** Dual-axis charts make readers compare two unrelated scales, and the line crossings mean nothing. Runners read "up" as better, so a pace chart where up means slower reads backwards. Fastest and slowest splits are marked with text tags in the table, so identity never relies on colour alone.

### Explaining slow first loads
- **Decision:** If a request takes more than 4 s, the app says the server is waking up (Render's free tier sleeps). The run page, and with it Chart.js, loads only when it's opened, which keeps the first download smaller.

### Tested in a real browser before shipping
- **Decision:** Before pushing, I ran the API on Postgres with a local stand-in for Supabase Storage, started the app, and drove it with Playwright: upload, run page, duplicate upload, light and dark mode, and phone width. I checked the screenshots by eye. It found two things to fix: an inconsistent label on the partial split, and a missing favicon (a 404 in the console).

---

## Week 3: analytics

### One shape for every run
- **Decision:** Every run, GPX or CSV, is converted to a `RunSeries`: cumulative distance against cumulative **moving** time. Splits, best efforts and drift all work on that single shape.
- **Why:** Each metric is written and tested once, and treadmill laps and GPS tracks are handled the same way. Using moving time means a stop at traffic lights doesn't count against a split.
- **Trade-off:** A CSV lap only has its end points, so pace is assumed to be even within each lap. A best effort that falls inside a lap is an estimate.
- **Code:** [`backend/app/analytics/series.py`](../backend/app/analytics/series.py)

### Splits and split type
- **Decision:** Splits are every 1 km, or every 400 m when the run's surface is `track`. A leftover under 50 m is added to the last split instead of being shown as a 12 m "split". The split type compares the time for the second half of the distance with the first, with a ±1% band counting as even.
- **Why:** These match how runners already talk about splits. The ±1% band stops a 2-second difference being labelled a positive split.
- **Code:** [`backend/app/analytics/splits.py`](../backend/app/analytics/splits.py)
- **Checked on real data:** for a real run, the km splits matched Strava's own splits to within a few seconds per km. Small differences are expected, because Strava smooths GPS and detects pauses differently.

### Pace drift as the fatigue measure
- **Decision:** Fatigue is measured as the least-squares slope of split pace against distance (s/km per km), using full splits only, and needs at least 3 of them.
- **Why:** It's one number with an obvious meaning: "+5" means each km was about 5 s slower than the one before. It uses every split, not just the first and last, so one odd split has less effect.
- **Limits:** It doesn't know about hills, so a hilly second half looks like fatigue. Interval sessions break it, because pace swings by design. Correcting for elevation, or detecting intervals, are possible next steps.
- **Code:** [`backend/app/analytics/fatigue.py`](../backend/app/analytics/fatigue.py)

### Best efforts with a sliding window
- **Decision:** For each standard distance, a window starts at every sample. Its end time is interpolated, and the fastest window wins. Durations are rounded to 0.1 s before choosing, so ties go to the **earliest** effort.
- **Why:** The fastest 5 km is rarely exactly km 0–5. These efforts are what race prediction (Week 5) will use, because easy runs aren't max efforts but a fast stretch inside one can be.
- **Limits:** GPS noise can flatter very short efforts like 400 m, and CSV efforts are estimates (see above).
- **Code:** [`backend/app/analytics/best_efforts.py`](../backend/app/analytics/best_efforts.py)

### Training load as moving minutes, with ACWR
- **Decision:** A run's load is its moving time in minutes. Acute load is the sum over 7 days, chronic load is the weekly average over 28 days, and ACWR is acute divided by chronic. It's flagged above 1.5 (spike) or below 0.8 (low), and only once there are 21 days of history.
- **Why:** Time-based load is transparent and works for every run, with or without heart rate. ACWR turns two windows into one number that's easy to read.
- **Limits:** Load ignores intensity, so a 60-minute easy run counts the same as a 60-minute tempo run. ACWR's power to predict injury is debated in sports-science research, so the app presents it as a description of training changes, not an injury risk score. Dates are in UTC.
- **Code:** [`backend/app/analytics/load.py`](../backend/app/analytics/load.py)

### Analytics stored, and reproducible from the original file
- **Decision:** Analytics are computed at upload and stored in `splits` and `best_efforts` tables, plus a few columns on `runs`. `POST /runs/{id}/reprocess` downloads the original file from storage and recomputes everything.
- **Why:** Reads stay fast and simple. Keeping the raw file (a Week 2 decision) pays off here: runs uploaded before this week, or before any future change to the analytics, can be brought up to date without re-uploading.
- **Migration:** `0002` adds the tables and columns without touching existing rows, and enables RLS on the new tables. It was tested by upgrading a Postgres database that already held a pre-analytics run.

### Heart rate from GPX extensions
- **Decision:** Heart rate is read from Garmin-style `<gpxtpx:hr>` extensions, which Strava and Garmin exports include. Averages are time-weighted, so a long stretch at one heart rate counts more than a brief spike.

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
| Best efforts reported a random one of several equal efforts | Float noise in interpolated times made identical efforts differ in the 10th decimal place | Round durations to 0.1 s before picking the minimum, so ties go to the earliest; covered by a test | Checking the analytics on the synthetic run |
| Upload returned a bare **500** when storage was unreachable | httpx network errors weren't wrapped, so they skipped the storage error handler | Wrap them in `StorageError` → clear **503**, with no database row saved, plus a test | Smoke test with storage pointed at a dead port |
| An upload would block the whole server while it saved | Synchronous database and HTTP calls inside `async def` routes | Made the routes plain `def`, so FastAPI runs them in its thread pool | Reviewing my own diff |
| Login failed with `PGRST125` | `SUPABASE_URL` was pasted from Supabase's Data API page with `/rest/v1` on the end, so the login request went to the database REST API | Settings normalise the URL to the project base, with a test | Setting up locally |
| Python startup timed out (`Errno 60`) on macOS | The project was in an iCloud-synced Desktop folder, and offloaded files timed out when read | Moved the project to `~/Projects`; noted in the README | Setting up locally |

---

## Open questions
- **Treadmill runs:** a GPX export of an indoor run has no usable distance, because it has no GPS. For now, treadmill runs come in as CSV laps, and the GPX error message says so. Importing the original watch file (FIT or TCX), which records distance every second, is a stretch goal.
- **Intensity in training load:** add a 1–10 effort rating (session RPE) or heart-rate-based TRIMP so that load reflects how hard a run was, not just how long.
- **Fatigue on hilly routes:** correct pace for elevation (grade-adjusted pace) before measuring drift.
