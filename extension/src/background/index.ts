/**
 * MV3 service worker: screenshot, crop, and every backend fetch (ARCHITECTURE §7).
 *
 * Content scripts run in x.com's page context, where X's CSP would block a
 * fetch to the local backend; the worker fetches with extension permissions.
 * No business logic and no stored captures live here.
 *
 * Permission note (ADR-028): `captureVisibleTab` needs `<all_urls>` when it is
 * triggered from an in-page button (S3 addendum). The broad grant is never
 * exercised elsewhere: captures are refused unless the requesting tab is on
 * x.com / twitter.com.
 */

import { cropRect, type CssRect } from "../shared/geometry";
import type {
  CaptureMeta,
  CaptureResponse,
  EdgeBody,
  EdgeResponse,
  Failure,
  HealthResponse,
  Request,
  Taxonomy,
  TaxonomyResponse,
} from "../shared/messages";

declare const __NIT_BACKEND__: string;
const BACKEND = __NIT_BACKEND__;
const X_HOSTS = new Set(["x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.twitter.com"]);

let taxonomyCache: Taxonomy | null = null;

function fail(kind: Failure["kind"], error: string): Failure {
  return { ok: false, kind, error };
}

async function call(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BACKEND}${path}`, init);
}

async function detail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg ?? ""}`)
        .join("; ");
    }
    return JSON.stringify(body.detail ?? body);
  } catch {
    return `HTTP ${response.status}`;
  }
}

async function asFailure(response: Response): Promise<Failure> {
  const text = await detail(response);
  return fail(response.status >= 500 ? "server_error" : "rejected", text);
}

function isXTab(tab: chrome.tabs.Tab | undefined): boolean {
  try {
    return !!tab?.url && X_HOSTS.has(new URL(tab.url).hostname);
  } catch {
    return false;
  }
}

async function health(): Promise<HealthResponse> {
  try {
    const response = await call("/healthz");
    if (!response.ok) return { ok: true, backendUp: false, phase: null };
    const body = (await response.json()) as { phase?: string };
    return { ok: true, backendUp: true, phase: body.phase ?? null };
  } catch {
    return { ok: true, backendUp: false, phase: null };
  }
}

async function taxonomy(): Promise<TaxonomyResponse> {
  if (taxonomyCache) return { ok: true, taxonomy: taxonomyCache };
  try {
    const response = await call("/api/taxonomy");
    if (!response.ok) return asFailure(response);
    taxonomyCache = (await response.json()) as Taxonomy;
    return { ok: true, taxonomy: taxonomyCache };
  } catch {
    return fail("backend_down", "Yerel backend'e ulaşılamadı.");
  }
}

interface Shot {
  viewport: Blob;
  crop: Blob | null;
  clamped: boolean;
}

/** Viewport PNG plus a best-effort crop; any crop error means crop = null. */
async function shoot(windowId: number, rect: CssRect, dpr: number): Promise<Shot> {
  const dataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: "png" });
  const viewport = await (await fetch(dataUrl)).blob();
  try {
    const bitmap = await createImageBitmap(viewport);
    const box = cropRect(rect, dpr, bitmap.width, bitmap.height);
    if (!box) return { viewport, crop: null, clamped: false };
    const canvas = new OffscreenCanvas(box.sw, box.sh);
    const context = canvas.getContext("2d");
    if (!context) return { viewport, crop: null, clamped: false };
    context.drawImage(bitmap, box.sx, box.sy, box.sw, box.sh, 0, 0, box.sw, box.sh);
    bitmap.close();
    return { viewport, crop: await canvas.convertToBlob({ type: "image/png" }), clamped: box.clamped };
  } catch {
    return { viewport, crop: null, clamped: false };
  }
}

async function capture(
  sender: chrome.runtime.MessageSender,
  meta: CaptureMeta,
  rect: CssRect,
  dpr: number,
): Promise<CaptureResponse> {
  const tab = sender.tab;
  if (!tab || tab.windowId === undefined || !isXTab(tab)) {
    return fail("capture_blocked", "Yakalama yalnız x.com sekmesinden yapılabilir.");
  }
  const up = await health();
  if (!up.backendUp) return fail("backend_down", "Yerel backend çalışmıyor.");

  let shot: Shot;
  try {
    shot = await shoot(tab.windowId, rect, dpr);
  } catch (error) {
    return fail("capture_blocked", `Ekran görüntüsü alınamadı: ${String(error)}`);
  }
  const body = new FormData();
  const cropFailed = meta.crop_failed || shot.crop === null;
  body.append("meta", JSON.stringify({ ...meta, crop_failed: cropFailed }));
  body.append("viewport", shot.viewport, "viewport.png");
  if (shot.crop) body.append("crop", shot.crop, "crop.png");
  try {
    const response = await call("/api/captures", { method: "POST", body });
    if (!response.ok) return asFailure(response);
    const result = (await response.json()) as {
      evidence_id: number;
      account_id: string;
      seq: number;
      canonical_name: string;
      screenshot_sha256: string;
      merged: boolean;
      crop_failed: boolean;
    };
    return { ok: true, ...result, clamped: shot.clamped };
  } catch {
    return fail("backend_down", "Gönderim sırasında backend bağlantısı koptu.");
  }
}

async function edge(body: EdgeBody): Promise<EdgeResponse> {
  try {
    const response = await call("/api/edges", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) return asFailure(response);
    const result = (await response.json()) as { edge_id: number; target_resolved: boolean };
    return { ok: true, ...result };
  } catch {
    return fail("backend_down", "Yerel backend'e ulaşılamadı.");
  }
}

chrome.runtime.onMessage.addListener((message: Request, sender, sendResponse) => {
  const handle = async () => {
    switch (message.type) {
      case "HEALTH_CHECK":
        return health();
      case "TAXONOMY_GET":
        return taxonomy();
      case "CAPTURE_REQUEST":
        return capture(sender, message.meta, message.rect, message.dpr);
      case "EDGE_REQUEST":
        return edge(message.edge);
      default:
        return fail("rejected", "Bilinmeyen mesaj.");
    }
  };
  handle().then(sendResponse, (error: unknown) => sendResponse(fail("server_error", String(error))));
  return true; // async response
});
