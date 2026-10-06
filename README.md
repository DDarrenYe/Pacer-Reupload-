# Run Analytics

Upload a GPX or CSV run and get pace splits, fatigue trends and a predicted race time. It handles outdoor GPS runs and treadmill sessions with no GPS.

**Status:** Week 1 of 6 is done: the GPX and CSV parsers and a parse-only upload endpoint. See the [project plan](docs/PROJECT_PLAN.md).

## Run the API locally

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Interactive docs are at http://localhost:8000/docs.

```bash
curl -F file=@tests/data/sample.gpx localhost:8000/uploads/parse
```

## Tests and lint

```bash
cd backend
pytest -q
ruff check . && ruff format --check .
```

## Supported files

- **GPX:** activity exports from a watch or app (the file needs timestamps). Paused points (speed under 0.5 m/s, or a gap of more than 60 s) count toward elapsed time but not moving time. GPS spikes that imply a speed over 12 m/s are dropped.
- **CSV:** one row per lap or interval of a single run. It needs a distance column (`distance_m`, `distance_km`, `miles`, or `distance`, which is read as km when every value is 50 or less) and a time column (`time`, `duration`, and so on, in seconds or `mm:ss` / `hh:mm:ss`). An `avg_hr` column is optional. See `backend/tests/data/treadmill.csv`.

## Layout

```
backend/app/parsing/   GPX + CSV parsers, haversine
backend/app/routes/    API routes
backend/app/schemas/   Pydantic response models
backend/tests/         pytest + sample files (tests/data/generate_samples.py rebuilds sample.gpx)
frontend/              React app (Week 4)
docs/PROJECT_PLAN.md   six-week plan
```
