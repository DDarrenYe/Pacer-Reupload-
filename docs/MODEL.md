# Race-time prediction model

Pacer predicts 5k, 10k, half-marathon and marathon times with three methods and measures how accurate each one has been. Code: [`backend/app/analytics/predict.py`](../backend/app/analytics/predict.py). Tests: [`backend/tests/test_predict.py`](../backend/tests/test_predict.py).

## The problem: most runs aren't races
A model fitted to every run learns your *easy* pace. The method stands or falls on choosing data that reflects what you can actually do.

| Term | Definition | Why |
|---|---|---|
| **Effort** | A GPX best effort of **1 km or more** that covers **at least 75% of its run**, or a whole run marked as a **race** (any source) | Sprint speed doesn't follow the same law as longer distances. A fast km *inside* a 10k was run at 10k pace, not flat out. CSV efforts are interpolated within laps, so they aren't real measurements. |
| **Envelope** | Your fastest effort per distance over the **last 180 days** | Approximates what you can currently do |
| **Target** | A race, or an effort that **beats an earlier one** at that distance within 180 days | These are the efforts we predict and score. A first effort at a distance has nothing to beat and is often easy. |
| **Anchor** | The envelope point (from earlier days only) nearest in log-distance, at a **different** distance | Predicting a 5k from last month's 5k is trivial for every method; the test is crossing distances |

## Methods
1. **Riegel (1977):** T₂ = T₁ · (D₂ / D₁)^1.06, using a fixed exponent.
2. **Personal exponent:** least squares of log T on log D over your own envelope, giving T = e^a · D^b. Your *b* against 1.06 says whether you hold pace over distance better (b < 1.06) or worse (b > 1.06) than average. It needs efforts at least 1.8× apart in distance, and anything over 2× your longest effort is flagged as extrapolated.
3. **Pooled regression** (statsmodels OLS on anchor→target pairs from every runner):

   log(T₂/T₁) = β₁ · log(D₂/D₁) + β₂ · log(D₂/D₁) · log(weekly km + 1) [+ surface terms]

   - Riegel is the special case β₁ = 1.06, β₂ = 0. Each runner's effective exponent is β₁ + β₂ · log(weekly km + 1), so β₂ < 0 would mean higher-volume runners fade less over distance.
   - There's **no intercept**. An earlier version had one, and it learned "targets are about 3% faster than their anchor". That's true only *because* targets are chosen as new bests (a selection effect), and it made predictions on later data worse.

## Evaluation
- All anchor→target pairs are sorted by date. The **earliest 70% train** the pooled model, and the **latest 30% test all three methods** on the same pairs.
- Every prediction uses only runs from earlier days, so nothing leaks from the future.
- Metrics: **MAE** in seconds and **MAPE** in %, with the number of test pairs. Below 3 test pairs, the app reports "not enough data" instead of a number.
- `python scripts/evaluate_model.py` prints the current table from the live database.

## Results

### Synthetic check (tests and local seed data)
- When simulated runners genuinely differ in exponent and there's plenty of data (about 100 pairs), the personal exponent beats Riegel: about 0.8% vs 1.2–1.7% MAPE. The regression recovers a planted volume effect (β₂ < 0).
- With **2 runners and 6 test pairs**, Riegel won: 4.5% against 8.2% (personal) and 11.2% (pooled), and the regression's confidence intervals were very wide. This is the **bias–variance trade-off**: with little data, a fixed, sensible exponent beats one estimated from a handful of noisy points.

### Real data
Output of `scripts/evaluate_model.py` on the live database, 8 Oct 2026:

| Runners | Runs | Races | Hard efforts | Anchor→target pairs |
|---|---|---|---|---|
| 1 | 14 | 1 | 3 | 0 |

**Not enough data yet to score the methods.** A pair needs a hard effort at one distance followed by a later one at a clearly different distance, and the test set needs at least 3 pairs. So far the real data is one runner (me), and none of my efforts make a pair yet. Until there are more runners and races, the synthetic check above is the evidence, and the app shows "not enough data" rather than a made-up accuracy. I'll re-run this as testers upload runs.

## Limitations
- **Small n.** With a handful of runners, the pooled model is mostly noise. Its coefficients come with 95% CIs for exactly this reason.
- **Effort detection is a heuristic.** Without heart rate or perceived effort, an easy run that happens to be your fastest recent 10k still counts. Filtering by heart rate is a natural next step.
- **Marathon predictions** from 5k–10k efforts are long extrapolations, so the app flags them.
- **Envelope lag.** A best from 5 months ago can anchor a prediction even if fitness has since changed.
- **GPS noise** affects best efforts. Splits were checked against Strava, but individual efforts can be a few seconds out.

## Goals

The Goals page reuses the Riegel prediction from your nearest recent effort (the same as the Trends page) and adds:

| Rule | Value |
|---|---|
| Trajectory | Prediction at the end of each of the last 12 weeks; least-squares slope; needs 4 weeks with a prediction, otherwise assumes today's fitness holds |
| Projection clamp | At most 1% faster or 0.5% slower per week |
| "Within reach" | Needs ≤ 0.5% improvement per week |
| Weekly distance guide | 5k 15 km, 10k 20 km, half 30 km, marathon 45 km (4-week average; within 5% counts as met) |
| Long run guide | 5k 8 km, 10k 12 km, half 16 km, marathon 28 km |
| Goal-pace practice | At least 3 km within 2 s/km of goal pace in one run in the last 4 weeks (full splits, or the whole run for manual entries) |
| Load warning | ACWR above 1.5 |
| Taper | From 14 days out: cut distance by 30–50% |
| Checkpoints | Equivalent 5k/10k times from your own exponent (if between 1.0 and 1.2), otherwise 1.06 |

These are common rules of thumb for recreational runners, not a coaching plan, and the app says so.

## Next steps
- Bootstrap the pooled model with a public dataset of race results, so it has enough data before Pacer has many users.
- Use heart rate to decide which efforts were hard.
- Weight recent efforts more than old ones, instead of a hard 180-day window.
