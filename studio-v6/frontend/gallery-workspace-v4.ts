import "./gallery-library-pane.js";
import "./printer-storage-workspace.js";
import "./makerworld-workspace.js";

type GalleryTab = "library" | "storage" | "makerworld";
type GalleryTarget = "studio" | "slicer";
type MakerWorldShell = HTMLElement & {
  preferredTarget?: GalleryTarget;
};

export class Ultimate3DGalleryWorkspaceV4 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #tab: GalleryTab = "library";
  #preferredTarget: GalleryTarget = "slicer";

  set selectedTab(value: GalleryTab) {
    if (!(["library", "storage", "makerworld"] as const).includes(value)) return;
    this.#tab = value;
    if (this.#root.childElementCount) {
      this.#updateTabs();
      this.#renderPane();
    }
  }

  get selectedTab(): GalleryTab {
    return this.#tab;
  }

  set preferredTarget(value: GalleryTarget) {
    if (value !== "studio" && value !== "slicer") return;
    this.#preferredTarget = value;
    const makerWorld = this.#root.querySelector<MakerWorldShell>(
      "ultimate-3d-makerworld-workspace",
    );
    if (makerWorld) makerWorld.preferredTarget = value;
  }

  get preferredTarget(): GalleryTarget {
    return this.#preferredTarget;
  }

  connectedCallback(): void {
    if (this.#root.childElementCount) return;
    this.#root.innerHTML = `<style>
      :host{display:block;min-height:650px;background:#08101a;color:#eef5ff}
      .tabs{display:flex;gap:8px;padding:10px 14px;border-bottom:1px solid #26384f;background:#0d1622;overflow:auto}
      .tabs button{min-height:38px;padding:8px 12px;border:1px solid #31506e;border-radius:8px;background:#14263a;color:#eef5ff;font-weight:700;white-space:nowrap}
      .tabs button.active{border-color:#42c8ff;background:#17638a}
      .pane{min-width:0}
    </style><nav class="tabs" aria-label="Galeriebereiche"><button data-tab="library">Galerie</button><button data-tab="storage">SD-Karte</button><button data-tab="makerworld">MakerWorld</button></nav><main class="pane" id="pane"></main>`;
    this.#root
      .querySelectorAll<HTMLButtonElement>("[data-tab]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          this.#tab = button.dataset.tab as GalleryTab;
          this.#updateTabs();
          this.#renderPane();
        });
      });
    this.#updateTabs();
    this.#renderPane();
  }

  #updateTabs(): void {
    this.#root
      .querySelectorAll<HTMLButtonElement>("[data-tab]")
      .forEach((button) => {
        const active = button.dataset.tab === this.#tab;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
      });
  }

  #renderPane(): void {
    const pane = this.#root.querySelector<HTMLElement>("#pane");
    if (!pane) return;

    if (this.#tab === "library") {
      pane.replaceChildren(
        document.createElement("ultimate-3d-gallery-library-pane"),
      );
      return;
    }

    if (this.#tab === "storage") {
      pane.replaceChildren(
        document.createElement("ultimate-3d-printer-storage-workspace"),
      );
      return;
    }

    const makerWorld = document.createElement(
      "ultimate-3d-makerworld-workspace",
    ) as MakerWorldShell;
    makerWorld.preferredTarget = this.#preferredTarget;
    pane.replaceChildren(makerWorld);
  }
}

if (!customElements.get("ultimate-3d-gallery-workspace")) {
  customElements.define(
    "ultimate-3d-gallery-workspace",
    Ultimate3DGalleryWorkspaceV4,
  );
}
