/**
 * Crop geometry: a viewport-relative CSS rect → a device-pixel rectangle inside
 * the `captureVisibleTab` bitmap.
 *
 * Edges are rounded, not the size (S3 addendum, 2026-10-31): rounding origin and
 * size independently left a 1-device-pixel shift at fractional dpr (1.1, 1.375,
 * 1.65) that a width-only check could not see. `round((x+w)·dpr) − round(x·dpr)`
 * measured 0 background pixels on the crop border in 13 of 14 combinations.
 */

export interface CssRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DeviceRect {
  sx: number;
  sy: number;
  sw: number;
  sh: number;
  /** The post was partly outside the viewport; the crop holds the visible part. */
  clamped: boolean;
}

export function cropRect(rect: CssRect, dpr: number, bitmapW: number, bitmapH: number): DeviceRect | null {
  if (![rect.x, rect.y, rect.w, rect.h, dpr].every(Number.isFinite) || dpr <= 0) return null;
  let left = Math.round(rect.x * dpr);
  let top = Math.round(rect.y * dpr);
  let right = Math.round((rect.x + rect.w) * dpr);
  let bottom = Math.round((rect.y + rect.h) * dpr);
  let clamped = false;
  if (left < 0) { left = 0; clamped = true; }
  if (top < 0) { top = 0; clamped = true; }
  if (right > bitmapW) { right = bitmapW; clamped = true; }
  if (bottom > bitmapH) { bottom = bitmapH; clamped = true; }
  const sw = right - left;
  const sh = bottom - top;
  // Entirely outside the viewport, or degenerate: the caller takes the
  // crop_failed path (viewport becomes the primary image). Never blocks.
  if (sw < 2 || sh < 2) return null;
  return { sx: left, sy: top, sw, sh, clamped };
}
