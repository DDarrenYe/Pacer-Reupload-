import { supabase } from "./supabase";
import type { Run, RunDetail, Surface } from "./types";

const API_URL = import.meta.env.VITE_API_URL.replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
  }
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
    const message =
      typeof detail === "string" ? detail : (detail?.message ?? `Request failed (${res.status})`);
    throw new ApiError(res.status, message, detail);
  }
  return body as T;
}

export const api = {
  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: string) => request<RunDetail>(`/runs/${id}`),
  reprocessRun: (id: string) => request<RunDetail>(`/runs/${id}/reprocess`, { method: "POST" }),
  deleteRun: (id: string) => request<void>(`/runs/${id}`, { method: "DELETE" }),
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
