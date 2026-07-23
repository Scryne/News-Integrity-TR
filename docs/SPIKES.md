# Phase-0 Spike Findings

**Status: all three Phase-0 spikes carry a go/no-go verdict — S1 GO (DOM-anchor,
2026-07-20), S2 recorded (authenticated SPN2 required; archive.today manual-first),
S3 GO. Phase 0 is CLOSED.**

**Phase-gate status:** the gate is now OPEN for all Phase-0-dependent production
work. S1 was the **last open Phase-0 gate**; its fallback-approach decision is
closed and recorded as **ADR-026** (draft pending commit to `DECISIONS.md`).
Downstream build constraints still stand *outside* the Phase-0 gate — notably the
Wayback adapter block (SPN2 refuses x.com, ADR-025) and archive.today manual-first
(ADR-007/S2); these gate specific adapters, not Phase 0.

Source: Scryne's 2026-07-17 spike run (combined spikes-extension helper +
`archive_probe.py`). Paste-backs recorded in `spikes/s1-rest-id/README.md`,
`spikes/s2-archive/README.md`, `spikes/s3-capture/README.md`. Raw data:
`spikes/spikes-test/`, `spikes/s1-rest-id/s1-deduplicated.json`,
`spikes/s2-archive/s2-probe-output-2026-07-17.log`.

Exception — provenance note: the **S2 authenticated-SPN2 confirmation run
(2026-07-19)** below was **Claude-executed in-session at Scryne's explicit
instruction** (S3 keys from `.env`), not a Scryne paste-back. Flagged distinctly so
the paste-back-only provenance model is not misrepresented. Raw log:
`spikes/s2-archive/s2-auth-spn2-output-2026-07-19.log`; paste-back in
`spikes/s2-archive/README.md`.

Phase gate: production code does not start until all three spikes have a
go/no-go verdict recorded here.

---

## S1 — rest_id + follower_count extraction (Risk R1)

**Verdict: GO — candidate 3 (DOM-anchor) is the primary `rest_id` extractor**,
with a mandatory aria-`@handle` self-check and a profile-page fallback (recorded
2026-07-20). This **supersedes** the earlier no-go, which was specific to the
*fiber-walk* approach only (retained below). **S1 was the last open Phase-0 gate;
with this verdict all of S1/S2/S3 carry a go/no-go and Phase 0 is closed.** The
fallback-approach decision — the only remaining S1 open item — is **CLOSED**,
recorded as **ADR-026** (draft pending commit): DOM-anchor primary + self-check,
revised fallback ladder, GraphQL interception parked.

The fiber-walk finding below is kept as a point-in-time record of *why the fiber
approach was rejected*; it is not the current verdict.

### Fiber-walk approach (probe s1-0.3) — NO-GO (retained for the record)

Findings:

- The fiber walk never located the tweet object (`tweet_path=null` in all rows),
  so the canonical `tweet.core.user_results.result` author path was never
  reached. Every `ok_rest_id=true` resolution instead came from
  `…tweet[.quoted_status].entities.media[0].additional_media_info.source_user.user_results.result`
  — the **media source user, not the post author**. Proven on the go/no-go
  permalink page: author is @bpthaber (visible in the S3 crop of the same page),
  but S1 resolved @aykiri / 367071498, the account the embedded video is
  attributed to. The `ok_rest_id=true` flags are false positives.
- Rows without attributed media resolved nothing (0/8 on the sama permalink).
- `followers_from` was only ever `legacy`, on that same media path;
  `relationship_counts` never observed.
- `quoted_author` / `retweeted_author` / `reply_to`: null in every row.
- Obfuscated fiber key suffix changes on every page navigation, stable across
  all rows within one page ⇒ prefix matching is mandatory.
