import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { useAnalysis } from "./hooks";
import { Pitch } from "./components/Pitch";
import {
  MATCH, events, hang, installMockApi, jsonResponse, meta, snapshotAt, type MockOptions,
} from "./test/mockApi";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const idx = (seq: number) => events.findIndex((e) => e.sequence === seq);
const slider = () => screen.getByRole("slider", { name: "Replay position" }) as HTMLInputElement;
const goTo = (seq: number) => fireEvent.change(slider(), { target: { value: String(idx(seq)) } });
const score = (side: "Home" | "Away") => screen.getByLabelText(`${side} score`);

async function renderApp(opts?: MockOptions) {
  const api = installMockApi(opts);
  render(<App matchId={MATCH} />);
  await screen.findByRole("slider", { name: "Replay position" });
  return api;
}

const goalScore = (seq: number) => (seq >= 2066 ? { home: 0, away: 1 } : { home: 0, away: 0 });

describe("1. never show analysis from past the watermark", () => {
  it("hides the post-goal score when scrubbing back while the new request hangs", async () => {
    await renderApp({
      scoreFor: goalScore,
      override: (ep, seq, call) => (ep === "snapshot" && seq === 2060 ? hang(call) : undefined),
    });
    goTo(2066);
    await waitFor(() => expect(score("Away")).toHaveTextContent("1"));
    goTo(2060);
    expect(score("Away")).toHaveTextContent("–");
    expect(screen.getByText("No metrics yet.")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 450));
    expect(score("Away")).toHaveTextContent("–");
  });

  it("hides the post-goal score when scrubbing back while the new request fails", async () => {
    await renderApp({
      scoreFor: goalScore,
      override: (ep, seq) =>
        ep !== "events" && ep !== "meta" && seq === 2060 ? jsonResponse({ code: "INTERNAL", message: "x" }, 500) : undefined,
    });
    goTo(2066);
    await waitFor(() => expect(score("Away")).toHaveTextContent("1"));
    goTo(2060);
    expect(await screen.findByText(/analysis unavailable/i)).toBeInTheDocument();
    expect(score("Away")).toHaveTextContent("–");
    expect(screen.getByText("No metrics yet.")).toBeInTheDocument();
  });

  it("drops a response whose snapshot_id does not match the requested at_seq", async () => {
    await renderApp({
      override: (ep, seq) =>
        ep === "snapshot" ? jsonResponse(snapshotAt((seq as number) + 1, { home: 9, away: 9 })) : undefined,
    });
    expect(await screen.findByText(/analysis unavailable/i)).toBeInTheDocument();
    expect(score("Home")).toHaveTextContent("–");
  });
});

