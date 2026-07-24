# Implementation Plan — News Integrity TR Evidence Capture Toolkit

**Budget:** ~1 week, solo developer. **Stack:** Python 3.12 / FastAPI / SQLite / SQLAlchemy 2.0 / Alembic / Typer / TypeScript / esbuild / Chrome MV3.
**Rule:** phases are strictly sequential; each has hard "done" criteria. If a phase overruns, cut from Day 7's buffer — never from evidence-integrity work.

MVP scope (locked): **capture, tag, edge-log, archive, export.** Everything else → §Risks or §v2 backlog.

---

## Phase 0 — De-risking spikes (Day 1)

Throwaway code only. Output: `docs/SPIKES.md` recording findings, chosen technique, and fallback per spike. **No production code is written until all three spikes have a go/no-go verdict.**

### S1 — rest_id + follower_count extraction from the X DOM ✅ DONE (verdict GO) — Risk R1
The tweet `article` DOM does not expose the author's numeric ID or follower count as plain attributes. **Chosen technique (ADR-026 / `docs/SPIKES.md` §S1): DOM-anchor, not the React-fiber walk** — the fiber walk was no-go (media-source misattribution). The author's `rest_id` is the numeric prefix of the follow/unfollow button's `data-testid` (`"<rest_id>-follow"` / `"-unfollow"`), gated by a mandatory aria-`@handle` self-check (accept only if the button's `@handle` == the visible author, else fall through — misattribution impossible).
- [x] Read-only console snippet (`spikes/s1-rest-id/console-snippet-dom-anchor.js`) that, given an `article[data-testid="tweet"]`, returns the author `rest_id` (+ handle, tweet_id, created_at) via DOM anchors and cross-checks the visible author.
- [x] Tested on timeline, permalink, quoted, reply, repost + two follow-state checks (a)/(b): 0 misattribution; inline anchor present for not-followed, absent for followed/timeline.
- [x] Documented the anchors + follow-state coverage rule (`docs/SPIKES.md` §S1).
- [x] Fallback ladder (revised, ADR-026): (1) post-inline anchor + self-check → (2) profile-page header anchor (~universal; also gives follower_count) → (3) hover-card scrape (opportunistic) → (4) manual paste. Capture never blocked.
- **Go/no-go: GO** — `rest_id` reliably + correctly extractable on ≥ the permalink page (and via profile fallback for followed accounts). Follower count nice-to-have, now reliable on a profile visit (nullable everywhere).

### S2 — archive.today submission behavior ⚠️ Risk R2
- [ ] Small httpx script: submit 2–3 real X post URLs to `https://archive.ph/submit/`. Space submissions ≥60s apart, normal browser User-Agent.
- [ ] Record: response shapes (redirect? `/wip/`? refresh header?), CAPTCHA/challenge frequency, minimum polite interval.
- [ ] Same exercise for Wayback SPN2 anonymous (`POST https://web.archive.org/save/{url}`): confirm job-id + status-poll flow and anonymous rate limits.
- **Go/no-go:** go for an automated archive.today adapter if ≥2 of 3 submissions succeed without a challenge; otherwise the adapter routes jobs **straight to `manual_pending`** at first challenge and the manual-assist loop becomes the normal archive.today path (queue design absorbs this without rework — that is why it exists).

### S3 — captureVisibleTab + crop geometry ⚠️ Risk R3
- [ ] Minimal throwaway MV3 extension: button in content script → SW `captureVisibleTab` → `OffscreenCanvas` crop with `getBoundingClientRect() × devicePixelRatio` → download the two PNGs.
- [ ] Verify crop alignment on: default zoom, 125% Windows display scaling, browser zoom 90%/110%, a post partially scrolled off-screen (expected: clamp rect to viewport; if the post is clipped, that is acceptable — user scrolls it into view first, overlay can warn).
- **Go/no-go:** go = pixel-accurate crop at default zoom + one scaling variant. Edge cases just flip `crop_failed` — never block.

**Phase 0 done when:** `docs/SPIKES.md` exists with verdicts + fallbacks for S1–S3, and any architecture adjustments are reflected in `ARCHITECTURE.md` / `DECISIONS.md`.

---

## Phase 1 — Backend core: the evidence write path (Day 2)

