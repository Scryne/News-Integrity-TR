import { describe, expect, it } from "vitest";

import { cropRect } from "../src/shared/geometry";

describe("cropRect", () => {
  it("is exact at integer dpr", () => {
    expect(cropRect({ x: 250, y: 40, w: 600, h: 260 }, 1, 1100, 800)).toEqual({
      sx: 250, sy: 40, sw: 600, sh: 260, clamped: false,
    });
  });

  it("rounds edges, not size, at fractional dpr (S3 addendum)", () => {
    // x=249.5 · 1.1 = 274.45 → 274; (249.5+600) · 1.1 = 934.45 → 934.
    const r = cropRect({ x: 249.5, y: 40, w: 600, h: 260 }, 1.1, 1210, 880);
    expect(r?.sx).toBe(274);
    expect(r?.sw).toBe(934 - 274);
    // Independent rounding would give round(600·1.1)=660: the right edge moves.
    expect(r?.sx! + r?.sw!).toBe(Math.round((249.5 + 600) * 1.1));
  });

  it("clamps a post partly above the viewport", () => {
    const r = cropRect({ x: 10, y: -130, w: 600, h: 260 }, 1.25, 1375, 1000);
    expect(r).toEqual({ sx: 13, sy: 0, sw: 750, sh: 163, clamped: true });
  });

  it("returns null when nothing of the post is visible (crop_failed path)", () => {
    expect(cropRect({ x: 0, y: 900, w: 600, h: 260 }, 1, 1100, 800)).toBeNull();
    expect(cropRect({ x: 0, y: 0, w: Number.NaN, h: 10 }, 1, 100, 100)).toBeNull();
    expect(cropRect({ x: 0, y: 0, w: 10, h: 10 }, 0, 100, 100)).toBeNull();
  });
});
