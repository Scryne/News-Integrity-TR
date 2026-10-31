/** Panel CSS — values are the DESIGN.md tokens; everything stays in the shadow root. */
export const STYLES = `
:host { all: initial; }
.panel {
  --surface: #14161B; --raised: #1C1F26; --sunken: #0F1115;
  --border: #2A2E37; --border-strong: #3A3F4B;
  --text-1: #ECEEF2; --text-2: #A9AFBC; --text-3: #858C9B;
  --accent: #E0694F; --accent-hover: #EB7D64; --accent-ink: #1B0E0A; --accent-soft: #3A211B;
  --success: #3FB37F; --warning: #E3A63A; --danger: #F0645A;
  --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
  position: fixed; top: 0; right: 0; z-index: 2147483646;
  width: 400px; max-width: 100%; height: 100vh; height: 100dvh;
  display: flex; flex-direction: column;
  background: var(--surface); color: var(--text-1);
  border-left: 1px solid var(--border);
  box-shadow: 0 12px 32px rgba(0, 0, 0, .45);
  font: 13px/1.45 system-ui, "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased; text-align: left;
}
@media (max-width: 480px) {
  .panel { top: auto; bottom: 0; left: 0; right: 0; width: auto; height: 85vh; height: 85dvh; border-left: 0; border-top: 1px solid var(--border); border-radius: 12px 12px 0 0; }
  .foot .kbd { display: none; }
}
*, *::before, *::after { box-sizing: border-box; }
h2 { margin: 0; font-size: 15px; font-weight: 600; letter-spacing: -.005em; }
p { margin: 0; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 16px; border-bottom: 1px solid var(--border); }
.sub { margin-top: 2px; color: var(--text-3); font-size: 12px; }
.body { flex: 1; overflow-y: auto; overscroll-behavior: contain; padding: 16px; display: grid; gap: 16px; align-content: start; }
.foot { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); background: var(--surface); }
.foot .kbd { margin-right: auto; font-size: 11px; }
.muted { color: var(--text-3); }
.mono { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; }
button { font: inherit; white-space: nowrap; cursor: pointer; border-radius: 6px; min-height: 32px; padding: 0 14px; border: 1px solid transparent; transition: background-color .12s, border-color .12s, color .12s; }
button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible, .chip:has(input:focus-visible) {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
button[disabled] { cursor: progress; opacity: .7; }
.primary { background: var(--accent); color: var(--accent-ink); font-weight: 600; }
.primary:hover:not([disabled]) { background: var(--accent-hover); }
.ghost { background: transparent; color: var(--text-2); border-color: var(--border-strong); }
.ghost:hover { color: var(--text-1); border-color: var(--text-3); }
.icon { min-height: 28px; width: 28px; padding: 0; background: transparent; color: var(--text-2); border-color: var(--border); }
.icon:hover { color: var(--text-1); border-color: var(--border-strong); }
.summary { display: grid; gap: 6px; padding: 12px; background: var(--raised); border: 1px solid var(--border); border-radius: 6px; }
.summary .row { display: flex; justify-content: space-between; gap: 8px; }
.handle { font-weight: 600; }
.text { color: var(--text-2); white-space: pre-wrap; overflow-wrap: anywhere; }
.identity { display: grid; gap: 8px; padding: 10px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--raised); }
.identity.ok { grid-template-columns: auto 1fr auto; align-items: center; }
.identity.warn { border-color: rgba(227, 166, 58, .5); }
.identity.warn strong { color: var(--warning); }
.dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
.field { display: grid; gap: 6px; }
label { color: var(--text-2); }
input, select, textarea {
  font: inherit; color: var(--text-1); background: var(--sunken);
  border: 1px solid var(--border-strong); border-radius: 6px; padding: 7px 10px; width: 100%;
}
input::placeholder, textarea::placeholder { color: var(--text-3); }
textarea { resize: vertical; min-height: 56px; }
select { appearance: auto; }
.groups { display: grid; gap: 12px; }
fieldset { margin: 0; padding: 0; border: 0; min-width: 0; }
legend { padding: 0 0 6px; color: var(--text-2); font-weight: 600; }
legend .mono { color: var(--text-3); }
.chips { display: grid; gap: 6px; }
.chip {
  display: grid; grid-template-columns: auto 30px 1fr; align-items: start; gap: 8px;
  padding: 7px 10px; border: 1px solid var(--border); border-radius: 6px; background: var(--raised);
  color: var(--text-1); cursor: pointer;
}
.chip:hover { border-color: var(--border-strong); }
.chip input { width: 14px; height: 14px; margin: 2px 0 0; padding: 0; accent-color: var(--accent); }
.chip .code { color: var(--text-2); }
.chip:has(input:checked) { background: var(--accent-soft); border-color: var(--accent); }
.chip:has(input:checked) .code { color: var(--text-1); font-weight: 600; }
.edgebox { display: grid; gap: 6px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 6px; background: var(--raised); }
.edgebox legend { padding: 0 4px; }
.radio { display: flex; align-items: center; gap: 8px; color: var(--text-1); cursor: pointer; flex-wrap: wrap; }
.radio input[type="radio"] { width: auto; accent-color: var(--accent); margin: 0; }
.radio input:not([type="radio"]) { width: 160px; }
.notice { display: grid; gap: 6px; margin: 0; padding: 10px 12px 10px 28px; border-radius: 6px; border: 1px solid var(--border); background: var(--raised); }
.notice.warn { border-color: rgba(227, 166, 58, .5); }
.notice.warn li::marker { color: var(--warning); }
.notice.danger { padding-left: 12px; border-color: rgba(240, 100, 90, .55); }
.notice.danger strong { color: var(--danger); }
.notice.danger button { justify-self: start; }
.skeleton { padding: 24px 12px; color: var(--text-3); border: 1px dashed var(--border); border-radius: 6px; text-align: center; }
.stamp { display: grid; gap: 4px; padding: 14px; border: 1px solid var(--accent); border-radius: 6px; background: var(--sunken); }
.stamp-title { font-weight: 600; color: var(--success); }
.stamp .mono:not(.muted) { font-size: 13px; color: var(--text-1); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
`;
