/**
 * Content script entry: decorate posts with [Yakala] / [Kenar] and open the
 * panel on click.
 *
 * The MutationObserver ONLY decorates (x-dom-extraction rule 7): it adds a
 * small button strip and never reads post content. Extraction runs inside the
 * click handlers, on the post the user chose.
 */

import { openCaptureOverlay, openEdgeOverlay, type CaptureHooks } from "./overlay";
import { extractPost, findArticles } from "./x-dom";

const MARK = "data-nit";
const STRIP_CSS = `
:host { all: initial; position: absolute; top: 8px; right: 48px; z-index: 3; }
.strip { display: flex; gap: 4px; opacity: .55; transition: opacity .12s; }
.strip:hover, .strip:focus-within { opacity: 1; }
button {
  font: 600 11px/1 system-ui, "Segoe UI", Roboto, sans-serif; letter-spacing: .01em;
  height: 24px; padding: 0 8px; border-radius: 6px; cursor: pointer;
  color: #ECEEF2; background: rgba(20, 22, 27, .88); border: 1px solid #3A3F4B;
}
button:hover { border-color: #E0694F; }
button:focus-visible { outline: 2px solid #E0694F; outline-offset: 2px; }
`;

function stop(event: Event): void {
  // The whole article is a link on X; our click must not navigate.
  event.preventDefault();
  event.stopPropagation();
}

function hooksFor(article: Element): CaptureHooks {
  const strips = () => Array.from(document.querySelectorAll<HTMLElement>(`nit-strip`));
  return {
    async prepare() {
      for (const strip of strips()) strip.style.visibility = "hidden";
      const before = article.getBoundingClientRect();
      if (before.top < 0 || before.bottom > window.innerHeight) {
        // captureVisibleTab only sees the viewport (S3 variant 5).
        article.scrollIntoView({ block: before.height > window.innerHeight ? "start" : "center" });
        await new Promise((resolve) => setTimeout(resolve, 250));
      }
      const r = article.getBoundingClientRect();
      return { rect: { x: r.x, y: r.y, w: r.width, h: r.height }, dpr: window.devicePixelRatio };
    },
    restore() {
      for (const strip of strips()) strip.style.visibility = "";
    },
  };
}

function decorate(article: HTMLElement): void {
  if (article.hasAttribute(MARK)) return;
  article.setAttribute(MARK, "");
  if (getComputedStyle(article).position === "static") article.style.position = "relative";
  const host = document.createElement("nit-strip");
  const root = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = STRIP_CSS;
  const strip = document.createElement("div");
  strip.className = "strip";
  const capture = document.createElement("button");
  capture.type = "button";
  capture.textContent = "Yakala";
  capture.title = "Bu gönderiyi kanıt olarak kodla ve kaydet";
  const edge = document.createElement("button");
  edge.type = "button";
  edge.textContent = "Kenar";
  edge.title = "Bu gönderideki etkileşimi kenar olarak kaydet";
  capture.addEventListener("click", (event) => {
    stop(event);
    openCaptureOverlay(extractPost(article), hooksFor(article));
  });
  edge.addEventListener("click", (event) => {
    stop(event);
    openEdgeOverlay(extractPost(article));
  });
  for (const button of [capture, edge]) {
    button.addEventListener("pointerdown", (event) => event.stopPropagation());
    button.addEventListener("mousedown", (event) => event.stopPropagation());
  }
  strip.append(capture, edge);
  root.append(style, strip);
  article.prepend(host);
}

let scheduled = false;
function scan(): void {
  scheduled = false;
  for (const article of findArticles(document)) decorate(article as HTMLElement);
}

function schedule(): void {
  if (scheduled) return;
  scheduled = true;
  setTimeout(scan, 150);
}

new MutationObserver(schedule).observe(document.documentElement, { childList: true, subtree: true });
scan();
