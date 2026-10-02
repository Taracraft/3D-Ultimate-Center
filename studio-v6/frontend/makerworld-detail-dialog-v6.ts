import { errorMessage } from "./ha-api-transport.js";
import { GalleryApi } from "./gallery-api.js";
import type { MakerWorldComment, MakerWorldDetail, MakerWorldInstance, MakerWorldRecommendation } from "./makerworld-api.js";
import { MakerWorldV6Adapter2 } from "./makerworld-v6-adapter2.js";
import { ProfileApi, type V6Profile, type V6ProfileCatalog } from "./profile-api.js";
import { queueWorkspaceFile, type WorkspaceFileTarget } from "./workspace-file-handoff.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function profileLabel(profile: V6Profile): string {
  const source = profile.source === "bambu_cloud"
    ? "Cloud"
    : profile.source === "builtin"
      ? "Integriert"
      : "Lokal";
  return `${profile.name} · ${source}`;
}

function optionRows(profiles: readonly V6Profile[], selectedId: string | null): string {
  return profiles.map((profile) => `<option value="${esc(profile.id)}" ${profile.id === selectedId ? "selected" : ""}>${esc(profileLabel(profile))}</option>`).join("");
}

function printerKey(value: string): string {
  const normalized = value.trim().toUpperCase();
  const match = normalized.match(/\b(P1S|P1P|X1E|X1C|X1|A1 MINI|A1|H2D|H2C|A2L)\b/);
  return match?.[1] || normalized || "OTHER";
}

function durationLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "–";
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours ? `${hours} h${minutes ? ` ${minutes} min` : ""}` : `${minutes} min`;
}

function profileDuration(instance: MakerWorldInstance): string {
  return durationLabel(instance.plates.reduce((sum, plate) => sum + Number(plate.print_time_seconds || 0), 0));
}

function profileWeight(instance: MakerWorldInstance): string {
  const weight = instance.plates.reduce((sum, plate) => sum + Number(plate.weight_grams || 0), 0);
  return weight > 0 ? `${weight.toFixed(weight >= 10 ? 0 : 1)} g` : "–";
}


function safeMediaUrl(value: string): string {
  try {
    const url = new URL(value, window.location.href);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : "";
  } catch (_error) {
    return "";
  }
}

function descriptionImageUrls(value: string): string[] {
  const urls = new Set<string>();
  const patterns = [
    /<img\b[^>]*\bsrc=["']([^"']+)["']/gi,
    /!\[[^\]]*\]\((https?:\/\/[^)\s]+)\)/gi,
    /(?:(?:https:)?\/\/[^\s"'<>)]*\.(?:png|jpe?g|webp|gif)(?:\?[^\s"'<>)]*)?)/gi,
  ];
  for (const pattern of patterns) {
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(value)) !== null) {
      const raw = (match[1] || match[0] || "").trim();
      const normalized = raw.startsWith("//") ? `https:${raw}` : raw;
      const safe = safeMediaUrl(normalized);
      if (safe) urls.add(safe);
    }
  }
  return [...urls];
}

