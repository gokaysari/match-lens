import type { MatchInfo, WindowMetrics } from "../api/types";
import { NO_VALUE, formatMetric, metricLabel, mmss } from "../lib/format";

export const NOT_REPORTED = "not reported";

/** Visible caption: the window may start before the replay segment (no earlier data exists). */
export function metricsCaption(windowStartMs: number, segmentStartMs: number): string {
  return windowStartMs < segmentStartMs ? `Since ${mmss(segmentStartMs)} (replay start)` : "Last 60 s";
}

interface Props {
  metrics: WindowMetrics | null;
  meta: MatchInfo;
  /** Clock of the shown metrics when they are behind the watermark; null when current. */
  staleAsOfMs: number | null;
}

export function MetricsPanel({ metrics, meta, staleAsOfMs }: Props) {
  if (!metrics) {
    return (
      <section className="panel" aria-labelledby="metrics-h">
        <h2 id="metrics-h">Metrics</h2>
        <p className="muted">No metrics yet.</p>
      </section>
    );
  }
  const names = [...new Set(metrics.metrics.map((m) => m.name))];
  const stale = staleAsOfMs !== null;
  return (
    <section className={stale ? "panel stale" : "panel"} aria-labelledby="metrics-h">
      <h2 id="metrics-h">Metrics</h2>
      {stale && <p className="asof small">{`as of ${mmss(staleAsOfMs)}`}</p>}
      <table aria-label="Last 60 s">
        <caption>{metricsCaption(metrics.window_start_ms, meta.segment_start_ms)}</caption>
        <thead>
          <tr>
            <th scope="col">Metric</th>
            {meta.teams.map((t) => (
              <th scope="col" key={t.id}>{t.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.map((name) => (
            <tr key={name}>
              <th scope="row">{metricLabel(name)}</th>
              {meta.teams.map((t) => {
                const m = metrics.metrics.find((x) => x.name === name && x.team_id === t.id);
                if (!m) return <td key={t.id} className="muted">{NOT_REPORTED}</td>;
                const text = formatMetric(m);
                return (
                  <td key={t.id} title={text === NO_VALUE ? "no attempts" : undefined}>{text}</td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