- [ ] Scaffold `backend/` (layout per ARCHITECTURE §2), `requirements.txt`, `pydantic-settings` config, `.gitignore` (`data/`, `.env`, `__pycache__`, `node_modules`, `dist`).
- [ ] SQLAlchemy models for all 8 tables (incl. `categories`; `evidence.phase`, `evidence.taxonomy_version`, `edges.phase` columns); Alembic init + migration 001; SQLite pragmas on connect (WAL, foreign_keys, busy_timeout).
- [ ] `taxonomy.json` shipped **with the real codebook** — `version: "1.0"`, group labels, the five fixed categories, and all codes H1–H7 / E1–E7 / I1–I5 with final Turkish labels/definitions + international-equivalent terms (content provided in repo-root `taxonomy.json`; no placeholders). Idempotent startup seeding of `taxonomy_codes` + `categories`.
  - **v1.1 shipped (ADR-027)** — Y axis "Yayın Sonrası Bütünlük" (Y1 "Bildirimsiz değiştirme", Y2 "Bildirimsiz silme") + H8 "Yanlış atıf"; migration 0002 widened the `group_prefix` CHECK; codes now 22. The v1.0 line above is left as the original ship item (append-only history).
- [ ] `services/evidence_store.py`: seq assignment, atomic write + hash + read-back verify, sidecar writer, folder layout.
- [ ] `services/accounts.py`: upsert-by-rest_id; creation seeds the initial handle into `handle_history`; change detection appends the newly observed handle (append-only, complete-from-birth history).
- [ ] Endpoints: `GET /healthz`, `GET /api/taxonomy` (returns `{version, groups, categories, codes}`), `POST /api/captures` (full transaction incl. phase + taxonomy_version stamping and archive-job enqueue; merge rule can be stubbed until Phase 4).
- [ ] Tests (pytest, tmp data dir): capture happy path; seq increments; account creation seeds the initial handle_history row; handle change appends the new handle; unknown category and unknown taxonomy code are rejected (422); `phase` and `taxonomy_version` stamped correctly; hash verify catches a corrupted write (monkeypatched); crop_failed path stores viewport as canonical name.

**Done when:** a scripted multipart `POST /api/captures` with two test PNGs produces correct files + sidecar + rows; hashes in DB match `sha256sum` of the files; a second capture increments seq; a new account's first handle is already present in handle_history; a changed handle appends history; `pytest` green.

---

## Phase 2 — Extension capture path (Day 3)

- [ ] `extension/` scaffold: TypeScript strict, esbuild bundling `content.js` + `background.js`, manifest per ARCHITECTURE §7.
- [ ] `src/content/x-dom.ts` from S1 findings: extractors returning `{value, method} | null`, fail-soft, extractor_version constant. Include 1–2 saved-DOM fixtures + unit tests (vitest) for the pure parsing parts.
- [ ] Content script: throttled MutationObserver injecting [Capture]/[Edge] buttons per tweet article (decoration only).
- [ ] Shadow-DOM overlay: taxonomy checkboxes + category select fed entirely from `TAXONOMY_GET` (server-seeded `{version, groups, categories, codes}` — the extension hardcodes no vocabulary), note field, edge-confirm block when a quote/RT/reply was detected, save/cancel, success (shows `{account_id}-{seq}`) / error (retry + backend-down hint via `HEALTH_CHECK`) states.
- [ ] Service worker: message handlers, captureVisibleTab + crop pipeline from S3, multipart POST, session-cached taxonomy.

**Done when:** on live x.com, one click on a real post → tagged capture lands end-to-end (files + rows verified); forcing a bad rect exercises the `crop_failed` fallback; killing the backend produces the friendly error path, and retry after restart succeeds without re-typing.

---

## Phase 3 — Edges + archive queue (Day 4)

- [ ] `POST /api/edges` (+ account auto-create for source; `target_handle_raw` fallback), `GET /api/accounts[/{id}]`.
- [ ] [Edge] button flow: detection pre-fill → mini-confirm → `EDGE_REQUEST`. Inline `edge` in capture meta also handled.
- [ ] `archive_jobs` worker: daemon thread in lifespan, due-job polling, per-service min intervals, backoff schedule, escalation to `manual_pending` after max attempts, `failed` for non-retryable, URL-level short-circuit (an existing `done`/`manual_done` job for the same service+URL is reused locally — no external call).
- [ ] Wayback adapter (SPN2, per S2). archive.today adapter (per S2 verdict — possibly a thin "always manual_pending" shim).
- [ ] Queue endpoints: `GET /api/archive/jobs?status=`, `POST /api/archive/jobs/{id}/retry`, `POST /api/archive/jobs/{id}/manual`.
- [ ] Worker tests with adapter fakes: backoff arithmetic, escalation, never-deleted invariant, rate-limit spacing, URL short-circuit completes a duplicate job without an adapter call.

**Done when:** a real capture enqueues both jobs and a Wayback link lands in `archive_jobs.archive_url` automatically; a forced archive.today failure walks pending→…→`manual_pending` and a paste-back completes it to `manual_done`; killing/restarting the backend loses no jobs.