function sanitizeDescriptionHtml(value: string): string {
  if (!value.trim()) return "Keine Beschreibung verfügbar.";
  if (!/<[a-z][\s\S]*>/i.test(value)) {
    return `<p>${esc(value).replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>")}</p>`;
  }
  const allowed = new Set(["P", "BR", "STRONG", "B", "EM", "I", "UL", "OL", "LI", "H1", "H2", "H3", "H4", "IMG", "A"]);
  const parser = new DOMParser();
  const doc = parser.parseFromString(`<div>${value}</div>`, "text/html");
  const renderNode = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return esc(node.textContent || "");
    if (!(node instanceof Element)) return "";
    const tag = node.tagName.toUpperCase();
    if (!allowed.has(tag)) return [...node.childNodes].map(renderNode).join("");
    if (tag === "BR") return "<br>";
    if (tag === "IMG") {
      const src = safeMediaUrl(node.getAttribute("src") || "");
      return src ? `<figure class="mw-desc-media"><img src="${esc(src)}" alt="${esc(node.getAttribute("alt") || "Beschreibung")}" loading="lazy"></figure>` : "";
    }
    if (tag === "A") {
      const href = safeMediaUrl(node.getAttribute("href") || "");
      const body = [...node.childNodes].map(renderNode).join("") || esc(href);
      return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${body}</a>` : body;
    }
    const lower = tag.toLowerCase();
    return `<${lower}>${[...node.childNodes].map(renderNode).join("")}</${lower}>`;
  };
  return [...(doc.body.firstElementChild?.childNodes || [])].map(renderNode).join("").trim() || "Keine Beschreibung verfügbar.";
}


function imageList(detail: MakerWorldDetail, selected: MakerWorldInstance | null): string[] {
  const values = [
    selected?.thumbnail_url || "",
    ...(selected?.images || []),
    detail.thumbnail_url || "",
    ...detail.images,
    ...descriptionImageUrls(detail.description),
    ...((detail.description_images || []) as readonly string[]),
  ].filter(Boolean);
  return [...new Set(values)];
}

function galleryAlreadyContains(error: unknown): boolean {
  const message = errorMessage(error, "").toLocaleLowerCase("de-DE");
  return message.includes("already exists")
    || message.includes("bereits vorhanden")
    || message.includes("existiert bereits");
}

type DetailTab = "description" | "reviews";

function compactNumber(value: unknown): string {
  const number = Number(value || 0);
  if (!Number.isFinite(number) || number <= 0) return "0";
  if (number >= 1_000_000) return `${(number / 1_000_000).toFixed(number >= 10_000_000 ? 0 : 1)} Mio.`;
  if (number >= 1000) return `${(number / 1000).toFixed(number >= 10_000 ? 0 : 1)} Tsd.`;
  return String(Math.round(number));
}

function shortDate(value: string): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("de-DE", { year: "numeric", month: "short", day: "2-digit" });
}

function ratingStars(value: number): string {
  const rounded = Math.max(0, Math.min(5, Math.round(Number(value || 0))));
  return `${"★".repeat(rounded)}${"☆".repeat(5 - rounded)}`;
}

function profileHeadingCount(detail: MakerWorldDetail): number {
  return detail.instance_count || detail.instances.length;
}

function statButtons(detail: MakerWorldDetail): string {
  return `<div class="mw-social">
    <button type="button" data-noop="like">♡ ${compactNumber(detail.stats.likes)}</button>
    <button type="button" data-noop="collect">Merken ${compactNumber(detail.stats.collects)}</button>
    <button type="button" data-noop="boost">Boost</button>
    <button type="button" data-noop="share">Teilen</button>
    <span>↓ ${compactNumber(detail.stats.downloads)}</span>
    <span>💬 ${compactNumber(detail.comment_count || detail.stats.comments || detail.comments.length)}</span>
    <span>🖨 ${compactNumber(detail.stats.prints)}</span>
  </div>`;
}

function descriptionPanel(detail: MakerWorldDetail): string {
  const description = sanitizeDescriptionHtml(detail.description);
  const inlineImages = [...new Set([...(detail.description_images || []), ...descriptionImageUrls(detail.description)])]
    .filter((value) => !detail.description.includes(value));
  const media = inlineImages.length
    ? `<div class="mw-description-media">${inlineImages.map((image) => `<figure><img src="${esc(image)}" alt="Beschreibung" loading="lazy"></figure>`).join("")}</div>`
    : "";
  const tags = detail.tags.map((tag) => `<button type="button" data-tag="${esc(tag)}">#${esc(tag)}</button>`).join("");
  return `<section class="mw-tab-panel"><div class="mw-description">${description}</div>${media}${tags ? `<div class="mw-tags">${tags}</div>` : ""}${detail.license ? `<div class="mw-license">Lizenz: ${esc(detail.license)}</div>` : ""}</section>`;
}

function commentHtml(comment: MakerWorldComment, depth = 0): string {
  const replies = comment.replies.slice(0, 4).map((reply) => commentHtml(reply, depth + 1)).join("");
  const remaining = Math.max(0, Number(comment.reply_count || 0) - comment.replies.length);
  return `<article class="mw-comment ${depth ? "reply" : ""}">
    <div class="mw-comment-avatar">${comment.avatar_url ? `<img src="${esc(comment.avatar_url)}" alt="">` : esc((comment.author || "M").slice(0, 1).toUpperCase())}</div>
    <div class="mw-comment-body">
      <div class="mw-comment-head"><strong>${esc(comment.author || "MakerWorld")}</strong>${comment.boosted ? '<span class="mw-boosted">Boosted</span>' : ""}<span>${esc(shortDate(comment.created_at))}</span></div>
      ${comment.rating ? `<div class="mw-stars" aria-label="${comment.rating} von 5">${ratingStars(comment.rating)}</div>` : ""}
      <p>${esc(comment.content).replace(/\n/g, "<br>")}</p>
      <div class="mw-comment-actions"><button type="button" data-noop="original">${comment.original_available ? "Original anzeigen" : "Original"}</button><button type="button" data-noop="reaction">♡ ${compactNumber(comment.like_count)}</button><button type="button" data-noop="reply">Antwort</button><button type="button" data-noop="more">⋯</button></div>
      ${replies ? `<div class="mw-replies">${replies}</div>` : ""}${remaining ? `<button type="button" class="mw-more-replies" data-noop="more-replies">${remaining} weitere Antworten anzeigen</button>` : ""}
    </div>
  </article>`;
}

function reviewsPanel(detail: MakerWorldDetail): string {
  const count = detail.comment_count || detail.stats.comments || detail.comments.length;
  const comments = detail.comments.length
    ? detail.comments.map((comment) => commentHtml(comment)).join("")
    : '<div class="mw-empty">Noch keine Bewertungen vom MakerWorld-Endpunkt geladen.</div>';
  return `<section class="mw-tab-panel">
    <div class="mw-review-composer"><input type="text" placeholder="Teile deine Erfahrungen mit diesem Druckprofil"><button type="button" data-noop="photo">Foto hinzufügen</button><button type="button" data-noop="publish">Veröffentlichen</button></div>
    <div class="mw-review-filters"><span>Rezensionen & Bewertungen (${compactNumber(count)})</span><button type="button" class="active" data-noop="all">Alle</button><button type="button" data-noop="top">Beliebteste</button><button type="button" data-noop="new">Neueste zuerst</button><button type="button" data-noop="answers">Die meisten Antworten</button></div>
    <div class="mw-comments">${comments}</div>
  </section>`;
}

function recommendationsHtml(items: readonly MakerWorldRecommendation[]): string {
  if (!items.length) return '<div class="mw-empty">Noch keine MakerWorld-Empfehlungen geladen.</div>';
  return items.slice(0, 8).map((item) => `<article class="mw-recommendation" data-recommendation="${esc(item.id)}">
    <div class="mw-rec-image">${item.thumbnail_url ? `<img src="${esc(item.thumbnail_url)}" alt="${esc(item.title)}">` : ""}</div>
    <div><strong>${esc(item.title)}</strong><span>${esc(item.creator || "MakerWorld")}</span><small>↓ ${compactNumber(item.stats.downloads)} · ♡ ${compactNumber(item.stats.likes)}</small></div>
  </article>`).join("");
}

export async function openMakerWorldDetailV6(
  host: HTMLElement,
  designId: string,
  api: MakerWorldV6Adapter2,
  onTag: (tag: string) => void,
): Promise<void> {
  const root = host.shadowRoot;
  if (!root) return;
  const overlay = document.createElement("div");
  overlay.className = "mw-overlay";
  overlay.innerHTML = `<style>
    .mw-overlay{position:fixed;inset:0;z-index:2147481000;display:grid;place-items:center;padding:18px;background:#000d;color:#f5f5f5;font:13px/1.4 Inter,Segoe UI,sans-serif}
    .mw-dialog{width:min(1220px,calc(100vw - 36px));max-height:calc(100vh - 36px);overflow:hidden;border:1px solid #454545;border-radius:12px;background:#202020;box-shadow:0 30px 90px #000c}
    .mw-loading{display:grid;place-items:center;min-height:420px;color:#bdbdbd}
  </style><section class="mw-dialog"><div class="mw-loading">Lade MakerWorld-Druckprofile …</div></section>`;
  root.append(overlay);
  try {
    const [detail, library, catalog] = await Promise.all([
      api.detail(designId),
      new GalleryApi().list("", "", false),
      new ProfileApi().getCatalog(),
    ]);
    render(host, overlay, detail, api, library.tree.map((item) => item.path), catalog, onTag);
  } catch (error) {
    overlay.querySelector<HTMLElement>(".mw-dialog")!.innerHTML = `<button class="mw-close">×</button><div class="mw-error">${esc(errorMessage(error))}</div>`;
    overlay.querySelector<HTMLButtonElement>(".mw-close")?.addEventListener("click", () => overlay.remove());
  }
}

function render(
  host: HTMLElement,
  overlay: HTMLElement,
  detail: MakerWorldDetail,
  api: MakerWorldV6Adapter2,
  folders: readonly string[],
  catalog: V6ProfileCatalog,
  onTag: (tag: string) => void,
  selectedId = "",
  selectedPrinter = "ALL",
  activeTab: DetailTab = "description",
  activeImage = "",
): void {
  const visibleInstances = selectedPrinter === "ALL"
    ? detail.instances
    : detail.instances.filter((item) => printerKey(item.printer_model || item.profile_name) === selectedPrinter);
  const selected = visibleInstances.find((item) => item.id === selectedId)
    || visibleInstances.find((item) => item.is_default)
    || visibleInstances[0]
    || detail.instances.find((item) => item.id === selectedId)
    || detail.instances.find((item) => item.is_default)
    || detail.instances[0]
    || null;
  const printers = [...new Set(detail.instances.map((item) => printerKey(item.printer_model || item.profile_name)).filter((value) => value && value !== "OTHER"))];
  const images = imageList(detail, selected);
  const selectedImage = images.includes(activeImage) ? activeImage : images[0] || "";
  const tabPanel = activeTab === "reviews" ? reviewsPanel(detail) : descriptionPanel(detail);
  const dialog = overlay.querySelector<HTMLElement>(".mw-dialog")!;

  dialog.innerHTML = `<style>
    *{box-sizing:border-box}.mw-shell{display:grid;grid-template-rows:auto minmax(0,1fr);height:min(900px,calc(100vh - 36px));background:#202020}.mw-top{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid #353535}.mw-avatar{width:44px;height:44px;display:grid;place-items:center;border-radius:50%;background:#ebebeb;color:#111;font-weight:900}.mw-title{min-width:0}.mw-title h2{margin:0;font-size:20px}.mw-creator{display:flex;align-items:center;gap:7px;margin-top:3px;color:#d1d1d1}.mw-verified{display:inline-grid;place-items:center;width:16px;height:16px;border-radius:50%;background:#00c853;color:#071}.mw-close{margin-left:auto;width:38px;height:38px;border:1px solid #494949;border-radius:50%;background:#2a2a2a;color:#fff;font-size:22px;cursor:pointer}.mw-content{display:grid;grid-template-columns:minmax(0,1fr) minmax(500px,.96fr);min-height:0}.mw-left{display:grid;grid-template-rows:minmax(260px,1fr) auto minmax(220px,.72fr);gap:12px;min-width:0;min-height:0;padding:18px;border-right:1px solid #3a3a3a}.mw-hero{display:grid;place-items:center;min-height:0;overflow:hidden;border-radius:8px;background:#171717}.mw-hero img{display:block;width:100%;height:100%;object-fit:contain}.mw-hero-empty{color:#777}.mw-thumbs{display:grid;grid-auto-flow:column;grid-auto-columns:132px;gap:12px;overflow-x:auto;padding-bottom:2px}.mw-thumb{height:92px;padding:0;overflow:hidden;border:2px solid transparent;border-radius:7px;background:#2b2b2b;cursor:pointer}.mw-thumb.active{border-color:#00d618}.mw-thumb img{width:100%;height:100%;object-fit:cover}.mw-info{min-height:0;overflow:auto;border-top:1px solid #343434;padding-top:10px}.mw-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}.mw-tab{padding:8px 12px;border:1px solid #444;border-radius:7px;background:#2b2b2b;color:#ddd;cursor:pointer;font-weight:800}.mw-tab.active{border-color:#00c916;color:#fff;background:#263a28}.mw-description{color:#e4e4e4}.mw-description p{margin:0 0 10px}.mw-description a{color:#9adfff}.mw-desc-media,.mw-description-media{display:grid;gap:10px;margin:10px 0}.mw-desc-media,.mw-description-media figure{margin:0}.mw-desc-media img,.mw-description-media img{display:block;max-width:100%;border-radius:7px;background:#151515}.mw-tags{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}.mw-tags button{border:1px solid #4d4d4d;border-radius:999px;background:#303030;color:#cde;padding:5px 9px;cursor:pointer}.mw-license,.mw-empty{margin-top:9px;color:#aaa}.mw-review-composer{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;margin-bottom:10px}.mw-review-composer input{min-width:0;padding:9px;border:1px solid #494949;border-radius:7px;background:#171717;color:#fff}.mw-review-composer button,.mw-review-filters button,.mw-comment-actions button,.mw-more-replies{border:1px solid #444;border-radius:6px;background:#303030;color:#eee;padding:7px 9px;cursor:pointer}.mw-review-filters{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;color:#ddd}.mw-review-filters span{font-weight:900}.mw-review-filters .active{border-color:#00cf14;background:#263a28}.mw-comments{display:grid;gap:12px}.mw-comment{display:grid;grid-template-columns:36px minmax(0,1fr);gap:10px}.mw-comment.reply{margin-top:10px}.mw-comment-avatar{width:36px;height:36px;display:grid;place-items:center;overflow:hidden;border-radius:50%;background:#444;color:#fff;font-weight:900}.mw-comment-avatar img{width:100%;height:100%;object-fit:cover}.mw-comment-body{min-width:0;padding:10px;border:1px solid #393939;border-radius:8px;background:#282828}.mw-comment-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;color:#aaa}.mw-comment-head strong{color:#fff}.mw-boosted{padding:2px 5px;border-radius:4px;background:#4a3200;color:#ffc75a;font-weight:800}.mw-stars{color:#ffd34d;margin-top:4px}.mw-comment-body p{margin:7px 0;color:#eee}.mw-comment-actions{display:flex;gap:7px;flex-wrap:wrap}.mw-replies{display:grid;gap:8px;margin-top:10px}.mw-more-replies{margin-top:8px}.mw-social{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:10px;color:#ccc}.mw-social button{border:1px solid #444;border-radius:999px;background:#303030;color:#eee;padding:6px 10px;cursor:pointer}.mw-social span{padding:6px 3px}.mw-right{display:grid;grid-template-rows:auto minmax(0,1fr) auto auto;min-width:0;min-height:0}.mw-profile-head{padding:16px 16px 12px;border-bottom:1px solid #373737}.mw-profile-head h3{margin:0 0 12px;font-size:15px}.mw-filters{display:flex;gap:8px;overflow-x:auto}.mw-filter{min-width:max-content;padding:7px 12px;border:1px solid #444;border-radius:6px;background:#303030;color:#c9c9c9;cursor:pointer;font-weight:700}.mw-filter.active{background:#555;color:#fff}.mw-profiles{display:grid;align-content:start;gap:10px;overflow:auto;padding:14px 16px}.mw-profile{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;min-height:86px;padding:7px;border:1px solid transparent;border-radius:8px;background:#2b2b2b;cursor:pointer}.mw-profile:hover{background:#313131}.mw-profile.active{border-color:#00d318;background:#303830}.mw-profile-image{overflow:hidden;border-radius:5px;background:#171717}.mw-profile-image img{width:100%;height:100%;object-fit:cover}.mw-profile-copy{display:grid;align-content:center;gap:7px;min-width:0}.mw-profile-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px}.mw-profile-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:#ddd;font-size:12px}.mw-badge{padding:2px 6px;border-radius:3px;background:#075f0c;color:#19ef2b}.mw-recommendations{border-top:1px solid #383838;padding:12px 16px;max-height:240px;overflow:auto}.mw-recommendations h3{margin:0 0 10px;font-size:14px}.mw-rec-grid{display:grid;gap:9px}.mw-recommendation{display:grid;grid-template-columns:66px minmax(0,1fr);gap:9px;align-items:center;padding:6px;border-radius:7px;background:#292929;cursor:pointer}.mw-recommendation:hover{background:#333}.mw-rec-image{height:54px;overflow:hidden;border-radius:5px;background:#171717}.mw-rec-image img{width:100%;height:100%;object-fit:cover}.mw-recommendation strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.mw-recommendation span,.mw-recommendation small{display:block;color:#bbb}.mw-target{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end;padding:12px 16px;border-top:1px solid #383838;background:#242424}.mw-field{display:grid;gap:5px}.mw-field span{color:#aaa;font-size:11px}.mw-field select,.mw-field input{width:100%;min-height:42px;padding:9px 10px;border:1px solid #494949;border-radius:7px;background:#171717;color:#fff}.mw-actions{display:flex;gap:8px;flex-wrap:wrap}.mw-button{min-height:44px;padding:10px 14px;border:1px solid #4d4d4d;border-radius:7px;background:#303030;color:#fff;cursor:pointer;font-weight:700}.mw-primary{min-width:250px;border-color:#00d20f;background:#00c90e;color:#071b08;font-size:15px}.mw-primary:hover{background:#12e120}.mw-secondary-row{display:flex;gap:8px;margin-top:8px}.mw-error{margin:10px 16px;padding:10px;border:1px solid #7a3f49;border-radius:7px;background:#431d24;color:#ffd5da}.mw-result{margin-top:8px;color:#9deaa7}.mw-hint{margin-top:6px;color:#8f8f8f;font-size:11px}
    @media(max-width:900px){.mw-shell{height:auto;max-height:calc(100vh - 24px);overflow:auto}.mw-content{grid-template-columns:1fr}.mw-left{min-height:600px;border-right:0;border-bottom:1px solid #3a3a3a}.mw-right{min-height:720px}.mw-target{grid-template-columns:1fr}.mw-actions{display:grid;grid-template-columns:1fr}.mw-primary{min-width:0}.mw-secondary-row{display:grid;grid-template-columns:1fr 1fr}.mw-thumbs{grid-auto-columns:104px}.mw-thumb{height:72px}.mw-review-composer{grid-template-columns:1fr}}
  </style>
  <section class="mw-shell">
    <header class="mw-top">
      <div class="mw-avatar">${esc((detail.creator || "M").slice(0,1).toUpperCase())}</div>
      <div class="mw-title"><h2>${esc(detail.title)}</h2><div class="mw-creator">${esc(detail.creator || "MakerWorld")} <span class="mw-verified">✓</span></div>${statButtons(detail)}</div>
      <button class="mw-close" type="button">×</button>
    </header>
    <div class="mw-content">
      <section class="mw-left">
        <div class="mw-hero">${selectedImage ? `<img src="${esc(selectedImage)}" alt="${esc(detail.title)}">` : '<div class="mw-hero-empty">Keine Vorschau verfügbar</div>'}</div>
        <div class="mw-thumbs">${images.map((image) => `<button class="mw-thumb ${image === selectedImage ? "active" : ""}" type="button" data-image="${esc(image)}"><img src="${esc(image)}" alt="Vorschau"></button>`).join("")}</div>
        <div class="mw-info"><div class="mw-tabs"><button class="mw-tab ${activeTab === "description" ? "active" : ""}" type="button" data-tab="description">Beschreibung</button><button class="mw-tab ${activeTab === "reviews" ? "active" : ""}" type="button" data-tab="reviews">Rezensionen & Bewertungen (${compactNumber(detail.comment_count || detail.stats.comments || detail.comments.length)})</button></div>${tabPanel}</div>
      </section>
      <section class="mw-right">
        <div class="mw-profile-head"><h3>Druckdateien (${profileHeadingCount(detail)})</h3><div class="mw-filters"><button class="mw-filter ${selectedPrinter === "ALL" ? "active" : ""}" data-printer="ALL" type="button">Alle</button>${printers.map((printer) => `<button class="mw-filter ${selectedPrinter === printer ? "active" : ""}" data-printer="${esc(printer)}" type="button">${esc(printer)}</button>`).join("")}</div></div>
        <div class="mw-profiles">${visibleInstances.map((item) => `<article class="mw-profile ${item.id === selected?.id ? "active" : ""}" data-profile="${esc(item.id)}"><div class="mw-profile-image">${item.thumbnail_url ? `<img src="${esc(item.thumbnail_url)}" alt="${esc(item.title)}">` : ""}</div><div class="mw-profile-copy"><strong>${esc(item.title)}</strong><div class="mw-profile-meta"><span class="mw-badge">Designer</span><span>◷ ${esc(profileDuration(item))}</span><span>▣ ${item.plate_count} Platten</span><span>⚖ ${esc(profileWeight(item))}</span><span>${esc(item.printer_model || item.profile_name || "")}</span></div></div></article>`).join("") || '<div class="mw-hint">Für diesen Drucker sind keine MakerWorld-Druckprofile vorhanden.</div>'}</div>
        <div class="mw-recommendations"><h3>Ideen für Sie</h3><div class="mw-rec-grid">${recommendationsHtml(detail.recommendations)}</div></div>
        <div class="mw-target">
          <div><label class="mw-field"><span>Ziel-Druckerprofil</span><select id="target-printer">${optionRows(catalog.groups.printer, catalog.selection.printer_profile_id)}</select></label><div class="mw-hint">Nur der Ziel-Drucker wird ersetzt. Alle übrigen MakerWorld-Slicerwerte bleiben erhalten.</div></div>
          <div class="mw-actions"><button class="mw-button mw-primary" data-action="studio" type="button">Im Studio öffnen</button><div class="mw-secondary-row"><button class="mw-button" data-action="save" type="button">Galerie</button><button class="mw-button" data-action="download" type="button">3MF</button></div></div>
          <div id="result" class="mw-result"></div>
        </div>
      </section>
    </div>
  </section>`;

  dialog.querySelector<HTMLButtonElement>(".mw-close")?.addEventListener("click", () => overlay.remove());
  dialog.querySelectorAll<HTMLButtonElement>("[data-printer]").forEach((button) => button.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, "", button.dataset.printer || "ALL", activeTab, selectedImage)));
  dialog.querySelectorAll<HTMLElement>("[data-profile]").forEach((node) => node.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, node.dataset.profile || "", selectedPrinter, activeTab, "")));
  dialog.querySelectorAll<HTMLButtonElement>("[data-image]").forEach((button) => button.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, selected?.id || "", selectedPrinter, activeTab, button.dataset.image || "")));
  dialog.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => button.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, selected?.id || "", selectedPrinter, (button.dataset.tab as DetailTab) || "description", selectedImage)));
  dialog.querySelectorAll<HTMLButtonElement>("[data-tag]").forEach((button) => button.addEventListener("click", () => { onTag(button.dataset.tag || ""); overlay.remove(); }));
  dialog.querySelectorAll<HTMLElement>("[data-recommendation]").forEach((node) => node.addEventListener("click", () => {
    const nextId = node.dataset.recommendation || "";
    if (nextId) {
      overlay.remove();
      void openMakerWorldDetailV6(host, nextId, api, onTag);
    }
  }));
  dialog.querySelectorAll<HTMLButtonElement>("[data-noop]").forEach((button) => button.addEventListener("click", () => {
    const result = dialog.querySelector<HTMLElement>("#result");
    if (result) result.textContent = "Diese MakerWorld-Aktion ist sichtbar vorbereitet; Schreibaktionen werden erst verbunden, wenn die offizielle Aktion im Backend verfügbar ist.";
  }));
  dialog.querySelector<HTMLButtonElement>('[data-action="studio"]')?.addEventListener("click", () => void transfer(host, overlay, detail, selected, api, "studio", folders));
  dialog.querySelector<HTMLButtonElement>('[data-action="save"]')?.addEventListener("click", () => void save(dialog, selected, api, folders));
  dialog.querySelector<HTMLButtonElement>('[data-action="download"]')?.addEventListener("click", () => void download(detail, selected, api, dialog));
}

