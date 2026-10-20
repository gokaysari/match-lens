import type {
  ApiErrorBody, CardList, EventPage, ScenarioMeta, Snapshot, WindowMetrics,
} from "./types";

const BASE = "/api";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

function isApiErrorBody(v: unknown): v is ApiErrorBody {
  return typeof v === "object" && v !== null
    && typeof (v as ApiErrorBody).code === "string"
    && typeof (v as ApiErrorBody).message === "string";
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal, headers: { Accept: "application/json" } });
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = undefined;
    }
    if (isApiErrorBody(body)) throw new ApiRequestError(res.status, body.code, body.message);
    throw new ApiRequestError(res.status, "HTTP_ERROR", `Request failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

const m = (matchId: string) => `/matches/${encodeURIComponent(matchId)}`;

export const getMeta = (matchId: string, signal?: AbortSignal) =>
  get<ScenarioMeta>(`${m(matchId)}/meta`, signal);

/** Full timeline (no at_seq): loaded once, the replay is driven locally. */
export const getEvents = (matchId: string, signal?: AbortSignal) =>
  get<EventPage>(`${m(matchId)}/events`, signal);

export const getSnapshot = (matchId: string, atSeq: number, signal?: AbortSignal) =>
  get<Snapshot>(`${m(matchId)}/snapshot?at_seq=${atSeq}`, signal);

export const getMetrics = (matchId: string, atSeq: number, windowS: number, signal?: AbortSignal) =>
  get<WindowMetrics>(`${m(matchId)}/metrics?at_seq=${atSeq}&window_s=${windowS}`, signal);

export const getCards = (matchId: string, atSeq: number, signal?: AbortSignal) =>
  get<CardList>(`${m(matchId)}/cards?at_seq=${atSeq}`, signal);
