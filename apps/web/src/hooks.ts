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

/** Seq encoded in a snapshot_id "<match>@<seq>"; NaN when malformed. */
export function seqOfSnapshotId(id: string): number {
  return Number(id.split("@").pop());
}

/**
 * Fetches snapshot, metrics and cards for the watermark. Leading + trailing throttle
 * (THROTTLE_MS) so fast playback still gets periodic updates. Only issuing a new request aborts
 * the previous one; a response is applied if it belongs to the most recently issued request, its
 * snapshot_id matches its own at_seq, and at_seq is not past the current watermark.
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
  const issuedId = useRef(0);
  const lastIssued = useRef(-Infinity);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ctl = useRef<AbortController | null>(null);

  const issue = useCallback(() => {
    timer.current = null;
    lastIssued.current = Date.now();
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    const id = ++issuedId.current;
    const at = latest.current;
    const expected = `${matchId}@${at}`;
    const valid = <T extends { snapshot_id: string }>(r: PromiseSettledResult<T>): T | null =>
      r.status === "fulfilled" && r.value.snapshot_id === expected ? r.value : null;
    void Promise.allSettled([
      getSnapshot(matchId, at, c.signal),
      getMetrics(matchId, at, WINDOW_S, c.signal),
      getCards(matchId, at, c.signal),
    ]).then(([s, m, k]) => {
      // An aborted request (superseded, or StrictMode/unmount cleanup) is not an outage.
      if (c.signal.aborted || id !== issuedId.current || at > latest.current) return;
      const sv = valid(s), mv = valid(m), kv = valid(k);
      if (sv) setSnapshot(sv);
      if (mv) setMetrics(mv);
      if (kv) setCards(kv.cards);
      const ok = !!(sv && mv && kv);
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
    });
  }, [matchId]);

  useEffect(() => {
    latest.current = seq;
    setStatus("loading");
    if (timer.current) return; // a trailing call is already scheduled and will read latest
    const wait = lastIssued.current + THROTTLE_MS - Date.now();
    if (wait <= 0) issue();
    else timer.current = setTimeout(issue, wait);
  }, [matchId, seq, issue]);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
      ctl.current?.abort();
    },
    [],
  );

  return { snapshot, metrics, cards, status, settled, recovered };
}
