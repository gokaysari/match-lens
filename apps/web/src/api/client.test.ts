import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, getCards, getEvents, getMeta, getMetrics, getSnapshot } from "./client";
import { MATCH, installMockApi, jsonResponse } from "../test/mockApi";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("builds the five contract URLs", async () => {
    const api = installMockApi();
    await getMeta(MATCH);
    await getEvents(MATCH);
    await getSnapshot(MATCH, 2005);
    await getMetrics(MATCH, 2005, 60);
    await getCards(MATCH, 2005);
    const urls = api.calls.map((c) => c.url.pathname + c.url.search);
    expect(urls).toEqual([
      `/api/matches/${MATCH}/meta`,
      `/api/matches/${MATCH}/events`,
      `/api/matches/${MATCH}/snapshot?at_seq=2005`,
      `/api/matches/${MATCH}/metrics?at_seq=2005&window_s=60`,
      `/api/matches/${MATCH}/cards?at_seq=2005`,
    ]);
  });

  it("passes the AbortSignal to fetch", async () => {
    const api = installMockApi();
    const ctl = new AbortController();
    await getSnapshot(MATCH, 2005, ctl.signal);
    expect(api.calls[0]!.signal).toBe(ctl.signal);
  });

  it("throws a typed error parsed from the ApiError body", async () => {
    installMockApi({
      override: () => jsonResponse({ code: "UNKNOWN_SEQUENCE", message: "no such seq" }, 404),
    });
    const err = await getSnapshot(MATCH, 1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 404, code: "UNKNOWN_SEQUENCE", message: "no such seq" });
  });

  it("throws a typed error even when the body is not JSON", async () => {
    installMockApi({ override: () => new Response("boom", { status: 502 }) });
    const err = await getMeta(MATCH).catch((e) => e);
    expect(err).toBeInstanceOf(ApiRequestError);
    expect(err).toMatchObject({ status: 502, code: "HTTP_ERROR" });
  });
});
