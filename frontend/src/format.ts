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

/** Personal Riegel exponent -> a sentence a runner would understand. */
export function describeExponent(b: number | null): string {
  if (b === null) return "Run a GPX effort at two quite different distances (e.g. 5k and 10k) to see your own exponent.";
  const diff = b - 1.06;
  if (Math.abs(diff) < 0.015) return `Your exponent is ${b.toFixed(3)}: you slow down over distance about as much as the standard 1.06 predicts.`;
  return diff > 0
    ? `Your exponent is ${b.toFixed(3)}, above the standard 1.06: you slow down more than average as races get longer, so speed is your relative strength.`
    : `Your exponent is ${b.toFixed(3)}, below the standard 1.06: you hold pace better than average as races get longer, so endurance is your relative strength.`;
}

/** "2026-03-16" -> "16 Mar". */
export function formatShortDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Hours, minutes and seconds from form fields -> total seconds (blank counts as 0). */
export function toSeconds(h: string, m: string, s: string): number {
  const n = (v: string) => (v.trim() === "" ? 0 : Number(v));
  return n(h) * 3600 + n(m) * 60 + n(s);
}

/** Pace in s/km, or null when it can't be worked out yet. */
export function paceFrom(distanceKm: number, seconds: number): number | null {
  if (!(distanceKm > 0) || !(seconds > 0) || !Number.isFinite(distanceKm) || !Number.isFinite(seconds)) return null;
  return seconds / distanceKm;
}

/** The name the server gives a manual run when you leave the name blank. */
export function defaultManualName(distanceKm: number, surface: string): string {
  // Same as the server's f"{distance_km:g}": up to 6 significant digits.
  return `${Number(distanceKm.toPrecision(6))} km ${surface} run`;
}

/** Total seconds -> ["h", "mm", "ss"] strings for the time fields (blank hours if under an hour). */
export function splitDuration(totalSeconds: number): [string, string, string] {
  const t = Math.round(totalSeconds);
  const h = Math.floor(t / 3600);
  return [h ? String(h) : "", String(Math.floor((t % 3600) / 60)), String(t % 60).padStart(2, "0")];
}

/** Days until a date -> "today", "tomorrow", "in 5 days", "in 6 weeks", or "3 days ago". */
export function describeCountdown(days: number): string {
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days < 0) return days === -1 ? "yesterday" : `${-days} days ago`;
  if (days < 14) return `in ${days} days`;
  return `in ${Math.round(days / 7)} weeks`;
}

/** Seconds of difference -> "1:23 faster" / "0:45 slower" / "spot on". */
export function describeGap(seconds: number): string {
  if (Math.abs(seconds) < 1) return "spot on";
  return `${formatDuration(Math.abs(seconds))} ${seconds < 0 ? "faster" : "slower"}`;
}
