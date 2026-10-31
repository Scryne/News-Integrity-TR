# News Integrity TR — X evidence capture toolkit

A local research tool for documenting manipulative behaviour patterns of Turkish news-style X accounts.
You browse X yourself; on a post you click **Yakala**, tag it with the codebook, and the tool stores a
screenshot, its SHA-256, a write-once sidecar and two archive jobs. Nothing is crawled, nothing leaves your
machine except the archive submissions you complete yourself.

- Design: `ARCHITECTURE.md` · decisions: `DECISIONS.md` (ADR-001…029) · plan: `PLAN.md` · spikes: `docs/SPIKES.md`
- Panel design tokens: `DESIGN.md` · codebook: `taxonomy.json` (v1.1, 22 codes)

## 1. Backend (Python 3.12)

```bash
cd backend
uv venv .venv --python 3.12              # or: python -m venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
cp .env.example .env                     # adjust NIT_PHASE, keys (see §5)
.venv/Scripts/python.exe -m app.main     # http://127.0.0.1:8765, loopback only (ADR-014)
```

On start the backend migrates the DB to Alembic head, seeds the codebook from `taxonomy.json` (a broken
codebook aborts startup) and starts the archive worker. `GET /healthz` answers when it is ready.

## 2. Extension (Chrome or Edge)

```bash
cd extension
npm install
npm run build                            # → extension/dist/
```

1. Open `chrome://extensions` (or `edge://extensions`), enable **Developer mode**, **Load unpacked** →
   `extension/dist`.
2. The browser warns that the extension can read all sites. That is ADR-028: `captureVisibleTab` needs
   `<all_urls>` when triggered from an in-page button. The content script only runs on x.com / twitter.com
   and the worker refuses captures from any other tab.
3. **Pin the extension id (numbered setup step, ADR-021):** copy the id shown on the extension card into
   `backend/.env` as `NIT_EXTENSION_ID=<id>` and restart the backend. Until then CORS accepts any
   `chrome-extension://` origin and the backend logs a warning.

A different backend port: `NIT_BACKEND=http://127.0.0.1:<port> npm run build` (loopback only).

## 3. Capturing

- Every post gets **Yakala** and **Kenar** buttons (top right). Click **Yakala**: the panel shows the author,
  whether the numeric id (rest_id) was verified, the category list and the codes grouped by axis.
- **Identity:** the rest_id is read from the follow button and accepted only if its @handle is the author's
  (ADR-026). X does not render it for accounts you follow or on timeline rows; open the author's profile and
  capture from there (the profile header carries it), or type it in. It is never guessed.
- **Kanıtı kaydet** (Ctrl+Enter) hides the panel and buttons, scrolls the post into view if needed, takes the
  screenshot and saves. The stamp shows the evidence name `{account_id}-{seq}` and the hash prefix.
- A quote or reply detected on the post can be saved as an edge in the same action. **Kenar** records an
  interaction on its own (quote, reply, repost, or a manual mention).
- Backend down: the panel says so and keeps everything you typed; start the backend and press **Yeniden dene**.

Files land in `backend/data/evidence/{phase}-{account_id}/`: the crop under the canonical name, the full
viewport as `-viewport.png`, and the sidecar `.json`. They are never edited; corrections are new captures.

## 4. CLI (`backend/`, backend running)

```bash
.venv/Scripts/python.exe -m app.cli bulk-archive --handle gundemhaber --urls-file urls.txt
.venv/Scripts/python.exe -m app.cli pending list              # open each, click Yakala → row completes in place
.venv/Scripts/python.exe -m app.cli pending archive-only 42   # post was deleted before completion
.venv/Scripts/python.exe -m app.cli archive pending           # jobs waiting for you
.venv/Scripts/python.exe -m app.cli archive manual            # opens the submit page, paste the link back
.venv/Scripts/python.exe -m app.cli export manifest --verify  # exit 1 on any mismatch / untracked file
.venv/Scripts/python.exe -m app.cli export case-file 1234567890123456789 -o case.json
.venv/Scripts/python.exe -m app.cli export edges -o edges.csv
```

The URL list is yours: the tool never fetches X. A handle the backend has not seen needs `--rest-id`.

## 5. Archiving — what is automatic and what is not

For X URLs both services are **manual-first**: Wayback's Save Page Now answers x.com with
`error:blocked-url` (ADR-025) and archive.today answers automated submits with a CAPTCHA (S2). The worker
therefore moves those jobs straight to `manual_pending` without any network call, and `archive manual`
walks you through them. Jobs are never deleted; re-captures of an already archived URL reuse the link
(ADR-022). SPN2 keys (`NIT_WAYBACK_S3_ACCESSKEY` / `NIT_WAYBACK_S3_SECRET`, from archive.org → account →
S3 keys) keep the automated path ready for non-X URLs and for the day archive.org lifts the block.

## 6. Phase switch, backup, restore

- `NIT_PHASE=VK1` during the first case-study sprint; switch to `VK2` **once**, at the start of sprint S2,
  and restart. Every evidence and edge row and the evidence folder carry the phase.
- **Backup:** stop the backend, copy the whole `backend/data/` folder (SQLite + evidence tree together).
- **Restore:** stop the backend, put the folder back, start, then run `export manifest --verify`.

## 7. Tests

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q          # 55 tests: write path, queue, CLI, exports
cd extension && npm run check                                # typecheck + 26 unit tests + build
# end to end in a real browser (backend on 8781, fixture x.com page, no network):
NIT_BACKEND=http://127.0.0.1:8781 npm run build
node scripts/e2e.mjs --backend http://127.0.0.1:8781 --data <backend data dir> --out e2e-out
```

Not yet verified: a capture on live x.com with a logged-in session (the extractor fixtures are synthetic,
modelled on the S1 spike's markup) and the Day 7 shakedown in `PLAN.md`.
