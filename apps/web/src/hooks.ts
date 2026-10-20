import { useEffect, useState } from "react";
import { getCards, getMetrics, getSnapshot } from "./api/client";
import type { Card, MatchEvent, Snapshot, WindowMetrics } from "./api/types";
import { playbackDelay } from "./lib/format";

export const SPEEDS = [1, 4, 16] as const;
export type Speed = (typeof SPEEDS)[number];
export const DEBOUNCE_MS = 150;
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

  return { index, setIndex, playing, setPlaying, speed, setSpeed, last };
}

export type AnalysisStatus = "loading" | "ready" | "unavailable";

/**
 * Fetches snapshot, metrics and cards for the watermark. Aborts in-flight requests and
 * debounces when the watermark changes. Keeps the last good data; never blocks the caller.
 */
export function useAnalysis(matchId: string, seq: number) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [metrics, setMetrics] = useState<WindowMetrics | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [status, setStatus] = useState<AnalysisStatus>("loading");

  useEffect(() => {
    setStatus("loading");
    const ctl = new AbortController();
    const timer = setTimeout(() => {
      void Promise.allSettled([
        getSnapshot(matchId, seq, ctl.signal),
        getMetrics(matchId, seq, WINDOW_S, ctl.signal),
        getCards(matchId, seq, ctl.signal),
      ]).then(([s, m, c]) => {
        if (ctl.signal.aborted) return;
        if (s.status === "fulfilled") setSnapshot(s.value);
        if (m.status === "fulfilled") setMetrics(m.value);
        if (c.status === "fulfilled") setCards(c.value.cards);
        setStatus(
          s.status === "fulfilled" && m.status === "fulfilled" && c.status === "fulfilled"
            ? "ready"
            : "unavailable",
        );
      });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      ctl.abort();
    };
  }, [matchId, seq]);

  return { snapshot, metrics, cards, status };
}
