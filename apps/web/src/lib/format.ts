import type { MetricValue } from "../api/types";

export function mmss(ms: number): string {
  const total = Math.floor(ms / 1000);
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export const NO_VALUE = "–";

export function formatMetric(m: MetricValue | undefined): string {
  if (!m || m.value === null) return NO_VALUE;
  if (m.unit === "ratio") {
    const pct = `${Math.round(m.value * 100)}%`;
    return m.numerator !== null && m.denominator !== null
      ? `${pct} (${m.numerator}/${m.denominator})`
      : pct;
  }
  return String(m.value);
}

export function humanize(name: string): string {
  return name.replace(/_/g, " ");
}

const METRIC_LABELS: Record<string, string> = {
  passes_attempted: "Passes attempted",
  passes_completed: "Passes completed",
  pass_completion: "Pass completion",
  pressures: "Pressures",
  pressures_opp_half: "Pressures in opponent half",
  ball_wins: "Ball wins",
  high_ball_wins: "Ball wins in opponent half",
  shots: "Shots",
  goals: "Goals",
};

/** Plain-language label for a metric name; unknown names fall back to the humanized id. */
export function metricLabel(name: string): string {
  return METRIC_LABELS[name] ?? humanize(name);
}

/** Real-time delay before advancing to the next event; a single gap is capped at 5 s. */
export const MAX_GAP_REAL_MS = 5000;
export function playbackDelay(gapMs: number, speed: number): number {
  return Math.min(Math.max(gapMs, 0) / speed, MAX_GAP_REAL_MS);
}
