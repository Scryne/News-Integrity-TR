# Phase 0 spikes — THROWAWAY

De-risking spikes for `PLAN.md` § Phase 0. **This code is throwaway.** None of
it becomes production; it exists only to produce a go/no-go verdict per risk.
No production code is written until S1, S2, and S3 each have a verdict, and
`docs/SPIKES.md` is authored **from your reported findings only** — never from
assumed results.

You run each artifact; you paste findings back; I write `docs/SPIKES.md`.

| Spike | Risk | Artifact | You run it by |
|---|---|---|---|
| **S1** rest_id / follower extraction | R1 (High/High) | `s1-rest-id/console-snippet.js` | Pasting into DevTools Console on live x.com |
| **S2** archive service behavior | R2 (High/Med) | `s2-archive/archive_probe.py` | `python archive_probe.py` on your machine |
| **S3** captureVisibleTab + crop | R3 (Med/Med) | `s3-capture/` (unpacked MV3) | Loading unpacked in Chrome |

Each subfolder has its own README with the exact steps, the variants to test,
and a **paste-back template** for what to record.

## Safety / boundary notes

- **S1 reads the page only.** It sends nothing anywhere and performs no network
  calls. It just walks the DOM/React fiber of tweets already on your screen.
- **S2 contacts external archive services** (Wayback, archive.today) — that is
  its whole point, and it is the services' intended use. It is polite by
  construction (one call at a time, ≥60s spacing, real UA) and supports
  `--dry-run` so you can review the plan before any network call. Keep the URL
  list to 2–3 posts. **I do not run this — you do.**
- **S3 captures your visible tab** and downloads two PNGs locally. Nothing
  leaves the machine.

Nothing here crawls, scrolls, auto-discovers, or bulk-collects — consistent with
the project's no-automated-collection boundary.

## Suggested order

S1 first (it gates the whole extension design), then S2 and S3 in any order.
