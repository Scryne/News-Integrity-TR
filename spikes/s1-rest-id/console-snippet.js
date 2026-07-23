/*
 * News Integrity TR — Spike S1: rest_id / follower_count extraction (THROWAWAY)
 * ---------------------------------------------------------------------------
 * Paste this whole file into the DevTools Console on a live, logged-in x.com
 * tab. It READS the page only — no network calls, nothing is sent anywhere.
 *
 * It installs `window.NIT` and immediately runs over every tweet article on
 * screen, printing a table. Use:
 *
 *     NIT.extractAll()     run over all article[data-testid="tweet"] on screen
 *     NIT.extract($0)      run on the element selected in the Elements panel
 *                          (select a tweet's <article> first)
 *     copy(NIT.report())   copy a compact, paste-back-safe JSON summary
 *     NIT.last             full detail objects from the last run
 *
 * This is an EXPLORER: it does not assume one property path. It walks the
 * article's React fiber ancestor chain, deep-searches each fiber's props for a
 * user-like and a tweet-like entity, and REPORTS THE PATH it found them at —
 * that reported path is the actual finding we need. It also cross-checks against
 * the DOM permalink/<time> so we can compare fiber vs DOM.
 */
(() => {
  const EXTRACTOR_PROBE_VERSION = "s1-0.3";

  // --- guards: only descend into plain data trees, never into React/DOM ------
  const isTraversable = (v) => {
    if (!v || typeof v !== "object") return false;
    if (v.$$typeof) return false;                         // React element
    if (typeof v.tag === "number" && "stateNode" in v) return false; // fiber node
    return true;
  };
  // keys that lead OUT of a props data-tree back into React/DOM internals
  const SKIP_KEYS = new Set([
    "_owner", "_store", "_self", "_source", "_debugOwner", "_debugSource",
    "return", "child", "sibling", "alternate", "stateNode", "memoizedState",
    "memoizedProps", "pendingProps", "updateQueue", "dependencies", "ref",
    "deletions",
  ]);

  const fiberKeyOf = (el) =>
    Object.keys(el).find((k) => k.startsWith("__reactFiber$")) || null;
  const getFiber = (el) => {
    const k = fiberKeyOf(el);
    return k ? el[k] : null;
  };

  // Bounded BFS over a plain props tree, tracking the property path. BFS so the
  // SHALLOWEST match wins (the outer tweet/user rather than a nested quote).
  function search(root, rootPath, predicate, opts = {}) {
    const { maxDepth = 30, maxNodes = 150000 } = opts;
    const seen = new WeakSet();
    const q = [{ node: root, path: rootPath, depth: 0 }];
    let head = 0, count = 0;
    while (head < q.length) {
      const { node, path, depth } = q[head++];
      if (!isTraversable(node)) continue;
      if (seen.has(node)) continue;
      seen.add(node);
      if (++count > maxNodes) break;
      try { if (predicate(node)) return { node, path }; } catch (e) { /* keep going */ }
      if (depth >= maxDepth) continue;
      const arr = Array.isArray(node);
      for (const k in node) {
        if (!arr && SKIP_KEYS.has(k)) continue;
        let v;
        try { v = node[k]; } catch (e) { continue; }
        if (v && typeof v === "object") {
          q.push({ node: v, path: path + (arr ? `[${k}]` : `.${k}`), depth: depth + 1 });
        }
      }
    }
    return null;
  }

  const isDigits = (s) => typeof s === "string" && /^\d+$/.test(s);

  const looksLikeUser = (o) =>
    isDigits(o.rest_id) &&
    (o.__typename === "User" ||
      (o.legacy && (typeof o.legacy.screen_name === "string" ||
                    typeof o.legacy.followers_count === "number")) ||
      (o.core && typeof o.core.screen_name === "string"));

  const looksLikeTweet = (o) =>
    isDigits(o.rest_id) &&
    (o.__typename === "Tweet" || o.__typename === "TweetWithVisibilityResults" ||
      (o.legacy && (typeof o.legacy.full_text === "string" ||
        (typeof o.legacy.created_at === "string" &&
         typeof o.legacy.conversation_id_str === "string"))));

  function readUser(u) {
    if (!u) return null;
    const legacy = u.legacy || {};
    const core = u.core || {};
    let followers = legacy.followers_count;
    if (typeof followers !== "number" && u.relationship_counts)
      followers = u.relationship_counts.followers;
    return {
      rest_id: u.rest_id ?? null,
      handle: core.screen_name ?? legacy.screen_name ?? null,
      followers_count: typeof followers === "number" ? followers : null,
      followers_from:
        typeof legacy.followers_count === "number" ? "legacy"
        : (u.relationship_counts && typeof u.relationship_counts.followers === "number") ? "relationship_counts"
        : "none",
    };
  }

  // GraphQL wraps entities as { result: {...} } or { result: { tweet: {...} } }.
  function unwrapResult(r) {
    let n = r;
    if (n && n.result) n = n.result;
    if (n && n.tweet && (n.__typename === "TweetWithVisibilityResults" || n.tweet.rest_id))
      n = n.tweet;
    return n;
  }

  function domCrossCheck(article) {
    const out = { handle: null, tweet_id: null, created_at: null };
    const timeEl = article.querySelector("time[datetime]");
    if (timeEl) {
      out.created_at = timeEl.getAttribute("datetime");
      const a = timeEl.closest("a[href*='/status/']");
      const m = a && a.getAttribute("href").match(/^\/([^/]+)\/status\/(\d+)/);
      if (m) { out.handle = m[1]; out.tweet_id = m[2]; }
    }
    if (!out.tweet_id) {
      const a = article.querySelector("a[href*='/status/']");
      const m = a && a.getAttribute("href").match(/^\/([^/]+)\/status\/(\d+)/);
      if (m) { out.handle = out.handle || m[1]; out.tweet_id = m[2]; }
    }
    return out;
  }

  function extract(article) {
    if (!article || !article.matches || !article.matches("article")) {
      console.warn("[NIT] pass a tweet <article> element, e.g. NIT.extract($0)");
      return null;
    }
    const fiber = getFiber(article);
    const result = {
      extractor_probe_version: EXTRACTOR_PROBE_VERSION,
      fiber_key_present: !!fiber,
      fiber_key_suffix: (fiberKeyOf(article) || "").replace("__reactFiber$", "") || null,
      author: null, author_path: null, author_ancestor_level: null,
      tweet: null, tweet_path: null,
      quoted_author: null, retweeted_author: null, reply_to: null,
      dom_crosscheck: domCrossCheck(article),
    };
    if (!fiber) return result;

    // Walk the ancestor (return) chain; each fiber's memoizedProps/pendingProps
    // is a candidate plain-data root to search.
    let node = fiber, level = 0, tweetHit = null, userHit = null;
    while (node && level < 80) {
      for (const propName of ["memoizedProps", "pendingProps"]) {
        const props = node[propName];
        if (!props || typeof props !== "object") continue;
        const rootPath = `props@ancestor+${level}.${propName}`;
        if (!tweetHit) {
          const t = search(props, rootPath, looksLikeTweet);
          if (t) { tweetHit = t; result.tweet_path = t.path; result.author_ancestor_level = level; }
        }
        if (!userHit) {
          const u = search(props, rootPath, looksLikeUser);
          if (u) { userHit = u; result.author_path = u.path; }
        }
      }
      if (tweetHit && userHit) break;
      node = node.return; level++;
    }

    if (tweetHit) {
      const t = tweetHit.node;
      const tl = t.legacy || {};
      result.tweet = {
        rest_id: t.rest_id ?? null,
        created_at: tl.created_at ?? null,
        conversation_id: tl.conversation_id_str ?? null,
        full_text_present: typeof tl.full_text === "string",
      };
      // Prefer the tweet's own embedded author.
      const coreUser = t.core && unwrapResult(t.core.user_results);
      if (coreUser && looksLikeUser(coreUser)) {
        result.author = readUser(coreUser);
        result.author_path = (result.tweet_path || "") + ".core.user_results.result";
      }
      // Nested quoted / retweeted authors (both authors of a quote post).
      const q = t.quoted_status_result && unwrapResult(t.quoted_status_result);
      if (q && q.core) result.quoted_author = readUser(unwrapResult(q.core.user_results));
      const rt = tl.retweeted_status_result && unwrapResult(tl.retweeted_status_result);
      if (rt && rt.core) result.retweeted_author = readUser(unwrapResult(rt.core.user_results));
      if (tl.in_reply_to_user_id_str || tl.in_reply_to_screen_name) {
        result.reply_to = {
          rest_id: tl.in_reply_to_user_id_str ?? null,
          handle: tl.in_reply_to_screen_name ?? null,
        };
      }
    }
    if (!result.author && userHit) result.author = readUser(userHit.node);
    return result;
  }

  function summarize(r) {
    const a = r.author || {};
    return {
      handle: a.handle ?? r.dom_crosscheck.handle ?? null,
      rest_id: a.rest_id ?? null,
      followers: a.followers_count ?? null,
      tweet_id: (r.tweet && r.tweet.rest_id) || r.dom_crosscheck.tweet_id || null,
      created_at: (r.tweet && r.tweet.created_at) || r.dom_crosscheck.created_at || null,
      quoted: r.quoted_author ? `${r.quoted_author.handle}/${r.quoted_author.rest_id}` : "",
      ancestor: r.author_ancestor_level,
    };
  }

  function extractAll() {
    const arts = [...document.querySelectorAll('article[data-testid="tweet"]')];
    const full = arts.map(extract);
    window.NIT.last = full;
    console.log(`[NIT] ${full.length} article(s). Full detail on NIT.last — run copy(NIT.report()) to grab a paste-back summary.`);
    console.table(full.map(summarize));
    if (full.length) console.log("[NIT] fiber key suffix (stability check across reloads):", full[0].fiber_key_suffix);
    return full;
  }

  // Compact, paste-back-safe summary (no post text; handles/ids/followers only).
  function report() {
    const rows = (window.NIT.last || []).map((r, i) => ({
      i,
      ok_rest_id: !!(r.author && r.author.rest_id),
      ...summarize(r),
      followers_from: r.author ? r.author.followers_from : "none",
      author_path: r.author_path,
      tweet_path: r.tweet_path,
      fiber_suffix: r.fiber_key_suffix,
      quoted_author: r.quoted_author,
      retweeted_author: r.retweeted_author,
      reply_to: r.reply_to,
    }));
    const payload = {
      probe_version: EXTRACTOR_PROBE_VERSION,
      page_url: location.href,
      captured_at: new Date().toISOString(),
      rows,
    };
    const text = JSON.stringify(payload, null, 2);
    console.log(text);
    return text;
  }

  window.NIT = {
    version: EXTRACTOR_PROBE_VERSION,
    last: null,
    extract: (el) => { const r = extract(el || null); window.NIT.last = r ? [r] : []; console.log(r); return r; },
    extractAll,
    summarize,
    report,
  };

  console.log(`%c[NIT] S1 probe ${EXTRACTOR_PROBE_VERSION} loaded — running extractAll()…`, "color:#1d9bf0;font-weight:bold");
  extractAll();
})();
