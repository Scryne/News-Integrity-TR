/**
 * The evidence panel: an open Shadow DOM docked to the right edge (DESIGN.md).
 *
 * All CSS lives inside the shadow root — X's styles cannot leak in, ours cannot
 * leak out. Text from the page (post text, handles) is only ever set through
 * `textContent`, never parsed as HTML. The panel hides itself while the service
 * worker takes the screenshot, so it never appears in the evidence.
 */

import type {
  CaptureResponse,
  EdgeResponse,
  Failure,
  HealthResponse,
  Request,
  Taxonomy,
  TaxonomyResponse,
} from "../shared/messages";
import { STYLES } from "./overlay-styles";
import { buildCaptureMeta, buildEdgeBody } from "./meta";
import type { EdgeCandidate, Extraction } from "./x-dom";

type Child = Node | string | null | undefined | false;

function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Record<string, string | boolean | ((event: Event) => void)> = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (typeof value === "function") el.addEventListener(key.slice(2).toLowerCase(), value);
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false) el.setAttribute(key, value);
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    el.append(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return el;
}

function send<T>(message: Request): Promise<T> {
  return chrome.runtime.sendMessage(message) as Promise<T>;
}

const EDGE_LABEL: Record<string, string> = {
  quote: "Alıntı",
  reply: "Yanıt",
  retweet: "Yeniden paylaşım",
  mention: "Anma",
};

const BACKEND_HINT = "Backend klasöründe `python -m app.main` ile başlatın, sonra yeniden deneyin.";

export interface CaptureHooks {
  /** Hide decorations and scroll the post into view; returns its fresh rect. */
  prepare(): Promise<{ rect: { x: number; y: number; w: number; h: number }; dpr: number }>;
  restore(): void;
}

class Panel {
  private host: HTMLElement;
  private root: ShadowRoot;
  private body!: HTMLElement;
  private footer!: HTMLElement;
  private previousFocus: Element | null = null;

  constructor() {
    this.host = document.createElement("nit-panel");
    this.host.style.all = "initial";
    this.root = this.host.attachShadow({ mode: "open" });
    this.root.addEventListener("keydown", (event) => this.onKey(event as KeyboardEvent));
  }

  open(title: string, subtitle: string): void {
    this.previousFocus = document.activeElement;
    this.root.replaceChildren(
      h("style", {}, STYLES),
      h(
        "section",
        { class: "panel", role: "dialog", "aria-modal": "true", "aria-labelledby": "nit-title" },
        h(
          "header",
          { class: "head" },
          h("div", {}, h("h2", { id: "nit-title" }, title), h("p", { class: "sub" }, subtitle)),
          h("button", { class: "icon", type: "button", "aria-label": "Paneli kapat", onclick: () => this.close() }, "✕"),
        ),
        (this.body = h("div", { class: "body" })),
        (this.footer = h("footer", { class: "foot" })),
      ),
    );
    if (!this.host.isConnected) document.documentElement.append(this.host);
    this.host.hidden = false;
    this.focusFirst();
  }

  close(): void {
    this.host.remove();
    if (this.previousFocus instanceof HTMLElement) this.previousFocus.focus({ preventScroll: true });
  }

  setHidden(hidden: boolean): void {
    this.host.style.visibility = hidden ? "hidden" : "visible";
  }

  content(...children: Child[]): void {
    this.body.replaceChildren(...(children.filter(Boolean) as (Node | string)[]));
  }

  actions(...children: Child[]): void {
    this.footer.replaceChildren(...(children.filter(Boolean) as (Node | string)[]));
  }

  focusFirst(): void {
    const target = this.root.querySelector<HTMLElement>("[data-autofocus], input, select, textarea, button");
    target?.focus({ preventScroll: true });
  }

