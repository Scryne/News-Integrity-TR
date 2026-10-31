---
name: premium-saas-dashboard-design
description: >
  A complete design system and decision protocol for producing premium, production-grade
  SaaS dashboard UI (web apps, admin panels, analytics tools, B2B platforms). Use this
  skill whenever building ANY dashboard, admin interface, SaaS product UI, analytics view,
  data table, KPI screen, or app shell — even if the user only says "make it look good"
  or gives nothing but a project topic. It adapts the visual direction to the project's
  domain while enforcing a consistent, professional quality bar.
---

# DESIGN.md — Premium SaaS Dashboard Design System

> **What this document is.** A self-contained design operating system. Given only a
> project topic (e.g. "tender analysis platform", "payments dashboard", "MES for
> factories"), follow the **Adaptation Protocol** in §2 to derive a unique, domain-specific
> visual identity, then execute it using the token systems, component specifications, and
> chart language defined below. The output must look like a funded product designed by a
> senior product design team — never like a template, a Bootstrap admin theme, or a
> default AI generation.

---

## 1. Design Philosophy — Non-Negotiables

These ten principles override everything else. If any later rule conflicts with a
principle, the principle wins.

1. **Calm surfaces, loud data.** The chrome (sidebar, cards, toolbars) is quiet and
   neutral. Color, weight, and size are spent almost exclusively on *data*: KPI values,
   deltas, chart highlights, statuses. If the interface is colorful but the numbers are
   not the first thing you see, the design has failed.
2. **One accent color.** Exactly one brand accent per product, plus the fixed semantic
   set (success / warning / danger / info). Never two competing brand hues. Data
   visualizations may extend to a controlled categorical palette (§8.1), but UI chrome
   uses one accent only.
3. **Borders before shadows.** Structure comes from 1px borders and surface-tone steps.
   Shadows are whispers (§6.4) used for elevation changes (dropdowns, modals, hover),
   never for decorating resting cards.
4. **Density with breathing room.** Dashboards are information-dense by nature. Achieve
   density through a strict 4px spatial grid and compact type — never by cramming.
   Every card interior gets 20–24px padding, no exceptions.
5. **Numbers are typography.** All numerals use `font-variant-numeric: tabular-nums`.
   Large KPI values are the typographic heroes of the page: big, semibold, tightly
   tracked. A dashboard's personality lives in how its numbers are set.
6. **Hierarchy in exactly three text tones.** Primary (headings, values), secondary
   (labels, body), tertiary (captions, axis labels, timestamps). If a fourth gray
   appears, consolidate.
7. **Real content, always.** Populate every screen with realistic, domain-correct mock
   data (§10). No "Lorem ipsum", no "Item 1 / Item 2", no obviously fake numbers like
   1234 or 9999. Believable data is 40% of what makes a dashboard look professional.
8. **One signature element.** Every project gets exactly one memorable visual device
   (§9) — a texture, a numeral treatment, a chart behavior, a canvas tint. One. The rest
   of the design stays disciplined so the signature can breathe.
9. **The 8-second test.** A stranger looking at the screen for 8 seconds should be able
   to say what the product does and what the most important number is right now. Design
   for that test.
10. **Quality floor without announcement.** Keyboard focus states, WCAG AA contrast,
    hover feedback, empty states, loading skeletons — all present, none advertised.

---

## 2. Adaptation Protocol — From Topic to Design Direction

Run this protocol **before writing any code**. Do it in your reasoning, then state the
resulting Design Brief in one short block before building.

### Step 1 — Pin the subject
Name: (a) the product's concrete domain, (b) its primary persona (who stares at this
screen for hours), (c) the screen's single job (the one decision it helps the persona
make). If the user gave only a topic, derive these yourself and state them.

### Step 2 — Choose the theme archetype
Select **one** archetype from §3 using this decision table:

| Signal from the domain | Archetype |
|---|---|
| Operational B2B tools: CRM, ERP, MES, HR, support desks, admin panels | **A — Clean Light** |
| Finance/enterprise tools that want warmth: expense, accounting, real-estate, sales | **B — Soft Light** |
| Money at night: payments infra, crypto, trading, treasury, personal finance | **C — Deep Dark** |
| Developer/technical: AI ops, observability, API platforms, agent orchestration | **D — Terminal Dark** |
| Products that want editorial edge: e-commerce analytics, creative-industry tools | **E — Mono Editorial** |

