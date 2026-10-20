import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { useAnalysis } from "./hooks";
import { Pitch } from "./components/Pitch";
import { MATCH, events, installMockApi, jsonResponse, meta, type MockOptions } from "./test/mockApi";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const idx = (seq: number) => events.findIndex((e) => e.sequence === seq);
const slider = () => screen.getByRole("slider", { name: "Replay position" }) as HTMLInputElement;
const goTo = (seq: number) => fireEvent.change(slider(), { target: { value: String(idx(seq)) } });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function renderApp(opts?: MockOptions) {
  const api = installMockApi(opts);
  render(<App matchId={MATCH} />);
  await screen.findByRole("slider", { name: "Replay position" });
  return api;
}

describe("1. liveness under backend latency", () => {
  it("applies responses during 16x-style playback when latency exceeds the step interval", async () => {
    vi.useFakeTimers();
    installMockApi();
    // add 150 ms latency on top of the mock
    const inner = globalThis.fetch;
    vi.stubGlobal("fetch", async (...a: Parameters<typeof fetch>) => {
      await new Promise((r) => setTimeout(r, 150));
      return inner(...a);
    });
    const { result, rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), {
      initialProps: { seq: 2001 },
    });
    const seen = new Set<number>();
    const seenMetrics = new Set<string>();
    for (let i = 1; i <= 24; i++) {
      await vi.advanceTimersByTimeAsync(125);
      const seq = 2001 + i;
      rerender({ seq });
      const s = result.current.snapshot;
      if (s) {
        seen.add(s.watermark_seq);
        expect(s.watermark_seq).toBeLessThanOrEqual(seq);
      }
      if (result.current.metrics) seenMetrics.add(result.current.metrics.snapshot_id);
    }
    expect(seen.size).toBeGreaterThanOrEqual(5);
    expect(seenMetrics.size).toBeGreaterThanOrEqual(5);
  });

  it("never applies a response for a seq past the watermark", async () => {
    vi.useFakeTimers();
    installMockApi();
    const inner = globalThis.fetch;
    vi.stubGlobal("fetch", async (...a: Parameters<typeof fetch>) => {
      await new Promise((r) => setTimeout(r, 150));
      return inner(...a);
    });
    const { result, rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), {
      initialProps: { seq: 2030 },
    });
    await vi.advanceTimersByTimeAsync(20);
    rerender({ seq: 2010 }); // scrub back while the 2030 request is in flight
    await vi.advanceTimersByTimeAsync(400);
    expect(result.current.snapshot?.watermark_seq ?? 0).toBeLessThanOrEqual(2010);
  });
});

describe("2/3. live region", () => {
  it("announces an outage once, not per step", async () => {
    const user = userEvent.setup();
    let fail = false;
    await renderApp({
      override: (ep) =>
        fail && ep !== "events" && ep !== "meta" ? jsonResponse({ code: "INTERNAL", message: "x" }, 500) : undefined,
    });
    const status = screen.getByRole("status");
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent("4"));
    fail = true;
    let mutations = 0;
    const mo = new MutationObserver((l) => (mutations += l.length));
    mo.observe(status, { childList: true, characterData: true, subtree: true });
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent("Analysis unavailable"));
    for (let i = 0; i < 5; i++) {
      await user.click(screen.getByRole("button", { name: "Step forward" }));
      await sleep(260);
    }
    await sleep(100);
    mo.disconnect();
    expect(status).toHaveTextContent("Analysis unavailable");
    expect(mutations).toBe(1);
  });

  it("restored is announced once and clears after the next successful update", async () => {
    const user = userEvent.setup();
    let fail = false;
    await renderApp({
      override: (ep) =>
        fail && ep !== "events" && ep !== "meta" ? jsonResponse({ code: "INTERNAL", message: "x" }, 500) : undefined,
    });
    const status = screen.getByRole("status");
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent("4"));
    fail = true;
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent("Analysis unavailable"));
    fail = false;
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent("Analysis restored"));
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent(/^$/));
  });
});

describe("4. throttling", () => {
  it("coalesces rapid watermark changes: the intermediate at_seq is never requested", async () => {
    const api = await renderApp();
    await waitFor(() => expect(api.forEndpoint("snapshot").length).toBe(1));
    goTo(2010);
    goTo(2011);
    goTo(2012);
    await waitFor(() => expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2012"));
    const seqs = api.forEndpoint("snapshot").map((c) => c.url.searchParams.get("at_seq"));
    expect(seqs).not.toContain("2011");
  });
});

describe("5. metrics caption comes from the metrics' own seq", () => {
  it("shows 'Since period start' for early metrics even when the watermark moved past 60 s", async () => {
    await renderApp({
      override: (ep, seq) =>
        ep === "metrics" && seq !== null && seq > 2001 ? new Promise<Response>(() => {}) : undefined,
    });
    expect(await screen.findByRole("table", { name: "Since period start" })).toBeInTheDocument();
    goTo(2050);
    await sleep(450);
    expect(screen.getByRole("table", { name: "Since period start" })).toBeInTheDocument();
  });
});

describe("6. unknown-team warning is per component instance", () => {
  it("warns once per instance", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const odd = events.map((e) => (e.event_id === "e001" ? { ...e, team_id: "zzz" } : e));
    const a = render(<Pitch events={odd} index={2} meta={meta} />);
    a.rerender(<Pitch events={odd} index={3} meta={meta} />);
    expect(warn).toHaveBeenCalledTimes(1);
    render(<Pitch events={odd} index={2} meta={meta} />);
    expect(warn).toHaveBeenCalledTimes(2);
  });
});
