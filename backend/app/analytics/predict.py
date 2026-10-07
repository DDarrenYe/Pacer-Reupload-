"""Race-time prediction: Riegel, a personal exponent, and a pooled regression.

The hard part isn't the maths, it's the data: most runs aren't flat out. So:

- an **effort** is a best effort of 1 km or more inside a run, or a whole race;
- the **envelope** is a runner's fastest effort per distance over the last 180 days,
  i.e. what they've recently shown they can do;
- **targets** (what we predict and score) are races and new 180-day bests only,
  so easy-run efforts are never treated as someone's best.

Every prediction for a target uses only runs from earlier days: no peeking at the future.
See docs/MODEL.md for the reasoning and results.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

RIEGEL_EXPONENT = 1.06
MIN_EFFORT_M = 1000.0  # sprint efforts don't follow the same law
ENVELOPE_DAYS = 180
VOLUME_DAYS = 28
MIN_PAIRS_TO_FIT = 8
MIN_TEST_PAIRS = 3
TRAIN_FRACTION = 0.7
# Predicting more than this multiple of your longest recent effort is extrapolation.
EXTRAPOLATION_RATIO = 2.0
# A personal exponent needs efforts this far apart in distance (e.g. 5k and 10k).
MIN_DISTANCE_SPREAD = 1.8

TARGET_DISTANCES_M = {"5k": 5000.0, "10k": 10000.0, "Half marathon": 21097.5, "Marathon": 42195.0}


@dataclass(frozen=True)
class Effort:
    user_id: str
    run_id: str
    day: date
    distance_m: float
    time_s: float
    surface: str = "road"
    is_race: bool = False

    @property
    def distance_key(self) -> int:
        # Standard best-effort distances match exactly; races are grouped to the nearest 10 m.
        return int(round(self.distance_m / 10.0))


@dataclass(frozen=True)
class RunVolume:
    user_id: str
    day: date
    distance_m: float


# --- building blocks --------------------------------------------------------------


def riegel(anchor: Effort, distance_m: float, exponent: float = RIEGEL_EXPONENT) -> float:
    return anchor.time_s * (distance_m / anchor.distance_m) ** exponent


def envelope(efforts: list[Effort], before: date) -> list[Effort]:
    """Fastest effort per distance in the 180 days before `before` (that day excluded)."""
    start = before - timedelta(days=ENVELOPE_DAYS)
    best: dict[int, Effort] = {}
    for e in efforts:
        if start <= e.day < before and e.distance_m >= MIN_EFFORT_M:
            current = best.get(e.distance_key)
            if current is None or e.time_s < current.time_s:
                best[e.distance_key] = e
    return sorted(best.values(), key=lambda e: e.distance_m)


def closest_anchor(
    env: list[Effort], distance_m: float, exclude_same_distance: bool = False
) -> Effort | None:
    """The envelope point nearest in log-distance; ties go to the faster-paced one.

    With exclude_same_distance, an effort at (about) the target distance can't be the
    anchor, so the prediction really crosses distances (a 10k from a 5k).
    """
    if exclude_same_distance:
        env = [e for e in env if abs(math.log(e.distance_m / distance_m)) > 0.05]
    if not env:
        return None
    return min(
        env,
        key=lambda e: (abs(math.log(e.distance_m / distance_m)), e.time_s / e.distance_m),
    )


@dataclass(frozen=True)
class PersonalFit:
    a: float
    b: float
    n_points: int
    longest_m: float

    def predict(self, distance_m: float) -> float:
        return math.exp(self.a + self.b * math.log(distance_m))

    def extrapolated(self, distance_m: float) -> bool:
        return distance_m > EXTRAPOLATION_RATIO * self.longest_m


def personal_fit(env: list[Effort]) -> PersonalFit | None:
    """Least squares of log T on log D. Needs distances spanning a factor of 1.8 or more."""
    distances = np.array([e.distance_m for e in env])
    if len(env) < 2 or distances.max() / distances.min() < MIN_DISTANCE_SPREAD:
        return None
    b, a = np.polyfit(np.log(distances), np.log([e.time_s for e in env]), 1)
    return PersonalFit(a=float(a), b=float(b), n_points=len(env), longest_m=float(distances.max()))


def weekly_km(volumes: list[RunVolume], user_id: str, before: date) -> float:
    start = before - timedelta(days=VOLUME_DAYS)
    total = sum(v.distance_m for v in volumes if v.user_id == user_id and start <= v.day < before)
    return total / 1000 / (VOLUME_DAYS / 7)


def is_target(effort: Effort, user_efforts: list[Effort]) -> bool:
    """Races always count. Otherwise only an effort that beats an earlier one at that
    distance within 180 days: a first effort has nothing to beat and is often easy."""
    if effort.is_race:
        return True
    if effort.distance_m < MIN_EFFORT_M:
        return False
    start = effort.day - timedelta(days=ENVELOPE_DAYS)
    earlier = [
        e.time_s
        for e in user_efforts
        if e.distance_key == effort.distance_key and start <= e.day < effort.day
    ]
    return bool(earlier) and effort.time_s < min(earlier)


# --- anchor -> target pairs --------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    user_id: str
    day: date
    target: Effort
    anchor: Effort
    weekly_km: float
    personal: PersonalFit | None

    @property
    def features(self) -> dict[str, float]:
        return {
            "log_ratio": math.log(self.target.distance_m / self.anchor.distance_m),
            # +1 so a week with no running doesn't send log() to -infinity.
            "log_wkm": math.log(self.weekly_km + 1),
            "treadmill": float(self.target.surface == "treadmill"),
            "track": float(self.target.surface == "track"),
        }


def build_pairs(efforts: list[Effort], volumes: list[RunVolume]) -> list[Pair]:
    by_user: dict[str, list[Effort]] = defaultdict(list)
    for e in efforts:
        by_user[e.user_id].append(e)

    pairs = []
    for user_id, user_efforts in by_user.items():
        for target in user_efforts:
            if not is_target(target, user_efforts):
                continue
            env = envelope(user_efforts, before=target.day)
            # Predicting a 5k from last month's 5k is trivial for every method; score
            # real race prediction instead: always cross to a different distance.
            anchor = closest_anchor(env, target.distance_m, exclude_same_distance=True)
            if anchor is None:
                continue
            pairs.append(
                Pair(
                    user_id=user_id,
                    day=target.day,
                    target=target,
                    anchor=anchor,
                    weekly_km=weekly_km(volumes, user_id, target.day),
                    personal=personal_fit(env),
                )
            )
    return sorted(pairs, key=lambda p: (p.day, p.target.distance_m))


# --- pooled regression -------------------------------------------------------------


@dataclass
class PooledModel:
    """log(T2/T1) = b1·log(D2/D1) + b2·log(D2/D1)·log(weekly km + 1) + surface terms.

    Riegel is the special case b1 = 1.06, everything else 0. The effective
    exponent for a runner is b1 + b2·log(weekly km + 1).
    """

    result: object
    formula: str
    n_train: int
    columns: list[str] = field(default_factory=list)

    def predict(self, pair_features: dict[str, float], anchor: Effort, distance_m: float) -> float:
        frame = pd.DataFrame([pair_features])
        log_ratio = float(self.result.predict(frame).iloc[0])  # type: ignore[attr-defined]
        return anchor.time_s * math.exp(log_ratio)

    def exponent(self, weekly_km_value: float) -> float:
        params = self.result.params  # type: ignore[attr-defined]
        return float(
            params["log_ratio"]
            + params.get("log_ratio:log_wkm", 0.0) * math.log(weekly_km_value + 1)
        )

    def coefficients(self) -> list[dict[str, float | str]]:
        params = self.result.params  # type: ignore[attr-defined]
        ci = self.result.conf_int()  # type: ignore[attr-defined]
        return [
            {
                "term": name,
                "estimate": round(float(params[name]), 4),
                "ci_low": round(float(ci.loc[name, 0]), 4),
                "ci_high": round(float(ci.loc[name, 1]), 4),
            }
            for name in params.index
        ]


def fit_pooled(pairs: list[Pair]) -> PooledModel | None:
    if len(pairs) < MIN_PAIRS_TO_FIT:
        return None
    frame = pd.DataFrame(
        [{**p.features, "y": math.log(p.target.time_s / p.anchor.time_s)} for p in pairs]
    )
    terms = ["log_ratio", "log_ratio:log_wkm"]
    # Surface dummies only when both values appear, otherwise the column is all zeros.
    terms += [c for c in ("treadmill", "track") if frame[c].nunique() > 1]
    # No intercept: like Riegel, predicting the same distance returns the anchor time. An
    # intercept would learn "targets are ~3% faster", which is true only because targets
    # are selected as new bests, and it hurt accuracy on later data.
    formula = "y ~ 0 + " + " + ".join(terms)
    result = smf.ols(formula, data=frame).fit()
    return PooledModel(result=result, formula=formula, n_train=len(pairs), columns=terms)


# --- evaluation --------------------------------------------------------------------


@dataclass(frozen=True)
class MethodScore:
    method: str
    n: int
    mae_s: float | None
    mape_pct: float | None


@dataclass(frozen=True)
class Evaluation:
    enough_data: bool
    n_pairs: int
    n_train: int
    n_test: int
    scores: list[MethodScore]
    coefficients: list[dict[str, float | str]]
    formula: str | None


def _score(method: str, errors: list[tuple[float, float]]) -> MethodScore:
    if not errors:
        return MethodScore(method, 0, None, None)
    abs_err = [abs(pred - actual) for pred, actual in errors]
    pct = [abs(pred - actual) / actual * 100 for pred, actual in errors]
    return MethodScore(
        method, len(errors), round(float(np.mean(abs_err)), 1), round(float(np.mean(pct)), 2)
    )


def evaluate(efforts: list[Effort], volumes: list[RunVolume]) -> Evaluation:
    """Time-ordered split: fit on the earliest 70% of pairs, score everything on the rest."""
    pairs = build_pairs(efforts, volumes)
    n_train = int(len(pairs) * TRAIN_FRACTION)
    train, test = pairs[:n_train], pairs[n_train:]
    if len(test) < MIN_TEST_PAIRS:
        return Evaluation(False, len(pairs), len(train), len(test), [], [], None)

    model = fit_pooled(train)
    riegel_err, personal_err, pooled_err = [], [], []
    for p in test:
        actual = p.target.time_s
        riegel_err.append((riegel(p.anchor, p.target.distance_m), actual))
        if p.personal is not None:
            personal_err.append((p.personal.predict(p.target.distance_m), actual))
        if model is not None:
            pooled_err.append((model.predict(p.features, p.anchor, p.target.distance_m), actual))

    return Evaluation(
        enough_data=True,
        n_pairs=len(pairs),
        n_train=len(train),
        n_test=len(test),
        scores=[
            _score("Riegel (b = 1.06)", riegel_err),
            _score("Personal exponent", personal_err),
            _score("Pooled regression", pooled_err),
        ],
        coefficients=model.coefficients() if model else [],
        formula=model.formula if model else None,
    )


# --- current predictions for one runner ---------------------------------------------


@dataclass(frozen=True)
class Prediction:
    name: str
    distance_m: float
    riegel_s: float | None
    personal_s: float | None
    pooled_s: float | None
    anchor_name: str | None
    anchor_time_s: float | None
    extrapolated: bool


@dataclass(frozen=True)
class RunnerPredictions:
    predictions: list[Prediction]
    personal_exponent: float | None
    pooled_exponent: float | None
    weekly_km: float
    envelope_size: int


def predict_for_runner(
    user_id: str,
    efforts: list[Effort],
    volumes: list[RunVolume],
    today: date,
    model: PooledModel | None,
) -> RunnerPredictions:
    mine = [e for e in efforts if e.user_id == user_id]
    env = envelope(mine, before=today + timedelta(days=1))
    fit = personal_fit(env)
    wkm = weekly_km(volumes, user_id, today + timedelta(days=1))
    longest = max((e.distance_m for e in env), default=0.0)

    preds = []
    for name, dist in TARGET_DISTANCES_M.items():
        anchor = closest_anchor(env, dist)
        pooled = None
        if model is not None and anchor is not None:
            features = {
                "log_ratio": math.log(dist / anchor.distance_m),
                "log_wkm": math.log(wkm + 1),
                "treadmill": 0.0,
                "track": 0.0,
            }
            pooled = round(model.predict(features, anchor, dist), 1)
        preds.append(
            Prediction(
                name=name,
                distance_m=dist,
                riegel_s=round(riegel(anchor, dist), 1) if anchor else None,
                personal_s=round(fit.predict(dist), 1) if fit else None,
                pooled_s=pooled,
                anchor_name=_effort_label(anchor) if anchor else None,
                anchor_time_s=anchor.time_s if anchor else None,
                extrapolated=bool(longest) and dist > EXTRAPOLATION_RATIO * longest,
            )
        )
    return RunnerPredictions(
        predictions=preds,
        personal_exponent=round(fit.b, 3) if fit else None,
        pooled_exponent=round(model.exponent(wkm), 3) if model else None,
        weekly_km=round(wkm, 1),
        envelope_size=len(env),
    )


def riegel_5k_as_of(efforts: list[Effort], user_id: str, as_of: date) -> float | None:
    """Predicted 5k from the envelope at the end of `as_of` (for the trends chart)."""
    env = envelope([e for e in efforts if e.user_id == user_id], before=as_of + timedelta(days=1))
    anchor = closest_anchor(env, 5000.0)
    return round(riegel(anchor, 5000.0), 1) if anchor else None


def _effort_label(e: Effort) -> str:
    km = e.distance_m / 1000
    kind = "race" if e.is_race else "best effort"
    return f"{km:g} km {kind} on {e.day.isoformat()}"
