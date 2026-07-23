/*
 * News Integrity TR — Spike S1 (candidate 3): DOM-anchor rest_id probe (THROWAWAY)
 * ---------------------------------------------------------------------------
 * Paste this whole file into the DevTools Console on a live, logged-in x.com
 * tab. It READS the page only — no network calls, nothing is sent anywhere.
 * Companion to console-snippet.js (the fiber probe); this one NEVER touches
 * React fiber — it only reads rendered DOM attributes/aria.
 *
 * Goal (candidate 3): can the AUTHOR's numeric rest_id be read from already-
 * rendered DOM, primarily the follow/unfollow button whose data-testid is
 * "<rest_id>-follow" / "<rest_id>-unfollow" — and is it the *author's* id, not
 * a wrong account (the failure mode that sank the fiber walk)?
 *
 *     NIT.extractAll()     run over every article[data-testid="tweet"] on screen
 *     NIT.extract($0)      run on the <article> selected in the Elements panel
 *     copy(NIT.report())   copy a compact, paste-back-safe JSON summary
 *     NIT.last             full detail objects from the last run
 *
 * Two things it surfaces, side by side, so misattribution is caught BY EYE:
 *   1) the numeric id found + the exact selector it came from + the post's
 *      visible @handle / display name (cross-check columns).
 *   2) EVERY other id-bearing attribute/aria inside the article (a catalog),
 *      so if the follow-anchor is NO-GO we can already see whether some other
 *      DOM node carries a usable rest_id — no second spike needed.
 */
