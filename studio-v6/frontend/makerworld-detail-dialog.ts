import { errorMessage } from "./ha-api-transport.js";
import { GalleryApi, type GalleryTreeItem } from "./gallery-api.js";
import {
  type MakerWorldApi,
  type MakerWorldDetail,
  type MakerWorldInstance,
  type MakerWorldPlate,
} from "./makerworld-api.js";
import { queueWorkspaceFile, type WorkspaceFileTarget } from "./workspace-file-handoff.js";

function esc(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[character] || character));
}

function safeFileName(value: string): string {
  const normalized = value.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, " ").trim();
  return `${normalized || "MakerWorld-Modell"}.3mf`;
}

function numberLabel(value: unknown): string {
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat("de-DE", { notation: numeric >= 10_000 ? "compact" : "standard" }).format(numeric)
    : "0";
}

function durationLabel(seconds: unknown): string {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "–";
  const hours = Math.floor(value / 3600);
  const minutes = Math.round((value % 3600) / 60);
  return hours ? `${hours} h ${minutes} min` : `${minutes} min`;
}

function image(url: string | null | undefined, title: string): HTMLElement {
  if (!url) {
    const fallback = document.createElement("div");
    fallback.className = "fallback";
    fallback.textContent = "◇";
    return fallback;
  }
  const element = document.createElement("img");
  element.src = url;
  element.alt = title;
  element.loading = "lazy";
  element.referrerPolicy = "no-referrer";
  element.addEventListener("error", () => element.replaceWith(image(null, title)), { once: true });
  return element;
}

function button(label: string, className = ""): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.className = className;
  return element;
}

