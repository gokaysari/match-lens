import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import { MetricsPanel, metricsCaption } from "./components/MetricsPanel";
import { REQUEST_TIMEOUT_MS, useAnalysis } from "./hooks";
import { MATCH, hang, installMockApi, meta, metricsAt } from "./test/mockApi";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("stuck request after a quick scrub", () => {
  it("fetches 100 after 100 -> 99 -> 100 within the throttle", async () => {
    vi.useFakeTimers();
    const api = installMockApi({ override: (ep, _s, call) => (ep === "snapshot" ? hang(call) : undefined) });
    const { rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2020 } });
    await vi.advanceTimersByTimeAsync(10);
    rerender({ seq: 2019 });
    await vi.advanceTimersByTimeAsync(10);
    rerender({ seq: 2020 });
    await vi.advanceTimersByTimeAsync(400);
    const ats = api.forEndpoint("snapshot").map((r) => r.url.searchParams.get("at_seq"));
    expect(ats.at(-1)).toBe("2020");
    expect(ats.length).toBeGreaterThanOrEqual(2);
  });

  it("retries once after a timeout while paused", async () => {
    vi.useFakeTimers();
    let first = true;
    const api = installMockApi({
      override: (ep, _s, call) => {
        if (ep !== "snapshot" || !first) return undefined;
        first = false;
        return hang(call);
      },
    });
    const { result } = renderHook(() => useAnalysis(MATCH, 2020));
    await act(async () => { await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 3000); });
    expect(api.forEndpoint("snapshot")).toHaveLength(2);
    expect(result.current.snapshot?.watermark_seq).toBe(2020);
    expect(result.current.status).toBe("ready");
  });

  it("does not retry forever when every attempt times out", async () => {
    vi.useFakeTimers();
    const api = installMockApi({ override: (ep, _s, call) => (ep === "snapshot" ? hang(call) : undefined) });
    renderHook(() => useAnalysis(MATCH, 2020));
    await act(async () => { await vi.advanceTimersByTimeAsync(4 * REQUEST_TIMEOUT_MS); });
    expect(api.forEndpoint("snapshot")).toHaveLength(2);
  });
});

describe("matchId change", () => {
  it("aborts in flight, resets state and fetches for the new match", async () => {
    vi.useFakeTimers();
    const api = installMockApi();
    const { result, rerender } = renderHook(({ id }) => useAnalysis(id, 2020), { initialProps: { id: MATCH } });
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(result.current.snapshot).not.toBeNull();
    rerender({ id: "other-match" });
    expect(result.current.snapshot).toBeNull();
    expect(result.current.metrics).toBeNull();
    expect(result.current.cards).toEqual([]);
    expect(result.current.settled).toBeNull();
    await vi.advanceTimersByTimeAsync(50);
    expect(api.forEndpoint("snapshot").at(-1)!.url.pathname).toContain("other-match");
  });
});

describe("as-of label contrast", () => {
  it("keeps the as-of label outside any element with reduced opacity", () => {
    const m = metricsAt(2020);
    render(<MetricsPanel metrics={m} meta={meta} staleAsOfMs={m.window_end_ms - 5000} />);
    const asof = screen.getByText(/^as of /);
    for (let el: HTMLElement | null = asof; el; el = el.parentElement) {
      expect(el.classList.contains("stale")).toBe(false);
      expect(el.classList.contains("stale-value")).toBe(false);
    }
    expect(screen.getByRole("table").closest(".stale-value")).not.toBeNull();
  });
});

describe("metrics caption", () => {
  const seg = 58 * 60000;
  it("normal window", () => expect(metricsCaption(seg + 1000, seg, 1)).toBe("Last 60 s"));
  it("segment start", () =>
    expect(metricsCaption(seg - 5000, seg, 2)).toBe("Last 60 s · since 58:00 (replay start)"));
  it("period boundary", () =>
    expect(metricsCaption(45 * 60000 - 10000, 40 * 60000, 2)).toBe("Last 60 s · since 45:00 (period start)"));
  it("table name follows the caption", () => {
    const m = { ...metricsAt(2020), window_start_ms: meta.segment_start_ms - 1000 };
    render(<MetricsPanel metrics={m} meta={meta} staleAsOfMs={null} />);
    expect(screen.getByRole("table", { name: /^Last 60 s · since .* \(replay start\)$/ })).toBeInTheDocument();
  });
});
