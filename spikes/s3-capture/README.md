# S3 — captureVisibleTab + crop geometry (Risk R3)

**Question:** does `getBoundingClientRect() × devicePixelRatio` produce a
**pixel-accurate crop** of a post from a `captureVisibleTab` PNG, across zoom and
Windows display-scaling variants?

**Go/no-go:** GO if the crop is pixel-accurate at **default zoom + at least one
scaling variant**. Edge cases (partly off-screen posts) just flip `crop_failed`
in the real tool — they never block a capture.

Everything stays local: two PNGs download to your machine; nothing is sent out.

## Load the unpacked extension

1. Chrome → `chrome://extensions` → toggle **Developer mode** (top-right).
2. **Load unpacked** → select this `s3-capture/` folder.
3. Open **x.com**. Each tweet gets a small blue **"S3 capture"** button
   (top-right of the article). If you don't see it, reload the tab.
4. Click it on a fully-visible post. Two files download:
   `s3-<ts>-viewport.png` and `s3-<ts>-crop.png`. An alert shows `dpr`, the
   captured image size, and the crop rectangle. Console logs the same.

> If Chrome refuses `captureVisibleTab` with a permissions error, add
> `"<all_urls>"` to `host_permissions` in `manifest.json` and reload the
> extension. Note it in your report if you had to.

## Test matrix (per PLAN S3)

For each variant: click **S3 capture** on a normal, fully-visible post, then open
`…-crop.png` and check it contains **exactly that post, edge-to-edge** (no drift,
no half-neighbor, not shifted/scaled).

| # | Variant | How to set it | Pass = crop is… |
|---|---|---|---|
| 1 | **Default** | 100% browser zoom, 100% Windows scaling | exact (the required baseline) |
| 2 | **125% Windows scaling** | Settings → Display → Scale = 125% (may need re-login) | exact (the key second variant) |
| 3 | **Browser zoom 90%** | Ctrl-Minus once from 100% | exact |
| 4 | **Browser zoom 110%** | Ctrl-Plus once from 100% | exact |
| 5 | **Partially scrolled off-screen** | scroll so the post is half above the top edge | clipped is OK; `clamped=true`; must not crash or misalign the visible part |

For each variant note the **`dpr`** value from the alert/console and the captured
image size — that tells us how zoom/scaling folds into `devicePixelRatio`.

## What to record / paste back

```
S3 variant 1 (default, dpr=…):        crop exact? Y/N   notes=…
S3 variant 2 (125% scaling, dpr=…):   crop exact? Y/N   notes=…
S3 variant 3 (zoom 90%, dpr=…):       crop exact? Y/N   notes=…
S3 variant 4 (zoom 110%, dpr=…):      crop exact? Y/N   notes=…
S3 variant 5 (scrolled off, dpr=…):   clamped OK? Y/N   notes=…
captured image size vs viewport×dpr matched? …
had to add "<all_urls>"? Y/N
any misalignment: off by N px? whole-post drift? scaled? …
```

Attaching one or two `-crop.png` files (especially any that look wrong) helps a
lot. I turn this into the S3 section of `docs/SPIKES.md` (verdict + which
variants are pixel-accurate + where `crop_failed` should trigger). Any deviation
that affects the design becomes an ADR-024+ proposal for your approval.

## Paste-back — 2026-07-17 run (combined spikes-extension helper)

Coverage note: this run tested five PAGE TYPES at ONE display config —
dpr=1.25 from **Windows display scaling 125% at browser zoom 100%** (zoom
confirmed at 100% via Ctrl+0). Matrix variants 1/3/4/5 not yet run; they will
be run before the S3 verdict is recorded.

```
S3 variant 1 (default 100%/100%):      NOT RUN
S3 variant 2 (125% Windows scaling, zoom 100%, dpr=1.25): crop exact? Y — 5/5 page types (below)
S3 variant 3 (zoom 90%):               NOT RUN
S3 variant 4 (zoom 110%):              NOT RUN
S3 variant 5 (scrolled off-screen):    NOT RUN
captured image size vs viewport×dpr matched? Y — every viewport PNG is
  1920×877 device px = 1536×701.6 CSS × 1.25; crop width 748 = 598.4 CSS
  article width × 1.25 exactly
had to add "<all_urls>"? The combined helper manifest ships with <all_urls>
  pre-added, so x.com-only host_permissions were not exercised this run
any misalignment: none — all five crops edge-to-edge, no drift/neighbor bleed
```

| page type | files (spikes-test/) | crop px | visual check |
|---|---|---|---|
| timeline  | s3-1784306222227-*  | 748×659 | exact — post + 4-photo grid |
| permalink | s3-1784306607131-*  | 748×811 | exact — post + video + view count |
| quoted    | s3-1784307113927-*  | 748×598 | exact — outer + embedded quoted post |
| reply     | s3-1784307359183-*  | 748×239 | exact — reply + action bar (thread-connector sliver belongs to the article element) |
| repost    | s3-1784307550110-*  | 748×641 | exact — incl. "yeniden yayınladı" repost banner |

Notes: dpr/crop-rect alert values were not persisted; dpr=1.25 was derived
from image geometry and matches the confirmed config (Windows scaling 125%,
zoom 100%). The injected blue "S3" button appears in each crop
(throwaway-tool artifact). Go/no-go requires default zoom + ≥1 scaling
variant — currently only the dpr=1.25 config is covered; remaining variants
to be run before the verdict.

## Paste-back — 2026-07-18 run (remaining variants, 100% Windows scaling)

Completes the matrix (variant 2 was the 2026-07-17 run at 125% scaling).
Geometry verified from PNG headers in `spikes-test/`.

```
S3 variant 1 (default 100%/100%, dpr=1.0):  crop exact? Y — 598 = 598 CSS × 1.0
S3 variant 3 (zoom 90%, dpr=0.9):           crop exact? Y — 538 = 598 × 0.9
S3 variant 4 (zoom 110%, dpr=1.1):          crop exact? Y — 658 = 598 × 1.1
S3 variant 5 (scrolled off, dpr=1.0):       clamped OK? Y — 598×401, visible-only
captured image size vs viewport×dpr matched? Y — viewport 1920×917 device px on
  all; crop width = round(598 CSS × dpr) across the full 0.9–1.25 range
had to add "<all_urls>"? Not exercised (combined helper ships <all_urls>)
misalignment: none on 1/3/4; variant 5 clamps to visible region (bottom cut)
```

| variant | files (spikes-test/) | crop px | check |
|---|---|---|---|
| 1 (100%/100%) | s3-1784394737838-* | 598×864 | EXACT |
| 3 (zoom 90%)  | s3-1784394822830-* (devicePixelRatio=0.9) | 538×869 | EXACT |
| 4 (zoom 110%) | s3-1784394831334-* (devicePixelRatio=1.1) | 658×859 | EXACT |
| 5 (scrolled)  | s3-1784395083222-* | 598×401 | CLAMP (visible-only) |

Design note (variant 5): `captureVisibleTab` sees only the viewport, so the real
tool must `scrollIntoView` + ensure full visibility before capture, else it
clamps and flips `clamped=true`/`crop_failed` (never blocks a capture). Go/no-go
(default + ≥1 scaling variant) now met → S3 verdict GO.