(() => {
  const PROBE = "s1-dom-0.1";

  const FOLLOW_RE = /^(\d+)-(un)?follow$/;      // data-testid of the follow/unfollow button
  const HANDLE_RE = /@([A-Za-z0-9_]{1,15})/;    // pull @handle from aria-label/text (language-agnostic)
  const IDNUM_RE  = /\d{5,}/g;                   // "id-like" run — rest/tweet ids are long; skips counts

  const norm = (h) => (h || "").toLowerCase();
  const clip = (s, n = 90) => (s && s.length > n ? s.slice(0, n) + "…" : s);

  // --- the post's VISIBLE author, from DOM only (canonical = permalink) -------
  function visibleAuthor(article) {
    const out = { url_handle: null, tweet_id: null, name_handle: null,
                  display_name: null, social_context: null };
    const timeEl = article.querySelector("time[datetime]");
    const a = (timeEl && timeEl.closest("a[href*='/status/']")) ||
              article.querySelector("a[href*='/status/']");
    const m = a && a.getAttribute("href").match(/^\/([^/]+)\/status\/(\d+)/);
    if (m) { out.url_handle = m[1]; out.tweet_id = m[2]; }

    const un = article.querySelector('[data-testid="User-Name"]');
    if (un) {
      const t = (un.textContent || "").replace(/\s+/g, " ").trim();
      const hm = t.match(HANDLE_RE);
      out.name_handle = hm ? hm[1] : null;
      const at = t.indexOf("@");
      out.display_name = (at > 0 ? t.slice(0, at) : t).trim() || null;
    }
    const sc = article.querySelector('[data-testid="socialContext"]');
    if (sc) out.social_context = (sc.textContent || "").replace(/\s+/g, " ").trim() || null;
    return out;
  }

  // --- every follow/unfollow anchor in the article, with parsed id + @handle --
  function followAnchors(article) {
    const list = [];
    article.querySelectorAll('[data-testid$="follow"]').forEach((el) => {
      const testid = el.getAttribute("data-testid") || "";
      const mm = testid.match(FOLLOW_RE);
      if (!mm) return;
      const aria = el.getAttribute("aria-label") || (el.textContent || "").trim();
      const hm = (aria || "").match(HANDLE_RE);
      list.push({
        id: mm[1],
        state: mm[2] ? "unfollow(you follow)" : "follow(you don't)",
        selector: `[data-testid="${testid}"]`,
        aria_handle: hm ? hm[1] : null,
        aria_label: clip(aria) || null,
      });
    });
    return list;
  }

  // --- catalog EVERY id-bearing attribute/aria in the article ----------------
  function otherIdBearing(article, tweetId, followIds) {
    const seen = new Set();
    const out = [];
    for (const el of article.querySelectorAll("*")) {
      const testid = el.getAttribute("data-testid");
      for (const attr of el.attributes) {
        const val = attr.value;
        if (!val) continue;
        const found = val.match(IDNUM_RE);
        if (!found) continue;
        for (const id of found) {
          const key = id + "@" + attr.name + "@" + (testid || el.tagName);
          if (seen.has(key)) continue;
          seen.add(key);
          const flags = [];
          if (id === tweetId) flags.push("==tweet_id");
          if (followIds.has(id)) flags.push("==follow_id");
          if (/profile_images|pbs\.twimg|\/media\//.test(val)) flags.push("img/media");
          if (attr.name === "href") flags.push("in_href");
          if (attr.name === "src") flags.push("in_src");
          if (attr.name === "data-testid") flags.push("in_testid");
          if (attr.name.startsWith("aria")) flags.push("in_aria");
          out.push({
            id,
            tag: el.tagName.toLowerCase(),
            attr: attr.name,
            testid: testid || null,
            sample: clip(val),
            flags: flags.join(",") || "?unexplained",
          });
          if (out.length >= 400) return out;   // perf cap
        }
      }
    }
    return out;
  }

  function extract(article) {
    if (!article || !article.matches || !article.matches("article")) {
      console.warn("[NIT-DOM] select a tweet <article> first, e.g. NIT.extract($0)");
      return null;
    }
    const author = visibleAuthor(article);
    const anchors = followAnchors(article);
    const followIds = new Set(anchors.map((a) => a.id));
    const others = otherIdBearing(article, author.tweet_id, followIds);

    // pick the anchor whose aria @handle == the post's author handle
    const byHandle = anchors.find(
      (a) => a.aria_handle &&
        (norm(a.aria_handle) === norm(author.url_handle) ||
         norm(a.aria_handle) === norm(author.name_handle))
    );
    let match, chosen = null;
    if (byHandle) { match = "match"; chosen = byHandle; }
    else if (anchors.length === 1 && !anchors[0].aria_handle) { match = "single-unverified"; chosen = anchors[0]; }
    else if (anchors.length === 1) match = "MISMATCH";           // one anchor, its handle ≠ author
    else if (anchors.length > 1) match = "ambiguous";            // several, none match author
    else match = "absent";                                       // no follow button in DOM

    return {
      probe: PROBE,
      page_url: location.href,
      author,
      follow_anchors: anchors,
      author_rest_id: chosen ? chosen.id : null,
      author_rest_id_selector: chosen ? chosen.selector : null,
      author_rest_id_aria_handle: chosen ? chosen.aria_handle : null,
      match,                       // match | single-unverified | MISMATCH | ambiguous | absent
      other_id_bearing: others,
    };
  }

  const MATCH_LABEL = {
    match: "✅ match", "single-unverified": "◻ single?",
    MISMATCH: "❌ MISMATCH", ambiguous: "⚠ ambiguous", absent: "— absent",
  };

  function summarize(r) {
    return {
      match: MATCH_LABEL[r.match] || r.match,
      url_handle: r.author.url_handle,        // ← visible author (canonical, from permalink)
      display_name: r.author.display_name,    // ← visible author (eyeball cross-check)
      author_rest_id: r.author_rest_id,       // ← the numeric id found
      via: r.author_rest_id_selector,         // ← which selector it came from
      aria_handle: r.author_rest_id_aria_handle, // ← handle the id's button claims
      social: r.author.social_context || "",
      tweet_id: r.author.tweet_id,
      n_follow: r.follow_anchors.length,
      n_other_ids: r.other_id_bearing.length,
    };
  }

  function extractAll() {
    const arts = [...document.querySelectorAll('article[data-testid="tweet"]')];
    const full = arts.map(extract);
    window.NIT.last = full;
    console.log(`[NIT-DOM] ${full.length} article(s). Full detail on NIT.last — run copy(NIT.report()) to grab a paste-back summary.`);
    console.table(full.map(summarize));

    const c = (s) => full.filter((r) => r.match === s).length;
    console.log(`[NIT-DOM] author rest_id via follow-anchor → ✅ ${c("match")} match / ◻ ${c("single-unverified")} single? / ❌ ${c("MISMATCH")} MISMATCH / ⚠ ${c("ambiguous")} ambiguous / — ${c("absent")} absent  (of ${full.length})`);

    // other id-bearing nodes NOT explained by tweet-id / follow-id / image =
    // candidate alternative rest_id sources to eyeball if the anchor is NO-GO
    const alt = [];
    full.forEach((r, i) => r.other_id_bearing.forEach((o) => {
      if (!/==tweet_id|==follow_id|img\/media/.test(o.flags)) alt.push({ i, ...o });
    }));
    if (alt.length) {
      console.log(`[NIT-DOM] ${alt.length} OTHER id-bearing node(s) not explained by tweet/follow/image — potential alt rest_id sources:`);
      console.table(alt.slice(0, 60));
    } else {
      console.log("[NIT-DOM] no unexplained id-bearing nodes (only tweet-id / follow-id / image ids present).");
    }
    return full;
  }

  // Compact, paste-back-safe summary: identities + ids + selectors only, NO post text.
  function report() {
    const rows = (window.NIT.last || []).map((r, i) => ({
      i,
      match: r.match,
      url_handle: r.author.url_handle,
      name_handle: r.author.name_handle,
      display_name: r.author.display_name,
      social_context: r.author.social_context,
      tweet_id: r.author.tweet_id,
      author_rest_id: r.author_rest_id,
      author_rest_id_selector: r.author_rest_id_selector,
      author_rest_id_aria_handle: r.author_rest_id_aria_handle,
      follow_anchors: r.follow_anchors,
      other_id_bearing: r.other_id_bearing,
    }));
    const payload = {
      probe: PROBE,
      page_url: location.href,
      captured_at: new Date().toISOString(),
      rows,
    };
    const text = JSON.stringify(payload, null, 2);
    console.log(text);
    return text;
  }

  window.NIT = {
    version: PROBE,
    last: null,
    extract: (el) => { const r = extract(el || null); window.NIT.last = r ? [r] : []; console.log(r); return r; },
    extractAll,
    summarize,
    report,
  };

  console.log(`%c[NIT-DOM] S1 DOM-anchor probe ${PROBE} loaded — running extractAll()…`, "color:#1d9bf0;font-weight:bold");
  extractAll();
})();
