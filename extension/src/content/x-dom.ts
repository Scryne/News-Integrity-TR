/**
 * x-dom.ts — the ONLY module that knows X's markup (x-dom-extraction skill).
 *
 * Every selector, `data-testid` string and markup heuristic lives here; when X
 * changes, this file changes. Every extractor returns `{ value, method } | null`
 * and never throws: a miss degrades to NULL plus a recorded method, and the
 * capture still lands. No identity is ever guessed.
 *
 * Author rest_id follows ADR-026 (S1 DOM-anchor GO): the follow/unfollow
 * button's `data-testid="<rest_id>-follow|-unfollow"`, accepted ONLY when the
 * button's aria `@handle` equals the post's author. Ladder:
 *   1. post-inline anchor (`dom-anchor`)
 *   2. profile-page header anchor (`profile-header`) — when the page is the
 *      author's profile, regardless of follow state
 *   3. an already-open hover card (`hovercard`) — never force-hovered
 *   4. manual paste in the overlay (`manual`)
 *
 * Extraction is called only from click handlers (rule 7); the MutationObserver
 * in index.ts only decorates.
 */

export const EXTRACTOR_VERSION = "1.0.0";

export type Extracted<T> = { value: T; method: string } | null;

const SEL = {
  article: 'article[data-testid="tweet"]',
  userName: '[data-testid="User-Name"]',
  tweetText: '[data-testid="tweetText"]',
  socialContext: '[data-testid="socialContext"]',
  followAnchor: '[data-testid$="follow"]',
  hoverCard: '[data-testid="HoverCard"]',
  statusLink: 'a[href*="/status/"]',
} as const;

const FOLLOW_RE = /^(\d{1,25})-(?:un)?follow$/;
const HANDLE_RE = /@([A-Za-z0-9_]{1,15})/;
const STATUS_PATH_RE = /^\/([A-Za-z0-9_]{1,15})\/status\/(\d{1,25})/;
const PROFILE_PATH_RE = /^\/([A-Za-z0-9_]{1,15})\/?$/;

const lower = (s: string | null | undefined) => (s ?? "").toLowerCase();

function safe<T>(fn: () => Extracted<T>): Extracted<T> {
  try {
    return fn();
  } catch {
    return null;
  }
}

/**
 * The @handle shown in an author line. Read per element, never from the
 * concatenated textContent: "@kaynakhesap" followed by a date span "1 Tem"
 * concatenates to "@kaynakhesap1 Tem", which a regex would read as
 * "kaynakhesap1" (caught by the quote fixture).
 */
function handleIn(root: Element | null | undefined): string | null {
  if (!root) return null;
  for (const el of Array.from(root.querySelectorAll("span, a"))) {
    const match = (el.textContent ?? "").trim().match(/^@([A-Za-z0-9_]{1,15})$/);
    if (match?.[1]) return match[1];
  }
  return null;
}

export function findArticles(root: ParentNode): Element[] {
  return Array.from(root.querySelectorAll(SEL.article));
}

/**
 * The embedded quoted post, if any: a `role="link"` block inside the article
 * that carries its own User-Name. Its time/text/handle must never be read as
 * the outer post's.
 */
export function quoteContainer(article: Element): Element | null {
  try {
    for (const block of Array.from(article.querySelectorAll('div[role="link"]'))) {
      if (block.querySelector(SEL.userName)) return block;
    }
  } catch {
    /* fail soft */
  }
  return null;
}

function outside(article: Element, el: Element): boolean {
  const quote = quoteContainer(article);
  return !quote || !quote.contains(el);
}

export interface Permalink {
  url: string;
  handle: string;
  postId: string;
  postedAt: string | null;
}

