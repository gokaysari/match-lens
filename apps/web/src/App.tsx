import { useCallback, useEffect, useRef, useState } from "react";
import { getEvents, getMeta } from "./api/client";
import type { Card, MatchEvent, MatchInfo, Score } from "./api/types";
import { CardsPanel, visibleCards } from "./components/CardsPanel";
import { Controls } from "./components/Controls";
import { MetricsPanel } from "./components/MetricsPanel";
import { Pitch } from "./components/Pitch";
import { seqOfSnapshotId, useAnalysis, useReplay } from "./hooks";
import { NO_VALUE, mmss } from "./lib/format";

type Loaded = { meta: MatchInfo; events: MatchEvent[] };
type Load =
  | { state: "loading" }
  | { state: "error"; message: string }
  | ({ state: "ready" } & Loaded);

function Header() {
  return (
    <header className="app-header">
      <h1>Match Lens</h1>
      <span className="badge">Synthetic data · fictional teams</span>
    </header>
  );
}

export default function App({ matchId = "synthetic-01" }: { matchId?: string }) {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => {
    setLoad({ state: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    Promise.all([getMeta(matchId, ctl.signal), getEvents(matchId, ctl.signal)])
      .then(([meta, page]) => {
        if (page.events.length === 0) throw new Error("The match has no events.");
        if (!meta.teams.some((t) => t.side === "home") || !meta.teams.some((t) => t.side === "away")) {
          throw new Error("The match info is missing a home and away team.");
        }
        setLoad({ state: "ready", meta, events: page.events });
      })
      .catch((err: unknown) => {
        if (ctl.signal.aborted) return;
        setLoad({ state: "error", message: err instanceof Error ? err.message : "Unknown error" });
      });
    return () => ctl.abort();
  }, [matchId, attempt]);

  return (
    <div className="app">
      <Header />
      {load.state === "loading" && <p role="status" className="muted">Loading match…</p>}
      {load.state === "error" && (
        <div role="alert" className="error">
          <p>Could not load the match: {load.message}</p>
          <button type="button" onClick={retry}>Retry</button>
        </div>
      )}
      {load.state === "ready" && <Replay matchId={matchId} meta={load.meta} events={load.events} />}
    </div>
  );
}

/**
 * Text for a separate polite live region: titles of cards not announced before (deduped by
 * card_id) and score changes. Stays unchanged on steps that bring neither.
 */
function usePoliteAnnouncement(shown: Card[], score: Score | undefined): string {
  const [text, setText] = useState("");
  const seenCards = useRef(new Set<string>());
  const lastScore = useRef<string | null>(null);
  const key = score ? `${score.home}-${score.away}` : null;
  const ids = shown.map((c) => c.card_id).join("|");
  useEffect(() => {
    const parts: string[] = [];
    for (const c of shown) {
      if (!seenCards.current.has(c.card_id)) {
        seenCards.current.add(c.card_id);
        parts.push(`New card: ${c.title}`);
      }
    }
    if (score && key !== lastScore.current) {
      if (lastScore.current !== null) parts.push(`Score is now ${score.home} to ${score.away}`);
      lastScore.current = key;
    }
    if (parts.length) setText(parts.join(". "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids, key]);
  return text;
}

function Replay({ matchId, meta, events }: { matchId: string } & Loaded) {
  const replay = useReplay(events);
  const current = events[replay.index]!;
  const analysis = useAnalysis(matchId, current.sequence);
  const home = meta.teams.find((t) => t.side === "home")!;
  const away = meta.teams.find((t) => t.side === "away")!;
  // Never show analysis from past the watermark (e.g. after scrubbing backwards).
  const snapshot =
    analysis.snapshot && analysis.snapshot.watermark_seq <= current.sequence ? analysis.snapshot : null;
  const metrics =
    analysis.metrics && seqOfSnapshotId(analysis.metrics.snapshot_id) <= current.sequence
      ? analysis.metrics
      : null;
  const score = snapshot?.score;
  const announcement =
    analysis.settled === "unavailable" ? "Analysis unavailable" : analysis.recovered ? "Analysis restored" : "";
  // Shown analysis that is behind the watermark is dimmed and labelled with its own clock.
  const scoreStale = !!snapshot && snapshot.watermark_seq < current.sequence;
  const metricsSeq = metrics ? seqOfSnapshotId(metrics.snapshot_id) : NaN;
  const metricsStale = !!metrics && metricsSeq < current.sequence;
  const metricsAsOf = metricsStale ? (events.find((e) => e.sequence === metricsSeq)?.event_time_ms ?? metrics.window_end_ms) : null;
  const shownCards = visibleCards(analysis.cards, current.sequence, current.event_time_ms);
  const polite = usePoliteAnnouncement(shownCards, score);

  return (
    <main>
      <section className="scorebar" aria-label="Score">
        <span className="team home">{home.name}</span>
        <span className={scoreStale ? "score stale" : "score"}>
          <span aria-label="Home score">{score ? score.home : NO_VALUE}</span>
          <span aria-hidden="true"> – </span>
          <span aria-label="Away score">{score ? score.away : NO_VALUE}</span>
          {scoreStale && <span className="asof">{`as of ${mmss(snapshot.clock_ms)}`}</span>}
        </span>
        <span className="team away">{away.name}</span>
        <span className="clock">
          <span aria-label="Match clock">{mmss(current.event_time_ms)}</span>
          {" · period "}
          <span aria-label="Period">{current.period}</span>
        </span>
        <p role="status" className="analysis-status" data-state={analysis.status}>
          {announcement}
        </p>
        <div data-testid="announcer" className="sr-only" aria-live="polite">{polite}</div>
        <span className="analysis-status" aria-hidden="true">
          {analysis.status === "loading" ? "Updating…" : ""}
        </span>
      </section>
      <div className="layout">
        <div className="left">
          <Pitch events={events} index={replay.index} meta={meta} />
          <Controls
            index={replay.index}
            last={replay.last}
            clockMs={current.event_time_ms}
            playing={replay.playing}
            speed={replay.speed}
            onIndex={replay.setIndex}
            onPlaying={replay.setPlaying}
            onSpeed={replay.setSpeed}
          />
        </div>
        <div className="right">
          <CardsPanel
            cards={analysis.cards}
            events={events}
            meta={meta}
            watermarkSeq={current.sequence}
            clockMs={current.event_time_ms}
          />
          <MetricsPanel metrics={metrics} meta={meta} staleAsOfMs={metricsAsOf} />
        </div>
      </div>
      <p className="muted small footer">
        All match data is synthetic. Not an official product of any league or club.
      </p>
    </main>
  );
}
