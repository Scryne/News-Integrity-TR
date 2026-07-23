# NIT Spikes helper — S1 + S2 + S3 in one panel (THROWAWAY)

Convenience wrapper so you can run the Phase-0 spikes fast, from a single panel
on x.com. **This is throwaway spike code, not production** — same as everything
under `spikes/`. It does not change the spike methods or the design docs.

- **S1** and **S3** are fully automated here (both are browser-native).
- **S2's real measurement stays in `../s2-archive/archive_probe.py`.** A browser
  `fetch` cannot observe the raw redirect / `/wip/` / refresh / challenge shape
  that S2's go/no-go depends on (cross-origin redirects come back opaque). So the
  panel only **collects the URLs** and hands you the exact python command; you
  still run the probe in Python. Nothing is submitted to any archive from here.

## Load it

1. Chrome → `chrome://extensions` → enable **Developer mode** (top-right).
2. **Load unpacked** → select this `spikes-extension/` folder.
   - Load **this** instead of `../s3-capture/` — it already includes the S3
     pipeline (loading both just double-adds capture buttons).
3. Open **x.com** (logged in). A **NIT Spikes** panel appears bottom-right.
   `–` collapses it. If you don't see it, reload the tab.

> If Chrome refuses `captureVisibleTab` with a permissions error, add
> `"<all_urls>"` to `host_permissions` in `manifest.json`, reload the extension,
> and note it in your S3 report.

## ▶▶ Hepsini çalıştır — all three at once

The button at the top of the panel fires S1 + S2 + S3 **concurrently** on the
current page:

- **S1** scans every tweet on screen, copies the JSON, adds it to the collection.
- **S2** adds the current post's canonical URL to the list — permalink pages
  only; elsewhere this step is skipped and reported as `S2 ✗ permalink değil`.
- **S3** captures the **most visible** tweet (no alert; both PNGs still download).

Best used on a **permalink** so all three have a target. The combined status
line shows `S1 ✓ … · S2 ✓ … · S3 ✓ …` per step. The per-section buttons keep
working as before, and S2's real probe still runs in Python (see below).

## S1 — rest_id / follower probe (read-only, no network)

The probe runs in the page's MAIN world (needed to read X's React fiber) and is
byte-for-byte the same extraction logic as `../s1-rest-id/console-snippet.js`.

- **▶ Bu sayfayı tara + kopyala** — runs over every tweet on screen, drops the
  paste-back JSON into the textarea **and** copies it to the clipboard, and adds
  it to the collection. (Console still prints the `console.table` + JSON too.)
- **⧉ Kopyala** — re-copy the textarea.
- **⇩ Tümünü indir (N)** — download every collected page as one
  `nit-s1-reports-<ts>.json` — that's the file to send back.
- **🗑 Temizle** — clear the collection.

Walk the five page types (**timeline · permalink · quoted · reply · repost**),
hit ▶ on each. To check obfuscated-key stability: note `fiber_suffix`, hard-reload,
run again, and tell me whether it changed. Then fill in `../s1-rest-id/README.md`'s
paste-back template using the collected JSON.

## S2 — archive URL collector (real probe stays in Python)

- **➕ Bu postu ekle** — on a permalink (`…/status/<id>`) adds that canonical URL.
- **URL yapıştır → Enter** — add any post URL manually.
- **⇩ urls.txt** — download the list. Put it in `../s2-archive/`.
- **⧉ dry-run komutu / ⧉ gerçek komut** — copies
  `python archive_probe.py --urls-file urls.txt [--dry-run]`.

Keep it to 2–3 URLs. Then, from `spikes/s2-archive/`:
`pip install httpx` → `python archive_probe.py --urls-file urls.txt --dry-run`
→ real run. Paste back the `PASTE THIS BACK` block per that folder's README.

## S3 — captureVisibleTab + crop (local only)

Each tweet gets an **S3** button (top-right). Toggle all buttons with
**Yakalama butonları: AÇIK/KAPALI** in the panel. Click **S3** on a fully-visible
post → `s3-<ts>-viewport.png` and `s3-<ts>-crop.png` download; an alert + the
panel status show `dpr`, captured image size, and the crop rect. Same pipeline as
`../s3-capture/`. Run the variant matrix (default zoom, 125% scaling, zoom 90/110%,
scrolled-off) from `../s3-capture/README.md` and paste back that template.

## Boundaries (unchanged from the spikes)

- S1 reads the page only — no network, nothing sent.
- S2 does **not** contact archive services from the browser; it only collects
  URLs for the Python probe.
- S3 captures your visible tab and downloads PNGs locally; nothing leaves the machine.
- Nothing crawls, scrolls, auto-discovers, or bulk-collects — you drive every action.
