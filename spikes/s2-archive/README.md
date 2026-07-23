# S2 — archive service submission behavior (Risk R2)

**Question:** how do Wayback SPN2 (anonymous) and archive.today actually respond
to a post submission — redirect? `/wip/`? refresh header? CAPTCHA? — and what is
a polite minimum interval? This decides whether archive.today gets an automated
adapter or routes **straight to `manual_pending`**.

**Go/no-go:** GO for an automated archive.today adapter if **≥2 of 3** submissions
succeed **without a challenge**. Otherwise archive.today is manual-first — the
queue + manual-assist loop (already in the design) becomes its normal path, with
zero rework. Wayback is expected to work automatically; we confirm the job-id +
status-poll flow and anonymous rate limits.

**I do not run this — you do.** It contacts external services (their intended
use). It is polite by construction and supports `--dry-run`.

## How to run

1. `pip install httpx`
2. Put 2–3 **real public X post URLs** in `urls.txt` (see `urls.example.txt`
   format), ideally posts you are already viewing.
3. Review the plan without touching the network:
   ```
   python archive_probe.py --urls-file urls.txt --dry-run
   ```
4. Real run (≥60s between every external call, ~a few minutes total):
   ```
   python archive_probe.py --urls-file urls.txt
   ```
   Narrower runs if you want to isolate one service:
   ```
   python archive_probe.py --urls-file urls.txt --only wayback
   python archive_probe.py --urls-file urls.txt --only archive_today
   ```

The script prints a verbose block per call and ends with a `PASTE THIS BACK`
summary.

## What to record / paste back

- The entire **`PASTE THIS BACK`** block (per-service status + archive_url +
  challenge + notes).
- For **archive.today** specifically:
  - How many submits succeeded **without a challenge** (the go/no-go number, X of N).
  - The response shape observed: `redirect` (Location to `/<id>`), `wip`
    (`/wip/` link), `refresh` (meta/refresh header), `challenge`, or `no_redirect`.
  - Any CAPTCHA / Cloudflare "Just a moment" page.
- For **Wayback**:
  - Did the submit return a `job_id`? Did polling reach `status=success`?
  - The final `archive_url`.
  - Any throttling / non-JSON responses (sign of anonymous rate limiting).
- Whether **60s spacing** felt sufficient or you saw `429` / `retry-after`.

Template:

```
S2 wayback:        job_id=Y/N  reached success=Y/N  archive_url=…  throttled=Y/N
S2 archive.today:  succeeded_without_challenge = _ of _
                   shapes seen: [redirect|wip|refresh|challenge|no_redirect]
                   captcha/cloudflare seen: Y/N
observed polite interval: … (60s ok? throttled?)
+ the full PASTE THIS BACK block
```

I turn this into the S2 section of `docs/SPIKES.md` (verdict: automated
archive.today adapter vs manual-first, plus the confirmed Wayback flow and the
min-interval defaults). If the verdict changes an assumption in the design, I
propose it as an ADR-024+ for your approval before any adapter is built.

## Paste-back — 2026-07-17 run (TR residential network, 60s interval, 3 URLs)

```
S2 wayback:        job_id=N (3/3 → HTTP 401)  reached success=N  archive_url=—  throttled=N
S2 archive.today:  succeeded_without_challenge = 0 of 3
                   shapes seen: none — TCP connect timeout (WinError 10060) on
                   archive.ph homepage AND /submit/, all attempts; no HTTP response
                   captcha/cloudflare seen: N (connection never established)
observed polite interval: 60s kept; no 429/retry-after seen (both services
                   failed before rate limiting was reachable)

================= PASTE THIS BACK =================
- wayback        no_job_id      https://x.com/bpthaber/status/2078065685536579776
    notes       : ['message: You need to be logged in to use Save Page Now.']
- archive_today  error          https://x.com/bpthaber/status/2078065685536579776
    notes       : ['warmup failed: [WinError 10060] …', '[WinError 10060] …']
- wayback        no_job_id      https://x.com/CrafterMind/status/2078156154262450467
    notes       : ['message: You need to be logged in to use Save Page Now.']
- archive_today  error          https://x.com/CrafterMind/status/2078156154262450467
    notes       : ['warmup failed: [WinError 10060] …', '[WinError 10060] …']
- wayback        no_job_id      https://x.com/sama/status/2077817060068057493
    notes       : ['message: You need to be logged in to use Save Page Now.']
- archive_today  error          https://x.com/sama/status/2077817060068057493
    notes       : ['warmup failed: [WinError 10060] …', '[WinError 10060] …']
(WinError 10060 = Windows TCP connect timeout; full verbatim log:
 s2-probe-output-2026-07-17.log)
```

Notes:
- Anonymous Wayback SPN2 no longer exists: POST https://web.archive.org/save/
  → 401 `{"message":"You need to be logged in to use Save Page Now."}` on all 3.
  Contradicts "Wayback is expected to work automatically" → ADR-024+ candidate
  (authenticated SPN2 with archive.org API keys).
- archive.ph was unreachable at TCP level from this network (Turkish ISP block
  of archive.today domains is the likely cause; web.archive.org connected fine).
  Go/no-go = 0 of 3, but failure mode is network unreachability, not challenge.
  Per the pre-registered criterion: archive.today → manual-first path.

