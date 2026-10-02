import { type PaintBrush } from "./studio-mesh-paint.js";

export type StudioPaintTool = "brush" | "pen" | "eraser" | "rectangle" | "circle" | "text";
export type StudioPaintMaterial = Readonly<{ key: string; name: string; color: string }>;
export type StudioPaintSettings = Readonly<{ active: boolean; tool: StudioPaintTool; brush: PaintBrush; text: string; textSizePx: number; }>;

const PAINT_TOOL_CSS = `
:host{display:block;padding:7px;border-bottom:1px solid #24384c;background:linear-gradient(180deg,#111b26,#09131d);color:#eef6ff;font:11px/1.3 Inter,Segoe UI,sans-serif}
.paint-head{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:7px}.paint-head b{font-size:11px;color:#ffe0a0}.paint-head span{font-size:9px;color:#8ea5b8}
.toggle{width:100%;min-height:30px;margin-bottom:7px;border:1px solid #8d6423;border-radius:4px;background:linear-gradient(180deg,#573e13,#2a1d09);color:#fff1cb;font-weight:800;cursor:pointer}.toggle.active{border-color:#ffd36a;background:linear-gradient(180deg,#76551a,#49330d);box-shadow:0 0 0 1px #ffd36a44}
.tools{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.tools button{min-height:29px;padding:4px;border:1px solid #31506e;border-radius:3px;background:#102335;color:#dcefff;font-size:10px;font-weight:700;cursor:pointer}.tools button.active{border-color:#ffd36a;background:#49330d;color:#fff1cb}
.controls{display:grid;gap:6px;margin-top:7px}.controls label{display:grid;gap:3px;color:#8ea5b8;font-size:9px}.controls input[type=range],.controls select,.controls input[type=text]{width:100%;accent-color:#ffd36a}.controls input[type=text]{min-height:27px;box-sizing:border-box;border:1px solid #31506e;border-radius:3px;background:#08131e;color:#eef6ff;font-size:10px;padding:4px 6px}.controls select{min-height:27px;border:1px solid #31506e;border-radius:3px;background:#08131e;color:#eef6ff;font-size:10px}.material-row{display:grid;grid-template-columns:minmax(0,1fr) 32px;gap:6px;align-items:end}.controls input[type=color]{width:32px;height:27px;padding:2px;border:1px solid #31506e;border-radius:3px;background:#08131e}.hint{margin-top:7px;color:#8299ad;font-size:9px}.hint b{color:#ffe0a0}.warning{color:#ffd36a}
`;

function normalColor(value: string): string {
  return /^#[0-9a-f]{6}$/i.test(value) ? value : "#6b7785";
}