  private onKey(event: KeyboardEvent): void {
    if (event.key === "Escape") {
      event.stopPropagation();
      this.close();
      return;
    }
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      this.root.querySelector<HTMLButtonElement>("button.primary:not([disabled])")?.click();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      this.root.querySelectorAll<HTMLElement>("button:not([disabled]), input, select, textarea, [tabindex='0']"),
    );
    if (focusable.length === 0) return;
    const first = focusable[0]!;
    const last = focusable[focusable.length - 1]!;
    const active = this.root.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
    // Keep X's own keyboard shortcuts (j/k/l…) from firing while typing here.
    event.stopPropagation();
  }
}

let panel: Panel | null = null;
function getPanel(): Panel {
  panel ??= new Panel();
  return panel;
}

function shortTime(iso: string | null): string {
  if (!iso) return "zaman okunamadı";
  try {
    return new Date(iso).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function summary(extraction: Extraction): HTMLElement {
  const permalink = extraction.permalink;
  const text = extraction.text ?? "(metin yok ya da yalnız medya)";
  return h(
    "div",
    { class: "summary" },
    h(
      "div",
      { class: "row" },
      h("span", { class: "handle" }, permalink ? `@${permalink.handle}` : "@?"),
      h("span", { class: "muted" }, shortTime(permalink?.postedAt ?? null)),
    ),
    h("p", { class: "text" }, text.length > 220 ? `${text.slice(0, 220)}…` : text),
    permalink ? h("p", { class: "mono muted" }, `gönderi ${permalink.postId}`) : null,
  );
}

function identityBlock(extraction: Extraction, manual: HTMLInputElement): HTMLElement {
  if (extraction.restId) {
    const via = extraction.restId.method === "dom-anchor" ? "takip düğmesinden" : extraction.restId.method === "profile-header" ? "profil başlığından" : "açık kartından";
    return h(
      "div",
      { class: "identity ok" },
      h("span", { class: "dot", "aria-hidden": "true" }),
      h("span", {}, "Kimlik doğrulandı ", h("span", { class: "muted" }, `(${via})`)),
      h("span", { class: "mono" }, extraction.restId.value),
    );
  }
  return h(
    "div",
    { class: "identity warn" },
    h("p", {}, h("strong", {}, "Yazarın kimliği bu satırdan okunamadı. "),
      "Takip ettiğiniz hesaplarda ve zaman akışında X kimliği göstermez. Yazarın profiline gidip oradan yakalayın ya da kimliği girin."),
    h("label", { for: "nit-restid" }, "Yazarın sayısal kimliği (rest_id)"),
    manual,
  );
}

function failureView(failure: Failure, retry: () => void): HTMLElement {
  const title =
    failure.kind === "backend_down" ? "Yerel backend çalışmıyor" :
    failure.kind === "rejected" ? "Kayıt reddedildi" :
    failure.kind === "capture_blocked" ? "Ekran görüntüsü alınamadı" : "Backend bir hata döndürdü";
  const hint = failure.kind === "backend_down" ? BACKEND_HINT :
    failure.kind === "rejected" ? "Girdiğiniz bilgiler korunuyor; düzeltip yeniden deneyin." :
    "Girdiğiniz bilgiler korunuyor; yeniden deneyebilirsiniz.";
  return h(
    "div",
    { class: "notice danger", role: "alert" },
    h("strong", {}, title),
    h("p", {}, failure.error),
    h("p", { class: "muted" }, hint),
    h("button", { class: "ghost", type: "button", onclick: retry }, "Yeniden dene"),
  );
}

function chips(taxonomy: Taxonomy, selected: Set<string>): HTMLElement {
  const groups = Object.entries(taxonomy.groups);
  return h(
    "div",
    { class: "groups" },
    ...groups.map(([prefix, label]) =>
      h(
        "fieldset",
        { class: "group" },
        h("legend", {}, h("span", { class: "mono" }, prefix), ` ${label}`),
        h(
          "div",
          { class: "chips" },
          ...taxonomy.codes
            .filter((c) => c.group_prefix === prefix)
            .map((code) => {
              const input = h("input", { type: "checkbox", value: code.code, id: `nit-code-${code.code}` });
              input.checked = selected.has(code.code);
              input.addEventListener("change", () => {
                if (input.checked) selected.add(code.code);
                else selected.delete(code.code);
              });
              const tip = [code.description, code.international_equivalent && `EN: ${code.international_equivalent}`]
                .filter(Boolean)
                .join("\n");
              return h(
                "label",
                { class: "chip", for: `nit-code-${code.code}`, title: tip },
                input,
                h("span", { class: "code mono" }, code.code),
                h("span", { class: "label" }, code.label),
              );
            }),
        ),
      ),
    ),
  );
}

function stamp(result: Extract<CaptureResponse, { ok: true }>): HTMLElement {
  return h(
    "div",
    { class: "stamp", role: "status" },
    h("p", { class: "stamp-title" }, result.merged ? "Bekleyen kayıt tamamlandı" : "Kanıt kaydedildi"),
    h("p", { class: "mono" }, result.canonical_name.replace(/\.png$/, "")),
    h("p", { class: "mono muted" }, `sha256 ${result.screenshot_sha256.slice(0, 12)}…`),
    result.crop_failed
      ? h("p", { class: "muted" }, "Kırpma yapılamadı; görünür alanın tamamı birincil görüntü olarak saklandı.")
      : result.clamped
        ? h("p", { class: "muted" }, "Gönderinin bir kısmı ekran dışındaydı; görünen bölüm kırpıldı, tam ekran da saklandı.")
        : null,
    h("p", { class: "muted" }, "Arşiv işleri kuyruğa alındı."),
  );
}

async function loadTaxonomy(p: Panel, onReady: (taxonomy: Taxonomy) => void): Promise<void> {
  p.content(h("div", { class: "skeleton", "aria-busy": "true" }, "Kod listesi yükleniyor…"));
  p.actions();
  let response: TaxonomyResponse;
  try {
    response = await send<TaxonomyResponse>({ type: "TAXONOMY_GET" });
  } catch (error) {
    response = { ok: false, kind: "server_error", error: String(error) };
  }
  if (!response.ok) {
    p.content(failureView(response, () => void loadTaxonomy(p, onReady)));
    return;
  }
  onReady(response.taxonomy);
}

export function openCaptureOverlay(extraction: Extraction, hooks: CaptureHooks): void {
  const p = getPanel();
  p.open("Kanıt yakala", "Kodları seçin; kaydettiğinizde ekran görüntüsü alınır.");
  // Form state lives outside render(), so a validation problem or a backend
  // outage re-renders the panel without losing anything already typed.
  const selected = new Set<string>();
  const kept = { category: "", note: "" };
  const manual = h("input", {
    id: "nit-restid", inputmode: "numeric", autocomplete: "off", spellcheck: "false",
    placeholder: "ör. 1234567890123456789",
  });
  const inlineCandidates = extraction.edges.filter((e) => e.edgeType !== "retweet");
  let inlineEdge: EdgeCandidate | null = inlineCandidates.find((e) => e.edgeType === "quote") ?? null;

  const render = (taxonomy: Taxonomy, problems: string[] = [], failure: Failure | null = null) => {
    const category = h(
      "select",
      { id: "nit-category", required: true },
      h("option", { value: "" }, "Kategori seçin"),
      ...taxonomy.categories.map((c) => h("option", { value: c.key }, c.label)),
    );
    category.value = kept.category;
    category.addEventListener("change", () => (kept.category = category.value));
    const note = h("textarea", { id: "nit-note", rows: "2", placeholder: "Bağlam, kaynak, dikkat çeken ayrıntı" });
    note.value = kept.note;
    note.addEventListener("input", () => (kept.note = note.value));

    const edgeBox = inlineCandidates.length
      ? h(
          "fieldset",
          { class: "edgebox" },
          h("legend", {}, "Etkileşimi de kaydet"),
          ...[...inlineCandidates, null].map((candidate, index) => {
            const radio = h("input", { type: "radio", name: "nit-inline-edge", id: `nit-ie-${index}` });
            radio.checked = candidate === inlineEdge;
            radio.addEventListener("change", () => (inlineEdge = candidate));
            return h(
              "label",
              { class: "radio", for: `nit-ie-${index}` },
              radio,
              candidate
                ? h("span", {}, `${EDGE_LABEL[candidate.edgeType]} → `, h("span", { class: "mono" }, `@${candidate.target.handle}`))
                : h("span", {}, "Kaydetme"),
            );
          }),
        )
      : null;

    const save = h("button", { class: "primary", type: "button" }, "Kanıtı kaydet");
    save.addEventListener("click", async () => {
      const built = buildCaptureMeta(extraction, {
        category: kept.category,
        codes: taxonomy.codes.map((c) => c.code).filter((c) => selected.has(c)),
        note: kept.note,
        manualRestId: manual.value,
        inlineEdge,
      });
      if (!built.ok) {
        render(taxonomy, built.problems);
        return;
      }
      save.disabled = true;
      save.textContent = "Kaydediliyor…";
      let response: CaptureResponse;
      try {
        const { rect, dpr } = await hooks.prepare();
        p.setHidden(true);
        // Two frames: the hidden panel and buttons are gone from the compositor
        // before the worker grabs the viewport.
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        response = await send<CaptureResponse>({ type: "CAPTURE_REQUEST", meta: built.value, rect, dpr });
      } catch (error) {
        response = { ok: false, kind: "server_error", error: String(error) };
      } finally {
        p.setHidden(false);
        hooks.restore();
      }
      if (response.ok) {
        p.content(summary(extraction), stamp(response));
        p.actions(h("button", { class: "primary", type: "button", "data-autofocus": true, onclick: () => p.close() }, "Kapat"));
        p.focusFirst();
        return;
      }
      render(taxonomy, [], response);
    });

    p.content(
      summary(extraction),
      failure ? failureView(failure, () => save.click()) : null,
      problems.length ? h("ul", { class: "notice warn", role: "alert" }, ...problems.map((x) => h("li", {}, x))) : null,
      identityBlock(extraction, manual),
      h("div", { class: "field" }, h("label", { for: "nit-category" }, "Kategori"), category),
      chips(taxonomy, selected),
      h("div", { class: "field" }, h("label", { for: "nit-note" }, "Not ", h("span", { class: "muted" }, "(isteğe bağlı)")), note),
      edgeBox,
    );
    p.actions(
      h("span", { class: "muted kbd" }, "Ctrl+Enter kaydeder · Esc kapatır"),
      h("button", { class: "ghost", type: "button", onclick: () => p.close() }, "Vazgeç"),
      save,
    );
  };

  void loadTaxonomy(p, (taxonomy) => render(taxonomy));
}

export function openEdgeOverlay(extraction: Extraction): void {
  const p = getPanel();
  p.open("Etkileşim kaydet", "Bu gönderideki etkileşimi iki hesap arasında bir kenar olarak kaydedin.");
  const author = extraction.permalink?.handle ?? extraction.visibleHandle;
  if (!extraction.permalink || !author) {
    p.content(h("div", { class: "notice warn" }, "Gönderinin bağlantısı okunamadı; gönderiyi açıp tekrar deneyin."));
    p.actions(h("button", { class: "ghost", type: "button", onclick: () => p.close() }, "Kapat"));
    return;
  }
  const candidates: EdgeCandidate[] = [...extraction.edges];
  const manualTarget = h("input", { id: "nit-mention", placeholder: "kullanici_adi", autocomplete: "off", spellcheck: "false" });
  let chosen = 0;
  const sourceId = h("input", { id: "nit-src", inputmode: "numeric", autocomplete: "off", placeholder: "rest_id" });
  const targetId = h("input", { id: "nit-tgt", inputmode: "numeric", autocomplete: "off", placeholder: "rest_id (biliniyorsa)" });
  const note = h("textarea", { id: "nit-edge-note", rows: "2", placeholder: "İsteğe bağlı not" });

  const render = (problems: string[] = [], failure: Failure | null = null) => {
    const list = h(
      "fieldset",
      { class: "edgebox" },
      h("legend", {}, candidates.length ? "Algılanan etkileşim" : "Etkileşim algılanmadı"),
      ...candidates.map((candidate, index) => {
        const radio = h("input", { type: "radio", name: "nit-edge", id: `nit-e-${index}` });
        radio.checked = index === chosen;
        radio.addEventListener("change", () => { chosen = index; render(); });
        return h(
          "label",
          { class: "radio", for: `nit-e-${index}` },
          radio,
          h("span", {}, `${EDGE_LABEL[candidate.edgeType]}: `,
            h("span", { class: "mono" }, `@${candidate.source.handle}`), " → ",
            h("span", { class: "mono" }, `@${candidate.target.handle}`)),
        );
      }),
      (() => {
        const radio = h("input", { type: "radio", name: "nit-edge", id: "nit-e-manual" });
        radio.checked = chosen === candidates.length;
        radio.addEventListener("change", () => { chosen = candidates.length; render(); });
        return h("label", { class: "radio", for: "nit-e-manual" }, radio, h("span", {}, "Anma (elle): ", h("span", { class: "mono" }, `@${author} → @`), manualTarget));
      })(),
    );
    // Read at click time: the manual mention's handle is typed after render.
    const current = (): EdgeCandidate | undefined =>
      chosen < candidates.length
        ? candidates[chosen]
        : {
            edgeType: "mention",
            source: { handle: author, restId: extraction.restId?.value ?? null },
            target: { handle: manualTarget.value.trim().replace(/^@/, ""), restId: null },
            method: "manual",
          };
    const candidate = current();
    const needSource = candidate && !candidate.source.restId;
    const needTarget = candidate && !candidate.target.restId;
    const save = h("button", { class: "primary", type: "button" }, "Kenarı kaydet");
    save.addEventListener("click", async () => {
      const candidate = current();
      if (!candidate || !/^[A-Za-z0-9_]{1,15}$/.test(candidate.target.handle)) {
        render(["Hedef hesabın kullanıcı adını girin."]);
        return;
      }
      const built = buildEdgeBody(extraction, { candidate, sourceRestId: sourceId.value, targetRestId: targetId.value, note: note.value });
      if (!built.ok) {
        render(built.problems);
        return;
      }
      save.disabled = true;
      save.textContent = "Kaydediliyor…";
      let response: EdgeResponse;
      try {
        response = await send<EdgeResponse>({ type: "EDGE_REQUEST", edge: built.value });
      } catch (error) {
        response = { ok: false, kind: "server_error", error: String(error) };
      }
      if (response.ok) {
        p.content(h("div", { class: "stamp", role: "status" },
          h("p", { class: "stamp-title" }, "Kenar kaydedildi"),
          h("p", { class: "mono" }, `kenar #${response.edge_id}`),
          h("p", { class: "muted" }, response.target_resolved ? "Hedef hesap kimliğiyle bağlandı." : "Hedef kimliği bilinmiyor; kullanıcı adıyla saklandı.")));
        p.actions(h("button", { class: "primary", type: "button", "data-autofocus": true, onclick: () => p.close() }, "Kapat"));
        p.focusFirst();
        return;
      }
      render([], response);
    });
    p.content(
      failure ? failureView(failure, () => save.click()) : null,
      problems.length ? h("ul", { class: "notice warn", role: "alert" }, ...problems.map((x) => h("li", {}, x))) : null,
      list,
      needSource ? h("div", { class: "field" }, h("label", { for: "nit-src" }, `@${candidate!.source.handle} kimliği (zorunlu)`), sourceId) : null,
      needTarget ? h("div", { class: "field" }, h("label", { for: "nit-tgt" }, "Hedef kimliği ", h("span", { class: "muted" }, "(yoksa kullanıcı adıyla saklanır)")), targetId) : null,
      h("div", { class: "field" }, h("label", { for: "nit-edge-note" }, "Not"), note),
    );
    p.actions(
      h("button", { class: "ghost", type: "button", onclick: () => p.close() }, "Vazgeç"),
      save,
    );
  };
  render();
}

export function healthCheck(): Promise<HealthResponse> {
  return send<HealthResponse>({ type: "HEALTH_CHECK" });
}

