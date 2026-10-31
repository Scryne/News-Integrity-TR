// End-to-end smoke test: the built extension in a real Edge/Chrome, against a
// running backend, on an x.com page served from a local fixture.
//
//   1. backend:   cd backend && NIT_DATA_DIR=<tmp> NIT_PORT=8766 python -m app.main
//   2. build:     NIT_BACKEND=http://127.0.0.1:8766 npm run build
//   3. run:       node scripts/e2e.mjs --backend http://127.0.0.1:8766 --data <tmp> --out <dir>
//
// x.com is never contacted: every https://x.com/* request is answered by
// Playwright from the fixture below (synthetic markup, see test/fixtures.ts).
// The backend-down path runs first, before the backend is reachable, when
// --down-first is given and the backend is started by the caller afterwards.

import { chromium } from "playwright-core";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { inflateSync } from "node:zlib";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, cur, i, all) => (cur.startsWith("--") ? [...acc, [cur.slice(2), all[i + 1]?.startsWith("--") ? "1" : all[i + 1] ?? "1"]] : acc), []),
);
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const backend = args.backend ?? "http://127.0.0.1:8765";
const dataDir = args.data;
const out = args.out ?? join(root, "e2e-out");
const browserPath =
  process.env.NIT_BROWSER ??
  ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Google/Chrome/Application/chrome.exe"].find(existsSync);
