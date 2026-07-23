/*
 * NIT S3 spike — content script (THROWAWAY)
 * Injects an "S3 capture" button into each tweet article. On click it sends the
 * article's getBoundingClientRect + devicePixelRatio to the service worker,
 * which captures the visible tab and crops to that rect. Two PNGs download:
 *   <base>-viewport.png  (full visible viewport)
 *   <base>-crop.png      (rect x dpr crop — this is what we check for alignment)
 */
const BTN_CLASS = "nit-s3-btn";

function addButton(article) {
  if (article.querySelector(`:scope > .${BTN_CLASS}`)) return;

  const btn = document.createElement("button");
  btn.className = BTN_CLASS;
  btn.textContent = "S3 capture";
  Object.assign(btn.style, {
    position: "absolute", top: "4px", right: "4px", zIndex: "99999",
    background: "#1d9bf0", color: "#fff", border: "none", borderRadius: "6px",
    padding: "2px 8px", font: "12px/1.4 sans-serif", cursor: "pointer",
    boxShadow: "0 1px 4px rgba(0,0,0,.3)",
  });

  if (getComputedStyle(article).position === "static") {
    article.style.position = "relative";
  }

  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const rect = article.getBoundingClientRect();
    const payload = {
      type: "NIT_SPIKE_CAPTURE",
      rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
      dpr: window.devicePixelRatio,
      viewport: { w: window.innerWidth, h: window.innerHeight },
      base: "s3-" + Date.now(),
    };
    console.log("[NIT S3] devicePixelRatio =", window.devicePixelRatio, "rect =", payload.rect);
    chrome.runtime.sendMessage(payload, (resp) => {
      if (chrome.runtime.lastError) {
        console.error("[NIT S3]", chrome.runtime.lastError.message);
        alert("S3 messaging error: " + chrome.runtime.lastError.message);
        return;
      }
      console.log("[NIT S3] result", resp);
      if (resp && resp.ok) {
        alert(
          `S3 OK\n` +
          `dpr = ${resp.dpr}\n` +
          `captured image = ${resp.captureW} x ${resp.captureH}px\n` +
          `crop src = ${resp.sw} x ${resp.sh} @ (${resp.sx}, ${resp.sy})\n` +
          `clamped = ${resp.clamped}\n\n` +
          `Downloads: ${payload.base}-viewport.png & ${payload.base}-crop.png\n` +
          `Check: does -crop.png contain exactly this post, edge-to-edge?`
        );
      } else {
        alert("S3 capture FAILED: " + (resp && resp.error));
      }
    });
  });

  article.appendChild(btn);
}

let scheduled = false;
function scan() {
  scheduled = false;
  document.querySelectorAll('article[data-testid="tweet"]').forEach(addButton);
}

const observer = new MutationObserver(() => {
  if (scheduled) return;
  scheduled = true;
  setTimeout(scan, 300); // throttle
});
observer.observe(document.body, { childList: true, subtree: true });
scan();

console.log("[NIT S3] content script loaded — buttons injected on tweet articles.");
