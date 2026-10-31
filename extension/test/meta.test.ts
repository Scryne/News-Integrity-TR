import { describe, expect, it } from "vitest";

import { buildCaptureMeta, buildEdgeBody } from "../src/content/meta";
import { extractPost } from "../src/content/x-dom";
import * as fx from "./fixtures";

function extraction(html: string, path = "/gundemhaber/status/1811111111111111111") {
  window.history.replaceState(null, "", path);
  document.body.innerHTML = html;
  return extractPost(document.querySelector("article")!);
}

const form = { category: "news", codes: ["H2"], note: "  ", manualRestId: "", inlineEdge: null };

describe("buildCaptureMeta", () => {
  it("builds the backend body with rest_id as a string and the extraction block", () => {
    const built = buildCaptureMeta(extraction(fx.permalink), form);
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.value.author).toEqual({ rest_id: "1234567890123456789", handle: "gundemhaber", follower_count: null });
    expect(built.value.post_id).toBe("1811111111111111111");
    expect(built.value.note).toBeNull();
    expect(built.value.extraction).toMatchObject({ rest_id_method: "dom-anchor", extractor_version: "1.0.0" });
    expect(JSON.stringify(built.value)).toContain('"rest_id":"1234567890123456789"');
  });

  it("requires a rest_id when extraction found none, and accepts a typed one as manual", () => {
    const ex = extraction(fx.timeline, "/home");
    const missing = buildCaptureMeta(ex, form);
    expect(missing.ok).toBe(false);
    if (!missing.ok) expect(missing.problems.join(" ")).toContain("rest_id");
    expect(buildCaptureMeta(ex, { ...form, manualRestId: "12ab" }).ok).toBe(false);
    const typed = buildCaptureMeta(ex, { ...form, manualRestId: " 987654321 " });
    expect(typed.ok && typed.value.author.rest_id).toBe("987654321");
    expect(typed.ok && typed.value.extraction.rest_id_method).toBe("manual");
  });

  it("lists every missing field at once", () => {
    const built = buildCaptureMeta(extraction(fx.permalink), { ...form, category: "", codes: [] });
    expect(built.ok).toBe(false);
    if (!built.ok) expect(built.problems).toHaveLength(2);
  });

  it("attaches a quote as inline edge with the author as source", () => {
    const ex = extraction(fx.quoted, "/gundemhaber/status/1811111111111111122");
    const built = buildCaptureMeta(ex, { ...form, inlineEdge: ex.edges[0]! });
    expect(built.ok && built.value.edge).toEqual({ target_rest_id: null, target_handle: "kaynakhesap", edge_type: "quote" });
  });

  it("refuses a repost as inline edge (its source is not the author)", () => {
    const ex = extraction(fx.repost, "/home");
    const built = buildCaptureMeta(ex, { ...form, manualRestId: "1", inlineEdge: ex.edges[0]! });
    expect(built.ok).toBe(false);
  });
});

describe("buildEdgeBody", () => {
  it("needs the reposter's id typed in, keeps the unknown target raw", () => {
    const ex = extraction(fx.repost, "/home");
    const candidate = ex.edges[0]!;
    expect(buildEdgeBody(ex, { candidate, sourceRestId: "", targetRestId: "", note: "" }).ok).toBe(false);
    const built = buildEdgeBody(ex, { candidate, sourceRestId: "555", targetRestId: "", note: "" });
    expect(built.ok && built.value).toEqual({
      source: { rest_id: "555", handle: "reposthesabi" },
      target: { rest_id: null, handle: "gundemhaber" },
      edge_type: "retweet",
      post_url: "https://x.com/gundemhaber/status/1811111111111111144",
      note: null,
    });
  });

  it("rejects a non-numeric target id", () => {
    const ex = extraction(fx.reply, "/gundemhaber/status/1811111111111111133");
    const built = buildEdgeBody(ex, { candidate: ex.edges[0]!, sourceRestId: "", targetRestId: "abc", note: "" });
    expect(built.ok).toBe(false);
  });
});