/** The outer post's own permalink: the `time` element wrapped in a /status/ link. */
export function extractPermalink(article: Element): Extracted<Permalink> {
  return safe(() => {
    for (const time of Array.from(article.querySelectorAll("time[datetime]"))) {
      if (!outside(article, time)) continue;
      const link = time.closest(SEL.statusLink);
      const href = link?.getAttribute("href") ?? "";
      const match = href.match(STATUS_PATH_RE);
      if (!match) continue;
      const [, handle, postId] = match as unknown as [string, string, string];
      return {
        value: {
          url: `https://x.com/${handle}/status/${postId}`,
          handle,
          postId,
          postedAt: time.getAttribute("datetime"),
        },
        method: "time-permalink",
      };
    }
    return null;
  });
}

/** Visible author line: "Display Name @handle · 3h". */
export function extractVisibleHandle(article: Element): Extracted<string> {
  return safe(() => {
    const name = Array.from(article.querySelectorAll(SEL.userName)).find((el) => outside(article, el));
    const handle = handleIn(name);
    return handle ? { value: handle, method: "user-name" } : null;
  });
}

export function extractText(article: Element): Extracted<string> {
  return safe(() => {
    const text = Array.from(article.querySelectorAll(SEL.tweetText)).find((el) => outside(article, el));
    const value = text?.textContent?.trim();
    return value ? { value, method: "tweet-text" } : null;
  });
}

interface Anchor {
  id: string;
  handle: string | null;
}

function anchorsIn(root: ParentNode, skip?: (el: Element) => boolean): Anchor[] {
  const out: Anchor[] = [];
  for (const el of Array.from(root.querySelectorAll(SEL.followAnchor))) {
    if (skip?.(el)) continue;
    const match = (el.getAttribute("data-testid") ?? "").match(FOLLOW_RE);
    if (!match?.[1]) continue;
    const aria = el.getAttribute("aria-label") ?? el.textContent ?? "";
    out.push({ id: match[1], handle: aria.match(HANDLE_RE)?.[1] ?? null });
  }
  return out;
}

/** The self-check: an id is accepted only if its own @handle is the author's. */
function verified(anchors: Anchor[], author: string): string | null {
  const hit = anchors.find((a) => a.handle !== null && lower(a.handle) === lower(author));
  return hit ? hit.id : null;
}

export function extractRestId(article: Element, author: string, doc: Document = document): Extracted<string> {
  return safe(() => {
    const inline = verified(anchorsIn(article, (el) => !outside(article, el)), author);
    if (inline) return { value: inline, method: "dom-anchor" };

    const path = doc.location?.pathname ?? "";
    const profile = path.match(PROFILE_PATH_RE)?.[1];
    if (profile && lower(profile) === lower(author)) {
      const header = verified(anchorsIn(doc, (el) => el.closest(SEL.article) !== null), author);
      if (header) return { value: header, method: "profile-header" };
    }

    const card = doc.querySelector(SEL.hoverCard);
    if (card) {
      const fromCard = verified(anchorsIn(card), author);
      if (fromCard) return { value: fromCard, method: "hovercard" };
    }
    return null;
  });
}

/**
 * Follower count from the author's profile header ("4.213 Takipçi",
 * "1,204 Followers"). Abbreviated displays ("48,2 B", "1.2M") are rejected:
 * storing 48200 for "48,2 B" would invent precision the page never showed.
 */
export function extractFollowerCount(author: string, doc: Document = document): Extracted<number> {
  return safe(() => {
    const path = doc.location?.pathname ?? "";
    const profile = path.match(PROFILE_PATH_RE)?.[1];
    if (!profile || lower(profile) !== lower(author)) return null;
    const links = Array.from(doc.querySelectorAll<HTMLAnchorElement>('a[href$="/followers"], a[href$="/verified_followers"]'));
    for (const link of links) {
      const href = link.getAttribute("href") ?? "";
      if (lower(href.split("/")[1]) !== lower(author)) continue;
      const parsed = parseExactCount(link.textContent ?? "");
      if (parsed !== null) return { value: parsed, method: "profile-header" };
    }
    return null;
  });
}

