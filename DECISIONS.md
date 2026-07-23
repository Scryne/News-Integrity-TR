# Decision Log (ADR-style)

Format: **Context → Decision → Consequences.** All decisions below are **Accepted** (2026-07-15) unless noted. New decisions get appended, never rewritten; a reversal is a new ADR that supersedes the old one.

---

## ADR-001 — X rest_id as TEXT primary key everywhere

**Context:** Handles (@names) are mutable and are actively rotated by the accounts under study; the numeric rest_id is immutable. rest_ids exceed JavaScript's `Number.MAX_SAFE_INTEGER`, so they must never pass through a JS number or a float column.
**Decision:** `accounts.account_id` is the rest_id stored as `TEXT` (digits only) and is the foreign key everywhere. Handles are observations recorded with detection dates in append-only `handle_history`; they are display data, never keys.
**Consequences:** Renames cannot break linkage; every JSON layer must keep rest_id a string (enforced in Pydantic schemas and TS types).

*Amended by ADR-020 (handle_history is complete from birth).*

## ADR-002 — Monorepo with three components

**Context:** Solo developer; extension, backend, and CLI share one evolving contract.
**Decision:** One repository: `backend/`, `extension/`, `cli/`, contract documented in `ARCHITECTURE.md`.
**Consequences:** Atomic cross-component changes; no versioned-API ceremony between components.

## ADR-003 — FastAPI (sync) + SQLite + SQLAlchemy 2.0 + Alembic

**Context:** Localhost, one user, tiny write rates. Developer already fluent in this exact stack (cognispace-backend uses the same layering: routers → services → models → schemas).
**Decision:** Sync FastAPI handlers, SQLite with WAL + `foreign_keys=ON` + busy_timeout, SQLAlchemy 2.0, Alembic migrations from day one. No async DB driver.
**Consequences:** Boring, debuggable, zero new learning. Alembic from migration 001 avoids the "first schema change is a crisis" trap.

## ADR-004 — Backend HTTP API is the single write path; CLI is a thin client

**Context:** SQLite tolerates one writer best; evidence invariants (seq, hashing, append-only rules) must live in exactly one place.
**Decision:** The CLI never touches the DB or filesystem directly; it calls the running backend via httpx.
**Consequences:** One writer process, invariants enforced once. Cost: CLI requires the backend to be up — acceptable for a solo workflow.

## ADR-005 — Dual screenshot: crop primary + viewport context, crop best-effort

**Context:** A cropped post is the clean report-ready evidence unit; the full viewport proves surrounding context. Crop geometry depends on DOM layout and display scaling and can fail.
**Decision:** Capture both, hash both. Crop is the primary report evidence at the canonical filename `{account_id}-{seq:04d}.png`; viewport is `…-viewport.png`. Crop failure never blocks: record downgrades to viewport-only at the canonical name with `crop_failed=1`.
**Consequences:** ~2× storage (cheap); the canonical name always holds the primary evidence, so report tooling never branches on crop success.

## ADR-006 — Tagging UI is an in-page Shadow-DOM overlay, not the extension action popup

**Context:** The spec said "popup", but Chrome cannot programmatically open the action popup from a button injected next to a post; a popup also loses the visual tie to the specific post.
**Decision:** Clicking [Capture] opens an overlay rendered into a shadow root appended to the page — one uninterrupted flow, unambiguous post association, full CSS isolation in both directions.
**Consequences:** Overlay code must be self-contained (all styles inside the shadow root); no toolbar-popup surface exists in MVP.

## ADR-007 — Wayback SPN2 is the primary archiver; archive.today is best-effort with a mandatory manual-assist queue

**Context:** Wayback has an official API; archive.today has aggressive anti-bot behavior (CAPTCHAs, throttling) that cannot be reliably automated — and evading it would be both fragile and inappropriate.
**Decision:** Both services get a job per capture. Wayback is expected to succeed automatically. archive.today attempts run with polite spacing and backoff; after max attempts the job escalates to `manual_pending` — a visible queue processed by `cli archive manual` (opens the submit page, user solves/submits, pastes the archive URL back). **No archive job is ever silently dropped**; rows are never deleted, only status-transitioned.
**Consequences:** Archive coverage is guaranteed by workflow (automated + manual) rather than by fragile automation. Spike S2 decides whether the automated archive.today adapter is even attempted or jobs route straight to manual.
*Amended by ADR-024 (authenticated SPN2).*

## ADR-008 — Archival is fully decoupled from capture

