import type { Card, MatchEvent, MetricValue, MatchInfo } from "../api/types";
import { playerName } from "./Pitch";
import { formatMetric, metricLabel, mmss } from "../lib/format";

interface Props {
  cards: Card[];
  events: MatchEvent[];
  meta: MatchInfo;
  watermarkSeq: number;
  clockMs: number;
}

/** Cards visible at this replay position: triggered already and not yet expired. Newest first. */
export function visibleCards(cards: Card[], watermarkSeq: number, clockMs: number): Card[] {
  return cards
    .filter((c) => c.trigger_seq <= watermarkSeq && clockMs <= c.expires_at_ms)
    .sort((a, b) => b.trigger_seq - a.trigger_seq);
}

export function CardsPanel({ cards, events, meta, watermarkSeq, clockMs }: Props) {
  const teamName = (id: string) => meta.teams.find((t) => t.id === id)?.name ?? id;
  const byId = new Map(events.map((e) => [e.event_id, e]));
  const shown = visibleCards(cards, watermarkSeq, clockMs);

  const metricLine = (m: MetricValue) =>
    `${metricLabel(m.name)} · ${teamName(m.team_id)} · ${formatMetric(m)}`;

  return (
    <section className="panel cards" aria-labelledby="cards-h">
      <h2 id="cards-h">Fact cards</h2>
      {shown.length === 0 && <p className="muted">No active cards at this moment.</p>}
      {shown.map((c) => (
        <article key={c.card_id} className="card" aria-labelledby={`t-${c.card_id}`}>
          <h3 id={`t-${c.card_id}`}>{c.title}</h3>
          <p>{c.body}</p>
          <p className="muted small">
            <span>{`as of ${mmss(c.trigger_clock_ms)}`}</span>
          </p>
          <details>
            <summary>{`Evidence (${c.evidence_event_ids.length})`}</summary>
            <ul>
              {c.evidence_event_ids.map((id) => {
                const e = byId.get(id);
                // Evidence must resolve inside the card's snapshot (sequence <= trigger_seq).
                const text = !e
                  ? `${id} · unknown event`
                  : e.sequence > c.trigger_seq
                    ? `${id} · outside snapshot`
                    : `${id} · ${mmss(e.event_time_ms)} · ${teamName(e.team_id)} · ${e.type} · ${e.player_id ? playerName(meta, e.player_id) : "–"}`;
                return (
                  <li key={id}>{text}</li>
                );
              })}
            </ul>
            {c.metrics.length > 0 && (
              <ul className="card-metrics" aria-label="Card metrics">
                {c.metrics.map((m) => (
                  <li key={`${m.name}-${m.team_id}`}>{metricLine(m)}</li>
                ))}
              </ul>
            )}
          </details>
        </article>
      ))}
    </section>
  );
}