- **Repost coverage closed (2026-07-18 re-run,
  `nit-s1-reports-2026-07-18T17-41-41-532Z.json`).** Re-run on Scryne's own
  profile (`x.com/whosb3rkay`); all 5 scanned rows were genuine repost rows
  (visually confirmed by the "yeniden yayınladı" banner — not machine-recorded
  in the export; a profile-repost substitute for the originally-requested
  home-timeline row, same repost render path). Even with repost rows exercised,
  `retweeted_author=null` and `tweet_path=null` in all 5, and every
  `ok_rest_id=true` still resolved via the `additional_media_info.source_user`
  path. The earlier coverage gap ("`retweeted_author` never exercised") is
  closed: the case is now exercised and the fiber walk still does not reach it.
  Profile-page fiber suffix `izisbj6tu2l`, stable across all 5 rows — a 6th
  distinct per-page suffix, reconfirming prefix matching.

### DOM-anchor approach (probe s1-dom-0.1) — GO (recorded 2026-07-20)

Source (Scryne's paste-backs, 2026-07-19/20): five page-type runs — `Home
timeline`, `Permalink`, `Quoted post`, `Reply`, `Repost` — plus two targeted
follow-state checks (a)/(b). Read-only console snippet
`spikes/s1-rest-id/console-snippet-dom-anchor.js` (no network).

- **Author rest_id is carried by the follow/unfollow button's `data-testid`
  (`"<rest_id>-follow"` / `"-unfollow"`).** On the four `/status/` permalink runs the
  focused-post author resolved correctly on 3/4 — umunsiofficial `994935396248276992`,
  numbertwentytu `1648744476930654208`, rejturk `1376312098108608513` — each with the
  button's aria `@handle` matching the visible author.
- **Zero misattribution across every row of all five runs.** A resolved id is always
  the correct author (aria `@handle` == post author); otherwise the row is a clean
  `absent`, never a false positive — the exact opposite of the fiber-walk failure mode.
  Hence the **mandatory self-check**: accept an id only if the button's `@handle`
  equals the post's visible author, else fall through — which makes misattribution
  structurally impossible.
- **The inline anchor renders only for accounts you do NOT follow.** The one absent
  permalink (platcornweb) and check (a) on a followed account (`erenn0189`:
  `match=absent`, `follow_anchors=[]`, no subscribe button) pin the trigger to the
  **follow relationship**, not subscription layout. Timeline articles carry no anchor
  at all (Home-timeline run 4/4 absent) — the author rest_id is simply not in a
  timeline article's DOM.
- **Profile-page fallback closes the followed/timeline gap.** Check (b) on the followed
  account's profile header returned `data-testid="1470799207837667331-unfollow"` — the
  profile header follow/unfollow button carries the owner's rest_id regardless of
  follow state, so it is a ~universal author-rest_id source (own profile "Edit profile"
  excepted; not a study subject). The header also shows **follower_count as text**, so
  one profile visit yields both id and count.
- **The snippet's `other id-bearing` catalog ruled out alternatives.** The only other
  id anchor found was `<id>-subscribe` (subscription accounts only);
  `UserAvatar-Container-<handle>` carries the *handle*, not the id; the rest is
  tweet-id / avatar-asset-id / view-count / colour / CSS / blob-UUID noise. Beyond
  follow/unfollow (and the rare subscribe), no general-purpose DOM rest_id source
  exists — which is why the profile header is the fallback of record.

Follower_count: **upgraded from "rarely reachable" (fiber walk) to "reliable whenever
a profile is visited"** (header text). Still nullable everywhere; a missing id or count
never blocks a capture (extractor skill rule 4).

Honesty notes: (1) resolved ids were **not** cross-checked against an external source
(no-network discipline) — the follow/unfollow and profile-header buttons target the
author/owner *by construction*, so confidence is high but the id is not independently
verified. (2) **Wiring the profile-page fallback into the capture flow is a build-time
design detail, not part of this verdict** ("post has no id → visit the author's profile
once → read id + follower from the header → upsert/cache by rest_id"); ADR-026 points at
this direction without mandating an implementation.

**Decision (S1 fallback-approach) — CLOSED → ADR-026 (draft pending commit).**
DOM-anchor primary + mandatory aria-`@handle` self-check; revised fallback ladder
(primary post-inline anchor → fallback-1 profile-page header anchor → fallback-2
hovercard, opportunistic → backstop candidate 2 manual paste); candidate 4 (GraphQL
interception) parked (its triggers — misattribution or total absence — were not
observed; stays in the ARCHITECTURE.md §v2 backlog). Consistent with ADR-015
(NULL-tolerant edge targets).

---

## S2 — archive service submission behavior (Risk R2)

### Wayback (SPN2)

**Verdict: anonymous SPN2 is NOT viable.** 3/3 submits to
`POST https://web.archive.org/save/` returned HTTP 401
`{"message":"You need to be logged in to use Save Page Now."}`. The job-id /
status-poll flow could not be observed anonymously. An automated Wayback
adapter therefore requires **authenticated SPN2** (archive.org account +
S3-style API keys). This contradicts the design assumption that Wayback works
automatically without credentials.

→ **ADR-024 (authenticated SPN2, archive.org account + S3 keys): recorded
2026-07-19** in `DECISIONS.md`, amending ADR-007's no-credentials assumption.

**Authenticated SPN2 confirmation run — DONE (2026-07-19, Claude-executed; see
provenance note above).** 3 authenticated submits, all HTTP 200 (vs anonymous
3/3 → 401), so the S3 keys are accepted and the login barrier is cleared. Two
outcomes:

- **Auth + status-poll flow CONFIRMED live** — discharges ADR-024's inference. On a
  fresh, non-blocked URL the submit returned
  `{"url":…,"job_id":"spn2-716f8156635f7118b88c868caf6dddee89dafd90"}`;
  `GET /save/status/<job_id>` went `pending → success` (~12s); success produced
  `archive_url = https://web.archive.org/web/20260719190822/https://example.com/?nit-spn2-confirm=1784488098`.
  No 429 / retry-after across 3 spaced calls.
- **NEW BLOCKER — x.com is `error:blocked-url` on SPN2.** The X-post submit returned
  HTTP 200 but `{"status":"error","status_ext":"error:blocked-url"}` ("currently
  facing some limitations when it comes to archiving this site"); **no `job_id` is
  ever issued for an x.com/twitter.com URL.** Because the Wayback adapter exists only
  to archive X posts, authenticated SPN2 **cannot currently archive our target content
  at all** — the ADR-024 auth fix is **necessary but not sufficient**. This contradicts
  ADR-024's working premise that authenticated SPN2 yields a usable Wayback adapter for
  X posts, so it is **not resolved here** (per the working agreement, no silent
  redesign) → **candidate ADR-025**. Options on the table, undecided: (a) Wayback
  demoted to manual-only for X and routed through the same manual-assist queue as
  archive.today; (b) request an x.com archiving exception from archive.org
  (info@archive.org, per the block message); (c) drop Wayback from the MVP archive set.
- **Error taxonomy observed** (for the eventual adapter): `error:blocked-url`
  (site-level, ~permanent) vs `error:too-many-daily-captures` (transient; example.com
  hit its per-URL cap = 5/day). The adapter should treat these differently.

### archive.today

**Verdict: manual-first — observation-supported** (updated 2026-07-19).
Automated submit is actively challenged, so archive.today routes straight to
`manual_pending`. This is exactly the behavior ADR-007 designed the manual-assist
queue for; no ADR contradiction.

- From a TR network on the reachable front, 3/3 `POST https://archive.md/submit/`
  returned **HTTP 429 with a captcha/recaptcha challenge body** on the *first*
  submit each time (0.15–0.22s, three byte-identical 55511-byte bodies). The
  instant challenge + identical bodies read as **automation/client detection, not
  quota/throttle**; the 60s interval is therefore not the operative factor (the
  first request is already challenged). Go/no-go: **0 of 3 without a challenge**
  → manual-first (pre-registered criterion).
- **Front-domain finding:** `archive.ph` is TR-blocked at the network level
  (TCP timeout, 2026-07-17 run) and 302-relays to `archive.md` (homepage and
  `/submit/`); `archive.md` is directly reachable from a TR network (200 OK,
  egress 95.70.153.129 @ AS12735). The TR block is **domain-specific**, not
  service-wide. (The 302-relay was observed manually; this run's log begins
  already on archive.md, and `archive_probe.py` was hand-pointed at archive.md
  for the run.) Design impact: the manual-assist loop and probe currently
  hardcode `archive.ph` (`ARCHITECTURE.md` §3.4, `PLAN.md` S2) — left as a
  backlog design note (the archive.today front should be configurable, no
  hardcoded front; includes adding `--base-url` to `archive_probe.py`), not
  changed here.

Backlog item **CLOSED (with caveat)** (2026-07-19): the one-time non-TR
verification run existed to observe archive.today's real response shape before
reconsidering automation. That shape is now observed on the reachable front — a
genuine automation challenge, not a network black hole — so the item is
answered. Caveat: the observing IP was still Turkish (AS12735), so "a non-TR IP
would be challenged identically" is an inference (automation detection is
IP-geography-independent in character), not a direct observation. It does not
change the manual-first verdict.

Rate limits: 429 was the challenge vehicle, fired on the first submit — no
genuine retry-after/quota signal was reachable, so the 60s polite-interval
default remains unvalidated.

---

## S3 — captureVisibleTab + crop geometry (Risk R3)

**Verdict: GO** (recorded 2026-07-19). Crop is pixel-exact at default zoom and
across every scaling/zoom variant tested; the go/no-go criterion (default zoom +
≥1 scaling variant) is met.

Findings:

- **Pixel-exact on the full variant matrix.** Crop width = `round(598 CSS × dpr)`
  holds across the whole dpr range 0.9–1.25:

  | Variant | dpr | viewport (device px) | crop width | check |
  |---|---|---|---|---|
  | 1 — 100% scaling / 100% zoom | 1.00 | 1920×917 | 598 | 598 × 1.00 |
  | 2 — 125% scaling / 100% zoom | 1.25 | 1920×877 | 748 | 598.4 × 1.25 |
  | 3 — browser zoom 90% | 0.90 | 1920×917 | 538 | 597.8 → 538 |
  | 4 — browser zoom 110% | 1.10 | 1920×917 | 658 | 657.8 → 658 |

  Variant 2 was additionally pixel-exact on 5/5 page types (timeline, permalink,
  quoted incl. embedded quote, reply, repost incl. repost banner). The viewport
  PNG stays 1920 device px wide across all variants (`captureVisibleTab` captures
  physical viewport pixels; browser zoom folds into dpr, not capture size). Crop
  heights differ per captured post, so this is a width×dpr invariant, not a
  same-post comparison. All crops visually edge-to-edge, no drift/neighbor bleed.
- **Variant 5 — post partially scrolled off-screen: crop CLAMPS to the visible
  region** (598×401 device px, full width, height truncated; the off-screen
  portion is lost, visibly mid-cut). Design note: `captureVisibleTab` can only
  see the viewport, so the real tool must `scrollIntoView` + guarantee full
  visibility before capture, else it flips `clamped=true`/`crop_failed` — which
  never blocks a capture.
- dpr persisted in the filename for the zoom variants
  (`…devicePixelRatio=0.9/1.1`); the dpr 1.0 variants carry no suffix. Earlier
  alert/crop-rect values were not persisted; dpr was derived from image geometry
  and confirmed against the display config.
- Coverage note carried forward: the combined helper manifest ships `<all_urls>`
  pre-added, so whether x.com-only `host_permissions` suffice for
  `captureVisibleTab` is still not exercised. Not blocking; carry into build.
