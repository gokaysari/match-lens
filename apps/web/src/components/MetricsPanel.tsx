import type { ScenarioMeta, WindowMetrics } from "../api/types";
import { NO_VALUE, formatMetric, humanize } from "../lib/format";

export function MetricsPanel({ metrics, meta }: { metrics: WindowMetrics | null; meta: ScenarioMeta }) {
  if (!metrics) {
    return (
      <section className="panel" aria-labelledby="metrics-h">
        <h2 id="metrics-h">Metrics</h2>
        <p className="muted">No metrics yet.</p>
      </section>
    );
  }
  const names = [...new Set(metrics.metrics.map((m) => m.name))];
  return (
    <section className="panel" aria-labelledby="metrics-h">
      <h2 id="metrics-h">Metrics</h2>
      <table>
        <caption>Last 60 s</caption>
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
              <th scope="row">{humanize(name)}</th>
              {meta.teams.map((t) => {
                const m = metrics.metrics.find((x) => x.name === name && x.team_id === t.id);
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
