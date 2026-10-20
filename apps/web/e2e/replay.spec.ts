import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const MATCH = "synthetic-01";
const API = `http://127.0.0.1:8000/api/matches/${MATCH}`;

interface Ev { event_id: string; sequence: number; event_time_ms: number }
interface CardDto { title: string; body: string; expires_at_ms: number; evidence_event_ids: string[] }

async function loadEvents(request: APIRequestContext): Promise<Ev[]> {
  const res = await request.get(`${API}/events`);
  expect(res.ok()).toBeTruthy();
  return (await res.json()).events;
}

const indexOf = (events: Ev[], id: string) => {
  const i = events.findIndex((e) => e.event_id === id);
  expect(i, `event ${id} exists`).toBeGreaterThanOrEqual(0);
  return i;
};

const slider = (page: Page) => page.getByRole("slider", { name: "Replay position" });
const goalCard = (page: Page) => page.getByRole("article", { name: "Goal - Harbour Athletic" });
const pressCard = (page: Page) => page.getByRole("article", { name: "Harbour Athletic press high" });

async function expectScore(page: Page, home: string, away: string) {
  await expect(page.getByLabel("Home score")).toHaveText(home);
  await expect(page.getByLabel("Away score")).toHaveText(away);
}

async function goTo(page: Page, index: number) {
  await slider(page).fill(String(index));
  await expect(slider(page)).toHaveValue(String(index));
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Synthetic data · fictional teams")).toBeVisible();
  await expect(slider(page)).toBeVisible();
});

test("1 load: badge, teams, 0-0, pitch", async ({ page }) => {
  await expect(page.getByText("Northbridge FC", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Harbour Athletic", { exact: true }).first()).toBeVisible();
  await expectScore(page, "0", "0");
  await expect(slider(page)).toHaveValue("0");
  await expect(page.getByRole("img").first()).toHaveAccessibleName(/\S/);
});

test("2 scrub to the goal: 0-1, goal card, evidence", async ({ page, request }) => {
  const events = await loadEvents(request);
  const cards: CardDto[] = (await (await request.get(`${API}/cards?at_seq=2066`)).json()).cards;
  const goal = cards.find((c) => c.title === "Goal - Harbour Athletic")!;
  await goTo(page, indexOf(events, "e066"));
  await expectScore(page, "0", "1");
  const card = goalCard(page);
  await expect(card).toBeVisible();
  await card.getByText(`Evidence (${goal.evidence_event_ids.length})`).click();
  const items = card.getByRole("listitem");
  for (const id of ["e063", "e064", "e065", "e066"]) {
    await expect(items.filter({ hasText: new RegExp(`^${id} `) })).toHaveCount(1);
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: "e2e/artifacts/goal-1280x800.png", fullPage: true });
});

test("3 scrub back before the goal: 0-0, no goal card, 0-1 never shown", async ({ page, request }) => {
  const events = await loadEvents(request);
  await goTo(page, indexOf(events, "e066"));
  await expectScore(page, "0", "1");
  // Record every value the away score shows from now on.
  await page.evaluate(() => {
    const w = window as unknown as { __seen: string[] };
    w.__seen = [];
    const el = document.querySelector('[aria-label="Away score"]')!;
    new MutationObserver(() => w.__seen.push(el.textContent ?? "")).observe(el, {
      childList: true, characterData: true, subtree: true,
    });
  });
  await goTo(page, indexOf(events, "e030"));
  await page.waitForLoadState("networkidle");
  await expectScore(page, "0", "0");
  const seen = await page.evaluate(() => (window as unknown as { __seen: string[] }).__seen);
  expect(seen).not.toContain("1");
  await expect(goalCard(page)).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  await expectScore(page, "0", "0");
  await expect(page.getByLabel("Away score")).not.toHaveText("1");
});

test("4 press card matches the API at e058, absent at e057", async ({ page, request }) => {
  const events = await loadEvents(request);
  const cards: CardDto[] = (await (await request.get(`${API}/cards?at_seq=2058`)).json()).cards;
  const press = cards.find((c) => c.title === "Harbour Athletic press high")!;
  expect(press).toBeTruthy();
  await goTo(page, indexOf(events, "e057"));
  await page.waitForLoadState("networkidle");
  await expect(pressCard(page)).toHaveCount(0);
  await goTo(page, indexOf(events, "e058"));
  const card = pressCard(page);
  await expect(card).toBeVisible();
  await expect(card.getByText(press.body, { exact: true })).toBeVisible();
  await expect(card.getByText(`Evidence (${press.evidence_event_ids.length})`)).toBeVisible();
});

test("5 press card expires after 45 s of match clock", async ({ page, request }) => {
  const events = await loadEvents(request);
  const cards: CardDto[] = (await (await request.get(`${API}/cards?at_seq=2058`)).json()).cards;
  const press = cards.find((c) => c.title === "Harbour Athletic press high")!;
  const firstExpired = events.findIndex((e) => e.event_time_ms > press.expires_at_ms);
  expect(firstExpired).toBeGreaterThan(indexOf(events, "e058"));
  await goTo(page, firstExpired - 1);
  await expect(pressCard(page)).toBeVisible();
  await goTo(page, firstExpired);
  await expect(pressCard(page)).toHaveCount(0);
});

test("6 playback at 16x reaches the goal without scrubbing", async ({ page, request }) => {
  test.setTimeout(90_000);
  const events = await loadEvents(request);
  const goalIdx = indexOf(events, "e066");
  await page.getByRole("button", { name: "Speed 16x" }).click();
  await expect(page.getByRole("button", { name: "Speed 16x" })).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.getByRole("button", { name: "Pause" })).toBeVisible();
  await expect
    .poll(async () => Number(await slider(page).inputValue()), { timeout: 60_000 })
    .toBeGreaterThan(goalIdx);
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByRole("button", { name: "Play" })).toBeVisible();
  await expectScore(page, "0", "1");
  await expect(goalCard(page)).toBeVisible();
});

