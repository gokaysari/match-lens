import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import App from "./App";
import { CardsPanel } from "./components/CardsPanel";
import { CASING_COLOR, GRASS_COLOR, Pitch, TEAM_COLORS } from "./components/Pitch";
import { REQUEST_TIMEOUT_MS, useAnalysis } from "./hooks";
import { metricLabel } from "./lib/format";
import {
  MATCH, events, goalCard, hang, installMockApi, jsonResponse, meta, metricsAt, type MockOptions,
} from "./test/mockApi";

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

function withLatency(ms: number) {
  const inner = globalThis.fetch;
  vi.stubGlobal("fetch", async (...a: Parameters<typeof fetch>) => {
    await new Promise((r) => setTimeout(r, ms));
    return inner(...a);
  });
}

describe("liveness: one request in flight, chained", () => {
  it("applies several responses with 300 ms latency and 125 ms steps, never past the watermark, and fetches the final watermark", async () => {
    vi.useFakeTimers();
    const api = installMockApi();
    withLatency(300);
    const { result, rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2001 } });
    const seen = new Set<number>();
    for (let i = 1; i <= 24; i++) {
      await vi.advanceTimersByTimeAsync(125);
      const seq = 2001 + i;
      rerender({ seq });
      const s = result.current.snapshot;
      if (s) {
        seen.add(s.watermark_seq);
        expect(s.watermark_seq).toBeLessThanOrEqual(seq);
      }
    }
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(seen.size).toBeGreaterThanOrEqual(5);
    expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2025");
    expect(result.current.snapshot?.watermark_seq).toBe(2025);
  });

  it("never has two snapshot requests in flight while the watermark only moves forward", async () => {
    vi.useFakeTimers();
    let open = 0, maxOpen = 0;
    installMockApi({
      override: (ep) => {
        if (ep === "snapshot") { open++; maxOpen = Math.max(maxOpen, open); }
        return undefined;
      },
    });
    const inner = globalThis.fetch;
    vi.stubGlobal("fetch", async (...a: Parameters<typeof fetch>) => {
      await new Promise((r) => setTimeout(r, 300));
      const r = await inner(...a);
      if (String(a[0]).includes("/snapshot")) open--;
      return r;
    });
    const { rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2001 } });
    for (let i = 1; i <= 24; i++) {
      await vi.advanceTimersByTimeAsync(125);
      rerender({ seq: 2001 + i });
    }
    expect(maxOpen).toBe(1);
  });

  it("aborts the in-flight request only when the watermark moves below its at_seq", async () => {
    vi.useFakeTimers();
    const api = installMockApi({ override: (ep, _s, call) => (ep === "snapshot" ? hang(call) : undefined) });
    const { rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2020 } });
    await vi.advanceTimersByTimeAsync(10);
    rerender({ seq: 2025 });
    await vi.advanceTimersByTimeAsync(300);
    expect(api.forEndpoint("snapshot")).toHaveLength(1);
    expect(api.forEndpoint("snapshot")[0]!.signal!.aborted).toBe(false);
    rerender({ seq: 2010 });
    await vi.advanceTimersByTimeAsync(300);
    expect(api.forEndpoint("snapshot")[0]!.signal!.aborted).toBe(true);
    expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2010");
  });

  it("gives up on a request that never answers so later positions are still fetched", async () => {
    vi.useFakeTimers();
    let first = true;
    const api = installMockApi({
      override: (ep, _s, call) => {
        if (ep !== "snapshot" || !first) return undefined;
        first = false;
        return hang(call);
      },
    });
    const { result, rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2001 } });
    await vi.advanceTimersByTimeAsync(10);
    rerender({ seq: 2002 });
    await act(async () => { await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS + 500); });
    expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2002");
    expect(result.current.snapshot?.watermark_seq).toBe(2002);
  });
});