If the user names a preference ("dark mode", "like Stripe", "corporate"), the user's
words win over the table.

### Step 3 — Choose the accent
Pick one accent from the domain table in §4.3, then **shift it** by 5–15° of hue or a
saturation step so it is *not* the raw default everyone uses (not pure `#3B82F6`
Tailwind blue, not `#8B5CF6` stock violet). State the final hex.

### Step 4 — Choose typography
Pick a body/UI face and decide whether the project earns a mono or display secondary
face (§5.1). Fintech and developer tools almost always earn a mono for numerals;
editorial archetype E requires one.

### Step 5 — Choose the signature element
Pick exactly one from §9, justified by the domain ("hatched bars because manufacturing
= engineering drawings", "phosphor-green numerals because trading terminals").

### Step 6 — Self-critique before building
Ask: *"If I ran this protocol for a generic project, would I land here anyway?"* If
yes, revise the accent, the signature, or the type choice until the answer is no. Then
write the code, following the brief exactly.

**Design Brief output format (state this, then build):**

```
DESIGN BRIEF
Domain/persona/job: …
Archetype: A|B|C|D|E
Accent: #HEX (name) — rationale
Type: UI face + numeric/display face
Signature: … — rationale
```

---

## 3. Theme Archetypes

Each archetype is a complete surface system. Values are starting points — the accent
and signature come from the protocol above.

### Archetype A — Clean Light (operational SaaS)
The default for tools people use 8 hours a day. Whisper-gray canvas, white cards,
hairline borders, ink text.

```css
--canvas:        #F7F8FA;   /* page background */
--surface:       #FFFFFF;   /* cards, sidebar */
--surface-2:     #F2F3F6;   /* insets: table headers, input bg, muted chips */
--border:        #E7E9EE;   /* default hairline */
--border-strong: #D8DBE2;   /* inputs, emphasized dividers */
--text-1:        #101319;
--text-2:        #4E5564;
--text-3:        #8A91A0;
```

### Archetype B — Soft Light (warm enterprise)
Same skeleton as A, but the canvas carries a barely-there tint of the accent's hue
family (2–4% saturation), cards feel softer (radius +2px, shadow slightly warmer), and
one hero card may be inverted to near-black for contrast (see sub.pay/Findexa pattern:
a dark "primary account" card sitting on a light page — or vice versa).

```css
--canvas:  hsl(<accent-hue> 20% 97%);
--surface: #FFFFFF;
/* remaining tokens as Archetype A; shadow: 0 1px 2px rgb(20 24 33 / .05) */
```

### Archetype C — Deep Dark (money at night)
Near-black, layered by *lightness steps*, not shadows. Charts glow slightly.

```css
--canvas:        #0A0B0E;
--surface:       #121317;   /* cards */
--surface-2:     #1A1C22;   /* raised: hover rows, insets, chips */
--surface-3:     #23262E;   /* overlays, dropdowns */
--border:        #24262D;   /* ≈ white @ 9% */
--border-strong: #32353E;
--text-1:        #F4F5F7;
--text-2:        #9CA2B0;
--text-3:        #646B7A;
```
Rules: success-green and the accent may use a subtle outer glow on chart strokes
(`filter: drop-shadow(0 0 6px <accent 25%>)`) — on chart elements only, never on UI.

### Archetype D — Terminal Dark (developer/technical)
Archetype C's surfaces with technical DNA: mono numerals everywhere, denser rows
(44–48px), squarer radii (8/6px), status text rendered in mono, tag-like colored
labels for entities (agent names, model ids) instead of pill badges. See the
observability pattern: colored inline entity names + mono durations.

### Archetype E — Mono Editorial (statement piece)
Light, near-monochrome, editorial. ALL numerals and labels in a monospace face,
UPPERCASE 11px letterspaced overlines for every card title, black-and-white charts
where *texture and pattern* (hatching, dot grids, solid vs. outline) replace hue as the
encoding. Accent restricted to semantic statuses and at most one interactive element.
Radius 8px max. This archetype is high-risk/high-reward — use when the domain wants to
feel like a designed object.

---

## 4. Color System

### 4.1 Semantic colors (fixed across all archetypes)

| Role | Light fg | Light bg tint | Dark fg | Dark bg tint |
|---|---|---|---|---|
| Success | `#158A4C` | `#E9F7EF` | `#34D57B` | `rgb(52 213 123 / .12)` |
| Warning | `#B4690E` | `#FCF3E4` | `#F5A623` | `rgb(245 166 35 / .12)` |
| Danger | `#D6362F` | `#FCECEB` | `#F26B5E` | `rgb(242 107 94 / .12)` |
| Info | `#2360D8` | `#EAF1FD` | `#5B9BF7` | `rgb(91 155 247 / .12)` |

Deltas: positive = success, negative = danger, always paired with a direction glyph
(`↑`/`↓` or a small triangle) — never color alone.

### 4.2 Accent usage budget
The accent appears in, and only in: primary buttons, active nav item, selected
segmented-control option, focus rings, links, the *highlighted* series/bar in charts,
and toggles. It never tints card backgrounds or body text.

### 4.3 Domain → accent starting points (shift per §2 Step 3)

| Domain family | Accent direction | Example hex |
|---|---|---|
| Payments / banking infra | Emerald or deep green on dark | `#2FBF71` |
| Crypto / trading | Signal green + cool blue secondary series | `#31C48D` / `#4C8DF6` |
| CRM / sales / marketing | Violet-indigo | `#6659F0` |
| Manufacturing / MES / ERP / logistics | Engineering blue, or chartreuse-on-dark for a bolder brief | `#2E6BE6` / `#C8F04B` |
| Procurement / legal / gov-tech / compliance | Deep teal or navy — institutional trust | `#0E7A8A` / `#1E3A8A` |
| DevTools / AI ops / observability | Electric blue or cyan, mono-heavy | `#3E8BFF` |
| Personal finance / consumer | Warm amber-orange gradient family | `#F59A23` → `#F0653A` |
| Health / wellness B2B | Teal-green | `#0FA47A` |
| E-commerce / retail analytics | Editorial black + one warm accent | `#111` + `#F0653A` |

### 4.4 Chart categorical palette
Ordered, max 6, accent first: `accent → info-blue → amber → violet → teal → rose`.
Series beyond the highlighted one drop to 70–80% opacity or the muted treatment (§8.3).
Sequential data uses tints of the accent (100% → 15%), never rainbow scales.

---

## 5. Typography

### 5.1 Font stacks (pick per protocol)

| Role | Options (choose one) |
|---|---|
| UI / body (default) | **Inter**, Geist, Manrope, Plus Jakarta Sans, Public Sans |
| Numeric / technical mono | **JetBrains Mono**, Geist Mono, IBM Plex Mono, Space Mono (archetype E) |
| Optional display (page titles only, rarely) | Same family at heavier weight is usually enough; only add a display face if the brief is consumer-flavored |

Load via fontshare/google fonts or system fallback:
`font-family: Inter, -apple-system, "Segoe UI", sans-serif;`

### 5.2 Type scale (px / line-height / weight / tracking)

| Token | Spec | Use |
|---|---|---|
| `display` | 30/36 · 650 · -0.02em | Hero KPI on overview pages |
| `kpi` | 24/30 · 600 · -0.015em | Stat-card values |
| `title-page` | 22/28 · 600 · -0.01em | "Welcome back, {name}", page titles |
| `title-card` | 15/22 · 600 · 0 | Card headers |
| `body` | 14/20 · 400–450 · 0 | Default text, table cells |
| `body-sm` | 13/18 · 400 · 0 | Secondary cell text, descriptions |
| `label` | 12/16 · 500 · +0.01em | Stat-card labels, form labels |
| `overline` | 11/14 · 600 · +0.06em · UPPERCASE | Sidebar section headers, archetype-E card titles |
| `axis` | 11/14 · 450 · 0 | Chart axes, timestamps |

### 5.3 Numeric rules
- `font-variant-numeric: tabular-nums` on **every** element that can contain a number.
- KPI values: integer part dominant; decimals/currency symbols may drop to 60–70% size
  and `--text-2` color (e.g. **$184,392**<small>.40</small>).
- Deltas: 12–13px, weight 550, semantic color, glyph + value + optional context
  ("+12.4% vs last week" — context in `--text-3`).
- Mono face (if chosen) applies to: table numerics, IDs/codes, timestamps, durations,
  API-ish strings. Not to prose.

---

## 6. Spatial System

### 6.1 Grid & spacing
Base unit **4px**. Approved steps: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- Card padding: 20px (dense) or 24px (default).
- Gap between cards: 16px (dense) / 20–24px (default).
- Section vertical rhythm: 24–32px.

### 6.2 Radius scale
| Token | Value | Use |
|---|---|---|
| `r-card` | 14px (A/B/C) · 10px (D) · 8px (E) | Cards, modals |
| `r-inner` | 8–10px | Inputs, buttons, chips inside cards |
| `r-pill` | 999px | Status pills, delta badges, avatars |

Never mix: a child's radius ≤ parent's radius − 4px.

### 6.3 Borders
Every resting card: `1px solid var(--border)`. Tables: horizontal row dividers only —
no vertical rules, no full grids. Inputs: `--border-strong`, focus swaps to accent +
3px soft ring (`box-shadow: 0 0 0 3px <accent 18%>`).

### 6.4 Shadows (light archetypes only; dark uses surface steps)
```css
--shadow-rest:  0 1px 2px rgb(16 20 28 / .04);
--shadow-hover: 0 4px 12px rgb(16 20 28 / .07);
--shadow-pop:   0 12px 32px rgb(16 20 28 / .12);  /* dropdowns, modals */
```

### 6.5 App shell

```
┌───────────┬──────────────────────────────────────────────┐
│  SIDEBAR  │ TOPBAR  (breadcrumb · search ⌘K · actions)   │
│  240–272  ├──────────────────────────────────────────────┤
│           │ PAGE HEADER (title + context · date/export)  │
│  sections │ ┌────────┬────────┬────────┬────────┐        │
│  + nav    │ │ KPI    │ KPI    │ KPI    │ KPI    │  4-up  │
│           │ └────────┴────────┴────────┴────────┘        │
│  ────     │ ┌───────────────────────────┬──────────┐     │
│  upgrade  │ │  primary chart (8 cols)   │ side (4) │     │
│  card     │ └───────────────────────────┴──────────┘     │
│  user     │ ┌──────────────────────────────────────┐     │
│  footer   │ │  data table (12 cols, full width)    │     │
└───────────┴──────────────────────────────────────────────┘
```

- Sidebar: 240–272px fixed, collapsible to 64px icon rail. Same surface as cards
  (light) or `--surface` (dark), 1px right border.
- Topbar: 56–64px, transparent or `--surface`, bottom border.
- Content: 24–32px padding, 12-column grid, max-width 1520px centered on ultrawide.
- Canonical splits: KPI row 4×3-col (2×2 on tablet) · primary+secondary 8/4 or 7/5 ·
  equal pair 6/6 · table 12.

---

## 7. Component Specifications

### 7.1 Sidebar navigation
- **Workspace switcher** (top): logo mark 28–32px + product name 15/600; optional
  environment pill ("Live", "Prod") in success tint.
- **Sections**: `overline` labels (`MAIN MENU`, `INSIGHTS`, `SETTINGS`), 16px top
  margin, first section unlabeled if obvious.
- **Items**: 36–40px height, `r-inner` radius, 18px icon (lucide, 1.5px stroke) +
  13.5–14px/500 label, `--text-2` resting.
  - Hover: `--surface-2` bg, `--text-1`.
  - **Active** (pick one style per project and keep it): (a) accent-tint bg
    (`<accent 10%>`) + accent text/icon, (b) solid inverse chip (dark bg + white text
    on light UIs — the "high-contrast" style), or (c) `--surface-2` + 2px accent left
    rail.
  - Count badges right-aligned: `r-pill`, `--surface-2` or accent tint, 11px/600.
- **Sub-items**: 28px indent with a 1px vertical guide line, tree-branch connectors optional.
- **Footer**: user card (avatar 32px, name 13/600, role/email 12 `--text-3`, chevron);
  optional **upgrade card** above it — `--surface-2` bg, `r-card`, 13px pitch, small
  primary button. One promo card max.

### 7.2 Topbar
Breadcrumb (`--text-3` › separators, current in `--text-1`) · global search — 320–420px
input, magnifier icon, `⌘K` kbd chip right-aligned (`--surface-2`, 11px mono, `r-inner`)
· icon buttons 36px square with dot indicators for unread · avatar/menu.

### 7.3 Page header
Title (`title-page`; greeting form "Welcome back, {name}" + optional 👋 only for
friendly consumer briefs) · one-line context in `--text-2` 13–14px · right cluster:
date-range picker (calendar icon + label, bordered) and primary action (`Export`,
`+ New {entity}`).

### 7.4 KPI stat card
Anatomy top→bottom: label row (`label` tone `--text-2`, optional 16px icon right) →
value (`kpi`, tabular) → delta row (semantic badge + "vs last {period}" in `--text-3`).
Optional right-side mini sparkline (48–64×28px, accent or neutral bars).
Variants: (a) plain, (b) sparkline, (c) icon-boxed — 36px rounded icon tile in accent
tint. Pick **one variant per project** and repeat it; mixed stat-card styles read as
template salad. Delta badge: `r-pill`, tint bg, 12/550.

### 7.5 Chart card
Header: `title-card` + optional ⓘ; right cluster from: segmented range control
(`24h · 7d · 30d · 90d · 1Y` — `--surface-2` track, active segment `--surface` +
border + shadow-rest), dropdown filter, kebab menu.
Optional sub-header KPI: big number + delta directly above the plot ("4,790 +8% vs
last week" pattern). Legend: 8px dot/square + 12px label, top-right or under header.
Plot area ≥180px tall; 24px padding all sides inside the card.

### 7.6 Data table
- Header row: `--surface-2` bg or transparent-with-strong-border; cells 12px/550
  `--text-2` (or `overline` style for archetype E); sortable arrows on hover.
- Rows: 52–60px (44–48 archetype D), bottom hairline only, hover `--surface-2` at 50%,
  selected rows accent-tint bg + checked box.
- Cell types: **entity** (avatar/logo 28–32px + name 13.5/550 + sub-line 12 `--text-3`),
  **numeric** (right-aligned, tabular, mono if chosen), **status pill** (§7.8),
  **role/tag badge** (square-ish `r-inner`, tinted), **trend** (mini sparkline 60×20),
  **actions** (kebab, visible on hover), **date** (`--text-2`).
- Toolbar above: result count chip, filter chips, date filter, search, view options.
- Footer: rows-per-page select + "1–10 of 145" + pagination.

### 7.7 Buttons & inputs
| Kind | Spec |
|---|---|
| Primary | accent bg, white text, 36–40px h, `r-inner`, 13.5/600; hover −6% lightness |
| Secondary | `--surface` bg, `--border-strong` border, `--text-1` |
| Ghost | transparent, `--text-2`, hover `--surface-2` |
| Destructive | danger, confirm-gated |
| Icon button | 32–36px square, ghost by default |

Inputs 36–40px, `r-inner`, placeholder `--text-3`; selects with chevron; segmented
controls per §7.5; toggles 36×20 accent-filled when on.

### 7.8 Status pills — the canonical pattern
`[● dot 6px] Label` · `r-pill` · tint bg at 10–14% · fg = semantic/darker shade ·
11.5–12px/550 · 4px gap · 8px horizontal padding.
Standard mapping: Active/Success/Done → success · Pending/In&nbsp;Review → warning ·
Suspended/Failed/Error → danger · Draft/Inactive → neutral (`--surface-2` +
`--text-2`) · Info/Queued → info. Domain synonyms map onto these five — never invent a
sixth color.

### 7.9 Activity feeds & funnel lists
Feed row: 32px icon tile (tinted per event type) + title 13.5/550 + description 12.5
`--text-3` + right-aligned relative time. Funnel/stage list: stage icon + name +
description + right-aligned count, with % of previous stage in `--text-3`.

### 7.10 Progress & targets
Linear: 6–8px track `--surface-2`, accent fill, `r-pill`; pair with "84.3% · $47,100
left" style labels. Radial/donut for single-goal cards (§8.5). Multi-segment bars
(spending breakdown): flat joined segments in the categorical palette, legend above.

### 7.11 Overlays
Dropdown/popover: `--surface-3` (dark) or white + `--shadow-pop`, `r-inner`+2, 6px item
padding rhythm. Modal: 480–640px, `r-card`, title 16/600, right-aligned footer actions.
Toast: bottom-right, dark surface, icon + 13px text, auto-dismiss 4s.

### 7.12 Empty & loading states
Empty: centered 40px icon tile, one plain-language sentence ("No invoices yet"), one
primary action. Loading: skeleton blocks (`--surface-2`, 1.4s shimmer) matching the
real layout — cards keep their heights; no spinners for content areas.

---

## 8. Data Visualization Language

Charts are where these designs win or lose. Follow this section exactly.

### 8.1 Global rules
- Horizontal gridlines only: 1px, `--border` at 60% opacity, 3–5 lines. **No vertical
  gridlines**, no chart borders, no axis spines.
- Axis labels: `axis` token, `--text-3`. Y-axis abbreviated ($50k, 1.2M); x-axis
  thinned to 6–12 ticks.
- Every chart answers one question; put that question's answer in the card header KPI.
- Color encodes meaning (accent = the thing that matters now); everything else is muted.

### 8.2 Line & area charts
Stroke 1.75–2px, `stroke-linejoin: round`, gentle curve (`monotoneX`) or straight
segments for volatile/financial series — choose per data honesty, not aesthetics.
Area fill: vertical gradient accent 12% → 0%. Hover: 4px dot with 2px surface ring +
vertical dashed guide + tooltip. Multi-series: max 3 lines; comparison series in
`--text-3` gray or dashed. Target/threshold: 1px dashed line + small end label chip
("Target: $180k").

### 8.3 Bar charts — the highlight-one pattern
Default state: **all bars muted, one bar highlighted.** Highlighted = current/selected
period in solid accent (or a vertical accent gradient for archetype C); muted =
`--surface-2` (light), `white @ 8%` (dark), or **diagonal hatching** (archetype E /
engineering domains). Bar radius 4–6px top; width ≤ 60% of slot. Value tag chip floats
above the highlighted bar. Grouped/stacked: max 3 segments, joined flat, legend
required.

### 8.4 Sparklines
60–80×24–28px, no axes/grid. Line: 1.5px accent with 2px end-dot. Bars: 3–4px wide,
2px gaps, last bar accent, rest muted.

### 8.5 Donut / radial
Ring thickness 22–28% of radius, 2px gaps between segments (`stroke-linecap: round`
optional), center: value (`kpi`) + label (`label`). Max 5 segments + "Other". Never a
pie; never 3D.

### 8.6 Tooltip (uniform across all charts)
Dark chip `#0F1115` (both themes) · white 12px text · `r-inner` · `--shadow-pop` ·
structure: period label (`--text-3`-on-dark) + rows of "series dot · name · **value**"
· follows cursor with 12px offset, flips at edges.

### 8.7 Realtime & technical variants (archetype C/D)
Live indicators: pulsing 6px success dot + "Live" 11px. Streams: row-based activity
tables with mono durations. Latency/error panels: bars colored by threshold, not by
category.

---

## 9. Signature Element — Choose Exactly One

The single device this product will be remembered by. Justify it from the domain.

| Signature | Description | Fits |
|---|---|---|
| **Hatched data** | Diagonal-line or dot-grid fills for muted chart series & progress tracks | Manufacturing, logistics, editorial |
| **Mono numerals** | All numbers in a characterful mono; UI text stays sans | Fintech infra, devtools, terminals |
| **Inverse hero card** | One near-black card (primary balance/KPI) on a light page — or one white card on dark | Banking, personal finance |
| **Glow accent** | Chart strokes carry a soft accent glow on deep-dark canvas | Crypto, trading, AI |
| **Gradient highlight bar** | The highlighted bar in every bar chart is a vertical accent gradient with a floating value chip | Consumer finance, growth analytics |
| **Tinted canvas** | Page canvas carries a 2–4% tint of the accent hue; cards stay pure white | Warm enterprise, health |
| **Oversized center-donut** | One dominant donut with a huge center KPI as the page's anchor | Ops dashboards with a single utilization metric |
| **Entity color-coding** | Inline entity names (agents, machines, reps) rendered in stable per-entity hues, mono | Observability, multi-agent, fleet ops |
| **Rail-active nav** | 2px accent left rail + tint as the nav active state, echoed as left rails on alert cards | Compliance, procurement, gov |
| **Pattern-coded statuses** | Statuses distinguished by fill pattern (solid/outline/hatch) in addition to color | Accessibility-first, print-adjacent domains |

Everything not the signature stays quiet. If two devices from this table appear, cut one.

---

## 10. Content, Copy & Data Guidelines

- **Names & entities**: realistic and domain-correct (companies, machine ids like
  `CNC-04`, tender numbers like `2026/128764`, SKUs, agent names). Localize when the
  product is regional (Turkish company names, ₺/TRY, `DD.MM.YYYY` dates for TR briefs;
  otherwise en-US defaults).
- **Numbers**: plausible magnitudes and *irregular* values (`$184,392.40`, `2,841`,
  `98.2%`) with internally consistent math (funnel stages decrease; percentages sum).
- **Time**: relative for recency ("2m ago", "Yesterday"), absolute elsewhere
  ("Jul 14, 2026"). Mixed feeds sort correctly.
- **Copy**: sentence case everywhere except overlines. Verbs on buttons ("Export CSV",
  "Invite user" — never "Submit"). Labels name what users control, not how the system
  works. Empty states = one fact + one action. Errors say what happened and what to do.
- **Icons**: one library (lucide), one stroke width (1.5px), 18px nav / 16px inline /
  20px feature tiles. No emojis as icons (a 👋 in a greeting is the only exception,
  and only on friendly briefs).

---

## 11. Motion & Interaction

- Durations: micro (hover, toggles) 120–150ms · standard (dropdowns, tab panels)
  180–220ms · large (modals, drawers) 240–300ms. Easing `cubic-bezier(0.2, 0, 0, 1)`.
- Charts animate **once** on load: bars grow (staggered 20ms), lines draw or fade-up,
  donuts sweep. 400–600ms total. No looping animations except live-dot pulses.
- Hover: rows tint, cards lift to `--shadow-hover` **only if clickable**, chart points
  enlarge. Cursor `pointer` only on real actions.
- Numbers may count up on first paint (≤800ms) — skip under `prefers-reduced-motion`,
  which disables all non-essential motion.
- Focus: 2px accent ring, offset 2px, on every interactive element. Tab order follows
  visual order.

---

## 12. Accessibility & Quality Floor

- Text contrast ≥ 4.5:1 (body) and ≥ 3:1 (large KPI numerals, UI glyphs). Verify
  semantic tints against their backgrounds in the chosen archetype.
- Never color-only encoding: statuses carry dots+labels, deltas carry glyphs, chart
  series get labels/legends.
- Hit targets ≥ 36×36px. Tables keyboard-navigable; sort state announced via
  `aria-sort`.
- Responsive floor: 4-up KPIs → 2×2 → 1-col; sidebar → icon rail → drawer under 1024px;
  tables scroll horizontally inside their card with a pinned entity column.

---

## 13. Implementation Tokens

Emit the chosen archetype as CSS custom properties on `:root` (and `[data-theme=dark]`
if dual-theme). Minimum contract — every component references only these:

```css
:root {
  /* surfaces */
  --canvas: …; --surface: …; --surface-2: …; --surface-3: …;
  --border: …; --border-strong: …;
  /* text */
  --text-1: …; --text-2: …; --text-3: …;
  /* brand + semantic */
  --accent: …; --accent-weak: <accent 10%>; --on-accent: #fff;
  --success: …; --success-weak: …;
  --warning: …; --warning-weak: …;
  --danger:  …; --danger-weak:  …;
  --info:    …; --info-weak:    …;
  /* shape & elevation */
  --r-card: …; --r-inner: …; --r-pill: 999px;
  --shadow-rest: …; --shadow-hover: …; --shadow-pop: …;
  /* type */
  --font-ui: …; --font-mono: …;
}
```

Tailwind projects: map these tokens in `theme.extend` (`colors.surface`,
`borderRadius.card`, …) and forbid raw palette classes (`bg-blue-500`) in components.
Charts (Recharts/Chart.js/D3): read colors from CSS variables so themes stay in sync.
React structure: `AppShell → Sidebar / Topbar / PageHeader / <Grid> of Card
compositions`; every card is `Card + CardHeader + slot`, so layouts recompose without
restyling.

---

## 14. Domain Playbooks — Worked Examples

Compressed runs of the §2 protocol. Use as calibration, not as fixed answers.

**Payments infrastructure (B2B)** — Archetype C · accent emerald `#2FBF71` · Inter +
Geist Mono numerals · signature: mono numerals · modules: gross-volume hero chart with
7d/30d segments, 4 KPI cards with sparklines, top-customers list, payment-methods
distribution bars, disputes badge in nav.

**Manufacturing MES/ERP** — Archetype A · accent engineering blue `#2E6BE6` · Inter ·
signature: hatched data (muted bars & progress tracks hatched like technical drawings)
· modules: OEE/downtime/quality KPI row, production-trend highlight-one bars, machine
uptime list with status pills, energy log table, realtime alert cards with severity
rails.

**CRM / sales analytics** — Archetype A or B · accent violet-indigo `#6659F0`
(shifted) · Manrope · signature: gradient highlight bar with floating value chip ·
modules: revenue trend vs dashed target, funnel stage list with conversion %, activity
donut, monthly-target progress card, deals table with stage badges.

**AI / LLM ops platform** — Archetype D · accent electric blue `#3E8BFF` · Inter +
JetBrains Mono · signature: entity color-coding (agent/model names in stable hues,
mono durations) · modules: trace-volume multiline chart, live activity stream, eval
scores as horizontal bars, top-errors table with trend chips, per-model latency bars.

**Public procurement / tender intelligence** — Archetype A · accent deep teal
`#0E7A8A` · Public Sans · signature: rail-active nav echoed on deadline/risk alert
cards · modules: active-tenders KPI row (deadline proximity as warning pills), tender
pipeline table (authority · budget ₺ · deadline · compliance status), requirement-
match donut per tender, deadline calendar strip, document-analysis activity feed.
Turkish locale formats throughout.

**Consumer personal finance** — Archetype C · accent amber-orange gradient
`#F59A23→#F0653A` · Plus Jakarta Sans · signature: gradient highlight bar + inverse
wallet card · modules: balance hero with multi-currency wallet chips, cash-flow bars
with one gradient month, spending-breakdown segmented bar, upcoming-bills list with
brand tiles, savings-goal progress cards.

---

## 15. Anti-Patterns — Never Ship These

1. Purple-gradient-on-white "AI startup" default, or any 2+ brand hues in chrome.
2. Raw framework palettes used verbatim (Tailwind `blue-500`, Bootstrap look, default
   Chart.js colors, default shadcn zinc without adjustment).
3. Heavy borders on all four sides of table cells; vertical gridlines; visible chart
   spines; 3D or pie charts.
4. Rainbow categorical charts, or every bar its own color when one metric is shown.
5. Shadowed everything: drop shadows on resting cards, buttons, and text.
6. Radius chaos (mixed 4/12/24px siblings) or >20px radii on data-dense cards.
7. Glassmorphism blur panels, neon on light backgrounds, decorative gradients behind
   text.
8. Emoji as icons; mixed icon libraries; 2px+ icon strokes next to 1.5px.
9. Fake content: Lorem ipsum, "User 1", 1000/2000/3000 round numbers, funnels that
   don't decrease.
10. Center-aligned dashboard layouts; KPI cards with 4 different internal layouts;
    stat values below 20px.
11. Color-only status encoding; disabled-gray text below 3:1 used for real content.
12. Two signature elements. Or zero — a competent-but-anonymous result is also a
    failure of this document.

---

## 16. Pre-Ship QA Checklist

Run before presenting. Every unchecked box is a required fix.

- [ ] Design Brief (§2) was stated and the final UI matches it.
- [ ] One accent in chrome; semantic colors only where meaning demands.
- [ ] All numerals tabular; KPI values are the visual anchors of the page.
- [ ] Exactly three text tones in use.
- [ ] Cards: consistent padding, radius, 1px borders; shadows only where specified.
- [ ] Charts: horizontal-only gridlines, muted-vs-highlight logic, uniform tooltip,
      target lines dashed with label chips.
- [ ] Table: entity cells with avatars, right-aligned numerics, canonical status
      pills, hover states, toolbar + pagination.
- [ ] Sidebar: sectioned with overlines, single active style, user footer.
- [ ] Mock data is realistic, domain-correct, locale-correct, and internally
      consistent.
- [ ] Empty, loading (skeleton), and hover/focus states exist.
- [ ] Contrast passes AA; nothing is encoded by color alone; reduced motion respected.
- [ ] The signature element is present, singular, and justified by the domain.
- [ ] 8-second test passes: purpose and top number are instantly legible.
- [ ] Nothing on screen could be mistaken for a template — if a section looks like the
      generic answer, it was redesigned before shipping.
