# S1 — rest_id + follower_count extraction (Risk R1)

**Question:** can we reliably read the author's immutable `rest_id` (and, nice-to-have,
`followers_count`) out of X's DOM, on the page types we capture from?

**Go/no-go:** GO if `rest_id` is reliably extractable on **≥ the permalink page**.
Follower count is nice-to-have (nullable everywhere). If fiber extraction is flaky,
the fallback ladder is (a) hover-card DOM scrape, (b) manual rest_id paste field —
capture is never blocked either way.

The artifact `console-snippet.js` reads the page only. No network, nothing sent.

## How to run

1. Log into **x.com** normally in Chrome.
2. Open DevTools (`F12`) → **Console**. If the console blocks pasting, type
   `allow pasting` and press Enter first.
3. Open `console-snippet.js`, copy the **whole file**, paste into the Console, Enter.
   It prints a table for every tweet on screen immediately.
4. For a single specific tweet: in the **Elements** panel select that tweet's
   `<article data-testid="tweet">` (so it becomes `$0`), then run `NIT.extract($0)`.
5. To hand results back to me: run **`copy(NIT.report())`** and paste the copied
   JSON. It contains handles, rest_ids, follower counts, and the property paths —
   **no post text**.

## Test these page types (run the snippet on each, `copy(NIT.report())` each time)

| # | Page | What to open | What we're checking |
|---|---|---|---|
| 1 | **Home timeline** | your Following/For-you feed | rest_id + followers present in feed props? |
| 2 | **Permalink** | open a single post (`x.com/<user>/status/<id>`) | the go/no-go page — rest_id must resolve here |
| 3 | **Quoted post** | a post that quote-tweets another | **both authors**: `author` + `quoted_author` populated? |
| 4 | **Reply thread** | open a reply (a post that replies to another) | `reply_to` populated; author still resolves |
| 5 | **Repost/RT** (if handy) | a reposted item in a timeline | `retweeted_author` populated; author = reposter |

Also, to check obfuscated-key stability (PLAN asks for this): note the printed
`fiber key suffix`, then **hard-reload the page** and run the snippet again —
tell me whether the suffix changed (expected: changes per load; the snippet
matches by prefix so it shouldn't matter, but we want it confirmed).

## Paste back to me

For each page type, paste the `copy(NIT.report())` JSON, and note:

- Did **rest_id** resolve for the primary author? (the `ok_rest_id` flag / `rest_id` field)
- Did **followers** resolve, and from where (`followers_from`: `legacy` / `relationship_counts` / `none`)?
- For the quoted post: are **both** `author` and `quoted_author` filled?
- The **`author_path` / `tweet_path`** strings (these are the actual finding — the real property path on your live bundle).
- Whether the **fiber key suffix** changed across a reload.
- Anything that threw, was blank, or looked wrong.

Template you can fill in:

```
S1 page 1 (timeline):   rest_id=Y/N  followers=Y/N(from=…)  notes=…
S1 page 2 (permalink):  rest_id=Y/N  followers=Y/N(from=…)  notes=…
S1 page 3 (quoted):     author rest_id=Y/N  quoted_author rest_id=Y/N  notes=…
S1 page 4 (reply):      rest_id=Y/N  reply_to filled=Y/N  notes=…
S1 page 5 (repost):     author=reposter? Y/N  retweeted_author=Y/N  notes=…
fiber suffix stable across reload? …
+ the copy(NIT.report()) JSON for each
```

I turn these into the S1 section of `docs/SPIKES.md` (verdict + the confirmed
property paths + fallback), and — only if a finding contradicts the architecture —
propose an ADR-024+ for your approval.

## Paste-back — 2026-07-17 run (spikes-extension helper, probe s1-0.3)

Sequential run timeline → permalink → quoted → reply → repost without clearing;
accumulated exports deduplicated (repeated blocks byte-identical). Clean data:
`s1-deduplicated.json` (5 unique page captures).

```
S1 page 1 (timeline, x.com/home):            rest_id=2/4 rows  followers=2/4 (from=legacy)  — see caveat
S1 page 2 (permalink, …/status/2078065685536579776): ok_rest_id=Y BUT resolved the WRONG user — see caveat
S1 page 3 (quoted, …/quotes):                author flags 4/4 (caveat)  quoted_author=N (null in all rows)
S1 page 4 (reply, CrafterMind/status/…467):  reply author rest_id=N  reply_to filled=N
S1 page 5 (repost, sama/status/…493):        rest_id=0/8  retweeted_author=N
  (note: page 5 ran on the reposted post's permalink, not a timeline repost row,
   so retweeted_author was not truly exercised)
fiber suffix stable? Changes on EVERY page navigation
  (v9qip2xayda → 4wd1efys5fg → uz53xb2op8e → r9l2guyuu8l → 9rotvxpk1v);
  stable across all rows within one page. Prefix-matching confirmed necessary.
  Same-page hard reload not separately tested.
```

**CAVEAT — the actual finding:** every resolved rest_id came via
`…tweet[.quoted_status].entities.media[0].additional_media_info.source_user.user_results.result`
— the media **source** user, not the post author. `tweet_path=null` in all 23 rows
(the walk never located the tweet object; the canonical
`tweet.core.user_results.result` path was never reached). Proof on the go/no-go
page: the permalink post is by @bpthaber (visible in the S3 crop of the same
page) but S1 resolved handle=aykiri / rest_id=367071498 — the account the
embedded video is attributed to ("Aykırı adlı kullanıcıdan"). Rows without
attributed media resolved nothing (0/8 on the sama page). `followers_from`:
only ever `legacy`, on that same path; `relationship_counts` never seen.
`quoted_author` / `retweeted_author` / `reply_to`: null in every row.

As measured, author rest_id is NOT reliably extractable on any tested page
type, including permalink — the `ok_rest_id=true` flags are false positives.
Verdict + fallback-ladder decision pending discussion (docs/SPIKES.md).

## Paste-back — 2026-07-18 repost re-run (profile page, probe s1-0.3)

Export: `nit-s1-reports-2026-07-18T17-41-41-532Z.json`. Page:
`x.com/whosb3rkay` (own profile) — used instead of the home timeline because all
five rows there are guaranteed genuine repost rows (visually confirmed via the
"yeniden yayınladı" banner), so `retweeted_author` was truly exercised this time.

```
S1 repost re-run (profile, 5 rows): retweeted_author=N (5/5)  tweet_path=null (5/5)
  ok_rest_id=Y (5/5) BUT all via additional_media_info.source_user (media false-pos)
  quoted_author=N  reply_to=N  followers_from=legacy (5/5)
fiber suffix: izisbj6tu2l — stable across all 5 rows (6th distinct per-page suffix)
```

Closes the prior coverage gap ("repost never truly exercised"): repost rows are
now exercised and the fiber walk still never reaches `retweeted_author` or the
tweet object. Verdict unchanged — **no-go with the current fiber-walk approach**;
the fallback-approach decision (4 candidates) is still open.