**Context:** Evidence integrity priority: a slow or down archive service must never lose or delay a capture.
**Decision:** `POST /api/captures` only *enqueues* archive jobs (same DB transaction as the evidence insert). A background worker thread drains the queue with per-service rate limits and exponential backoff.
**Consequences:** Capture latency is local-disk latency. Archive links arrive asynchronously and live in the DB, not the sidecar (see ADR-009).

## ADR-009 — Sidecar JSON is write-once; archive links live in DB and exports only

**Context:** The sidecar is part of the evidence artifact; mutating it after capture would undermine the integrity story. Archive links arrive minutes-to-days later.
**Decision:** Sidecar is written exactly once (at capture completion) and never touched again. Archive URLs are stored in `archive_jobs` and surfaced in the case-file export and manifest report.
**Consequences:** A sidecar's hashables are stable from birth; consumers needing archive links read exports, not sidecars.

## ADR-010 — Hybrid CLI flow: archive at queue time, complete in browser, `archive_only` degrade

**Context:** Retrospective bulk work needs immediate archiving (deletion insurance), but archive-links-only records would violate the project's screenshot standard — and Wayback snapshots of X posts often fail to render due to JS.
**Decision:** `bulk-archive` creates `pending_completion` evidence rows (seq assigned immediately, reserving the filename slot) and enqueues archive jobs at once. A same-sprint browser completion pass captures each URL normally; the capture endpoint merges into the pending row by `post_id` (same id/seq, jobs kept). Posts deleted before completion are explicitly marked `archive_only` — a labeled, degraded evidence tier where the archive link serves as the visual evidence.
**Consequences:** Deletion insurance without weakening the evidence standard; exports must always label the tier. Bulk-archive requires the account to already exist (or an explicit `--rest-id`) because pending rows need the immutable PK.

*Clarified by ADR-023 (capture_source semantics on merge).*

## ADR-011 — Service worker mediates all backend communication

**Context:** Content scripts fetch under the page's CSP/CORS regime; x.com's policies would interfere with calls to `http://127.0.0.1:8765`. MV3 service workers fetch with extension host permissions.
**Decision:** All HTTP goes through the SW. Content↔SW messages carry metadata only; the screenshot is captured in the SW itself (`captureVisibleTab`) and never transits messaging.
**Consequences:** Small, stable message protocol; no large-payload messaging issues; backend CORS allows only `chrome-extension://` origins.

## ADR-012 — Vanilla TypeScript + esbuild, no UI framework

**Context:** MVP UI is one overlay form and one confirm dialog. A framework adds build complexity and bundle weight for two components.
**Decision:** Strict TypeScript, esbuild bundling, hand-rolled DOM in the shadow root.
**Consequences:** Trivial build; if v2 grows real UI surface, revisit then (that rework is contained in the overlay module).

## ADR-013 — Explicit evidence status model: `complete` / `pending_completion` / `archive_only`

**Context:** The hybrid CLI flow (ADR-010) creates records at different assurance levels; conflating them would poison the methodology's credibility.
**Decision:** Status is a first-class column with the only legal transitions being `pending_completion → complete` (merge) and `pending_completion → archive_only` (user-confirmed deletion). `complete` is never downgraded; nothing is deleted.
**Consequences:** Every export and case-file states the tier per item; reviewers can audit exactly what backs each claim.

## ADR-014 — Localhost binding is the security boundary; no auth in MVP

**Context:** Single user, single machine, no network exposure requirement.
**Decision:** Bind `127.0.0.1` only; no auth, no TLS. CORS restricted to extension origins.
**Consequences:** Zero auth friction. If the backend ever needs to leave localhost, that is a v2 decision requiring auth first.

