/*
 * NIT Spikes helper — service worker (THROWAWAY)
 * S3 pipeline, unchanged from the standalone s3-capture spike: receive a rect +
 * dpr, capture the visible tab, crop to rect x dpr on an OffscreenCanvas, and
 * download both the viewport and the crop as PNGs. This is the exact pipeline
 * the real service worker will use (ARCHITECTURE §7).
 */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "NIT_SPIKE_CAPTURE") {
    handleCapture(msg, sender)
      .then(sendResponse)
      .catch((e) => sendResponse({ ok: false, error: String((e && e.message) || e) }));
    return true; // keep the message channel open for the async response
  }
});

async function blobToDataUrl(blob) {
  // No FileReader in a service worker: base64-encode the ArrayBuffer ourselves.
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let bin = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return "data:image/png;base64," + btoa(bin);
}

async function handleCapture(msg, sender) {
  const { rect, dpr, base } = msg;
  const windowId = sender.tab.windowId;

  // 1) Capture the full visible viewport as a PNG data URL.
  const shotDataUrl = await chrome.tabs.captureVisibleTab(windowId, { format: "png" });
  await chrome.downloads.download({
    url: shotDataUrl, filename: `${base}-viewport.png`, saveAs: false,
  });

  // 2) Decode it to a bitmap so we know the true captured pixel dimensions.
  const shotBlob = await (await fetch(shotDataUrl)).blob();
  const bitmap = await createImageBitmap(shotBlob);

  // 3) Map the CSS-pixel rect into captured (device) pixels: rect x dpr.
  let sx = Math.round(rect.x * dpr);
  let sy = Math.round(rect.y * dpr);
  let sw = Math.round(rect.w * dpr);
  let sh = Math.round(rect.h * dpr);

  // Clamp to the captured image bounds (a partly off-screen post is expected to
  // clip — real capture flips crop_failed rather than blocking).
  let clamped = false;
  if (sx < 0) { sw += sx; sx = 0; clamped = true; }
  if (sy < 0) { sh += sy; sy = 0; clamped = true; }
  if (sx + sw > bitmap.width) { sw = bitmap.width - sx; clamped = true; }
  if (sy + sh > bitmap.height) { sh = bitmap.height - sy; clamped = true; }

  if (sw <= 0 || sh <= 0) {
    return { ok: false, error: `empty crop after clamp (sw=${sw}, sh=${sh})`,
             dpr, captureW: bitmap.width, captureH: bitmap.height };
  }

  // 4) Crop on an OffscreenCanvas and download.
  const canvas = new OffscreenCanvas(sw, sh);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(bitmap, sx, sy, sw, sh, 0, 0, sw, sh);
  const cropBlob = await canvas.convertToBlob({ type: "image/png" });
  const cropUrl = await blobToDataUrl(cropBlob);
  await chrome.downloads.download({
    url: cropUrl, filename: `${base}-crop.png`, saveAs: false,
  });

  return {
    ok: true, dpr, captureW: bitmap.width, captureH: bitmap.height,
    sx, sy, sw, sh, clamped,
  };
}

console.log("[NIT Spikes] service worker ready.");