export function parseExactCount(text: string): number | null {
  const token = text.trim().split(/\s+/)[0] ?? "";
  if (!/^\d{1,3}(?:[.,  ]\d{3})*$|^\d+$/.test(token)) return null;
  const digits = token.replace(/\D/g, "");
  const value = Number(digits);
  return Number.isSafeInteger(value) ? value : null;
}

export interface EdgeCandidate {
  edgeType: "quote" | "retweet" | "reply" | "mention";
  source: { handle: string; restId: string | null };
  target: { handle: string; restId: string | null };
  method: string;
}

/**
 * Interaction structure of the clicked post (ARCHITECTURE §3.2). Language-
 * agnostic: reply targets are `@handle` links that point at `/handle` outside
 * the post text, author line and quote; reposts are read from the
 * socialContext link's href, not its translated text.
 */
export function detectEdges(article: Element, author: string, authorRestId: string | null): EdgeCandidate[] {
  const out: EdgeCandidate[] = [];
  try {
    const quote = quoteContainer(article);
    if (quote) {
      const target = handleIn(quote.querySelector(SEL.userName));
      if (target) {
        out.push({
          edgeType: "quote",
          source: { handle: author, restId: authorRestId },
          target: { handle: target, restId: verified(anchorsIn(quote), target) },
          method: "quote-block",
        });
      }
    }

    const social = article.querySelector(SEL.socialContext);
    const reposter = social?.closest("a[href]")?.getAttribute("href")?.match(PROFILE_PATH_RE)?.[1]
      ?? social?.querySelector("a[href]")?.getAttribute("href")?.match(PROFILE_PATH_RE)?.[1];
    if (reposter && lower(reposter) !== lower(author)) {
      out.push({
        edgeType: "retweet",
        source: { handle: reposter, restId: null },
        target: { handle: author, restId: authorRestId },
        method: "social-context",
      });
    }

    const seen = new Set<string>();
    for (const link of Array.from(article.querySelectorAll("a[href]"))) {
      if (!outside(article, link)) continue;
      if (link.closest(SEL.tweetText) || link.closest(SEL.userName) || link.closest(SEL.socialContext)) continue;
      const text = (link.textContent ?? "").trim();
      const handle = text.match(/^@([A-Za-z0-9_]{1,15})$/)?.[1];
      if (!handle || link.getAttribute("href") !== `/${handle}`) continue;
      if (lower(handle) === lower(author) || seen.has(lower(handle))) continue;
      seen.add(lower(handle));
      out.push({
        edgeType: "reply",
        source: { handle: author, restId: authorRestId },
        target: { handle, restId: null },
        method: "replying-to",
      });
    }
  } catch {
    /* fail soft: no candidates */
  }
  return out;
}

export interface Extraction {
  permalink: Permalink | null;
  visibleHandle: string | null;
  restId: Extracted<string>;
  followerCount: Extracted<number>;
  text: string | null;
  edges: EdgeCandidate[];
  methods: Record<string, string>;
}

/** Everything the overlay needs, read once at click time. */
export function extractPost(article: Element, doc: Document = document): Extraction {
  const permalink = extractPermalink(article)?.value ?? null;
  const visibleHandle = extractVisibleHandle(article)?.value ?? null;
  const author = permalink?.handle ?? visibleHandle;
  const restId = author ? extractRestId(article, author, doc) : null;
  const followerCount = author ? extractFollowerCount(author, doc) : null;
  const text = extractText(article)?.value ?? null;
  const edges = author ? detectEdges(article, author, restId?.value ?? null) : [];
  const methods: Record<string, string> = { extractor_version: EXTRACTOR_VERSION };
  methods.rest_id_method = restId?.method ?? "none";
  methods.follower_count_method = followerCount?.method ?? "none";
  if (permalink && visibleHandle && lower(permalink.handle) !== lower(visibleHandle)) {
    methods.handle_check = `mismatch:${visibleHandle}`;
  }
  return { permalink, visibleHandle, restId, followerCount, text, edges, methods };
}