export async function openMakerWorldDetail(
  host: HTMLElement,
  designId: string,
  api: MakerWorldApi,
  addTag: (tag: string) => void,
): Promise<void> {
  const root = host.shadowRoot;
  if (!root) throw new Error("MakerWorld-Dialog benötigt ein Shadow-Root.");
  root.querySelector(".mw-detail-overlay")?.remove();

  const overlay = document.createElement("div");
  overlay.className = "mw-detail-overlay";
  overlay.innerHTML = `<style>
    .mw-detail-overlay{position:fixed;inset:0;z-index:2147481000;display:grid;place-items:center;padding:16px;background:#000c;backdrop-filter:blur(5px);color:#eef5ff;font:13px/1.45 Inter,Segoe UI,sans-serif}.mw-detail-overlay *{box-sizing:border-box}.dialog{position:relative;width:min(1480px,calc(100vw - 32px));height:min(900px,calc(100vh - 32px));display:grid;grid-template-columns:minmax(0,1.2fr) minmax(400px,.8fr);overflow:hidden;border:1px solid #3e6b90;border-radius:15px;background:#0c1622;box-shadow:0 26px 90px #000d}.loading{grid-column:1/-1;display:grid;place-items:center;color:#9fb4c8;font-size:16px}.visual{display:grid;grid-template-columns:92px minmax(0,1fr);min-width:0;background:#050a10}.thumbs{display:grid;align-content:start;gap:7px;padding:10px;overflow:auto;border-right:1px solid #26384f}.thumb{width:72px;height:72px;padding:0;overflow:hidden;border:1px solid #304c67;border-radius:8px;background:#101b28;cursor:pointer}.thumb.active{border-color:#49c7ff;box-shadow:0 0 0 2px #49c7ff44}.thumb img{width:100%;height:100%;object-fit:cover}.stage{display:grid;place-items:center;min-width:0;min-height:0;padding:15px;overflow:hidden}.stage img{max-width:100%;max-height:100%;object-fit:contain}.fallback{font-size:64px;color:#6284a2}.side{min-width:0;overflow:auto;padding:18px;border-left:1px solid #26384f}.side h2{margin:0 42px 5px 0;font-size:24px;overflow-wrap:anywhere}.by{color:#9db2c7}.stats,.tags{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}.stat,.tag{padding:4px 8px;border:1px solid #2e4a64;border-radius:999px;color:#a9c5da;font-size:11px}.tag{cursor:pointer;background:#132335}.description{color:#a9bbcc;line-height:1.55;white-space:pre-wrap;max-height:220px;overflow:auto}.section{margin-top:16px;padding-top:14px;border-top:1px solid #26384f}.section h3{margin:0 0 9px}.instances{display:grid;gap:7px}.instance{display:grid;grid-template-columns:62px minmax(0,1fr);gap:9px;padding:8px;border:1px solid #2a3e55;border-radius:9px;background:#0a141f;color:#eef5ff;text-align:left;cursor:pointer}.instance.active{border-color:#45c5ff;background:#10283a}.instance img{width:62px;height:54px;border-radius:6px;object-fit:cover}.instance strong,.instance small{display:block}.instance small{margin-top:3px;color:#8199b0}.plates{display:grid;grid-template-columns:repeat(auto-fill,minmax(125px,1fr));gap:7px;margin-top:10px}.plate{overflow:hidden;padding:0;border:1px solid #2a3e55;border-radius:9px;background:#0a141f;color:#eef5ff;text-align:left;cursor:pointer}.plate.active{border-color:#45c5ff}.plate img{display:block;width:100%;height:86px;object-fit:cover}.plate-body{padding:7px}.plate-body strong,.plate-body small{display:block}.plate-body small{margin-top:3px;color:#8199b0}.target{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:15px}.target label{display:grid;gap:5px;color:#9eb2c6;font-size:11px}.target label:first-child{grid-column:1/-1}.target select,.target input{width:100%;padding:9px;border:1px solid #31506e;border-radius:8px;background:#09131f;color:#fff}.actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:13px}.actions button,.close{border:1px solid #315f83;border-radius:8px;padding:9px 12px;background:#15334d;color:#eef5ff;cursor:pointer;font-weight:700}.actions .wide{grid-column:1/-1}.actions .primary{border-color:#45bdf5;background:#176187}.actions button:disabled{opacity:.4;cursor:not-allowed}.close{position:absolute;right:14px;top:14px;z-index:3;width:36px;height:36px;padding:0;border-radius:50%;font-size:20px}.notice,.error{margin-top:10px;padding:10px;border:1px solid #2c684b;border-radius:8px;background:#10261b;color:#92e7b4}.error{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}@media(max-width:1000px){.dialog{grid-template-columns:1fr;height:calc(100vh - 20px);width:calc(100vw - 20px);overflow:auto}.visual{min-height:50vh}.side{border-left:0;border-top:1px solid #26384f;overflow:visible}}@media(max-width:620px){.visual{grid-template-columns:1fr}.thumbs{display:flex;overflow:auto;border-right:0;border-bottom:1px solid #26384f}.stage{min-height:320px}.target,.actions{grid-template-columns:1fr}.target label:first-child,.actions .wide{grid-column:1}}
  </style><section class="dialog"><button class="close" aria-label="Schließen">×</button><div class="loading">MakerWorld-Details und Druckprofile werden geladen …</div></section>`;
  root.append(overlay);
  const close = (): void => overlay.remove();
  overlay.querySelector<HTMLButtonElement>(".close")?.addEventListener("click", close);
  overlay.addEventListener("click", (event) => { if (event.target === overlay) close(); });

  try {
    const galleryApi = new GalleryApi();
    const [detail, library] = await Promise.all([
      api.detail(designId),
      galleryApi.list("", "", false),
    ]);
    renderDetail(host, overlay, detail, library.tree, api, addTag, close);
  } catch (error) {
    const loading = overlay.querySelector<HTMLElement>(".loading");
    if (loading) {
      loading.className = "loading error";
      loading.textContent = errorMessage(error);
    }
  }
}

