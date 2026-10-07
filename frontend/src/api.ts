import { supabase } from "./supabase";
import type {
  Evaluation,
  LoadDay,
  Run,
  RunDetail,
  RunnerPredictions,
  Surface,
  Week,
} from "./types";

const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

export interface ManualRunInput {
  distance_km: number;
  duration_s: number;
  started_at: string;
  surface: Surface;
  name?: string;
  is_race: boolean;
  avg_hr?: number;
}

/** FastAPI errors come as a string, {message}, or a list of validation errors. */
export function errorMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const msg = (detail[0] as { msg?: string }).msg;
    return msg ? msg.replace(/^Value error, /, "") : null;
  }
  if (detail && typeof detail === "object" && "message" in detail) return String(detail.message);
  return null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  // getSession refreshes the access token when it's close to expiring.
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...init.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message = errorMessage(detail) ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, message, detail);
  }
  return body as T;
}

export const api = {
  listRuns: () => request<Run[]>("/runs"),
  predictions: () => request<RunnerPredictions>("/predictions"),
  evaluation: () => request<Evaluation>("/predictions/evaluation"),
  trends: (weeks = 26) => request<Week[]>(`/trends?weeks=${weeks}`),
  trainingLoad: (days = 84) => request<LoadDay[]>(`/training-load?days=${days}`),
  getRun: (id: string) => request<RunDetail>(`/runs/${id}`),
  reprocessRun: (id: string) => request<RunDetail>(`/runs/${id}/reprocess`, { method: "POST" }),
  reprocessAll: () =>
    request<{ reprocessed: number; failed: number }>("/runs/reprocess-all", { method: "POST" }),
  deleteRun: (id: string) => request<void>(`/runs/${id}`, { method: "DELETE" }),
  createManualRun: (input: ManualRunInput) =>
    request<RunDetail>("/runs/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  updateManualRun: (id: string, input: ManualRunInput) =>
    request<RunDetail>(`/runs/${id}/manual`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  uploadRun: (input: {
    file: File;
    surface?: Surface;
    isRace: boolean;
    name?: string;
    startedAt?: string;
  }) => {
    const form = new FormData();
    form.append("file", input.file);
    form.append("is_race", String(input.isRace));
    if (input.surface) form.append("surface", input.surface);
    if (input.name) form.append("name", input.name);
    if (input.startedAt) form.append("started_at", input.startedAt);
    return request<RunDetail>("/runs", { method: "POST", body: form });
  },
};
