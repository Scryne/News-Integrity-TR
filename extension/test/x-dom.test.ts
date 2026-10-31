import { beforeEach, describe, expect, it } from "vitest";

import {
  detectEdges,
  extractPost,
  extractRestId,
  parseExactCount,
  quoteContainer,
} from "../src/content/x-dom";
import * as fx from "./fixtures";

function load(html: string, path = "/gundemhaber/status/1811111111111111111"): Element {
  window.history.replaceState(null, "", path);
  document.body.innerHTML = html;
  const article = document.querySelector('article[data-testid="tweet"]');
  if (!article) throw new Error("fixture has no article");
  return article;
}

beforeEach(() => {
  document.body.innerHTML = "";
});

describe("permalink, text, author", () => {
  it("reads the outer post's own permalink and time", () => {
    const post = extractPost(load(fx.permalink));
    expect(post.permalink).toEqual({
      url: "https://x.com/gundemhaber/status/1811111111111111111",
      handle: "gundemhaber",
      postId: "1811111111111111111",
      postedAt: "2026-07-14T18:03:00.000Z",
    });
    expect(post.text).toBe("Son dakika: köprüde trafik durdu");
    expect(post.visibleHandle).toBe("gundemhaber");
  });

  it("never reads the quoted post's time, text or handle as the outer post's", () => {
    const article = load(fx.quoted, "/gundemhaber/status/1811111111111111122");
    expect(quoteContainer(article)).not.toBeNull();
    const post = extractPost(article);
    expect(post.permalink?.postId).toBe("1811111111111111122");
    expect(post.permalink?.postedAt).toBe("2026-07-15T08:00:00.000Z");
    expect(post.text).toBe("Bakın ne demiş");
    expect(post.visibleHandle).toBe("gundemhaber");
  });
});

describe("author rest_id (ADR-026 ladder)", () => {
  it("takes the inline follow anchor when its @handle is the author", () => {
    const post = extractPost(load(fx.permalink));
    expect(post.restId).toEqual({ value: "1234567890123456789", method: "dom-anchor" });
    expect(typeof post.restId?.value).toBe("string");
    expect(post.methods.rest_id_method).toBe("dom-anchor");
  });

  it("refuses an anchor that belongs to someone else (self-check)", () => {
    const post = extractPost(load(fx.permalinkWrongAnchor));
    expect(post.restId).toBeNull();
    expect(post.methods.rest_id_method).toBe("none");
  });

  it("returns null on a timeline row (no anchor) instead of guessing", () => {
    expect(extractPost(load(fx.timeline, "/home")).restId).toBeNull();
  });

  it("falls back to the profile header on the author's own profile", () => {
    const article = load(fx.profileHeader("4.213"), "/gundemhaber");
    expect(extractRestId(article, "gundemhaber")).toEqual({
      value: "1234567890123456789",
      method: "profile-header",
    });
  });

  it("does not use a profile header on someone else's profile", () => {
    const article = load(fx.profileHeader("4.213"), "/baskahesap");
    expect(extractRestId(article, "gundemhaber")).toBeNull();
  });

  it("uses an already-open hover card", () => {
    const article = load(
      `${fx.timeline}<div data-testid="HoverCard"><button data-testid="1234567890123456789-follow" aria-label="Takip et @gundemhaber"></button></div>`,
      "/home",
    );
    expect(extractRestId(article, "gundemhaber")?.method).toBe("hovercard");
  });
});

describe("follower count", () => {
  it("accepts an exact count from the author's profile header", () => {
    expect(extractPost(load(fx.profileHeader("4.213"), "/gundemhaber")).followerCount).toEqual({
      value: 4213,
      method: "profile-header",
    });
  });

  it("rejects abbreviated counts rather than inventing precision", () => {
    expect(extractPost(load(fx.profileHeader("48,2 B"), "/gundemhaber")).followerCount).toBeNull();
    for (const text of ["48,2 B", "1.2M", "12K", "", "abc"]) expect(parseExactCount(text)).toBeNull();
    expect(parseExactCount("1,204")).toBe(1204);
    expect(parseExactCount("987")).toBe(987);
  });
});

describe("edge detection", () => {
  it("detects a quote with the quoted handle as target", () => {
    const article = load(fx.quoted);
    expect(detectEdges(article, "gundemhaber", "1234567890123456789")).toEqual([
      {
        edgeType: "quote",
        source: { handle: "gundemhaber", restId: "1234567890123456789" },
        target: { handle: "kaynakhesap", restId: null },
        method: "quote-block",
      },
    ]);
  });

  it("detects reply targets but not mentions inside the text", () => {
    const edges = detectEdges(load(fx.reply), "gundemhaber", "1");
    expect(edges.map((e) => [e.edgeType, e.target.handle])).toEqual([["reply", "hedefhesap"]]);
  });

  it("detects a repost: reposter → original author, reposter id left for manual entry", () => {
    const edges = detectEdges(load(fx.repost, "/home"), "gundemhaber", null);
    expect(edges).toEqual([
      {
        edgeType: "retweet",
        source: { handle: "reposthesabi", restId: null },
        target: { handle: "gundemhaber", restId: null },
        method: "social-context",
      },
    ]);
  });

  it("finds nothing on a plain post", () => {
    expect(detectEdges(load(fx.permalink), "gundemhaber", "1")).toEqual([]);
  });
});

describe("fail soft", () => {
  it("never throws on a foreign element", () => {
    const div = document.createElement("div");
    const post = extractPost(div);
    expect(post.permalink).toBeNull();
    expect(post.restId).toBeNull();
    expect(post.edges).toEqual([]);
    expect(post.methods.extractor_version).toBe("1.0.0");
  });
});
