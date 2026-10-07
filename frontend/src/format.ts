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