describe("4. late responses are not rendered", () => {
  it("ignores a response that ignores the abort signal and resolves after the watermark moved", async () => {
    const user = userEvent.setup();
    let resolveLate: () => void = () => {};
    const api = await renderApp({
      override: (ep, seq) =>
        ep === "snapshot" && seq === 2001
          ? new Promise<Response>((res) => {
              resolveLate = () => res(jsonResponse(snapshotAt(2001, { home: 9, away: 9 })));
            })
          : undefined,
    });
    await waitFor(() => expect(api.forEndpoint("snapshot").length).toBe(1));
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await act(async () => {
      resolveLate();
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(score("Home")).toHaveTextContent("–");
    await waitFor(() => expect(score("Home")).toHaveTextContent("4"));
  });
});

describe("2. throttle", () => {
  it("issues requests at least every ~200 ms while stepping every 50 ms, and fetches the final watermark", async () => {
    vi.useFakeTimers();
    const times: number[] = [];
    const api = installMockApi({
      override: (ep) => {
        if (ep === "snapshot") times.push(Date.now());
        return undefined;
      },
    });
    const { rerender } = renderHook(({ seq }) => useAnalysis(MATCH, seq), { initialProps: { seq: 2001 } });
    for (let i = 1; i <= 40; i++) {
      await vi.advanceTimersByTimeAsync(50);
      rerender({ seq: 2001 + i });
    }
    await vi.advanceTimersByTimeAsync(400);
    expect(times.length).toBeGreaterThanOrEqual(8);
    expect(times.length).toBeLessThanOrEqual(14);
    const gaps = times.slice(1).map((t, i) => t - times[i]!);
    expect(Math.max(...gaps)).toBeLessThanOrEqual(250);
    expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2041");
  });
});

describe("3. pitch geometry", () => {
  const ev = (seq: number) => events.findIndex((e) => e.sequence === seq);
  const flipped = (c: HTMLElement) => c.querySelector("svg > g[transform]");

  it("flips y so the contract origin is bottom-left", () => {
    const { container } = render(<Pitch events={events} index={0} meta={meta} />);
    expect(flipped(container)).toHaveAttribute("transform", "translate(0,68) scale(1,-1)");
  });

  it("draws a home pass toward larger x with x2/y2 = end_x/end_y", () => {
    const e = events[0]!;
    const { container } = render(<Pitch events={events} index={ev(e.sequence)} meta={meta} />);
    const g = container.querySelector(`[data-event-id="${e.event_id}"]`)!;
    const line = g.querySelector("line")!;
    expect(line).toHaveAttribute("x1", String(e.x));
    expect(line).toHaveAttribute("y1", String(e.y));
    expect(line).toHaveAttribute("x2", String(e.end_x));
    expect(line).toHaveAttribute("y2", String(e.end_y));
  });

  it("draws an away event with no mirroring", () => {
    const e = events.find((x) => x.team_id === "hba" && x.type === "pressure")!;
    const { container } = render(<Pitch events={events} index={ev(e.sequence)} meta={meta} />);
    const circle = container.querySelector(`[data-event-id="${e.event_id}"] circle`)!;
    expect(circle).toHaveAttribute("cx", String(e.x));
    expect(circle).toHaveAttribute("cy", String(e.y));
  });

  it("11. skips events of an unknown team and warns once", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const odd = events.map((e) => (e.event_id === "e001" || e.event_id === "e002" ? { ...e, team_id: "zzz" } : e));
    const { container } = render(<Pitch events={odd} index={3} meta={meta} />);
    expect(container.querySelector('[data-event-id="e001"]')).toBeNull();
    expect(container.querySelector('[data-event-id="e002"]')).toBeNull();
    expect(container.querySelector('[data-event-id="e003"]')).not.toBeNull();
    expect(warn).toHaveBeenCalledTimes(1);
  });
});

describe("5/6. metrics panel", () => {
  it("renders pressures_opp_half as a row", async () => {
    await renderApp();
    const table = await screen.findByRole("table");
    const row = within(table).getByRole("row", { name: /pressures opp half/i });
    expect(within(row).getByText("6")).toBeInTheDocument();
    expect(within(row).getByText("7")).toBeInTheDocument();
  });

  it("caption is 'Since period start' in the first 60 s of a period and 'Last 60 s' after", async () => {
    await renderApp();
    expect(await screen.findByRole("table", { name: "Since period start" })).toBeInTheDocument();
    const later = events.find((e) => e.event_time_ms - events[0]!.event_time_ms >= 60000)!;
    goTo(later.sequence);
    expect(await screen.findByRole("table", { name: "Last 60 s" })).toBeInTheDocument();
  });
});

describe("7. player names", () => {
  it("uses meta.players names in the pitch aria-label", async () => {
    await renderApp();
    expect(screen.getByRole("img", { name: /^58:00 Northbridge FC pass, Rowan Locke to Idris Vane/ })).toBeInTheDocument();
  });
});

describe("8. button names contain their visible text", () => {
  it("every button's accessible name includes its visible text", async () => {
    await renderApp();
    for (const b of screen.getAllByRole("button")) {
      const visible = (b.textContent ?? "").trim();
      const hidden = b.querySelector('[aria-hidden="true"]');
      if (!visible || (hidden && hidden.textContent === visible && !/[A-Za-z0-9]/.test(visible))) continue;
      const name = (b.getAttribute("aria-label") ?? visible).toLowerCase();
      for (const word of visible.match(/[A-Za-z0-9]+/g) ?? []) {
        expect(name, `${b.outerHTML}`).toContain(word.toLowerCase());
      }
    }
    expect(screen.getByRole("button", { name: "Step forward" })).toHaveTextContent("Step forward");
    expect(screen.getByRole("button", { name: "Step back" })).toHaveTextContent("Step back");
  });
});

describe("9. live region", () => {
  it("does not announce Updating on each step, only unavailable and recovery", async () => {
    const user = userEvent.setup();
    let fail = false;
    await renderApp({
      override: (ep) =>
        fail && ep !== "events" && ep !== "meta" ? jsonResponse({ code: "INTERNAL", message: "x" }, 500) : undefined,
    });
    const status = screen.getByRole("status");
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(status).not.toHaveTextContent(/updating/i);
    await waitFor(() => expect(score("Home")).toHaveTextContent("4"));
    fail = true;
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent(/analysis unavailable/i));
    fail = false;
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await waitFor(() => expect(status).toHaveTextContent(/analysis restored/i));
  });
});

describe("10. play at the last event", () => {
  it("restarts from the first event", async () => {
    const user = userEvent.setup();
    await renderApp();
    await user.click(screen.getByRole("button", { name: "Speed 16x" }));
    fireEvent.change(slider(), { target: { value: String(events.length - 1) } });
    await user.click(screen.getByRole("button", { name: "Play" }));
    expect(Number(slider().value)).toBeLessThan(events.length - 1);
    expect(Number(slider().value)).toBeLessThanOrEqual(1);
    await user.click(screen.getByRole("button", { name: "Pause" }));
  });
});
