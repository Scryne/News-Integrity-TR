/*
 * NIT Spikes helper — panel, ISOLATED world (THROWAWAY)
 * ---------------------------------------------------------------------------
 * Injects one floating "NIT Spikes" panel onto x.com with three sections:
 *
 *   S1  run the rest_id probe over every tweet on screen, copy/collect the
 *       paste-back JSON, export all collected pages as one file. The actual
 *       fiber read happens in probe-main.js (MAIN world); we just drive it and
 *       show the result. READ-ONLY, no network.
 *
 *   S2  collect the canonical URL of a post you're viewing into a small list,
 *       export urls.txt, and copy the exact python command. The REAL archive
 *       probe stays in spikes/s2-archive/archive_probe.py — a browser fetch
 *       cannot observe the raw redirect/challenge shape that S2 exists to
 *       measure, so we do not submit from here.
 *
 *   S3  per-tweet capture button -> captureVisibleTab + rect x dpr crop in the
 *       service worker; two PNGs download locally. Same pipeline as the
 *       standalone s3-capture spike.
 *
 *   "▶▶ Hepsini çalıştır" fires all three concurrently on the current page:
 *   S1 scan+collect, S2 add-current-URL (skipped off-permalink), S3 capture of
 *   the most visible tweet (no alert). S2's real probe still runs in Python.
 */
