import { errorMessage } from "./ha-api-transport.js";
import { GalleryApi } from "./gallery-api.js";
import type { MakerWorldDetail, MakerWorldInstance } from "./makerworld-api.js";
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

function imageList(detail: MakerWorldDetail, selected: MakerWorldInstance | null): string[] {
  const values = [
    selected?.thumbnail_url || "",
    ...(selected?.images || []),
    detail.thumbnail_url || "",
    ...detail.images,
  ].filter(Boolean);
  return [...new Set(values)];
}

function galleryAlreadyContains(error: unknown): boolean {
  const message = errorMessage(error, "").toLocaleLowerCase("de-DE");
  return message.includes("already exists")
    || message.includes("bereits vorhanden")
    || message.includes("existiert bereits");
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
  const dialog = overlay.querySelector<HTMLElement>(".mw-dialog")!;

  dialog.innerHTML = `<style>
    *{box-sizing:border-box}.mw-shell{display:grid;grid-template-rows:auto minmax(0,1fr);height:min(860px,calc(100vh - 36px));background:#202020}.mw-top{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid #353535}.mw-avatar{width:44px;height:44px;display:grid;place-items:center;border-radius:50%;background:#ebebeb;color:#111;font-weight:900}.mw-title{min-width:0}.mw-title h2{margin:0;font-size:20px}.mw-creator{display:flex;align-items:center;gap:7px;margin-top:3px;color:#d1d1d1}.mw-verified{display:inline-grid;place-items:center;width:16px;height:16px;border-radius:50%;background:#00c853;color:#071}.mw-close{margin-left:auto;width:38px;height:38px;border:1px solid #494949;border-radius:50%;background:#2a2a2a;color:#fff;font-size:22px;cursor:pointer}.mw-content{display:grid;grid-template-columns:minmax(0,1fr) minmax(470px,.98fr);min-height:0}.mw-left{display:grid;grid-template-rows:minmax(0,1fr) auto;gap:12px;min-width:0;min-height:0;padding:18px;border-right:1px solid #3a3a3a}.mw-hero{display:grid;place-items:center;min-height:0;overflow:hidden;border-radius:8px;background:#171717}.mw-hero img{display:block;width:100%;height:100%;object-fit:contain}.mw-hero-empty{color:#777}.mw-thumbs{display:grid;grid-auto-flow:column;grid-auto-columns:132px;gap:12px;overflow-x:auto;padding-bottom:2px}.mw-thumb{height:92px;padding:0;overflow:hidden;border:2px solid transparent;border-radius:7px;background:#2b2b2b;cursor:pointer}.mw-thumb.active{border-color:#00d618}.mw-thumb img{width:100%;height:100%;object-fit:cover}.mw-right{display:grid;grid-template-rows:auto minmax(0,1fr) auto;min-width:0;min-height:0}.mw-profile-head{padding:16px 16px 12px;border-bottom:1px solid #373737}.mw-profile-head h3{margin:0 0 12px;font-size:15px}.mw-filters{display:flex;gap:8px;overflow-x:auto}.mw-filter{min-width:max-content;padding:7px 12px;border:1px solid #444;border-radius:6px;background:#303030;color:#c9c9c9;cursor:pointer;font-weight:700}.mw-filter.active{background:#555;color:#fff}.mw-profiles{display:grid;align-content:start;gap:10px;overflow:auto;padding:14px 16px}.mw-profile{display:grid;grid-template-columns:96px minmax(0,1fr);gap:12px;min-height:86px;padding:7px;border:1px solid transparent;border-radius:8px;background:#2b2b2b;cursor:pointer}.mw-profile:hover{background:#313131}.mw-profile.active{border-color:#00d318;background:#303830}.mw-profile-image{overflow:hidden;border-radius:5px;background:#171717}.mw-profile-image img{width:100%;height:100%;object-fit:cover}.mw-profile-copy{display:grid;align-content:center;gap:7px;min-width:0}.mw-profile-copy strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px}.mw-profile-meta{display:flex;align-items:center;gap:12px;flex-wrap:wrap;color:#ddd;font-size:12px}.mw-badge{padding:2px 6px;border-radius:3px;background:#075f0c;color:#19ef2b}.mw-target{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end;padding:12px 16px;border-top:1px solid #383838;background:#242424}.mw-field{display:grid;gap:5px}.mw-field span{color:#aaa;font-size:11px}.mw-field select,.mw-field input{width:100%;min-height:42px;padding:9px 10px;border:1px solid #494949;border-radius:7px;background:#171717;color:#fff}.mw-actions{display:flex;gap:8px;flex-wrap:wrap}.mw-button{min-height:44px;padding:10px 14px;border:1px solid #4d4d4d;border-radius:7px;background:#303030;color:#fff;cursor:pointer;font-weight:700}.mw-primary{min-width:250px;border-color:#00d20f;background:#00c90e;color:#071b08;font-size:15px}.mw-primary:hover{background:#12e120}.mw-secondary-row{display:flex;gap:8px;margin-top:8px}.mw-error{margin:10px 16px;padding:10px;border:1px solid #7a3f49;border-radius:7px;background:#431d24;color:#ffd5da}.mw-result{margin-top:8px;color:#9deaa7}.mw-hint{margin-top:6px;color:#8f8f8f;font-size:11px}
    @media(max-width:900px){.mw-shell{height:auto;max-height:calc(100vh - 24px);overflow:auto}.mw-content{grid-template-columns:1fr}.mw-left{min-height:420px;border-right:0;border-bottom:1px solid #3a3a3a}.mw-right{min-height:620px}.mw-target{grid-template-columns:1fr}.mw-actions{display:grid;grid-template-columns:1fr}.mw-primary{min-width:0}.mw-secondary-row{display:grid;grid-template-columns:1fr 1fr}.mw-thumbs{grid-auto-columns:104px}.mw-thumb{height:72px}}
  </style>
  <section class="mw-shell">
    <header class="mw-top">
      <div class="mw-avatar">${esc((detail.creator || "M").slice(0,1).toUpperCase())}</div>
      <div class="mw-title"><h2>${esc(detail.title)}</h2><div class="mw-creator">${esc(detail.creator || "MakerWorld")} <span class="mw-verified">✓</span></div></div>
      <button class="mw-close" type="button">×</button>
    </header>
    <div class="mw-content">
      <section class="mw-left">
        <div class="mw-hero">${selectedImage ? `<img src="${esc(selectedImage)}" alt="${esc(detail.title)}">` : '<div class="mw-hero-empty">Keine Vorschau verfügbar</div>'}</div>
        <div class="mw-thumbs">${images.map((image) => `<button class="mw-thumb ${image === selectedImage ? "active" : ""}" type="button" data-image="${esc(image)}"><img src="${esc(image)}" alt="Vorschau"></button>`).join("")}</div>
      </section>
      <section class="mw-right">
        <div class="mw-profile-head"><h3>Print Profile (${detail.instance_count})</h3><div class="mw-filters"><button class="mw-filter ${selectedPrinter === "ALL" ? "active" : ""}" data-printer="ALL" type="button">All</button>${printers.map((printer) => `<button class="mw-filter ${selectedPrinter === printer ? "active" : ""}" data-printer="${esc(printer)}" type="button">${esc(printer)}</button>`).join("")}</div></div>
        <div class="mw-profiles">${visibleInstances.map((item) => `<article class="mw-profile ${item.id === selected?.id ? "active" : ""}" data-profile="${esc(item.id)}"><div class="mw-profile-image">${item.thumbnail_url ? `<img src="${esc(item.thumbnail_url)}" alt="${esc(item.title)}">` : ""}</div><div class="mw-profile-copy"><strong>${esc(item.title)}</strong><div class="mw-profile-meta"><span class="mw-badge">Designer</span><span>◷ ${esc(profileDuration(item))}</span><span>▣ ${item.plate_count} plates</span><span>⚖ ${esc(profileWeight(item))}</span><span>${esc(item.printer_model || item.profile_name || "")}</span></div></div></article>`).join("") || '<div class="mw-hint">Für diesen Drucker sind keine MakerWorld-Druckprofile vorhanden.</div>'}</div>
        <div class="mw-target">
          <div><label class="mw-field"><span>Ziel-Drucker</span><select id="target-printer">${optionRows(catalog.groups.printer, catalog.selection.printer_profile_id)}</select></label><div class="mw-hint">Nur der Ziel-Drucker wird ersetzt. Alle übrigen MakerWorld-Slicerwerte bleiben erhalten.</div></div>
          <div class="mw-actions"><button class="mw-button mw-primary" data-action="studio" type="button">Im Studio öffnen</button><div class="mw-secondary-row"><button class="mw-button" data-action="save" type="button">Galerie</button><button class="mw-button" data-action="download" type="button">3MF</button></div></div>
          <div id="result" class="mw-result"></div>
        </div>
      </section>
    </div>
  </section>`;

  dialog.querySelector<HTMLButtonElement>(".mw-close")?.addEventListener("click", () => overlay.remove());
  dialog.querySelectorAll<HTMLButtonElement>("[data-printer]").forEach((button) => button.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, "", button.dataset.printer || "ALL", selectedImage)));
  dialog.querySelectorAll<HTMLElement>("[data-profile]").forEach((node) => node.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, node.dataset.profile || "", selectedPrinter, "")));
  dialog.querySelectorAll<HTMLButtonElement>("[data-image]").forEach((button) => button.addEventListener("click", () => render(host, overlay, detail, api, folders, catalog, onTag, selected?.id || "", selectedPrinter, button.dataset.image || "")));
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
    show(dialog, new Error("Bitte einen Ziel-Drucker auswählen."));
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