import {
  DEFAULT_SLICE_PROCESS_OVERRIDES,
  loadSliceProcessOverrides,
  saveSliceProcessOverrides,
  type SliceProcessOverrides,
  type SupportMode,
} from "./plate-slice-api.js";

export class Ultimate3DSlicerProcessOptions extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #value: SliceProcessOverrides = loadSliceProcessOverrides();

  connectedCallback(): void {
    this.#render();
  }

  get value(): SliceProcessOverrides {
    return this.#value;
  }

  #read(): SliceProcessOverrides {
    const brimEnabled = this.#root.querySelector<HTMLInputElement>("#brim-enabled");
    const raftEnabled = this.#root.querySelector<HTMLInputElement>("#raft-enabled");
    const brim = this.#root.querySelector<HTMLInputElement>("#brim");
    const raft = this.#root.querySelector<HTMLInputElement>("#raft");
    const support = this.#root.querySelector<HTMLSelectElement>("#support");
    const plateOnly = this.#root.querySelector<HTMLInputElement>("#plate-only");
    const angle = this.#root.querySelector<HTMLInputElement>("#angle");

    const adhesionMode = raftEnabled?.checked
      ? "raft"
      : brimEnabled?.checked
        ? "brim"
        : "none";

    return {
      ...this.#value,
      adhesion_mode: adhesionMode,
      brim_width_mm: Math.max(1, Math.min(30, Number(brim?.value) || 5)),
      raft_layers: Math.max(1, Math.min(10, Math.round(Number(raft?.value) || 2))),
      support_mode: (support?.value || "off") as SupportMode,
      support_build_plate_only: plateOnly?.checked !== false,
      support_threshold_angle: Math.max(0, Math.min(89, Math.round(Number(angle?.value) || 30))),
    };
  }

  #save(): void {
    this.#value = this.#read();
    saveSliceProcessOverrides(this.#value);
    this.#updateVisibility();
    this.#updateSummary();
    this.dispatchEvent(new CustomEvent("v6-slicer-process-options-changed", {
      bubbles: true,
      composed: true,
      detail: this.#value,
    }));
  }

  #selectAdhesion(mode: "none" | "brim" | "raft"): void {
    const brimEnabled = this.#root.querySelector<HTMLInputElement>("#brim-enabled");
    const raftEnabled = this.#root.querySelector<HTMLInputElement>("#raft-enabled");
    if (brimEnabled) brimEnabled.checked = mode === "brim";
    if (raftEnabled) raftEnabled.checked = mode === "raft";
    this.#save();
  }

  #reset(): void {
    this.#value = DEFAULT_SLICE_PROCESS_OVERRIDES;
    saveSliceProcessOverrides(this.#value);
    this.#render();
  }

  #updateVisibility(): void {
    const adhesion = this.#value.adhesion_mode;
    const support = this.#value.support_mode;
    const brimFields = this.#root.querySelector<HTMLElement>("#brim-fields");
    const raftFields = this.#root.querySelector<HTMLElement>("#raft-fields");
    const supportFields = this.#root.querySelector<HTMLElement>("#support-fields");
    const supportPlateField = this.#root.querySelector<HTMLElement>("#support-plate-field");
    if (brimFields) brimFields.hidden = adhesion !== "brim";
    if (raftFields) raftFields.hidden = adhesion !== "raft";
    if (supportFields) supportFields.hidden = support === "off";
    if (supportPlateField) supportPlateField.hidden = support === "off";
  }

  #updateSummary(): void {
    const node = this.#root.querySelector<HTMLElement>("#summary");
    if (!node) return;
    const adhesion = this.#value.adhesion_mode === "none"
      ? "Brim aus · Raft aus"
      : this.#value.adhesion_mode === "brim"
        ? `Brim ein · ${this.#value.brim_width_mm} mm · Raft aus`
        : `Brim aus · Raft ein · ${this.#value.raft_layers} Schichten`;
    const support = this.#value.support_mode === "off"
      ? "Support aus"
      : `${this.#value.support_mode === "tree" ? "Baum-Support" : "Normaler Support"}${this.#value.support_build_plate_only ? " · nur Druckplatte" : " · überall"} · ${this.#value.support_threshold_angle}°`;
    node.textContent = `${adhesion} · ${support}`;
  }

  #render(): void {
    const value = this.#value;
    this.#root.innerHTML = `<style>
      :host{display:block;color:#eef5ff}*{box-sizing:border-box}.panel{margin:10px 12px 0;border:1px solid #2b4158;border-radius:12px;background:#0d1824}.head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px 13px;border-bottom:1px solid #26384f}.head h2{margin:0;font-size:15px}.head button{min-height:34px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:12px}.field{display:grid;gap:5px}.field label{font-size:11px;color:#94a9be;text-transform:uppercase}.field small{color:#7e93a7}.field.inline{display:flex;align-items:center;gap:8px;padding-top:24px}.field.inline label{font-size:12px;text-transform:none;color:#d9e6f0}.adhesion-switches{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.choice{display:flex;align-items:center;gap:8px;min-height:42px;padding:8px 10px;border:1px solid #31506e;border-radius:8px;background:#132538;cursor:pointer}.choice.active{border-color:#4fd37d;background:#123321}.choice input{width:17px;height:17px;min-height:0;margin:0}.choice span{font-weight:700}.choice small{display:block;color:#8fa4b8;font-weight:400}select,input,button{min-height:38px;border:1px solid #31506e;border-radius:8px;background:#132538;color:#eef5ff;padding:7px 9px}button{cursor:pointer;font-weight:700}.summary{margin:0 12px 12px;padding:10px;border:1px solid #2a5c78;border-radius:9px;background:#10263a;color:#9ee7ff}.warning{margin:0 12px 12px;color:#f4c77e;font-size:12px}[hidden]{display:none!important}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.adhesion-switches{grid-template-columns:1fr}}@media(max-width:520px){.grid{grid-template-columns:1fr}}
    </style><section class="panel"><header class="head"><div><h2>Haftung und Stützstrukturen</h2><small>Sichtbare Auftragswerte haben Vorrang vor dem Profil.</small></div><button type="button" id="reset">Standard</button></header><div class="grid"><div class="field" style="grid-column:1/-1"><label>Druckbetthaftung</label><div class="adhesion-switches"><label class="choice ${value.adhesion_mode === "none" ? "active" : ""}"><input id="adhesion-off" type="radio" name="adhesion" ${value.adhesion_mode === "none" ? "checked" : ""}><span>Aus<small>Kein Brim und kein Raft</small></span></label><label class="choice ${value.adhesion_mode === "brim" ? "active" : ""}"><input id="brim-enabled" type="radio" name="adhesion" ${value.adhesion_mode === "brim" ? "checked" : ""}><span>Brim verwenden<small>Raft bleibt ausgeschaltet</small></span></label><label class="choice ${value.adhesion_mode === "raft" ? "active" : ""}"><input id="raft-enabled" type="radio" name="adhesion" ${value.adhesion_mode === "raft" ? "checked" : ""}><span>Raft verwenden<small>Brim bleibt ausgeschaltet</small></span></label></div></div><div class="field" id="brim-fields"><label for="brim">Brim-Breite</label><input id="brim" type="number" min="1" max="30" step="0.5" value="${value.brim_width_mm}"><small>1 bis 30 mm</small></div><div class="field" id="raft-fields"><label for="raft">Raft-Schichten</label><input id="raft" type="number" min="1" max="10" step="1" value="${value.raft_layers}"><small>1 bis 10 Schichten</small></div><div class="field"><label for="support">Stützstrukturen</label><select id="support"><option value="off">Aus</option><option value="normal">Normal automatisch</option><option value="tree">Baum automatisch</option></select></div><div class="field" id="support-fields"><label for="angle">Überhangwinkel</label><input id="angle" type="number" min="0" max="89" step="1" value="${value.support_threshold_angle}"><small>0 bis 89 Grad</small></div><div class="field inline" id="support-plate-field"><input id="plate-only" type="checkbox" ${value.support_build_plate_only ? "checked" : ""}><label for="plate-only">Nur auf Druckplatte</label></div></div><div class="summary" id="summary"></div><div class="warning">Aus bedeutet verbindlich: Brim aus, Raft aus und vorhandene Profilwerte werden überschrieben.</div></section>`;

    const support = this.#root.querySelector<HTMLSelectElement>("#support");
    if (support) support.value = value.support_mode;

    this.#root.querySelector<HTMLInputElement>("#adhesion-off")?.addEventListener("change", () => this.#selectAdhesion("none"));
    this.#root.querySelector<HTMLInputElement>("#brim-enabled")?.addEventListener("change", () => this.#selectAdhesion("brim"));
    this.#root.querySelector<HTMLInputElement>("#raft-enabled")?.addEventListener("change", () => this.#selectAdhesion("raft"));

    this.#root.querySelectorAll<HTMLInputElement | HTMLSelectElement>("#brim,#raft,#support,#angle,#plate-only").forEach((control) => {
      control.addEventListener("change", () => this.#save());
      control.addEventListener("input", () => this.#save());
    });
    this.#root.querySelector<HTMLButtonElement>("#reset")?.addEventListener("click", () => this.#reset());
    this.#updateVisibility();
    this.#updateSummary();
  }
}

if (!customElements.get("ultimate-3d-slicer-process-options")) {
  customElements.define("ultimate-3d-slicer-process-options", Ultimate3DSlicerProcessOptions);
}
