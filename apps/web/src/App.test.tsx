import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import {
  API_SCORE, MATCH, events, goalCard, hang, installMockApi, jsonResponse, meta,
  type MockOptions,
} from "./test/mockApi";

afterEach(() => vi.unstubAllGlobals());

const idx = (seq: number) => events.findIndex((e) => e.sequence === seq);
const slider = () => screen.getByRole("slider", { name: "Replay position" });
const goTo = (seq: number) => fireEvent.change(slider(), { target: { value: String(idx(seq)) } });

async function renderApp(opts?: MockOptions) {
  const api = installMockApi(opts);
  render(<App matchId={MATCH} />);
  await screen.findByRole("slider", { name: "Replay position" });
  return api;
}

describe("header", () => {
  it("shows the product name and a synthetic-data badge", async () => {
    await renderApp();
    expect(screen.getByRole("heading", { name: "Match Lens" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic data · fictional teams")).toBeVisible();
  });
});

describe("score", () => {
  it("shows the score from the snapshot response, not counted from events", async () => {
    await renderApp();
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent(String(API_SCORE.home)));
    expect(screen.getByLabelText("Away score")).toHaveTextContent(String(API_SCORE.away));
    const bar = screen.getByRole("region", { name: "Score" });
    expect(within(bar).getByText("Northbridge FC")).toBeInTheDocument();
    expect(within(bar).getByText("Harbour Athletic")).toBeInTheDocument();
  });

  it("shows match clock and period of the watermark event", async () => {
    await renderApp();
    expect(screen.getByLabelText("Match clock")).toHaveTextContent("58:00");
    expect(screen.getByLabelText("Period")).toHaveTextContent("2");
  });
});

describe("pitch", () => {
  it("describes the latest event in its aria-label", async () => {
    await renderApp();
    expect(screen.getByRole("img", { name: /^58:00 Northbridge FC pass, Rowan Locke to Idris Vane/ })).toBeInTheDocument();
  });

  it("draws at most the last 6 events up to the watermark", async () => {
    await renderApp();
    goTo(2020);
    const pitch = screen.getByRole("img", { name: /Northbridge FC|Harbour Athletic/ });
    await waitFor(() => expect(pitch.querySelectorAll("[data-event-id]").length).toBe(6));
    expect(pitch.querySelector('[data-event-id="e020"]')).toHaveAttribute("data-latest", "true");
    expect(pitch.querySelector('[data-event-id="e021"]')).toBeNull();
  });
});

describe("replay controls", () => {
  it("step forward and back change the watermark and request a snapshot for the new at_seq", async () => {
    const user = userEvent.setup();
    const api = await renderApp();
    await waitFor(() => expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2001"));
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(slider()).toHaveValue("1");
    await waitFor(() => expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2002"));
    expect(api.forEndpoint("metrics").at(-1)!.url.searchParams.get("at_seq")).toBe("2002");
    expect(api.forEndpoint("metrics").at(-1)!.url.searchParams.get("window_s")).toBe("60");
    expect(api.forEndpoint("cards").at(-1)!.url.searchParams.get("at_seq")).toBe("2002");
    await user.click(screen.getByRole("button", { name: "Step back" }));
    expect(slider()).toHaveValue("0");
    await waitFor(() => expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2001"));
  });

  it("keeps the in-flight request when stepping forward and aborts it when scrubbing below its at_seq", async () => {
    const user = userEvent.setup();
    const api = await renderApp({
      override: (endpoint, seq, call) => (endpoint === "snapshot" && seq === 2001 ? hang(call) : undefined),
    });
    await waitFor(() => expect(api.forEndpoint("snapshot").length).toBe(1));
    const first = api.forEndpoint("snapshot")[0]!;
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    await new Promise((r) => setTimeout(r, 300));
    expect(first.signal!.aborted).toBe(false);
    expect(api.forEndpoint("snapshot")).toHaveLength(1);
    goTo(2001); // back to the first event: at_seq 2001 is not below 2001, still in flight
    expect(first.signal!.aborted).toBe(false);
  });

  it("debounces rapid watermark changes into one request burst", async () => {
    const api = await renderApp();
    await waitFor(() => expect(api.forEndpoint("snapshot").length).toBe(1));
    goTo(2010);
    goTo(2011);
    goTo(2012);
    await waitFor(() => expect(api.forEndpoint("snapshot").at(-1)!.url.searchParams.get("at_seq")).toBe("2012"));
    expect(api.forEndpoint("snapshot").length).toBeLessThanOrEqual(3);
  });

  it("play advances the replay and the label flips to Pause", async () => {
    const user = userEvent.setup();
    await renderApp();
    await user.click(screen.getByRole("button", { name: "Speed 16x" }));
    await user.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByRole("button", { name: "Pause" })).toBeInTheDocument();
    await waitFor(() => expect(Number((slider() as HTMLInputElement).value)).toBeGreaterThan(0), { timeout: 3000 });
    await user.click(screen.getByRole("button", { name: "Pause" }));
    expect(screen.getByRole("button", { name: "Play" })).toBeInTheDocument();
  });

  it("offers 1x, 4x and 16x speeds", async () => {
    const user = userEvent.setup();
    await renderApp();
    for (const s of ["1x", "4x", "16x"]) {
      await user.click(screen.getByRole("button", { name: `Speed ${s}` }));
      expect(screen.getByRole("button", { name: `Speed ${s}` })).toHaveAttribute("aria-pressed", "true");
    }
  });
});

describe("cards", () => {
  const card = () => screen.queryByRole("article", { name: goalCard.title });

  it("is hidden before trigger_seq, visible from it, hidden after expires_at_ms", async () => {
    // API returns the card regardless of at_seq: the UI must filter by trigger and expiry itself
    await renderApp({ allCards: true });
    goTo(goalCard.trigger_seq - 1);
    await waitFor(() => expect(screen.getByLabelText("Match clock")).toBeInTheDocument());
    expect(card()).toBeNull();

    goTo(goalCard.trigger_seq);
    expect(await screen.findByRole("article", { name: goalCard.title })).toBeInTheDocument();

    goTo(2040); // clock == expires_at_ms: still valid
    expect(card()).toBeInTheDocument();

    goTo(2041); // clock > expires_at_ms
    await waitFor(() => expect(card()).toBeNull());
  });

  it("renders model text as plain text", async () => {
    await renderApp();
    goTo(goalCard.trigger_seq);
    const c = await screen.findByRole("article", { name: goalCard.title });
    expect(within(c).getByText(/<b>not html<\/b>/)).toBeInTheDocument();
    expect(c.querySelector("b")).toBeNull();
    expect(within(c).getByText(/^as of \d\d:\d\d$/)).toBeInTheDocument();
  });

  it("evidence disclosure lists the evidence event ids with time, team, type and player", async () => {
    const user = userEvent.setup();
    await renderApp();
    goTo(goalCard.trigger_seq);
    const c = await screen.findByRole("article", { name: goalCard.title });
    const toggle = within(c).getByText("Evidence (2)");
    await user.click(toggle);
    const e029 = events.find((e) => e.event_id === "e029")!;
    const mm = Math.floor(e029.event_time_ms / 60000);
    const ss = Math.floor((e029.event_time_ms % 60000) / 1000);
    const stamp = `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
    expect(within(c).getByText(new RegExp(`^e029 · ${stamp} · .+ · ${e029.type} · ${meta.players.find((p) => p.id === e029.player_id)!.name}$`))).toBeVisible();
    expect(within(c).getByText(/^e030 ·/)).toBeInTheDocument();
    expect(within(c).getByText(/Goals · Harbour Athletic · 1/)).toBeInTheDocument();
  });
});

describe("metrics", () => {
  it("shows a Last 60 s table with ratios as percent and null as a dash", async () => {
    await renderApp();
    goTo(2050);
    const table = await screen.findByRole("table", { name: "Last 60 s" });
    expect(within(table).getByRole("columnheader", { name: "Northbridge FC" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Harbour Athletic" })).toBeInTheDocument();
    expect(within(table).getByText("44% (4/9)")).toBeInTheDocument();
    const dash = within(table).getByText("–");
    expect(dash).toHaveAttribute("title", "no attempts");
    expect(within(table).getByText("12")).toBeInTheDocument();
  });
});

describe("analysis failure", () => {
  it("keeps the pitch and controls and says analysis is unavailable", async () => {
    const user = userEvent.setup();
    await renderApp({
      override: (endpoint) =>
        endpoint === "snapshot" || endpoint === "metrics" || endpoint === "cards"
          ? jsonResponse({ code: "INTERNAL", message: "down" }, 500)
          : undefined,
    });
    expect(await screen.findByText(/analysis unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Northbridge FC pass/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(slider()).toHaveValue("1");
    expect(screen.getByRole("img", { name: /Northbridge FC pass, Idris Vane to Tomas Reed/ })).toBeInTheDocument();
  });

  it("keeps the last good score while the next snapshot is failing", async () => {
    const user = userEvent.setup();
    await renderApp({
      override: (endpoint, seq) =>
        endpoint === "snapshot" && seq !== 2001 ? jsonResponse({ code: "INTERNAL", message: "x" }, 500) : undefined,
    });
    await waitFor(() => expect(screen.getByLabelText("Home score")).toHaveTextContent("4"));
    await user.click(screen.getByRole("button", { name: "Step forward" }));
    expect(await screen.findByText(/analysis unavailable/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Home score")).toHaveTextContent("4");
  });
});

describe("load failure", () => {
  it("shows a message and a retry button when meta cannot load, then recovers", async () => {
    const user = userEvent.setup();
    let fail = true;
    installMockApi({
      override: (endpoint) =>
        fail && endpoint === "meta" ? jsonResponse({ code: "UNKNOWN_MATCH", message: "no match" }, 404) : undefined,
    });
    render(<App matchId={MATCH} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/no match/);
    fail = false;
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("slider", { name: "Replay position" })).toBeInTheDocument();
  });
});