describe("metric labels and copy", () => {
  it("maps metric names to readable labels", () => {
    expect(metricLabel("pressures_opp_half")).toBe("Pressures in opponent half");
    expect(metricLabel("high_ball_wins")).toBe("Ball wins in opponent half");
    expect(metricLabel("something_new")).toBe("something new");
  });

  it("panel heading is 'Fact cards'", async () => {
    await renderApp();
    expect(screen.getByRole("heading", { name: "Fact cards" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Insight cards" })).toBeNull();
  });

  it("shows 'not reported' for a missing metric and a dash with a title only for a null value", async () => {
    await renderApp({
      override: (ep, seq) => {
        if (ep !== "metrics") return undefined;
        const m = metricsAt(seq!);
        m.metrics = m.metrics.filter((x) => !(x.name === "pressures" && x.team_id === "hba"));
        return jsonResponse(m);
      },
    });
    const table = await screen.findByRole("table", { name: "Last 60 s" });
    expect(within(table).getByText("not reported")).toBeInTheDocument();
    expect(within(table).getByText("–")).toHaveAttribute("title", "no attempts");
  });
});

describe("staleness", () => {
  it("shows 'as of mm:ss' and dims score and metrics while the shown analysis is behind the watermark", async () => {
    await renderApp({
      override: (ep, seq) =>
        ep !== "events" && ep !== "meta" && seq !== null && seq > 2001 ? new Promise<Response>(() => {}) : undefined,
    });
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent("4"));
    const bar = screen.getByRole("region", { name: "Score" });
    expect(within(bar).queryByText(/^as of/)).toBeNull();
    goTo(2010);
    expect(within(bar).getByText("as of 58:00")).toBeInTheDocument();
    expect(bar.querySelector(".score")).toHaveClass("stale");
    const metrics = screen.getByRole("region", { name: "Metrics" });
    expect(within(metrics).getByText("as of 58:00")).toBeInTheDocument();
    expect(metrics).toHaveClass("stale");
  });
});

describe("polite announcements", () => {
  const goalScore = (seq: number) => (seq >= 2035 ? { home: 0, away: 1 } : { home: 0, away: 0 });
  const announcer = () => screen.getByTestId("announcer");

  it("announces a new card title and a score change, not plain steps, separate from the outage region", async () => {
    await renderApp({ scoreFor: goalScore });
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent("0"));
    expect(announcer()).toHaveAttribute("aria-live", "polite");
    expect(announcer()).toHaveTextContent(/^$/);
    expect(screen.getByRole("status")).not.toBe(announcer());
    goTo(2035);
    await waitFor(() => expect(announcer()).toHaveTextContent("Goal for Harbour Athletic"));
    expect(announcer()).toHaveTextContent("Score is now 0 to 1");
    let changed = 0;
    const mo = new MutationObserver(() => { changed++; });
    mo.observe(announcer(), { childList: true, characterData: true, subtree: true });
    fireEvent.click(screen.getByRole("button", { name: "Step forward" }));
    await sleep(450);
    mo.disconnect();
    expect(changed).toBe(0);
  });
});

describe("pitch legibility", () => {
  const ratio = (a: string, b: string) => {
    const lum = (hex: string) => {
      const c = [1, 3, 5]
        .map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
        .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return 0.2126 * c[0]! + 0.7152 * c[1]! + 0.0722 * c[2]!;
    };
    const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
    return (hi! + 0.05) / (lo! + 0.05);
  };

  it("casing reaches 3:1 on the grass and both team colours reach 3:1 on the casing", () => {
    expect(ratio(CASING_COLOR, GRASS_COLOR)).toBeGreaterThanOrEqual(3);
    expect(ratio(TEAM_COLORS.home, CASING_COLOR)).toBeGreaterThanOrEqual(3);
    expect(ratio(TEAM_COLORS.away, CASING_COLOR)).toBeGreaterThanOrEqual(3);
  });

  it("draws a wider casing line under a pass line, and casing under pressure rings and arrowheads", () => {
    const pass = events.find((e) => e.type === "pass" && e.end_x !== null)!;
    const a = render(<Pitch events={events} index={idx(pass.sequence)} meta={meta} />);
    const g = a.container.querySelector(`[data-event-id="${pass.event_id}"]`)!;
    const lines = [...g.querySelectorAll("line")];
    expect(lines).toHaveLength(2);
    expect(lines[0]).toHaveAttribute("data-casing", "true");
    expect(Number(lines[0]!.getAttribute("stroke-width"))).toBeGreaterThan(Number(lines[1]!.getAttribute("stroke-width")));
    expect(a.container.querySelector("#arrow-home path")!.getAttribute("stroke")).toBe(CASING_COLOR);
    a.unmount();
    const press = events.find((e) => e.type === "pressure" && e.x !== null)!;
    const b = render(<Pitch events={events} index={idx(press.sequence)} meta={meta} />);
    const rings = b.container.querySelectorAll(`[data-event-id="${press.event_id}"] circle`);
    expect(rings).toHaveLength(2);
    expect(rings[0]).toHaveAttribute("data-casing", "true");
  });

  it("separates teams by shape and dash, not only colour", () => {
    const awayP = events.find((e) => e.team_id === "hba" && e.type === "pressure")!;
    const homeEvents = events.map((e) => (e.event_id === awayP.event_id ? { ...e, team_id: "nbr" } : e));
    const ring = (list: typeof events) => {
      const { container, unmount } = render(<Pitch events={list} index={idx(awayP.sequence)} meta={meta} />);
      const dash = container.querySelector(`[data-event-id="${awayP.event_id}"] circle:not([data-casing])`)!.getAttribute("stroke-dasharray");
      unmount();
      return dash;
    };
    expect(ring(homeEvents)).not.toBe(ring(events));
    const away = events.find((e) => e.team_id === "hba" && e.type === "pass")!;
    const a = render(<Pitch events={events} index={idx(away.sequence)} meta={meta} />);
    expect(a.container.querySelector(`[data-event-id="${away.event_id}"] rect[data-shape="square"]`)).not.toBeNull();
    a.unmount();
    const home = events.find((e) => e.team_id === "nbr" && e.type === "pass")!;
    const h = render(<Pitch events={events} index={idx(home.sequence)} meta={meta} />);
    expect(h.container.querySelector(`[data-event-id="${home.event_id}"] circle:not([data-casing])`)).not.toBeNull();
    expect(h.container.querySelector(`[data-event-id="${home.event_id}"] rect[data-shape="square"]`)).toBeNull();
  });
});

describe("evidence outside the snapshot", () => {
  it("marks later and unknown evidence ids instead of showing a normal row", () => {
    const card = { ...goalCard, evidence_event_ids: ["e029", "e031", "e999"] };
    render(<CardsPanel cards={[card]} events={events} meta={meta} watermarkSeq={2035} clockMs={events[idx(2035)]!.event_time_ms} />);
    const c = screen.getByRole("article", { name: card.title });
    expect(within(c).getByText(/^e029 · \d\d:\d\d · /)).toBeInTheDocument();
    expect(within(c).getByText("e031 · outside snapshot")).toBeInTheDocument();
    expect(within(c).getByText("e999 · unknown event")).toBeInTheDocument();
  });

  it("shows 'as of mm:ss' and no snapshot sequence", () => {
    render(<CardsPanel cards={[goalCard]} events={events} meta={meta} watermarkSeq={2035} clockMs={events[idx(2035)]!.event_time_ms} />);
    expect(screen.queryByText(/snapshot @/)).toBeNull();
    expect(screen.getByText(/^as of \d\d:\d\d$/)).toBeInTheDocument();
  });
});

describe("meta validation", () => {
  it("shows the load-error panel when a team is missing", async () => {
    installMockApi({
      override: (ep) =>
        ep === "meta" ? jsonResponse({ ...meta, teams: meta.teams.filter((t) => t.side === "home") }) : undefined,
    });
    render(<App matchId={MATCH} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/home and away team/i);
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
