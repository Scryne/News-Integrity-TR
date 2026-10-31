/**
 * Content script ↔ service worker protocol (ARCHITECTURE §7). Metadata only:
 * the screenshot never transits messaging — the worker captures it itself.
 * Every snowflake id (rest_id, post_id) is a `string` end to end.
 */

import type { CssRect } from "./geometry";

export type EdgeType = "quote" | "retweet" | "reply" | "mention";

export interface CaptureMeta {
  post_url: string;
  post_id: string | null;
  post_text: string | null;
  posted_at: string | null;
  author: { rest_id: string; handle: string; follower_count: number | null };
  category: string;
  codes: string[];
  note: string | null;
  crop_failed: boolean;
  edge: { target_rest_id: string | null; target_handle: string; edge_type: EdgeType } | null;
  extraction: Record<string, string>;
}

export interface EdgeBody {
  source: { rest_id: string; handle: string };
  target: { rest_id: string | null; handle: string };
  edge_type: EdgeType;
  post_url: string;
  note: string | null;
}

export interface TaxonomyCode {
  code: string;
  group_prefix: string;
  label: string;
  description: string | null;
  international_equivalent: string | null;
}

export interface Taxonomy {
  version: string;
  groups: Record<string, string>;
  categories: { key: string; label: string }[];
  codes: TaxonomyCode[];
}

export type Request =
  | { type: "CAPTURE_REQUEST"; meta: CaptureMeta; rect: CssRect; dpr: number }
  | { type: "EDGE_REQUEST"; edge: EdgeBody }
  | { type: "TAXONOMY_GET" }
  | { type: "HEALTH_CHECK" };

/** Why a request failed, so the overlay can say what to do next. */
export type FailureKind = "backend_down" | "rejected" | "server_error" | "capture_blocked";

export interface Failure {
  ok: false;
  kind: FailureKind;
  error: string;
}

export type CaptureResponse =
  | {
      ok: true;
      evidence_id: number;
      account_id: string;
      seq: number;
      canonical_name: string;
      screenshot_sha256: string;
      merged: boolean;
      crop_failed: boolean;
      clamped: boolean;
    }
  | Failure;

export type EdgeResponse = { ok: true; edge_id: number; target_resolved: boolean } | Failure;
export type TaxonomyResponse = { ok: true; taxonomy: Taxonomy } | Failure;
export type HealthResponse = { ok: true; backendUp: boolean; phase: string | null };