function renderDetail(
  host: HTMLElement,
  overlay: HTMLElement,
  detail: MakerWorldDetail,
  folders: readonly GalleryTreeItem[],
  api: MakerWorldApi,
  addTag: (tag: string) => void,
  close: () => void,
): void {
  let selectedInstance = detail.instances.find((item) => item.is_default) ?? detail.instances[0] ?? null;
  let selectedPlate = selectedInstance?.plates[0] ?? null;
  let selectedImage = detail.images[0] || detail.thumbnail_url || "";
  let busy = false;
  let message = "";
  let failure = "";

  const dialog = overlay.querySelector<HTMLElement>(".dialog");
  if (!dialog) return;

  const transfer = async (target: WorkspaceFileTarget): Promise<void> => {
    if (!selectedInstance || busy) return;
    busy = true;
    failure = "";
    render();
    try {
      const format = target === "studio" ? "stl" : "3mf";
      const file = await api.downloadInstance(selectedInstance.id, format, `${detail.title} - ${selectedInstance.title}`);
      queueWorkspaceFile(target, file);
      close();
      host.dispatchEvent(new CustomEvent(target === "studio" ? "gallery-open-studio" : "gallery-open-slicer", {
        bubbles: true,
        composed: true,
        detail: { designId: detail.id, instanceId: selectedInstance.id, fileName: file.name },
      }));
    } catch (error) {
      failure = errorMessage(error);
      busy = false;
      render();
    }
  };

  const save = async (): Promise<void> => {
    if (!selectedInstance || busy) return;
    const folder = dialog.querySelector<HTMLSelectElement>("#mw-folder")?.value ?? "";
    const filename = dialog.querySelector<HTMLInputElement>("#mw-filename")?.value.trim() || safeFileName(detail.title);
    busy = true;
    failure = "";
    message = "";
    render();
    try {
      let result;
      try {
        result = await api.saveInstance(selectedInstance.id, folder, filename, false);
      } catch (error) {
        const text = errorMessage(error);
        if (!text.toLocaleLowerCase("de-DE").includes("exist") || !window.confirm("Im Zielordner existiert bereits eine gleichnamige Datei. Überschreiben?")) throw error;
        result = await api.saveInstance(selectedInstance.id, folder, filename, true);
      }
      message = `${result.name} wurde in der Galerie gespeichert.`;
      busy = false;
      render();
    } catch (error) {
      failure = errorMessage(error);
      busy = false;
      render();
    }
  };

  const download = async (): Promise<void> => {
    if (!selectedInstance || busy) return;
    busy = true;
    failure = "";
    render();
    try {
      const file = await api.downloadInstance(selectedInstance.id, "3mf", `${detail.title} - ${selectedInstance.title}`);
      const url = URL.createObjectURL(file);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = file.name;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      message = `${file.name} wurde bereitgestellt.`;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      busy = false;
      render();
    }
  };

  const render = (): void => {
    const images = detail.images.length ? [...detail.images] : detail.thumbnail_url ? [detail.thumbnail_url] : [];
    dialog.innerHTML = `<button class="close" aria-label="Schließen">×</button><section class="visual"><div class="thumbs" id="mw-thumbs"></div><div class="stage" id="mw-stage"></div></section><aside class="side"><h2>${esc(detail.title)}</h2><div class="by">Von ${esc(detail.creator)}</div><div class="stats"><span class="stat">♥ ${numberLabel(detail.stats.likes)}</span><span class="stat">⇩ ${numberLabel(detail.stats.downloads)}</span><span class="stat">💬 ${numberLabel(detail.stats.comments)}</span><span class="stat">Drucke ${numberLabel(detail.stats.prints)}</span></div><div class="description"></div><div class="tags" id="mw-tags"></div><section class="section"><h3>Druckprofile und Platten</h3><div class="instances" id="mw-instances"></div><div class="plates" id="mw-plates"></div></section><div class="target"><label>Zielordner<select id="mw-folder">${folders.map((folder) => `<option value="${esc(folder.path)}">${esc(folder.path || "Hauptordner")}</option>`).join("")}</select></label><label>Dateiname<input id="mw-filename" value="${esc(safeFileName(`${detail.title}${selectedInstance ? ` - ${selectedInstance.title}` : ""}`))}"></label><label>Ausgewählte Platte<input value="${esc(selectedPlate?.name || "Alle Platten des Druckprofils")}" disabled></label></div>${message ? `<div class="notice">${esc(message)}</div>` : ""}${failure ? `<div class="error">${esc(failure)}</div>` : ""}<div class="actions"><button class="primary wide" data-action="save" ${!selectedInstance || busy ? "disabled" : ""}>${busy ? "Wird verarbeitet …" : "In Galerie speichern"}</button><button data-action="studio" ${!selectedInstance || busy ? "disabled" : ""}>CAD-Studio</button><button data-action="slicer" ${!selectedInstance || busy ? "disabled" : ""}>Slicer</button><button class="wide" data-action="download" ${!selectedInstance || busy ? "disabled" : ""}>Original-3MF herunterladen</button><button class="wide" data-action="official">Auf MakerWorld öffnen ↗</button></div></aside>`;

    dialog.querySelector<HTMLButtonElement>(".close")?.addEventListener("click", close);
    const description = dialog.querySelector<HTMLElement>(".description");
    if (description) description.textContent = detail.description || "Keine Beschreibung verfügbar.";

    const thumbs = dialog.querySelector<HTMLElement>("#mw-thumbs");
    for (const url of images) {
      const element = button("", `thumb${url === selectedImage ? " active" : ""}`);
      element.append(image(url, detail.title));
      element.addEventListener("click", () => { selectedImage = url; render(); });
      thumbs?.append(element);
    }
    dialog.querySelector<HTMLElement>("#mw-stage")?.append(image(selectedImage || detail.thumbnail_url, detail.title));

    const tags = dialog.querySelector<HTMLElement>("#mw-tags");
    for (const tag of detail.tags) {
      const element = button(tag, "tag");
      element.addEventListener("click", () => { addTag(tag); close(); });
      tags?.append(element);
    }

    const instanceHost = dialog.querySelector<HTMLElement>("#mw-instances");
    for (const instance of detail.instances) {
      instanceHost?.append(instanceButton(instance, instance.id === selectedInstance?.id, () => {
        selectedInstance = instance;
        selectedPlate = instance.plates[0] ?? null;
        if (instance.images[0]) selectedImage = instance.images[0];
        render();
      }));
    }
    const plateHost = dialog.querySelector<HTMLElement>("#mw-plates");
    for (const plate of selectedInstance?.plates ?? []) {
      plateHost?.append(plateButton(plate, plate.id === selectedPlate?.id, () => {
        selectedPlate = plate;
        if (plate.thumbnail_url) selectedImage = plate.thumbnail_url;
        render();
      }));
    }

    dialog.querySelector<HTMLButtonElement>("[data-action='save']")?.addEventListener("click", () => void save());
    dialog.querySelector<HTMLButtonElement>("[data-action='studio']")?.addEventListener("click", () => void transfer("studio"));
    dialog.querySelector<HTMLButtonElement>("[data-action='slicer']")?.addEventListener("click", () => void transfer("slicer"));
    dialog.querySelector<HTMLButtonElement>("[data-action='download']")?.addEventListener("click", () => void download());
    dialog.querySelector<HTMLButtonElement>("[data-action='official']")?.addEventListener("click", () => window.open(detail.model_url, "_blank", "noopener,noreferrer"));
  };

  render();
}