test("7 analysis outage: fallback shown, pitch keeps updating, then restored", async ({ page }) => {
  const pitch = page.getByRole("img").first();
  await goTo(page, 3);
  await expectScore(page, "0", "0");
  const before = await pitch.getAttribute("aria-label");
  const pattern = /\/api\/matches\/[^/]+\/(snapshot|cards|metrics)/;
  await page.route(pattern, (route) => route.abort());
  await page.getByRole("button", { name: "Step forward" }).click();
  await expect(slider(page)).toHaveValue("4");
  await expect(page.getByRole("status").filter({ hasText: "Analysis unavailable" })).toBeVisible();
  await expect(pitch).not.toHaveAttribute("aria-label", before!);
  const during = await pitch.getAttribute("aria-label");
  await page.getByRole("button", { name: "Step forward" }).click();
  await expect(slider(page)).toHaveValue("5");
  await expect(pitch).not.toHaveAttribute("aria-label", during!);
  await page.unroute(pattern);
  await page.getByRole("button", { name: "Step forward" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Analysis restored" })).toBeVisible();
  await expectScore(page, "0", "0");
});

test("8 phone width: no horizontal scroll, controls reachable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(slider(page)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  for (const name of ["Play", "Step back", "Step forward", "Speed 1x", "Speed 4x", "Speed 16x"]) {
    const b = page.getByRole("button", { name });
    await b.scrollIntoViewIfNeeded();
    await expect(b).toBeVisible();
    const box = (await b.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(390);
  }
  await page.getByRole("button", { name: "Step forward" }).click();
  await expect(slider(page)).toHaveValue("1");
  const request = page.request;
  const events: Ev[] = (await (await request.get(`${API}/events`)).json()).events;
  await goTo(page, indexOf(events, "e066"));
  await expect(goalCard(page)).toBeVisible();
  await page.screenshot({ path: "e2e/artifacts/goal-390x844.png", fullPage: true });
});

test("9 keyboard: Tab to Step forward, Enter advances", async ({ page }) => {
  const step = page.getByRole("button", { name: "Step forward" });
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press("Tab");
    if (await step.evaluate((el) => el === document.activeElement)) break;
  }
  await expect(step).toBeFocused();
  await expect(slider(page)).toHaveValue("0");
  await page.keyboard.press("Enter");
  await expect(slider(page)).toHaveValue("1");
});
