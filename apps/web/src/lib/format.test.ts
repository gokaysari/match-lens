import { describe, expect, it } from "vitest";
import { formatMetric, mmss, playbackDelay } from "./format";
import { metric } from "../test/mockApi";

describe("format", () => {
  it("mmss", () => {
    expect(mmss(3480000)).toBe("58:00");
    expect(mmss(3484999)).toBe("58:04");
  });
  it("playbackDelay scales by speed and caps a gap at 5 s real time", () => {
    expect(playbackDelay(2400, 1)).toBe(2400);
    expect(playbackDelay(2400, 16)).toBe(150);
    expect(playbackDelay(60000, 1)).toBe(5000);
    expect(playbackDelay(60000, 4)).toBe(5000);
  });
  it("formatMetric", () => {
    expect(formatMetric(metric("pass_completion", "a", 0.444, { unit: "ratio", numerator: 4, denominator: 9 }))).toBe("44% (4/9)");
    expect(formatMetric(metric("pass_completion", "a", null, { unit: "ratio" }))).toBe("–");
    expect(formatMetric(metric("shots", "a", 3))).toBe("3");
  });
});
