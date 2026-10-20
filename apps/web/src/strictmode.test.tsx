import { StrictMode } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";
import { MATCH, cardsAt, events, installMockApi, jsonResponse, metricsAt, snapshotAt, type Call } from "./test/mockApi";

/** Like real fetch: answers after `ms`, rejects with AbortError if aborted first. */
function slow(body: unknown, call: Call, ms = 40): Promise<Response> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => resolve(jsonResponse(body)), ms);
    call.signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// main.tsx renders under StrictMode, which mounts effects twice in development.
// A request aborted by that cleanup (or by a newer request) is not an outage.
it("an aborted request is never reported as unavailable or restored", async () => {
  installMockApi({
    override: (endpoint, seq, call) =>
      endpoint === "snapshot" ? slow(snapshotAt(seq!), call)
      : endpoint === "metrics" ? slow(metricsAt(seq!), call)
      : endpoint === "cards" ? slow(cardsAt(seq!), call)
      : undefined,
  });
  render(
    <StrictMode>
      <App matchId={MATCH} />
    </StrictMode>,
  );
  const slider = (await screen.findByRole("slider", { name: "Replay position" })) as HTMLInputElement;
  const seen = new Set<string>();
  const status = () => screen.getByRole("status").textContent ?? "";
  for (const seq of [2010, 2030, 2066]) {
    fireEvent.change(slider, { target: { value: String(events.findIndex((e) => e.sequence === seq)) } });
    for (let i = 0; i < 6; i++) {
      seen.add(status());
      await sleep(60);
    }
  }
  expect([...seen].filter(Boolean)).toEqual([]);
});
