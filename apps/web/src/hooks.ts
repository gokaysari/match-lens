import { useCallback, useEffect, useRef, useState } from "react";
import { getCards, getMetrics, getSnapshot } from "./api/client";
import type { Card, MatchEvent, Snapshot, WindowMetrics } from "./api/types";
import { playbackDelay } from "./lib/format";

export const SPEEDS = [1, 4, 16] as const;
export type Speed = (typeof SPEEDS)[number];
export const WINDOW_S = 60;

export function useReplay(events: MatchEvent[]) {
  const [index, setIndexRaw] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const last = events.length - 1;
  const setIndex = (i: number) => setIndexRaw(Math.min(Math.max(i, 0), last));

  useEffect(() => {
    if (!playing) return;
    if (index >= last) {
      setPlaying(false);
      return;
    }
    const gap = events[index + 1]!.event_time_ms - events[index]!.event_time_ms;
    const t = setTimeout(() => setIndexRaw(index + 1), playbackDelay(gap, speed));
    return () => clearTimeout(t);
  }, [playing, index, speed, events, last]);

  const play = (p: boolean) => {
    if (p && index >= last) setIndexRaw(0);
    setPlaying(p);
  };

  return { index, setIndex, playing, setPlaying: play, speed, setSpeed, last };
}

export type AnalysisStatus = "loading" | "ready" | "unavailable";

export const THROTTLE_MS = 200;
/** A request that has not answered by then is abandoned so later positions can still be fetched. */
export const REQUEST_TIMEOUT_MS = 5000;
/** Delay before the single retry of a timed-out request for the current watermark. */
export const RETRY_DELAY_MS = 1000;

/** Seq encoded in a snapshot_id "<match>@<seq>"; NaN when malformed. */
export function seqOfSnapshotId(id: string): number {
  return Number(id.split("@").pop());
}

interface InFlight { id: number; at: number; ctl: AbortController; timedOut: boolean }

/**
 * Fetches snapshot, metrics and cards for the watermark with at most one request in flight.
 * When it completes it is applied if its at_seq is not past the current watermark and its
 * snapshot_ids match; then, if the watermark moved meanwhile, one request for the latest watermark
 * is issued (never closer than THROTTLE_MS after the previous one). The in-flight request is
 * aborted only when the watermark moves BELOW its at_seq (scrub back) or after REQUEST_TIMEOUT_MS,
 * so under high latency responses keep being applied during playback instead of being starved.
 * `settled` is the last applied outcome (never the transient loading state).
 */
export function useAnalysis(matchId: string, seq: number) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [metrics, setMetrics] = useState<WindowMetrics | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [status, setStatus] = useState<AnalysisStatus>("loading");
  const [settled, setSettled] = useState<"ready" | "unavailable" | null>(null);
  const [recovered, setRecovered] = useState(false);
  const wasUnavailable = useRef(false);

  const latest = useRef(seq);
  const nextId = useRef(0);
  const inflight = useRef<InFlight | null>(null);
  const lastAt = useRef<number | null>(null); // at_seq of the most recently issued request
  const lastIssuedTime = useRef(-Infinity);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retriedAt = useRef<number | null>(null); // watermark already retried after a timeout

  const pump = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
    const cur = inflight.current;
    if (cur) {
      if (latest.current >= cur.at) return; // still useful: its completion will chain
      cur.ctl.abort(); // scrubbed back below it
      inflight.current = null;
      lastAt.current = null; // the aborted watermark was never answered; it must be requestable again
    }
    if (lastAt.current === latest.current) return; // already requested for this watermark
    const wait = lastIssuedTime.current + THROTTLE_MS - Date.now();
    if (wait > 0) {
      timer.current = setTimeout(pump, wait);
      return;
    }
    const ctl = new AbortController();
    const at = latest.current;
    const req: InFlight = { id: ++nextId.current, at, ctl, timedOut: false };
    inflight.current = req;
    lastAt.current = at;
    lastIssuedTime.current = Date.now();
    const to = setTimeout(() => {
      req.timedOut = true;
      ctl.abort();
    }, REQUEST_TIMEOUT_MS);
    const expected = `${matchId}@${at}`;
    const valid = <T extends { snapshot_id: string }>(r: PromiseSettledResult<T>): T | null =>
      r.status === "fulfilled" && r.value.snapshot_id === expected ? r.value : null;
    void Promise.allSettled([
      getSnapshot(matchId, at, ctl.signal),
      getMetrics(matchId, at, WINDOW_S, ctl.signal),
      getCards(matchId, at, ctl.signal),
    ]).then(([s, m, k]) => {
      clearTimeout(to);
      // Superseded, scrubbed away or unmounted (also StrictMode cleanup): not an outage.
      if (inflight.current !== req || (ctl.signal.aborted && !req.timedOut)) return;
      inflight.current = null;
      if (req.timedOut) {
        if (at < latest.current) lastAt.current = null;
        else if (at === latest.current && retriedAt.current !== at) {
          retriedAt.current = at;
          lastAt.current = null;
          timer.current = setTimeout(pump, RETRY_DELAY_MS); // retry once, shortly
          lastIssuedTime.current = Date.now();
        }
      }
      if (at <= latest.current) {
        const sv = valid(s), mv = valid(m), kv = valid(k);
        if (sv) setSnapshot(sv);
        if (mv) setMetrics(mv);
        if (kv) setCards(kv.cards);
        const ok = !!(sv && mv && kv);
        if (ok) retriedAt.current = null;
        if (!ok) {
          wasUnavailable.current = true;
          setRecovered(false);
        } else if (wasUnavailable.current) {
          wasUnavailable.current = false;
          setRecovered(true);
        } else {
          setRecovered(false);
        }
        setSettled(ok ? "ready" : "unavailable");
        setStatus(at === latest.current ? (ok ? "ready" : "unavailable") : "loading");
      }
      if (!timer.current) pump();
    });
  }, [matchId]);

  // New match: drop everything belonging to the previous one.
  useEffect(() => {
    setSnapshot(null);
    setMetrics(null);
    setCards([]);
    setStatus("loading");
    setSettled(null);
    setRecovered(false);
    wasUnavailable.current = false;
    retriedAt.current = null;
    return () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
      inflight.current?.ctl.abort();
      inflight.current = null;
      lastAt.current = null;
      lastIssuedTime.current = -Infinity;
    };
  }, [matchId]);

  useEffect(() => {
    latest.current = seq;
    setStatus("loading");
    pump();
  }, [matchId, seq, pump]);

  return { snapshot, metrics, cards, status, settled, recovered };
}