---

## Phase 4 — CLI + hybrid completion flow (Day 5)

- [ ] `POST /api/cli/bulk-archive` (account resolution rule, URL validation, `skipped` reporting), `GET /api/pending`, `POST /api/evidence/{id}/archive-only`.
- [ ] Merge rule in `POST /api/captures`: same-`post_id` `pending_completion` row is upgraded in place (id/seq/jobs kept, sidecar written now, status→`complete`).
- [ ] Typer CLI: `bulk-archive` (confirm prompt), `pending list`, `pending archive-only`, `archive pending`, `archive manual` (webbrowser open + paste-back loop), `export …` wrappers.
- [ ] Tests: bulk-archive creates N pending rows + 2N jobs (`phase` stamped from config); completion merge preserves id/seq/phase/jobs and keeps `capture_source='cli'`; archive-only transition only valid from pending_completion; unknown handle without `--rest-id` is rejected.

**Done when:** a 10-URL file for a known account creates 10 pending rows + 20 jobs after one confirm; opening one URL in Chrome and clicking [Capture] upgrades the matching row (verified: same id/seq, files now present); `pending archive-only` degrades a row correctly; `archive manual` round-trips a pasted link.

---

## Phase 5 — Exports + hardening (Day 6)

- [ ] `GET /api/exports/edges.csv`, `case-file.json`, `manifest?verify=` (formats per ARCHITECTURE §6).
- [ ] Case-file explicitly labels evidence tier (`complete` vs `archive_only`), phase (VK1/VK2), and taxonomy_version, and includes archive links per evidence row; edges.csv includes the `phase` column.
- [ ] Manifest verify: recompute from disk, report per-file `ok|mismatch|missing`.
- [ ] Overlay polish: all failure states human-readable; double-submit guard on save.
- [ ] `README.md` runbook: start backend, load unpacked extension, **pin `NIT_EXTENSION_ID` from chrome://extensions into `.env`** (CORS lock — numbered setup step), capture workflow, CLI workflows, **phase switch** (`NIT_PHASE` VK1 → VK2 exactly once, at the start of sprint S2), backup = copy `data/` while backend is stopped (SQLite + evidence tree together), restore note.
- [ ] Full-loop test: tamper 1 byte of one PNG in a scratch copy → `manifest?verify=true` flags exactly that file.

**Done when:** all three exports validate against the data captured in Phases 2–4; the tamper test flags the tampered file and nothing else; README lets future-you cold-start the system.

---

## Day 7 — Shakedown buffer

- [ ] Real-world pass: ~20 captures across ≥3 accounts, several edges, one CLI bulk run + completion pass, drain the archive queue incl. one manual-assist.
- [ ] Fix paper cuts; note anything non-trivial in `DECISIONS.md` or v2 backlog. Unspent time = slack absorbed by earlier overruns.

---

## Risks

| # | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R1 | X DOM/React-fiber changes break rest_id / follower extraction | High / High | Spike S1 first; all selectors isolated in `x-dom.ts` with fixtures; fail-soft extractors; manual rest_id fallback field. Breakage = update one module, evidence flow otherwise unaffected |
| R2 | archive.today anti-bot blocks automation | High / Medium | Spike S2; queue + `manual_pending` + manual-assist designed in from day one — worst case archive.today is always manual, zero rework |
| R3 | Crop geometry wrong under DPI/zoom variations; MV3 capture quirks | Medium / Medium | Spike S3; `crop_failed` downgrade path means worst case is viewport-only evidence, never a lost capture |

Consciously accepted (not risks): SQLite concurrency — single writer process, CLI goes through HTTP. Wayback often renders X posts poorly — screenshots are the primary evidence; archives are deletion insurance. Extension has no offline queue — the post is on screen; retry is cheap.

---

## v2 backlog (explicitly out of MVP)

- GraphQL/XHR response interception for raw post payloads (deferred by explicit project decision)
- Dashboards / statistics screens; settings pages; auth / multi-user
- Scroll-stitched full-post screenshots; video/media capture
- Firefox (MV2/MV3 divergence) port
- Auto-resolution of `target_handle_raw` edges when the target account is later captured
- Authenticated / proxy archive.today strategies; Wayback S3-key auth by default
- DOM-drift canary test (scheduled fixture check that alerts when X markup changes)
- RFC-3161 trusted timestamping of the hash manifest (strengthens the "hash existed at time T" claim)
- Sidecar/manifest signing (age or minisign)
- Handle-change alerting; case-file → report (PDF/HTML) generator
