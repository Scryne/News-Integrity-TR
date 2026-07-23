---
name: x-dom-extraction
description: >-
  Rules for reading data out of the X (twitter) DOM in News Integrity TR. Load
  this before writing or modifying any extension code that touches X's DOM or
  React fiber, adds a selector, or defines an extractor — in practice, anything
  in extension/src/content/x-dom.ts and its callers. Enforces: every X selector
  and the React-fiber walk live ONLY in x-dom.ts, every extractor returns
  {value, method} | null and fails soft, an extractor_version constant is
  stamped into the sidecar, and a capture is NEVER blocked by extraction failure.
---

# x-dom-extraction

X's markup and its obfuscated React-fiber keys change without notice — this is
the project's single highest-likelihood breakage (Risk R1). The mitigation is
containment: all fragility lives in one module, everything fails soft, and the
evidence flow survives any extraction miss.

## The rules

1. **One module owns all X coupling.** Every CSS selector against X, every
   `data-testid` string, and the entire React-fiber / `__reactProps$…` /
   `__reactFiber$…` walk live **only** in `extension/src/content/x-dom.ts`. No
   other file (content script, overlay, service worker) contains an X selector
   or reaches into fiber internals. When X breaks, exactly one file changes.

2. **Never hardcode the obfuscated key suffix.** Find fiber/props keys by prefix
   at runtime: `Object.keys(el).find(k => k.startsWith("__reactFiber$"))`. The
   suffix is stable within a page load but changes across bundle versions.

3. **Every extractor returns `{ value, method } | null`.** `value` is the datum;
   `method` records *how* it was obtained (e.g. `"dom-anchor"`, `"profile-header"`,
   `"hovercard"`, `"manual"`). A clean miss returns `null` — never throws, never
   returns a fabricated or guessed value. Extractors are pure of side effects and
   swallow their own exceptions (return `null` on any error).

   ```ts
   export type Extracted<T> = { value: T; method: string } | null;

   export function extractRestId(article: Element): Extracted<string> {
     try {
       // ...DOM-anchor extraction...
       return restId ? { value: restId, method: "dom-anchor" } : null;
     } catch {
       return null;   // fail soft — never throw out of an extractor
     }
   }
   ```

4. **A capture is never blocked by extraction failure.** Missing follower count
   ⇒ field is `NULL`, `method` recorded in the sidecar's `extraction` block, and
   the capture still lands. The only hard requirement is enough to identify the
   evidence; when `rest_id` cannot be extracted, the overlay offers the manual
   rest_id paste field (fallback (b)) rather than aborting. Extraction quality is
   metadata; the screenshot + hash + archive chain is the evidence.

5. **Integrity over completeness — never guess an identity.** If a target
   rest_id (edge) or an author rest_id is not extractable, store the raw handle
   as a fallback (`target_handle_raw`) or prompt for manual entry. Never
   synthesize, infer, or approximate a numeric id. rest_id stays a `string`
   end-to-end (see the `evidence-integrity` skill).

6. **`EXTRACTOR_VERSION` constant, stamped into evidence.** `x-dom.ts` exports a
   version constant (e.g. `export const EXTRACTOR_VERSION = "1.0.0"`); it is
   written into the sidecar `extraction.extractor_version`. Bump it whenever the
   extraction logic changes so every artifact records which extractor produced
   it. The rest_id `method` also goes into `extraction.rest_id_method`.

7. **Extraction runs only inside user click handlers.** The MutationObserver
   only *decorates* the UI (injects buttons); it must never extract, fetch, or
   read post content. No extraction on scroll, hover-sweep, or timer — that would
   cross the "no automated collection" boundary. Extraction happens when, and
   only when, the user clicks `[Capture]`/`[Edge]`.

8. **Testable pure core + saved fixtures.** The parsing logic (given a fiber
   props object or a saved DOM fragment → fields) is pure and unit-tested
   (vitest) against 1–2 saved fixtures per page type (timeline, permalink,
   quoted, reply). Fixtures are how R1 breakage is caught early; keep them
   current when you touch extraction.

## Fallback order (per ADR-026 / PLAN S1)

Author `rest_id` extraction is **DOM-anchor-based** — the React-fiber walk is no-go
(it misattributes the media-source user; `docs/SPIKES.md` §S1). Every rung applies
the **aria-`@handle` self-check**: accept an id only if the button's `@handle`
equals the post's visible author, else return `null` and fall through — so a wrong
identity is never recorded.

1. **Post-inline follow/unfollow anchor (primary)** — the author's `rest_id` is the
   numeric prefix of the button's `data-testid` (`"<rest_id>-follow"` /
   `"-unfollow"`). Present for accounts the user does NOT follow; absent for followed
   accounts and on timeline rows.
2. **Profile-page header anchor (fallback-1)** — the profile header follow/unfollow
   button carries the owner's `rest_id` regardless of follow state (~universal), and
   the header also renders `follower_count` as text. Resolves followed accounts and
   timeline-only captures (once per author, then cached by `rest_id`).
3. **Hover-card DOM scrape (fallback-2, opportunistic)** — only if a card is already
   open from user hover; never force-hover programmatically.
4. **Manual rest_id paste field (backstop)** — in the overlay.

**The capture is never blocked** at any rung (rule 4). Tweet id + created_at come
from `time[datetime]` / the `/status/` permalink; follower_count from the profile
header.

## Checklist before you commit extension code

- [ ] No X selector or fiber access outside `x-dom.ts`.
- [ ] No hardcoded `__reactFiber$`/`__reactProps$` suffix — prefix match only.
- [ ] Every extractor returns `{value, method} | null` and cannot throw.
- [ ] Missing fields degrade to `NULL` + recorded `method`; capture still completes.
- [ ] No identity is ever guessed; rest_id stays a string everywhere.
- [ ] `EXTRACTOR_VERSION` bumped if logic changed; stamped into the sidecar.
- [ ] No extraction outside a user click handler; observer only decorates.
- [ ] Pure parsing paths covered by fixture-based unit tests.
