// Mirrors backend/app/schemas/run.py.

export type Surface = "road" | "track" | "treadmill";
export type SplitType = "negative" | "even" | "positive";

export interface Run {
  id: string;
  name: string | null;
  started_at: string;
  source: "gpx" | "csv";
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