function instanceButton(instance: MakerWorldInstance, active: boolean, select: () => void): HTMLButtonElement {
  const element = button("", `instance${active ? " active" : ""}`);
  element.append(image(instance.thumbnail_url, instance.title));
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = instance.title;
  const meta = document.createElement("small");
  meta.textContent = `${instance.printer_model || "Druckermodell offen"}${instance.nozzle_diameter ? ` · ${instance.nozzle_diameter} mm` : ""} · ${instance.plate_count} Platte${instance.plate_count === 1 ? "" : "n"}`;
  content.append(title, meta);
  element.append(content);
  element.addEventListener("click", select);
  return element;
}

function plateButton(plate: MakerWorldPlate, active: boolean, select: () => void): HTMLButtonElement {
  const element = button("", `plate${active ? " active" : ""}`);
  if (plate.thumbnail_url) element.append(image(plate.thumbnail_url, plate.name));
  const content = document.createElement("div");
  content.className = "plate-body";
  const title = document.createElement("strong");
  title.textContent = plate.name;
  const meta = document.createElement("small");
  meta.textContent = `${durationLabel(plate.print_time_seconds)}${plate.weight_grams ? ` · ${plate.weight_grams} g` : ""}`;
  content.append(title, meta);
  element.append(content);
  element.addEventListener("click", select);
  return element;
}