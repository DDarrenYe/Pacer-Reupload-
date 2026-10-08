// Mirrors backend/app/schemas/run.py.

export type Surface = "road" | "track" | "treadmill";
export type SplitType = "negative" | "even" | "positive";

export interface Run {
  id: string;
  name: string | null;
  started_at: string;
  source: "gpx" | "csv" | "manual";
  surface: Surface;
  distance_m: number;
  elapsed_s: number;
  moving_time_s: number;
  avg_pace_s_per_km: number;
  elevation_gain_m: number | null;
  avg_hr: number | null;
  is_race: boolean;
  notes: string | null;
  created_at: string;
  split_type: SplitType | null;
  pace_drift_s_per_km: number | null;
  fastest_split_no: number | null;
  slowest_split_no: number | null;
}

export interface Split {
  split_no: number;
  split_length_m: number;
  distance_m: number;
  duration_s: number;
  pace_s_per_km: number;
  avg_hr: number | null;
  is_partial: boolean;
}

export interface BestEffort {
  name: string;
  distance_m: number;
  duration_s: number;
  start_offset_m: number;
}

export interface RunDetail extends Run {
  splits: Split[];
  best_efforts: BestEffort[];
}

export interface Prediction {
  name: string;
  distance_m: number;
  riegel_s: number | null;
  personal_s: number | null;
  pooled_s: number | null;
  anchor_name: string | null;
  anchor_time_s: number | null;
  extrapolated: boolean;
}

export interface RunnerPredictions {
  predictions: Prediction[];
  personal_exponent: number | null;
  pooled_exponent: number | null;
  weekly_km: number;
  envelope_size: number;
}

export interface MethodScore {
  method: string;
  n: number;
  mae_s: number | null;
  mape_pct: number | null;
}

export interface Evaluation {
  enough_data: boolean;
  n_pairs: number;
  n_train: number;
  n_test: number;
  scores: MethodScore[];
  formula: string | null;
}

export interface Week {
  week_start: string;
  runs: number;
  distance_km: number;
  avg_pace_s_per_km: number | null;
  predicted_5k_s: number | null;
}

export interface LoadDay {
  date: string;
  load_min: number;
  acute_7d: number;
  chronic_28d: number;
  acwr: number | null;
  flag: "spike" | "normal" | "low" | null;
}

export type GoalStatus = "no_data" | "already_there" | "on_track" | "within_reach" | "stretch" | "passed";

export interface GoalAnalysis {
  status: GoalStatus;
  days_left: number;
  target_pace_s_per_km: number;
  now_s: number | null;
  personal_now_s: number | null;
  anchor: string | null;
  projected_s: number | null;
  projection_note: string | null;
  needed_pct_per_week: number | null;
  weekly: { week_end: string; predicted_s: number | null }[];
  equivalents: { name: string; distance_m: number; time_s: number }[];
  recommendations: string[];
  result_s: number | null;
  result_hit: boolean | null;
}

export interface Goal {
  id: string;
  name: string;
  distance_m: number;
  target_time_s: number;
  race_date: string;
  created_at: string;
  analysis: GoalAnalysis;
}