## Paste-back — 2026-07-18 archive.today re-run (TR network, WARP off, archive.md front)

Log: `s2-probe-output-2026-07-18-archive-md.log`. `archive_probe.py` was hand-
pointed at `archive.md` (`ARCHIVE_TODAY_HOST`) because `archive.ph` 302-relays
everything to `archive.md` (empty body) and is TR-blocked; the probe does not
follow redirects, so the earlier run never reached the real endpoint.

```
S2 archive.today (archive.md): succeeded_without_challenge = 0 of 3
  shape: HTTP 429 + captcha/recaptcha body on the FIRST submit each time
  bodies byte-identical (55511), 0.15–0.22s → automation detection, not throttle
  homepage archive.md/ = 200 OK; egress 95.70.153.129 @ AS12735 (TR, WARP off)
observed interval: 60s kept but not operative — first submit already challenged
```

Findings: (1) automated submit is actively challenged → manual-first, now
observation-supported (not just inferred from a network block); (2) the TR block
is domain-specific — archive.ph unreachable, archive.md reachable, both are
archive.today fronts. Non-TR verification-run backlog item CLOSED (with caveat):
real response shape is now observed on the reachable front, but the observing IP
was still TR, so IP-geography independence is an inference, not an observation.

> Backlog (not done here): make the archive.today front configurable (no
> hardcoded front) rather than switching the hardcode to archive.md; add
> `--base-url` to `archive_probe.py` (currently hand-edited to archive.md).

## Paste-back — 2026-07-19 authenticated SPN2 confirmation run (Claude-executed)

**Provenance (read this first):** run by Claude in-session at Scryne's explicit
instruction — NOT a Scryne paste-back. Keys came from `.env`
(`NIT_WAYBACK_S3_ACCESSKEY` / `NIT_WAYBACK_S3_SECRET`, both 16 chars, added
2026-07-19). The probe gained an opt-in `--auth` path (adds
`Authorization: LOW <access>:<secret>`; anonymous stays the default, so the
2026-07-17 anonymous result is preserved). Verbatim log:
`s2-auth-spn2-output-2026-07-19.log`. Recorded distinctly so the SPIKES.md
provenance model stays honest — this is a machine-run confirmation, not a human
paste-back.

3 authenticated submits, **all HTTP 200** (anonymous was 3/3 → 401, so the S3
keys are accepted and the "you need to be logged in" barrier is cleared):

```
S2 wayback (authenticated SPN2):  job_id=Y  reached success=Y
                                  archive_url=(see #3)  throttled=N (no 429/retry-after, 3 spaced calls)

1) x.com/bpthaber/status/2078065685536579776
     → 200  status=error  status_ext=error:blocked-url         (NO job_id)
       "We're currently facing some limitations when it comes to archiving this site."
2) https://example.com/
     → 200  status=error  status_ext=error:too-many-daily-captures   (NO job_id)
       "already captured 5 times today, which is a daily limit ... for that Resource type"
3) https://example.com/?nit-spn2-confirm=1784488098   (fresh, cache-busted)
     → 200  job_id=spn2-716f8156635f7118b88c868caf6dddee89dafd90
       poll 0: status=pending  →  poll 1: status=success   (~12s @ poll_interval 6s)
       archive_url: https://web.archive.org/web/20260719190822/https://example.com/?nit-spn2-confirm=1784488098

================= PASTE THIS BACK =================
- wayback  no_job_id  x.com/bpthaber/.../2078065685536579776   (error:blocked-url)
- wayback  no_job_id  https://example.com/                     (error:too-many-daily-captures)
- wayback  done       https://example.com/?nit-spn2-confirm=1784488098
    archive_url : https://web.archive.org/web/20260719190822/https://example.com/?nit-spn2-confirm=1784488098
```

**Findings:**
1. **Authentication confirmed.** S3 keys accepted (200 on all 3, vs anonymous 401).
   This directly confirms ADR-024's inference, which previously rested only on the
   anonymous 401 — not on an observation of the authenticated path.
2. **job_id + status-poll flow confirmed live.** Submit returns `{url, job_id}`;
   `GET /save/status/<job_id>` transitions `pending → success`; success yields
   `timestamp` + `original_url` → `web/<ts>/<orig>`. The backlog item's core goal is
   met (observed once, on a non-blocked URL).
3. **NEW BLOCKER — x.com is `error:blocked-url` on SPN2.** Authenticated SPN2 returns
   200 but refuses to archive x.com/twitter.com at the domain level, so no `job_id` is
   ever issued for an X post. Since the Wayback adapter exists only to archive X posts,
   **authenticated SPN2 cannot currently archive our target content at all** — the
   ADR-024 auth fix is necessary but **not sufficient**. This contradicts ADR-024's
   working premise and needs a decision (candidate **ADR-025**); NOT resolved here.
4. **Error taxonomy for the adapter:** `error:blocked-url` (site-level, ~permanent) vs
   `error:too-many-daily-captures` (transient; per-URL cap observed = 5/day). The
   adapter should distinguish permanent block from transient cap.