*Amended by ADR-021 (CORS pinned to the installed extension's ID).*

## ADR-015 — Unresolved edge targets are kept raw, never guessed

**Context:** The target account's rest_id is not always extractable from a quote/RT/reply structure.
**Decision:** Edges store `target_account_id = NULL` + `target_handle_raw` rather than blocking the log or guessing an ID. Auto-resolution when the target is later captured is v2.
**Consequences:** edges.csv consumers must handle NULL targets; integrity of the ID space is preserved.

## ADR-016 — Taxonomy seeded from `taxonomy.json`; codes immutable, labels editable

**Context:** Codes H1–H7 / E1–E7 / I1–I5 are fixed identifiers of the user's methodology; labels/descriptions may be refined.
**Decision:** Repo-root `taxonomy.json` is seeded idempotently at startup — labels upsert, codes are never deleted (evidence references them). Scaffolded with placeholder labels for the user to fill in.
**Consequences:** Taxonomy edits are a file change + restart; no taxonomy admin UI needed (in line with locked MVP scope).

*Amended by ADR-017 (codebook versioning), ADR-018 (fixed category list; taxonomy.json ships with the real codebook, not placeholders).*

## ADR-017 — Taxonomy is versioned; every coded evidence row stamps its codebook version

**Context:** The taxonomy is a living codebook — candidate codes discovered during VK2 will produce v1.1+. Without a per-evidence version stamp it is impossible to prove which codebook an item was coded under. This is a methodological requirement (and an explicit project requirement the original design missed).
**Decision:** `taxonomy.json` carries a top-level `version`. At the moment codes are attached (extension capture, or completion of a CLI row), the backend stamps `evidence.taxonomy_version` from the currently seeded version; the sidecar records the same value; `GET /api/taxonomy` returns the version. The stamp is applied server-side — the extension never supplies it.
**Consequences:** Codebook evolution is auditable per evidence item. `taxonomy_version` is NULL only while `pending_completion` (no codes attached yet). Amends ADR-016.

## ADR-018 — Categories are a fixed seeded list, never free text

**Context:** The methodology defines exactly five account categories. Free-text entry fragments the data ("magazin" vs "Magazin") and silently corrupts category statistics.
**Decision:** Categories live in `taxonomy.json` next to the codes (`key` + Turkish label; keys: `news`, `magazine`, `agenda`, `viral`, `anonymous_news`) and are seeded idempotently into a `categories` table. `evidence.category` is a foreign key to it; the Pydantic layer rejects unknown keys before the DB does. The seed file also ships the real code labels/definitions and international-equivalent terms — no placeholders anywhere.
**Consequences:** One seed file is the single source of truth for the entire coding vocabulary (version + groups + categories + codes); the overlay renders exclusively from `GET /api/taxonomy`, so the extension hardcodes no vocabulary. Amends ADR-016.

## ADR-019 — Case-study phase (VK1/VK2) is first-class data, not a folder-name convention

**Context:** The original design carried the phase only in a folder-prefix env var. Phase membership (VK1 exploratory open coding vs VK2 systematic archive-first coding) is methodologically essential; recovering it by parsing path strings is fragile and breaks if the prefix changes mid-project. The tool is used in both phases.
**Decision:** `NIT_PHASE` config (`VK1`|`VK2`, switched exactly once at the start of sprint S2) is stamped as a `phase` column on every evidence **and** edge row at creation, recorded in the sidecar, and derives the evidence folder prefix `{phase}-{account_id}/`. Every export labels it. `NIT_EVIDENCE_PREFIX` is removed.
**Consequences:** An account captured in both phases has two evidence folders; per-account `seq` remains globally unique, so filenames never collide across them. Any claim in the report can state which case study each item of evidence belongs to without touching the filesystem.

## ADR-020 — handle_history is complete from birth

**Context:** The original rule ("insert a row whenever an observed handle differs") never recorded an account's first handle, and left ambiguous whether the old or the new handle gets appended on change — if the new one, the original handle is lost the moment `current_handle` is updated. Handle churn is the I5 code; this table is core evidence, not bookkeeping.
**Decision:** Account creation inserts the initial handle into `handle_history` (detected_at = first_seen_at, evidence_id when creation happened via a capture). On change detection, the **newly observed** handle is appended. `handle_history` is thus the complete dated list of every handle ever observed; `current_handle` is denormalized convenience only.
**Consequences:** I5 evidence is airtight; "how many handles has this account used" is a plain COUNT with no special-casing. Amends ADR-001.

## ADR-021 — CORS pinned to the installed extension's ID

**Context:** `^chrome-extension://.*$` allows any extension on the machine to write to the backend. Localhost binding remains the primary security boundary, but closing this surface costs one config value.
**Decision:** `NIT_EXTENSION_ID` env var. When set, CORS allows exactly `chrome-extension://{id}`. When unset (first run — an unpacked extension's ID is only known after loading), the backend falls back to the wildcard regex and logs a prominent startup warning; the README makes pinning the ID a numbered setup step.
**Consequences:** The second-extension attack surface is closed after setup with zero first-run friction. Amends ADR-014.

## ADR-022 — Archive worker short-circuits duplicate URLs

**Context:** Re-capturing a post is a designed feature (temporal re-observation), but each re-capture enqueues fresh archive jobs for a URL that may already be archived — wasting rate-limit budget and politeness margin against services we must treat gently.
**Decision:** Before contacting a service, the worker checks for an existing `done`/`manual_done` job with the same `(service, target_url)`; if found, it copies that job's `archive_url` and completes the new job locally without an external call.
**Consequences:** Per-evidence archive linkage is preserved (every evidence row keeps its own jobs) while external submissions are deduplicated by URL. No schema change — it is a worker rule.

## ADR-023 — `capture_source` records row origin; merged rows stay `cli`

**Context:** After an ADR-010 merge one could ask whether the completing capture should overwrite the row's `capture_source`.
**Decision:** No overwrite and no new column: `capture_source` means "how the row came into existence". Only the CLI creates `pending_completion` rows and only extension captures complete them, so `('cli', status='complete')` unambiguously reads as *CLI-queued, extension-completed*. Documented as a schema comment.
**Consequences:** No information loss, no schema growth, no ambiguity.

## ADR-024 — Automated Wayback archiving requires authenticated SPN2 (archive.org account + S3 keys)

**Context:** ADR-007 assumed Wayback SPN2 works automatically with no credentials. Spike S2 (2026-07-18, `docs/SPIKES.md` §S2) disproved this: 3/3 anonymous `POST https://web.archive.org/save/` returned HTTP 401 `{"message":"You need to be logged in to use Save Page Now."}`, and the anonymous job-id/status-poll flow could not be observed at all. Anonymous SPN2 is no longer a usable path.
**Decision:** The Wayback adapter authenticates every SPN2 call with an archive.org account's S3-style API keys (accesskey/secret), supplied via config secrets (e.g. `NIT_WAYBACK_S3_ACCESSKEY` / `NIT_WAYBACK_S3_SECRET`) and never committed. If keys are absent or the submit is rejected, the Wayback job does not silently no-op — it escalates to the same `manual_pending` path archive.today uses (open `https://web.archive.org/save/<url>` in the browser, paste the result back), so no archive job is ever silently dropped (consistent with ADR-007/ADR-008). Scope is Wayback only; archive.today stays manual-first per S2.
**Consequences:** Automated Wayback now has an operational prerequisite — an archive.org account + S3 keys — to be documented in setup. The authenticated SPN2 response shape (job_id + status poll) was never reached anonymously in S2, so it still needs one live confirmation run with real keys before the adapter is finalized (backlog line in `docs/SPIKES.md` §S2). Politeness/retry defaults stay as designed until that run. Amends ADR-007 (removes its no-credentials assumption); leaves the manual-assist queue and the ADR-008 capture/archive decoupling unchanged.

*See ADR-025 (SPN2 blocks x.com; Wayback manual-first for X URLs).*

## ADR-025 — Wayback is manual-first for x.com/twitter.com URLs (SPN2 blocks the domain)

**Status:** Accepted 2026-07-19 — **pending an external exception request to archive.org** (see Decision).

**Context:** The ADR-024 confirmation backlog run (2026-07-19, Claude-executed at the maintainer's instruction with real S3 keys; `docs/SPIKES.md` §S2, log `spikes/s2-archive/s2-auth-spn2-output-2026-07-19.log`) established two things. (1) **Authenticated SPN2 works** — keys are accepted (HTTP 200, vs the anonymous 401 in S2), and the `job_id → status-poll → success → archive_url` flow was observed live on a non-blocked URL, closing ADR-024's confirmation backlog. (2) **But SPN2 refuses x.com/twitter.com at the domain level** — every X-post submit returns HTTP 200 with `{"status":"error","status_ext":"error:blocked-url"}` ("currently facing some limitations when it comes to archiving this site") and **no `job_id` is ever issued**. Since the tool archives only X posts, the ADR-024 auth fix is *necessary but not sufficient*: automated Wayback cannot currently reach our target content.

**Decision:** Wayback is **manual-first for x.com/twitter.com URLs.** Because SPN2 returns `error:blocked-url` for these hosts, no automated submit is attempted for them; the job routes straight to the existing `manual_pending` / manual-assist queue — the **same mechanism archive.today already uses (ADR-007 / ADR-008), with no new design**: the queue, the `cli archive manual` loop, and the status-transition model are reused unchanged. Host detection happens *before* any external call, so no blocked submit is ever fired. The **authenticated SPN2 infrastructure from ADR-024 is preserved, not removed**: non-X URLs keep the automated path, and if the block is lifted the automated path re-engages for X URLs by removing the host exception (a config/flag change, not a redesign). **Parallel action (outside code):** an x.com/twitter.com archiving-exception request will be sent to archive.org (`info@archive.org`, per the block message) as a manual maintainer step — hence this ADR is **Accepted with a pending external request**; a favorable reply is captured by a new superseding ADR, not by editing this one.

**Consequences:** In the MVP, **both** archive services (Wayback and archive.today) are now manual-first for X content, so the **manual-assist queue is the primary archive path for X posts, not a fallback side-path** — manual-assist UX therefore moves onto the **build critical path** (no longer "nice to have after automation"). The no-silent-drop guarantee holds: X-URL Wayback jobs are still created and escalated to `manual_pending`, never no-op'd (ADR-007/008). Non-X URLs are unaffected (still automated). ADR-008 decoupling and the manual queue are unchanged. Amends ADR-024's expectation that authenticated Wayback is automatic for X posts; if archive.org grants the exception, a superseding ADR flips X-URL Wayback back to automated.

## ADR-026 — S1 author rest_id: DOM-anchor extraction primary, with a mandatory `@handle` self-check and profile-page fallback

**Status:** Accepted 2026-07-20 (closes the S1 fallback-approach open item; `docs/SPIKES.md` §S1).

**Context:** Spike S1 established that the React-fiber walk cannot reliably extract the author's `rest_id` — every apparent hit was a media-source-user false positive (misattribution), so the fiber approach is no-go (`docs/SPIKES.md` §S1, probe s1-0.3). A follow-up DOM-anchor spike (probe s1-dom-0.1: five page-type paste-backs + two follow-state checks) found that the author's numeric `rest_id` is carried verbatim by the follow/unfollow button's `data-testid` (`"<rest_id>-follow"` / `"-unfollow"`), and — critically — that across every sampled row it produced **zero misattribution** (a resolved id always matched the visible author's `@handle`; otherwise a clean miss). The inline anchor renders only for accounts the user does not follow and never on timeline rows; but the **profile-page header** follow/unfollow button carries the owner's `rest_id` regardless of follow state (and also shows follower_count as text), giving a near-universal fallback. This closes the last open Phase-0 gate.

**Decision:** Author `rest_id` extraction is **DOM-anchor-based, not fiber-based.** The primary source is the post-inline follow/unfollow button's `data-testid`. A **mandatory aria-`@handle` self-check** gates acceptance: an extracted id is accepted **only if** the button's parsed `@handle` equals the post's visible author handle; on any mismatch or absence the extractor returns `null` and the next fallback runs — so a wrong identity can never be recorded (integrity over completeness; consistent with the `x-dom-extraction` skill's fail-soft, never-guess rules). The **revised fallback ladder** is: (1) **primary** — post-inline follow/unfollow `data-testid` anchor + self-check; (2) **fallback-1** — profile-page header follow/unfollow anchor (~universal; also yields follower_count), for accounts the user follows or captures from a timeline; (3) **fallback-2** — hover-card DOM scrape (opportunistic; only if a card is already open from user hover, never force-hovered); (4) **backstop** — manual rest_id paste field. Every rung applies the same `@handle` self-check where a handle is available. **Candidate 4 (GraphQL response interception) is parked**: its adoption triggers were misattribution or total DOM absence, and neither was observed; it stays in the `ARCHITECTURE.md` §v2 backlog and is **not** brought into MVP scope (no scope change).

**Consequences:** `follower_count` is upgraded from "rarely reachable" (fiber walk) to **reliably available whenever a profile is visited** (header text); it remains nullable everywhere and a missing id or count **never blocks a capture** (`x-dom-extraction` skill rule 4 preserved). Coverage: not-followed accounts resolve inline on permalink; followed accounts and timeline-only captures resolve via the profile-page fallback (once per author; thereafter keyed and reused by `rest_id`). Wiring that fallback into the capture flow — *post has no id → visit the author's profile once → read id + follower_count from the header → upsert/cache by `rest_id`* — is a **design note pointing the build in a direction, not a mandate**; the exact UX is a build decision. The `x-dom-extraction` skill's "Fallback order" and `PLAN.md` §S1 should be updated to match this ladder (fiber-walk demoted from primary). NULL-tolerant edge targets are unaffected and consistent (ADR-015): an author/target id that fails the self-check stays raw (`target_handle_raw`) rather than guessed. Honesty note (from the spike): resolved ids were not cross-checked against an external source (no-network discipline) — the buttons target the author/owner by construction, so confidence is high but ids are not independently verified; the runtime id↔handle self-check is what enforces correctness. Numbering is append-only (follows ADR-025).
