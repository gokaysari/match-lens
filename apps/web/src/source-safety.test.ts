import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

describe("source safety", () => {
  it("no source file renders raw HTML or evaluates code", () => {
    const self = __filename;
    const files = walk(join(__dirname)).filter(
      (f) => /\.(ts|tsx|js|jsx|html)$/.test(f) && f !== self,
    );
    expect(files.length).toBeGreaterThan(3);
    // Built by concatenation so this test file never contains the literal either.
    const banned = ["dangerously" + "SetInnerHTML", "inner" + "HTML", "ev" + "al(", "new Func" + "tion"];
    for (const f of files) {
      const text = readFileSync(f, "utf8");
      for (const word of banned) {
        expect(text.includes(word), `${f} contains ${word}`).toBe(false);
      }
    }
  });
});