async function transfer(
  host: HTMLElement,
  overlay: HTMLElement,
  detail: MakerWorldDetail,
  instance: MakerWorldInstance | null,
  api: MakerWorldV6Adapter2,
  target: WorkspaceFileTarget,
  folders: readonly string[],
): Promise<void> {
  if (!instance) return;
  const dialog = dialogOf(overlay);
  const printerProfileId = dialog.querySelector<HTMLSelectElement>("#target-printer")?.value.trim() || "";
  if (!printerProfileId) {
    show(dialog, new Error("Bitte ein Ziel-Druckerprofil auswählen."));
    return;
  }
  try {
    await new ProfileApi().saveSelection({ printer_profile_id: printerProfileId });
    if (target === "studio") {
      try {
        await api.save(instance, folders[0] || "", `${instance.title}.3mf`, false);
      } catch (error) {
        if (!galleryAlreadyContains(error)) throw error;
      }
    }
    const file = await api.download(instance, target === "studio" ? "stl" : "3mf", `${detail.title} - ${instance.title}`);
    queueWorkspaceFile(target, file);
    overlay.remove();
    host.dispatchEvent(new CustomEvent(target === "studio" ? "gallery-open-studio" : "gallery-open-slicer", { bubbles: true, composed: true }));
  } catch (error) {
    show(dialog, error);
  }
}

async function save(dialog: HTMLElement, instance: MakerWorldInstance | null, api: MakerWorldV6Adapter2, folders: readonly string[]): Promise<void> {
  if (!instance) return;
  try {
    const folder = folders[0] || "";
    const saved = await api.save(instance, folder, `${instance.title}.3mf`, false);
    const result = dialog.querySelector<HTMLElement>("#result");
    if (result) result.textContent = `${saved.name} wurde gespeichert.`;
  } catch (error) { show(dialog, error); }
}

async function download(detail: MakerWorldDetail, instance: MakerWorldInstance | null, api: MakerWorldV6Adapter2, dialog: HTMLElement): Promise<void> {
  if (!instance) return;
  try {
    const file = await api.download(instance, "3mf", `${detail.title} - ${instance.title}`);
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file.name;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) { show(dialog, error); }
}

function dialogOf(overlay: HTMLElement): HTMLElement {
  return overlay.querySelector<HTMLElement>(".mw-dialog") || overlay;
}

function show(host: HTMLElement, error: unknown): void {
  const existing = host.querySelector<HTMLElement>(".mw-error");
  if (existing) existing.remove();
  const message = document.createElement("div");
  message.className = "mw-error";
  message.textContent = errorMessage(error);
  host.append(message);
}