export class StudioPaintTools extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #active = false; #tool: StudioPaintTool = "brush"; #radiusMm = 10; #color = "#ff4444"; #materialKey = ""; #text = "Text"; #textSizePx = 28;
  #materials: StudioPaintMaterial[] = [];

  connectedCallback(): void {
    if (this.#root.childNodes.length) return;
    this.#root.innerHTML = "<style>" + PAINT_TOOL_CSS + "</style><section><div class=\"paint-head\"><b>Malwerkzeuge</b><span>Modelloberfläche</span></div><button class=\"toggle\" data-paint-toggle type=\"button\">🎨 Malen AN</button><div class=\"tools\"><button data-paint-tool=\"brush\" type=\"button\">🖌 Pinsel</button><button data-paint-tool=\"pen\" type=\"button\">✏ Stift</button><button data-paint-tool=\"eraser\" type=\"button\">⌫ Radierer</button><button data-paint-tool=\"rectangle\" type=\"button\">▭ Rechteck</button><button data-paint-tool=\"circle\" type=\"button\">◯ Kreis</button><button data-paint-tool=\"text\" type=\"button\">T Text</button></div><div class=\"controls\"><label>Größe <input data-paint-radius type=\"range\" min=\"1\" max=\"40\" step=\"1\" value=\"10\"></label><label>Text <input data-paint-text type=\"text\" maxlength=\"48\" value=\"Text\"></label><label>Schriftgröße <input data-paint-text-size type=\"range\" min=\"12\" max=\"96\" step=\"1\" value=\"28\"></label><div class=\"material-row\"><label>Druckfilament <select data-paint-material></select></label><label>Farbe <input data-paint-color type=\"color\" value=\"#ff4444\" disabled></label></div></div><div class=\"hint\"><b>Malen:</b> Drehen und Verschieben sind gesperrt. Pinsel/Stift ziehen frei; Rechteck/Kreis mit Klick-Ziehen. Text eingeben, Text wählen und auf die Modelloberfläche klicken. Farbe folgt immer dem gewählten AMS-Slot.</div></section>";
    this.#root.addEventListener("click", (event) => {
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>("[data-paint-toggle],[data-paint-tool]") : null;
      if (!target) return;
      if (target.hasAttribute("data-paint-toggle")) this.toggle();
      const next = target.dataset.paintTool as StudioPaintTool | undefined;
      if (next) { this.#tool = next; this.#active = true; this.#render(); this.#emit(); }
    });
    this.#root.querySelector<HTMLInputElement>("[data-paint-radius]")?.addEventListener("input", (event) => {
      this.#radiusMm = Number((event.currentTarget as HTMLInputElement).value) || 10; this.#emit();
    });
    this.#root.querySelector<HTMLInputElement>("[data-paint-text]")?.addEventListener("input", (event) => {
      this.#text = (event.currentTarget as HTMLInputElement).value.slice(0, 48); this.#emit();
    });
    this.#root.querySelector<HTMLInputElement>("[data-paint-text-size]")?.addEventListener("input", (event) => {
      this.#textSizePx = Math.max(12, Math.min(96, Number((event.currentTarget as HTMLInputElement).value) || 28)); this.#emit();
    });
    this.#root.querySelector<HTMLSelectElement>("[data-paint-material]")?.addEventListener("change", (event) => {
      this.#materialKey = (event.currentTarget as HTMLSelectElement).value || "";
      const material = this.#materials.find((item) => item.key === this.#materialKey);
      if (material) this.#color = normalColor(material.color);
      this.#render(); this.#emit();
    });
    this.#render();
  }

  setMaterials(materials: readonly StudioPaintMaterial[]): void {
    const unique = new Map<string, StudioPaintMaterial>();
    for (const material of materials) {
      const key = String(material.key || "").trim();
      if (key && !unique.has(key)) unique.set(key, { key, name: String(material.name || key), color: normalColor(String(material.color || "")) });
    }
    this.#materials = [...unique.values()];
    if (!this.#materials.some((item) => item.key === this.#materialKey)) {
      this.#materialKey = this.#materials[0]?.key || "";
      this.#color = this.#materials[0]?.color || "#ff4444";
    }
    this.#render(); this.#emit();
  }

  toggle(): void { this.#active = !this.#active; this.#render(); this.#emit(); }
  isActive(): boolean { return this.#active; }
  getTool(): StudioPaintTool { return this.#tool; }
  getBrush(): PaintBrush {
    const brush = {
      radiusMm: this.#tool === "pen" ? 1.5 : this.#radiusMm,
      color: this.#color,
      mode: this.#tool === "eraser" ? "remove" as const : "add" as const,
    };
    return this.#materialKey ? { ...brush, materialKey: this.#materialKey } : brush;
  }
  getText(): string { return this.#text.trim(); }
  getTextSizePx(): number { return this.#textSizePx; }
  getSettings(): StudioPaintSettings { return { active: this.#active, tool: this.#tool, brush: this.getBrush(), text: this.getText(), textSizePx: this.getTextSizePx() }; }
  #emit(): void { this.dispatchEvent(new CustomEvent<StudioPaintSettings>("studio-paint-change", { bubbles: true, composed: true, detail: this.getSettings() })); }

  #render(): void {
    const toggle = this.#root.querySelector<HTMLButtonElement>("[data-paint-toggle]");
    if (toggle) { toggle.classList.toggle("active", this.#active); toggle.textContent = this.#active ? "✋ Malen AUS" : "🎨 Malen AN"; }
    this.#root.querySelectorAll<HTMLButtonElement>("[data-paint-tool]").forEach((button) => button.classList.toggle("active", button.dataset.paintTool === this.#tool));
    const select = this.#root.querySelector<HTMLSelectElement>("[data-paint-material]");
    if (select) {
      const empty = this.#materials.length ? "" : "<option value=\"\">Kein belegter AMS-Slot</option>";
      select.innerHTML = empty + this.#materials.map((item) => "<option value=\"" + item.key.replace(/"/g, "&quot;") + "\"" + (item.key === this.#materialKey ? " selected" : "") + ">" + item.name.replace(/[<>&]/g, (character) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[character] || character)) + "</option>").join("");
      select.disabled = this.#materials.length === 0;
    }
    const text = this.#root.querySelector<HTMLInputElement>("[data-paint-text]");
    if (text && text.value !== this.#text) text.value = this.#text;
    const textSize = this.#root.querySelector<HTMLInputElement>("[data-paint-text-size]");
    if (textSize) textSize.value = String(this.#textSizePx);
    const color = this.#root.querySelector<HTMLInputElement>("[data-paint-color]");
    if (color) color.value = normalColor(this.#color);
    const hint = this.#root.querySelector<HTMLElement>(".hint");
    if (hint) hint.classList.toggle("warning", !this.#materialKey && this.#tool !== "eraser");
  }
}
if (!customElements.get("studio-paint-tools")) customElements.define("studio-paint-tools", StudioPaintTools);
