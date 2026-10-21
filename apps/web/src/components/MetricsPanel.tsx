import type { MatchInfo, WindowMetrics } from "../api/types";
import { NO_VALUE, formatMetric, metricLabel, mmss } from "../lib/format";

export const NOT_REPORTED = "not reported";

const PERIOD_2_START_MS = 45 * 60000;

/** Visible caption: the window may start before the replay segment or before the period start. */
export function metricsCaption(windowStartMs: number, segmentStartMs: number, period: 1 | 2 = 1): string {
  if (windowStartMs < segmentStartMs) return `Last 60 s · since ${mmss(segmentStartMs)} (replay start)`;
  if (period === 2 && windowStartMs < PERIOD_2_START_MS) {
    return `Last 60 s · since ${mmss(PERIOD_2_START_MS)} (period start)`;
  }
  return "Last 60 s";
}

interface Props {
  metrics: WindowMetrics | null;
  meta: MatchInfo;
  /** Clock of the shown metrics when they are behind the watermark; null when current. */
  staleAsOfMs: number | null;
  /** Period of the metrics' watermark. */
  period?: 1 | 2;
}

export function MetricsPanel({ metrics, meta, staleAsOfMs, period = 1 }: Props) {
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
    <section className="panel" aria-labelledby="metrics-h">
      <h2 id="metrics-h">Metrics</h2>
      {stale && <p className="asof small">{`as of ${mmss(staleAsOfMs)}`}</p>}
      <div className={stale ? "stale-value" : undefined}>
      <table>
        <caption>{metricsCaption(metrics.window_start_ms, meta.segment_start_ms, period)}</caption>
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
      </div>
    </section>
  );
}