(() => {
  if (document.getElementById("nit-spikes-panel")) return; // idempotent

  const S3_BTN_CLASS = "nit-s3-btn";
  const store = {
    get: (k, d) => new Promise((res) => chrome.storage.local.get({ [k]: d }, (o) => res(o[k]))),
    set: (k, v) => new Promise((res) => chrome.storage.local.set({ [k]: v }, res)),
  };

  // ------------------------------------------------------------------ helpers
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; }
    catch (e) {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed"; ta.style.top = "-1000px"; ta.style.opacity = "0";
        document.documentElement.appendChild(ta);
        ta.focus(); ta.select();
        const ok = document.execCommand("copy");
        ta.remove();
        return ok;
      } catch (e2) { return false; }
    }
  }

  function downloadText(filename, text, mime = "text/plain") {
    const blob = new Blob([text], { type: mime + ";charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.documentElement.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }

  const ts = () => new Date().toISOString().replace(/[:.]/g, "-");

  // ------------------------------------------------------------------- styles
  const style = document.createElement("style");
  style.textContent = `
    #nit-spikes-panel{position:fixed;bottom:14px;right:14px;z-index:2147483647;
      width:300px;font:12px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;
      color:#e7e9ea;background:#15181c;border:1px solid #2f3336;border-radius:12px;
      box-shadow:0 6px 24px rgba(0,0,0,.5);overflow:hidden}
    #nit-spikes-panel *{box-sizing:border-box}
    #nit-spikes-panel .nit-hd{display:flex;align-items:center;justify-content:space-between;
      padding:8px 10px;background:#1d9bf0;color:#fff;cursor:default;user-select:none}
    #nit-spikes-panel .nit-hd b{font-size:12px;letter-spacing:.2px}
    #nit-spikes-panel .nit-hd button{background:rgba(255,255,255,.2);color:#fff;border:none;
      border-radius:6px;padding:1px 7px;cursor:pointer;font-size:13px;line-height:1.4}
    #nit-spikes-panel .nit-body{padding:8px 10px;max-height:70vh;overflow:auto}
    #nit-spikes-panel.nit-collapsed .nit-body{display:none}
    #nit-spikes-panel section{border-top:1px solid #2f3336;padding-top:8px;margin-top:8px}
    #nit-spikes-panel section:first-child{border-top:none;margin-top:0;padding-top:0}
    #nit-spikes-panel h4{margin:0 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#8b98a5}
    #nit-spikes-panel .row{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0}
    #nit-spikes-panel button.nit-b{background:#2a2e33;color:#e7e9ea;border:1px solid #3a3f45;
      border-radius:7px;padding:5px 9px;cursor:pointer;font-size:12px}
    #nit-spikes-panel button.nit-b:hover{background:#33383e}
    #nit-spikes-panel button.nit-b.pri{background:#1d9bf0;border-color:#1d9bf0;color:#fff;font-weight:600}
    #nit-spikes-panel button.nit-b.pri:hover{background:#1a8cd8}
    #nit-spikes-panel input[type=text]{width:100%;background:#0c0e10;color:#e7e9ea;border:1px solid #3a3f45;
      border-radius:7px;padding:5px 7px;font-size:12px;margin:2px 0}
    #nit-spikes-panel textarea{width:100%;height:88px;background:#0c0e10;color:#a9e5a0;border:1px solid #3a3f45;
      border-radius:7px;padding:6px;font:11px/1.4 ui-monospace,Consolas,monospace;resize:vertical;margin-top:4px}
    #nit-spikes-panel .nit-note{color:#8b98a5;font-size:11px;margin:4px 0}
    #nit-spikes-panel .nit-status{color:#7ecb74;font-size:11px;min-height:14px;margin-top:4px}
    #nit-spikes-panel .nit-status.err{color:#f4726e}
    #nit-spikes-panel ul.nit-urls{list-style:none;margin:4px 0;padding:0;max-height:96px;overflow:auto}
    #nit-spikes-panel ul.nit-urls li{display:flex;gap:6px;align-items:center;padding:2px 0;color:#c9d2d9;
      font:11px/1.3 ui-monospace,Consolas,monospace;word-break:break-all}
    #nit-spikes-panel ul.nit-urls li button{margin-left:auto;background:none;border:none;color:#f4726e;cursor:pointer;font-size:13px}
    #nit-spikes-panel .nit-count{color:#1d9bf0;font-weight:700}
    .${S3_BTN_CLASS}{position:absolute;top:4px;right:4px;z-index:99999;background:#1d9bf0;color:#fff;
      border:none;border-radius:6px;padding:2px 8px;font:12px/1.4 sans-serif;cursor:pointer;
      box-shadow:0 1px 4px rgba(0,0,0,.3)}
  `;
  document.documentElement.appendChild(style);

  // -------------------------------------------------------------------- panel
  const panel = document.createElement("div");
  panel.id = "nit-spikes-panel";
  panel.innerHTML = `
    <div class="nit-hd"><b>NIT Spikes — S1 · S2 · S3</b><button id="nit-collapse" title="Aç/Kapat">–</button></div>
    <div class="nit-body">
      <section>
        <div class="row">
          <button class="nit-b pri" id="all-run" style="width:100%">▶▶ Hepsini çalıştır — S1 + S2 + S3</button>
        </div>
        <div class="nit-note">Tek tıkla eş zamanlı: S1 sayfayı tarar, S2 bu postun URL'ini ekler (permalink değilse atlar), S3 en görünür tweet'i yakalar. S2'nin gerçek probu yine Python'da.</div>
        <div class="nit-status" id="all-status"></div>
      </section>

      <section>
        <h4>S1 — rest_id probu (salt okuma)</h4>
        <div class="row">
          <button class="nit-b pri" id="s1-run">▶ Bu sayfayı tara + kopyala</button>
          <button class="nit-b" id="s1-copy">⧉ Kopyala</button>
        </div>
        <div class="row">
          <button class="nit-b" id="s1-export">⇩ Tümünü indir (<span class="nit-count" id="s1-count">0</span>)</button>
          <button class="nit-b" id="s1-clear">🗑 Temizle</button>
        </div>
        <div class="nit-note">5 sayfa tipini gez: timeline · permalink · alıntı · yanıt · repost. Her birinde ▶. Reload sonrası fiber suffix değişti mi bak.</div>
        <div class="nit-status" id="s1-status"></div>
        <textarea id="s1-out" readonly placeholder="rapor JSON'u burada görünür ve panoya kopyalanır"></textarea>
      </section>

      <section>
        <h4>S2 — arşiv URL toplayıcı</h4>
        <div class="row">
          <button class="nit-b pri" id="s2-add">➕ Bu postu ekle</button>
        </div>
        <input type="text" id="s2-manual" placeholder="veya URL yapıştır → Enter" />
        <ul class="nit-urls" id="s2-list"></ul>
        <div class="row">
          <button class="nit-b" id="s2-export">⇩ urls.txt</button>
          <button class="nit-b" id="s2-cmd-dry">⧉ dry-run komutu</button>
          <button class="nit-b" id="s2-cmd-real">⧉ gerçek komut</button>
          <button class="nit-b" id="s2-clear">🗑</button>
        </div>
        <div class="nit-note">Asıl probe Python'da: urls.txt'i <code>spikes/s2-archive/</code> içine koy, oradan çalıştır. Tarayıcı ham redirect/challenge şeklini göremez.</div>
        <div class="nit-status" id="s2-status"></div>
      </section>

      <section>
        <h4>S3 — captureVisibleTab + crop</h4>
        <div class="row">
          <button class="nit-b pri" id="s3-toggle">Yakalama butonları: AÇIK</button>
        </div>
        <div class="nit-note">Her tweet'in sağ üstünde <b>S3</b> butonu. Tık → viewport + crop PNG iner. dpr ve crop dikdörtgeni alert'te.</div>
        <div class="nit-status" id="s3-status"></div>
      </section>
    </div>`;
  document.documentElement.appendChild(panel);

  const $ = (id) => panel.querySelector(id);
  const setStatus = (el, msg, isErr = false) => {
    el.textContent = msg;
    el.classList.toggle("err", !!isErr);
  };

  $("#nit-collapse").addEventListener("click", () => {
    panel.classList.toggle("nit-collapsed");
    $("#nit-collapse").textContent = panel.classList.contains("nit-collapsed") ? "+" : "–";
  });

  // ----------------------------------------------------------------- S1 logic
  const s1Status = $("#s1-status"), s1Out = $("#s1-out"), s1Count = $("#s1-count");

  async function refreshS1Count() {
    const arr = await store.get("nit_s1_reports", []);
    s1Count.textContent = String(arr.length);
  }

  function runS1() {
    return new Promise((resolve) => {
      const onMsg = (ev) => {
        if (ev.source !== window) return;
        const d = ev.data;
        if (!d || d.__nit !== "main->ui" || d.type !== "S1_RESULT") return;
        window.removeEventListener("message", onMsg);
        resolve(d);
      };
      window.addEventListener("message", onMsg);
      window.postMessage({ __nit: "ui->main", cmd: "S1_RUN" }, "*");
      setTimeout(() => {
        window.removeEventListener("message", onMsg);
        resolve({ ok: false, error: "MAIN world probu yanıt vermedi (uzantıyı reload edip sayfayı yenile)." });
      }, 5000);
    });
  }

  async function s1RunAndCollect() {
    setStatus(s1Status, "taranıyor…");
    const res = await runS1();
    if (!res.ok) { setStatus(s1Status, res.error, true); return { ok: false, summary: res.error }; }
    s1Out.value = res.text;
    const arr = await store.get("nit_s1_reports", []);
    arr.push({ url: res.url, at: new Date().toISOString(), count: res.count, text: res.text });
    await store.set("nit_s1_reports", arr);
    await refreshS1Count();
    const copied = await copyText(res.text);
    setStatus(s1Status, `${res.count} tweet · toplandı (#${arr.length})` + (copied ? " · panoya kopyalandı" : " · kopyalanamadı, textarea'dan al"));
    return { ok: true, summary: `${res.count} tweet` };
  }

  $("#s1-run").addEventListener("click", s1RunAndCollect);

  $("#s1-copy").addEventListener("click", async () => {
    if (!s1Out.value) { setStatus(s1Status, "önce ▶ ile tara", true); return; }
    const ok = await copyText(s1Out.value);
    setStatus(s1Status, ok ? "kopyalandı" : "kopyalanamadı", !ok);
  });

  $("#s1-export").addEventListener("click", async () => {
    const arr = await store.get("nit_s1_reports", []);
    if (!arr.length) { setStatus(s1Status, "toplanmış rapor yok", true); return; }
    const payload = {
      tool: "nit-spikes-helper", spike: "S1", exported_at: new Date().toISOString(),
      pages: arr.map((p) => {
        let report = null; try { report = JSON.parse(p.text); } catch (e) { report = p.text; }
        return { url: p.url, at: p.at, count: p.count, report };
      }),
    };
    downloadText(`nit-s1-reports-${ts()}.json`, JSON.stringify(payload, null, 2), "application/json");
    setStatus(s1Status, `${arr.length} sayfa indirildi`);
  });

  $("#s1-clear").addEventListener("click", async () => {
    await store.set("nit_s1_reports", []);
    s1Out.value = "";
    await refreshS1Count();
    setStatus(s1Status, "temizlendi");
  });

  // ----------------------------------------------------------------- S2 logic
  const s2Status = $("#s2-status"), s2List = $("#s2-list");

  function currentStatusUrl() {
    const m = location.pathname.match(/^\/([^/]+)\/status\/(\d+)/);
    return m ? `https://x.com/${m[1]}/status/${m[2]}` : null;
  }

  async function renderS2() {
    const urls = await store.get("nit_s2_urls", []);
    s2List.innerHTML = "";
    urls.forEach((u, i) => {
      const li = document.createElement("li");
      const span = document.createElement("span");
      span.textContent = u;
      const rm = document.createElement("button");
      rm.textContent = "✕"; rm.title = "kaldır";
      rm.addEventListener("click", async () => {
        const cur = await store.get("nit_s2_urls", []);
        cur.splice(i, 1);
        await store.set("nit_s2_urls", cur);
        renderS2();
      });
      li.append(span, rm);
      s2List.appendChild(li);
    });
  }

  const X_POST_RE = /^https?:\/\/(x\.com|twitter\.com)\/[^/]+\/status\/\d+/i;

  async function addS2(url) {
    if (!url) { setStatus(s2Status, "URL yok", true); return { ok: false, summary: "URL yok" }; }
    if (!X_POST_RE.test(url)) { setStatus(s2Status, "…/status/<id> gibi görünmüyor", true); return { ok: false, summary: "post URL'i değil" }; }
    const urls = await store.get("nit_s2_urls", []);
    if (urls.includes(url)) { setStatus(s2Status, "zaten listede", true); return { ok: true, summary: "zaten listede" }; }
    urls.push(url);
    await store.set("nit_s2_urls", urls);
    await renderS2();
    setStatus(s2Status, `eklendi (${urls.length})` + (urls.length > 3 ? " — S2 için 2-3 yeter, nazik ol" : ""));
    return { ok: true, summary: `eklendi (${urls.length})` };
  }

  async function s2AddCurrent() {
    const u = currentStatusUrl();
    if (!u) {
      setStatus(s2Status, "bu sayfa bir post değil; permalink aç ya da URL yapıştır", true);
      return { ok: false, summary: "permalink değil, atlandı" };
    }
    return addS2(u);
  }

  $("#s2-add").addEventListener("click", s2AddCurrent);

  $("#s2-manual").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const v = e.target.value.trim();
    if (v) { addS2(v); e.target.value = ""; }
  });

  $("#s2-export").addEventListener("click", async () => {
    const urls = await store.get("nit_s2_urls", []);
    if (!urls.length) { setStatus(s2Status, "liste boş", true); return; }
    const header = [
      "# S2 probe input — one public X post URL per line.",
      "# Put this file in spikes/s2-archive/ and run archive_probe.py there.",
      "# Keep it to 2-3 URLs. Use posts you are already looking at.",
      "",
    ].join("\n");
    downloadText("urls.txt", header + urls.join("\n") + "\n");
    setStatus(s2Status, `urls.txt indirildi (${urls.length})`);
  });

  $("#s2-cmd-dry").addEventListener("click", async () => {
    const ok = await copyText("python archive_probe.py --urls-file urls.txt --dry-run");
    setStatus(s2Status, ok ? "dry-run komutu kopyalandı" : "kopyalanamadı", !ok);
  });
  $("#s2-cmd-real").addEventListener("click", async () => {
    const ok = await copyText("python archive_probe.py --urls-file urls.txt");
    setStatus(s2Status, ok ? "gerçek komut kopyalandı" : "kopyalanamadı", !ok);
  });
  $("#s2-clear").addEventListener("click", async () => {
    await store.set("nit_s2_urls", []);
    await renderS2();
    setStatus(s2Status, "liste temizlendi");
  });

  // ----------------------------------------------------------------- S3 logic
  const s3Status = $("#s3-status"), s3Toggle = $("#s3-toggle");
  let s3On = true;

  function s3Capture(article, { showAlert = true } = {}) {
    return new Promise((resolve) => {
      const rect = article.getBoundingClientRect();
      const payload = {
        type: "NIT_SPIKE_CAPTURE",
        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
        dpr: window.devicePixelRatio,
        viewport: { w: window.innerWidth, h: window.innerHeight },
        base: "s3-" + Date.now(),
      };
      console.log("[NIT S3] devicePixelRatio =", window.devicePixelRatio, "rect =", payload.rect);
      setStatus(s3Status, "yakalanıyor…");
      chrome.runtime.sendMessage(payload, (resp) => {
        if (chrome.runtime.lastError) {
          const msg = "mesaj hatası: " + chrome.runtime.lastError.message;
          setStatus(s3Status, msg, true);
          resolve({ ok: false, summary: msg });
          return;
        }
        if (resp && resp.ok) {
          setStatus(s3Status, `OK dpr=${resp.dpr} img=${resp.captureW}x${resp.captureH} crop=${resp.sw}x${resp.sh}@(${resp.sx},${resp.sy}) clamped=${resp.clamped}`);
          if (showAlert) {
            alert(
              `S3 OK\n` +
              `dpr = ${resp.dpr}\n` +
              `captured image = ${resp.captureW} x ${resp.captureH}px\n` +
              `crop src = ${resp.sw} x ${resp.sh} @ (${resp.sx}, ${resp.sy})\n` +
              `clamped = ${resp.clamped}\n\n` +
              `Downloads: ${payload.base}-viewport.png & ${payload.base}-crop.png\n` +
              `Check: does -crop.png contain exactly this post, edge-to-edge?`
            );
          }
          resolve({ ok: true, summary: `crop ${resp.sw}x${resp.sh} indirildi` });
        } else {
          const msg = "FAILED: " + (resp && resp.error);
          setStatus(s3Status, msg, true);
          resolve({ ok: false, summary: msg });
        }
      });
    });
  }

  function mostVisibleArticle() {
    let best = null, bestArea = 0;
    document.querySelectorAll('article[data-testid="tweet"]').forEach((a) => {
      const r = a.getBoundingClientRect();
      const w = Math.min(r.right, window.innerWidth) - Math.max(r.left, 0);
      const h = Math.min(r.bottom, window.innerHeight) - Math.max(r.top, 0);
      const area = Math.max(0, w) * Math.max(0, h);
      if (area > bestArea) { bestArea = area; best = a; }
    });
    return best;
  }

  async function s3CaptureBest() {
    const article = mostVisibleArticle();
    if (!article) {
      setStatus(s3Status, "ekranda tweet yok", true);
      return { ok: false, summary: "ekranda tweet yok" };
    }
    return s3Capture(article, { showAlert: false });
  }

  function addS3Button(article) {
    if (article.querySelector(`:scope > .${S3_BTN_CLASS}`)) return;
    const btn = document.createElement("button");
    btn.className = S3_BTN_CLASS;
    btn.textContent = "S3";
    if (getComputedStyle(article).position === "static") article.style.position = "relative";
    btn.addEventListener("click", (e) => {
      e.preventDefault(); e.stopPropagation();
      s3Capture(article);
    });
    article.appendChild(btn);
  }

  function removeS3Buttons() {
    document.querySelectorAll(`.${S3_BTN_CLASS}`).forEach((b) => b.remove());
  }

  let scheduled = false;
  function scan() {
    scheduled = false;
    if (!s3On) return;
    document.querySelectorAll('article[data-testid="tweet"]').forEach(addS3Button);
  }
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    setTimeout(scan, 300);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  function applyS3(on) {
    s3On = on;
    s3Toggle.textContent = "Yakalama butonları: " + (on ? "AÇIK" : "KAPALI");
    if (on) scan(); else removeS3Buttons();
    store.set("nit_s3_on", on);
  }
  s3Toggle.addEventListener("click", () => applyS3(!s3On));

  // ------------------------------------------------------------ run-all logic
  const allStatus = $("#all-status"), allRun = $("#all-run");

  allRun.addEventListener("click", async () => {
    allRun.disabled = true;
    setStatus(allStatus, "S1 + S2 + S3 eş zamanlı çalışıyor…");
    try {
      const [r1, r2, r3] = await Promise.all([s1RunAndCollect(), s2AddCurrent(), s3CaptureBest()]);
      const part = (name, r) => `${name} ${r.ok ? "✓" : "✗"} ${r.summary}`;
      const anyErr = !(r1.ok && r2.ok && r3.ok);
      setStatus(allStatus, [part("S1", r1), part("S2", r2), part("S3", r3)].join("  ·  "), anyErr);
    } finally {
      allRun.disabled = false;
    }
  });

  // ----------------------------------------------------------------- init
  (async () => {
    await refreshS1Count();
    await renderS2();
    const on = await store.get("nit_s3_on", true);
    applyS3(on);
  })();

  console.log("[NIT Spikes] panel loaded (isolated world).");
})();
