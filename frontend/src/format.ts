/** 300 -> "5:00", 3725 -> "1:02:05". */
export function formatDuration(seconds: number): string {
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

/** Seconds per km -> "5:00 /km". */
export function formatPace(secondsPerKm: number): string {
  return `${formatDuration(secondsPerKm)} /km`;
}

/** 5012 -> "5.01 km", 400 -> "400 m". */
export function formatDistance(metres: number): string {
  return metres < 1000 ? `${Math.round(metres)} m` : `${(metres / 1000).toFixed(2)} km`;
}

/** Pace drift in s/km per km -> a sentence a runner would say. */
export function describeDrift(drift: number | null): string {
  if (drift === null) return "Not enough full splits to measure.";
  if (Math.abs(drift) < 1) return "Steady: pace barely changed.";
  const s = Math.abs(drift).toFixed(1);
  return drift > 0 ? `Faded: about ${s} s/km slower each km.` : `Built: about ${s} s/km faster each km.`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}
