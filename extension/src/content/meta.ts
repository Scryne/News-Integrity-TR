/**
 * Pure assembly of request bodies from an extraction + the overlay's form state.
 * Kept free of DOM and chrome APIs so the rules are unit-tested:
 *   - rest_id comes from extraction or the manual field, never guessed;
 *   - an inline edge always has the post author as source (ARCHITECTURE §3.2);
 *   - the sidecar's extraction block records how each identity was obtained.
 */

import type { CaptureMeta, EdgeBody } from "../shared/messages";
import type { EdgeCandidate, Extraction } from "./x-dom";

export const REST_ID_RE = /^\d{1,25}$/;

export interface CaptureForm {
  category: string;
  codes: string[];
  note: string;
  manualRestId: string;
  inlineEdge: EdgeCandidate | null;
}

export type Built<T> = { ok: true; value: T } | { ok: false; problems: string[] };

export function authorRestId(extraction: Extraction, manual: string): { id: string; method: string } | null {
  if (extraction.restId) return { id: extraction.restId.value, method: extraction.restId.method };
  const typed = manual.trim();
  return REST_ID_RE.test(typed) ? { id: typed, method: "manual" } : null;
}

export function buildCaptureMeta(extraction: Extraction, form: CaptureForm): Built<CaptureMeta> {
  const problems: string[] = [];
  const permalink = extraction.permalink;
  if (!permalink) problems.push("Gönderinin bağlantısı okunamadı; gönderiyi açıp tekrar deneyin.");
  const identity = authorRestId(extraction, form.manualRestId);
  if (!identity) problems.push("Yazarın sayısal kimliği (rest_id) gerekli.");
  if (!form.category) problems.push("Bir kategori seçin.");
  if (form.codes.length === 0) problems.push("En az bir kod seçin.");
  if (form.inlineEdge && form.inlineEdge.edgeType === "retweet") {
    problems.push("Yeniden paylaşım kenarı yazardan çıkmaz; Kenar düğmesiyle kaydedin.");
  }
  if (problems.length || !permalink || !identity) return { ok: false, problems };

  const extractionBlock: Record<string, string> = { ...extraction.methods, rest_id_method: identity.method };
  if (form.inlineEdge) extractionBlock.edge_method = form.inlineEdge.method;
  return {
    ok: true,
    value: {
      post_url: permalink.url,
      post_id: permalink.postId,
      post_text: extraction.text,
      posted_at: permalink.postedAt,
      author: {
        rest_id: identity.id,
        handle: permalink.handle,
        follower_count: extraction.followerCount?.value ?? null,
      },
      category: form.category,
      codes: [...form.codes],
      note: form.note.trim() || null,
      crop_failed: false,
      edge: form.inlineEdge
        ? {
            target_rest_id: form.inlineEdge.target.restId,
            target_handle: form.inlineEdge.target.handle,
            edge_type: form.inlineEdge.edgeType,
          }
        : null,
      extraction: extractionBlock,
    },
  };
}

export interface EdgeForm {
  candidate: EdgeCandidate;
  sourceRestId: string;
  targetRestId: string;
  note: string;
}

export function buildEdgeBody(extraction: Extraction, form: EdgeForm): Built<EdgeBody> {
  const problems: string[] = [];
  const permalink = extraction.permalink;
  if (!permalink) problems.push("Gönderinin bağlantısı okunamadı.");
  const source = form.candidate.source.restId ?? (REST_ID_RE.test(form.sourceRestId.trim()) ? form.sourceRestId.trim() : null);
  if (!source) problems.push(`@${form.candidate.source.handle} için sayısal kimlik (rest_id) gerekli.`);
  const typedTarget = form.targetRestId.trim();
  if (typedTarget && !REST_ID_RE.test(typedTarget)) problems.push("Hedef kimliği yalnız rakamlardan oluşmalı.");
  if (problems.length || !permalink || !source) return { ok: false, problems };
  return {
    ok: true,
    value: {
      source: { rest_id: source, handle: form.candidate.source.handle },
      target: { rest_id: form.candidate.target.restId ?? (typedTarget || null), handle: form.candidate.target.handle },
      edge_type: form.candidate.edgeType,
      post_url: permalink.url,
      note: form.note.trim() || null,
    },
  };
}
