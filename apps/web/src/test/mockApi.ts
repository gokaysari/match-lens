import { vi } from "vitest";
import type {
  Card, CardList, EventPage, MatchEvent, MetricValue, ScenarioMeta, Snapshot, WindowMetrics,
} from "../api/types";
import eventsJson from "./fixtures/events.json";
import metaJson from "./fixtures/meta.json";

export const meta = metaJson as unknown as ScenarioMeta;
export const events = eventsJson as unknown as MatchEvent[];
export const MATCH = meta.match_id;

// Deliberately NOT derivable from the events: proves the UI shows the API score.
export const API_SCORE = { home: 4, away: 2 };

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function snapshotAt(seq: number): Snapshot {
  const last = events.find((e) => e.sequence === seq)!;
  return {
    schema_version: "1.0",
    match_id: MATCH,
    snapshot_id: `${MATCH}@${seq}`,
    watermark_seq: seq,
    watermark_event_id: last.event_id,
    clock_ms: last.event_time_ms,
    period: last.period,
    score: API_SCORE,
    goal_event_ids: [],
    last_event: last,
    synthetic: true,
  };
}

export function metric(
  name: MetricValue["name"], team_id: string, value: number | null,
  extra: Partial<MetricValue> = {},
): MetricValue {
  return {
    name, team_id, value, unit: "count", numerator: null, denominator: null,
    definition_version: "metrics-v1", event_ids: [], ...extra,
  };
}

export function metricsAt(seq: number): WindowMetrics {
  const last = events.find((e) => e.sequence === seq)!;
  return {
    schema_version: "1.0",
    match_id: MATCH,
    snapshot_id: `${MATCH}@${seq}`,
    window_start_ms: last.event_time_ms - 60000,
    window_end_ms: last.event_time_ms,
    metrics: [
      metric("pass_completion", "nbr", 4 / 9, { unit: "ratio", numerator: 4, denominator: 9 }),
      metric("pass_completion", "hba", null, { unit: "ratio", numerator: 0, denominator: 0 }),
      metric("pressures", "nbr", 1),
      metric("pressures", "hba", 12),
    ],
    synthetic: true,
  };
}

export const SEQ_CARD_TRIGGER = 2030;
export const goalCard: Card = {
  card_id: `goal@${SEQ_CARD_TRIGGER}`,
  kind: "goal",
  template_id: "fact-card",
  title: "Goal for Harbour Athletic",
  body: "Harbour scored. <b>not html</b>",
  trigger_seq: SEQ_CARD_TRIGGER,
  trigger_clock_ms: events.find((e) => e.sequence === SEQ_CARD_TRIGGER)!.event_time_ms,
  expires_at_ms: events.find((e) => e.sequence === 2040)!.event_time_ms,
  metrics: [metric("goals", "hba", 1)],
  evidence_event_ids: ["e029", "e030"],
  origin: "template",
};

export function cardsAt(seq: number, all = false): CardList {
  return {
    schema_version: "1.0",
    match_id: MATCH,
    snapshot_id: `${MATCH}@${seq}`,
    cards: all || seq >= goalCard.trigger_seq ? [goalCard] : [],
    synthetic: true,
  };
}

export interface Call { url: URL; signal: AbortSignal | undefined }

export interface MockOptions {
  /** return a Response (or promise) to override an endpoint; undefined falls through */
  override?: (endpoint: string, seq: number | null, call: Call) => Response | Promise<Response> | undefined;
  /** cards endpoint ignores at_seq filtering (to prove the UI filters too) */
  allCards?: boolean;
}

export function installMockApi(opts: MockOptions = {}) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const call = { url, signal: init?.signal ?? undefined };
    calls.push(call);
    const endpoint = url.pathname.split("/").pop()!;
    const raw = url.searchParams.get("at_seq");
    const seq = raw === null ? null : Number(raw);
    const o = opts.override?.(endpoint, seq, call);
    if (o) return o;
    switch (endpoint) {
      case "meta": return jsonResponse(meta);
      case "events": {
        const page: EventPage = {
          schema_version: "1.0", match_id: MATCH,
          snapshot_id: `${MATCH}@${events[events.length - 1]!.sequence}`,
          events, synthetic: true,
        };
        return jsonResponse(page);
      }
      case "snapshot": return jsonResponse(snapshotAt(seq!));
      case "metrics": return jsonResponse(metricsAt(seq!));
      case "cards": return jsonResponse(cardsAt(seq!, opts.allCards));
      default: return jsonResponse({ code: "NOT_FOUND", message: "x" }, 404);
    }
  });
  vi.stubGlobal("fetch", fn);
  const forEndpoint = (name: string) => calls.filter((c) => c.url.pathname.endsWith(`/${name}`));
  return { fn, calls, forEndpoint };
}

/** Hangs until the request is aborted (then rejects like fetch does). */
export function hang(call: Call): Promise<Response> {
  return new Promise((_, reject) => {
    call.signal?.addEventListener("abort", () =>
      reject(new DOMException("Aborted", "AbortError")));
  });
}