mkdirSync(out, { recursive: true });

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "OK  " : "FAIL"} ${name}${detail ? ` — ${detail}` : ""}`);
}

const author = (name, handle, postId, datetime) => `
  <div data-testid="User-Name" style="display:flex;gap:6px;align-items:baseline">
    <a href="/${handle}" role="link"><span style="font-weight:700">${name}</span></a>
    <a href="/${handle}" role="link"><span>@${handle}</span></a><span>·</span>
    <a href="/${handle}/status/${postId}" role="link"><time datetime="${datetime}">3s</time></a>
  </div>`;
const page = `<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>X fixture</title>
<style>
  body{margin:0;background:#ffffff;color:#536471;font:15px system-ui,sans-serif}
  main{width:600px;margin:0 auto;border-left:1px solid #eff3f4;border-right:1px solid #eff3f4}
  article{background:#f4f7fa;padding:14px 16px;border-bottom:1px solid #d9e1e8;cursor:pointer}
  a{color:#1d6fb8;text-decoration:none}
  [data-testid=tweetText]{margin-top:6px;color:#1d4f91;line-height:1.4}
  .quote{margin-top:10px;border:1px solid #c9d6e2;border-radius:12px;padding:10px;background:#eaf1f7}
  .media{height:160px;margin-top:10px;border-radius:12px;background:linear-gradient(135deg,#7fb3e6,#2a6db0)}
</style></head><body><main>
<article data-testid="tweet" id="p1" onclick="location.hash='navigated'">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111111", "2026-07-14T18:03:00.000Z")}
  <button data-testid="1234567890123456789-follow" aria-label="Takip et @gundemhaber" style="float:right;color:#1d6fb8;background:#fff;border:1px solid #1d6fb8;border-radius:12px">Takip et</button>
  <div data-testid="tweetText"><span>Son dakika: köprüde trafik durdu, görüntüler 2019'dan.</span></div>
  <div class="media"></div>
</article>
<article data-testid="tweet" id="p2">
  ${author("Gündem Haber", "gundemhaber", "1811111111111111122", "2026-07-15T08:00:00.000Z")}
  <button data-testid="1234567890123456789-follow" aria-label="Takip et @gundemhaber" style="float:right;color:#1d6fb8;background:#fff;border:1px solid #1d6fb8;border-radius:12px">Takip et</button>
  <div data-testid="tweetText"><span>Bakın ne demiş</span></div>
  <div role="link" tabindex="0" class="quote">
    <div data-testid="User-Name"><span>Kaynak Hesap</span> <span>@kaynakhesap</span> <time datetime="2026-07-01T10:00:00.000Z">1 Tem</time></div>
    <div data-testid="tweetText"><span>orijinal iddia</span></div>
  </div>
</article>
<article data-testid="tweet" id="p3">
  ${author("Takip Edilen", "takipedilen", "1811111111111111133", "2026-07-16T09:30:00.000Z")}
  <div data-testid="tweetText"><span>Zaman akışı satırı: kimlik bağlantısı yok.</span></div>
</article>
<div style="height:1400px"></div>
</main></body></html>`;

// --- tiny PNG reader (RGBA/RGB, 8-bit, filter-aware) for pixel checks ---------
function readPng(buf) {
  let pos = 8, width = 0, height = 0, colorType = 0;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos), type = buf.toString("ascii", pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === "IHDR") { width = data.readUInt32BE(0); height = data.readUInt32BE(4); colorType = data[9]; }
    if (type === "IDAT") idat.push(data);
    pos += 12 + len;
  }
  const bpp = colorType === 6 ? 4 : 3, stride = width * bpp;
  const raw = inflateSync(Buffer.concat(idat));
  const px = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y++) {
    const f = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? px[y * stride + x - bpp] : 0, b = y ? px[(y - 1) * stride + x] : 0, c = x >= bpp && y ? px[(y - 1) * stride + x - bpp] : 0;
      const v = raw[y * (stride + 1) + 1 + x];
      const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
      const pred = f === 0 ? 0 : f === 1 ? a : f === 2 ? b : f === 3 ? (a + b) >> 1 : pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      px[y * stride + x] = (v + pred) & 0xff;
    }
  }
  return { width, height, at: (x, y) => [...px.subarray(y * stride + x * bpp, y * stride + x * bpp + 3)] };
}

const ctx = await chromium.launchPersistentContext(join(out, "profile"), {
  executablePath: browserPath,
  headless: false,
  viewport: null,
  args: [`--disable-extensions-except=${dist}`, `--load-extension=${dist}`, "--window-size=1280,900", "--force-device-scale-factor=1"],
});
await ctx.route("https://x.com/**", (route) => route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: page }));
const tab = ctx.pages()[0] ?? (await ctx.newPage());
await tab.goto("https://x.com/gundemhaber/status/1811111111111111111");
await tab.waitForSelector("nit-strip", { timeout: 10000 });
check("buttons injected on every post", (await tab.locator("nit-strip").count()) === 3);

const panel = tab.locator("nit-panel");

if (args["down-first"]) {
  await tab.locator("#p1 nit-strip button", { hasText: "Yakala" }).click();
  await panel.getByText("Yerel backend çalışmıyor").waitFor({ timeout: 10000 });
  check("backend down: readable error with next step", await panel.getByText("python -m app.main").isVisible());
  await tab.screenshot({ path: join(out, "01-backend-down.png") });
  console.log("waiting for backend…");
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch(`${backend}/healthz`)).ok) break; } catch {}
    await new Promise((r) => setTimeout(r, 1000));
  }
  await panel.getByRole("button", { name: "Yeniden dene" }).click();
} else {
  await tab.locator("#p1 nit-strip button", { hasText: "Yakala" }).click();
}

// --- capture with codes, quote-free post ---------------------------------------
await panel.locator("#nit-category").waitFor({ timeout: 10000 });
check("click on our button did not trigger the post's own navigation", !tab.url().includes("#navigated"));
check("identity verified from the follow anchor", await panel.getByText("1234567890123456789").isVisible());
await panel.getByRole("button", { name: "Kanıtı kaydet" }).click();
check("validation lists missing fields", (await panel.locator(".notice.warn li").count()) === 2);
await panel.locator("#nit-category").selectOption("news");
await panel.locator('label[for="nit-code-H1"]').click();
await panel.locator('label[for="nit-code-H4"]').click();
await panel.locator("#nit-note").fill("E2E: eski görüntü güncel gibi sunulmuş");
await tab.screenshot({ path: join(out, "02-panel-filled.png") });
await panel.getByRole("button", { name: "Kanıtı kaydet" }).click();
await panel.getByText("Kanıt kaydedildi").waitFor({ timeout: 15000 });
const stampText = await panel.locator(".stamp").innerText();
check("stamp shows canonical name and hash", /1234567890123456789-0001/.test(stampText) && /sha256 [0-9a-f]{12}/.test(stampText), stampText.replace(/\n/g, " | "));
await tab.screenshot({ path: join(out, "03-stamp.png") });
await panel.getByRole("button", { name: "Kapat", exact: true }).click();

// --- quote post: inline edge ------------------------------------------------------
await tab.locator("#p2 nit-strip button", { hasText: "Yakala" }).click();
await panel.locator("#nit-category").waitFor();
check("quote detected as inline edge", await panel.getByText("@kaynakhesap").isVisible());
await panel.locator("#nit-category").selectOption("agenda");
await panel.locator('label[for="nit-code-H8"]').click();
await tab.keyboard.press("Control+Enter");
await panel.getByText("Kanıt kaydedildi").waitFor({ timeout: 15000 });
await tab.keyboard.press("Escape");
check("Esc closes the panel", (await panel.count()) === 0);

// --- timeline row: no identity → manual field -------------------------------------
await tab.locator("#p3 nit-strip button", { hasText: "Yakala" }).click();
await panel.locator("#nit-restid").waitFor();
check("missing identity asks for manual rest_id", await panel.getByText("Yazarın kimliği bu satırdan okunamadı").isVisible());
await tab.setViewportSize({ width: 390, height: 844 });
await tab.screenshot({ path: join(out, "04-mobile-manual-id.png") });
await tab.setViewportSize({ width: 1280, height: 900 });
await tab.keyboard.press("Escape");

// --- edge overlay on the quote post ------------------------------------------------
await tab.locator("#p2 nit-strip button", { hasText: "Kenar" }).click();
await panel.getByRole("button", { name: "Kenarı kaydet" }).click();
await panel.getByText("Kenar kaydedildi").waitFor({ timeout: 10000 });
check("edge overlay saves the detected quote", await panel.getByText("kullanıcı adıyla saklandı").isVisible());
await tab.keyboard.press("Escape");

// --- backend side ------------------------------------------------------------------
const manifest = await (await fetch(`${backend}/api/exports/manifest?verify=true`)).json();
check("manifest verify: all files match", manifest.all_ok === true, `${manifest.entries.length} entries`);
const caseFile = await (await fetch(`${backend}/api/exports/accounts/1234567890123456789/case-file.json`)).json();
const first = caseFile.evidence[0];
check("evidence row: codes, category, phase, version", JSON.stringify(first.codes) === '["H1","H4"]' && first.category === "news" && first.taxonomy_version === "1.1", JSON.stringify({ codes: first.codes, phase: first.phase }));
check("inline quote edge stored", caseFile.edges.some((e) => e.edge_type === "quote" && e.target_handle_raw === "kaynakhesap" && e.evidence_id === caseFile.evidence[1].evidence_id));

if (dataDir) {
  const primary = readFileSync(join(dataDir, first.files.primary.path));
  check("primary file hash = recorded hash", createHash("sha256").update(primary).digest("hex") === first.files.primary.sha256);
  const crop = readPng(primary);
  const rect = await tab.evaluate(() => { const r = document.querySelector("#p1").getBoundingClientRect(); return { w: r.width, h: r.height }; });
  check("crop size = post size × dpr", Math.abs(crop.width - Math.round(rect.w)) <= 1 && Math.abs(crop.height - Math.round(rect.h)) <= 1, `${crop.width}×${crop.height} vs ${rect.w}×${rect.h}`);
  let dark = 0;
  for (let y = 0; y < crop.height; y++) for (let x = 0; x < crop.width; x++) {
    const [r, g, b] = crop.at(x, y);
    if (r < 40 && g < 40 && b < 45) dark++;
  }
  check("no panel or button pixels in the crop", dark === 0, `${dark} dark pixels`);
  writeFileSync(join(out, "crop-p1.png"), primary);
}

await ctx.close();
writeFileSync(join(out, "e2e-report.json"), JSON.stringify(results, null, 2));
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
