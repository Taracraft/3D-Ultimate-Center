import { callEnvelopeApi } from "./ha-api-transport.js";

type AuditEvent = Readonly<Record<string, unknown>>;
type Filter = "all" | "info" | "warning" | "error";

function escapeHtml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[character] || character));
}

function levelOf(event: AuditEvent): Filter {
  const level = String(event.level || event.severity || "info").toLowerCase();
  if (level.includes("error") || level.includes("fail")) return "error";
  if (level.includes("warn")) return "warning";
  return "info";
}

function timestampLabel(value: unknown): string {
  const date = new Date(String(value || ""));
  return Number.isNaN(date.getTime()) ? "–" : date.toLocaleString("de-DE");
}

function eventSignature(events: readonly AuditEvent[]): string {
  return events.map((event) => [
    event.id,
    event.timestamp,
    event.level,
    event.event,
    event.message,
    event.action,
    event.status,
  ].join("|")).join("\n");
}

export class Ultimate3DAuditLogPanelV2 extends HTMLElement {
  readonly #root = this.attachShadow({ mode: "open" });
  #events: readonly AuditEvent[] = [];
  #filter: Filter = "all";
  #timer: number | null = null;
  #signature = "";
  #loading = true;
  #error = "";

  connectedCallback(): void {
    if (this.#timer !== null) return;
    this.#mount();
    void this.#refresh();
    this.#timer = window.setInterval(() => void this.#refresh(), 5000);
  }

  disconnectedCallback(): void {
    if (this.#timer !== null) window.clearInterval(this.#timer);
    this.#timer = null;
  }

  async #refresh(): Promise<void> {
    try {
      const data = await callEnvelopeApi<{ items?: AuditEvent[] }>(
        "GET",
        "ultimate_3d_studio_v6/v1/audit?limit=80",
      );
      const events = Array.isArray(data?.items) ? data.items : [];
      const signature = eventSignature(events);
      this.#error = "";
      this.#loading = false;
      if (signature === this.#signature) {
        this.#updateStatus();
        return;
      }
      this.#events = events;
      this.#signature = signature;
      this.#renderRows();
      this.#updateStatus();
    } catch (error) {
      this.#loading = false;
      this.#error = error instanceof Error ? error.message : String(error);
      this.#updateStatus();
    }
  }

  #mount(): void {
    this.#root.innerHTML = `<style>
      :host{display:block;color:#eef5ff}
      *{box-sizing:border-box}
      .panel{overflow:hidden;border:1px solid #26384f;border-radius:12px;background:#101925}
      .head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 15px;border-bottom:1px solid #26384f}
      .head h2{margin:0;font-size:15px}.head small{color:#7890a8}
      .toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:10px 12px;border-bottom:1px solid #223449;background:#0c1622}
      .toolbar button{border:1px solid #31506e;border-radius:8px;padding:7px 9px;background:#14263a;color:#eef5ff;cursor:pointer;font-weight:700}.toolbar button.active{border-color:#41c5ff;background:#173b58}
      .status{margin-left:auto;color:#8298ad;font-size:11px}.status.error{color:#ffb7c0}
      .list{max-height:430px;overflow:auto;padding:10px;scrollbar-gutter:stable}
      .entry{display:grid;grid-template-columns:118px 78px minmax(0,1fr);gap:10px;padding:9px;border-bottom:1px solid #223449}
      .entry:last-child{border-bottom:0}.entry time{color:#7890a8;font-size:11px}.badge{align-self:start;padding:3px 6px;border:1px solid #31506e;border-radius:999px;text-align:center;font-size:9px;text-transform:uppercase}.badge.warning{border-color:#9c7330;color:#ffd589}.badge.error{border-color:#8f3f4b;color:#ffb9c2}.message{min-width:0;overflow-wrap:anywhere}.message strong,.message small{display:block}.message small{margin-top:3px;color:#7f95aa}.empty{padding:24px;text-align:center;color:#8298ad}
      @media(max-width:650px){.entry{grid-template-columns:1fr}.status{width:100%;margin-left:0}.list{max-height:360px}}
    </style><section class="panel"><header class="head"><h2>Audit-Log</h2><small>Live · ohne Neuaufbau</small></header><div class="toolbar"><button type="button" data-filter="all" class="active">Alle</button><button type="button" data-filter="info">Info</button><button type="button" data-filter="warning">Warnungen</button><button type="button" data-filter="error">Fehler</button><button type="button" id="refresh">Aktualisieren</button><span class="status" id="status">Wird geladen …</span></div><div class="list" id="list"><div class="empty">Audit-Log wird geladen …</div></div></section>`;

    this.#root.querySelectorAll<HTMLButtonElement>("[data-filter]").forEach((button) => {
      button.addEventListener("click", () => {
        this.#filter = button.dataset.filter as Filter;
        this.#root.querySelectorAll<HTMLButtonElement>("[data-filter]").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        this.#renderRows();
      });
    });
    this.#root.querySelector<HTMLButtonElement>("#refresh")?.addEventListener("click", () => void this.#refresh());
  }

  #renderRows(): void {
    const list = this.#root.querySelector<HTMLElement>("#list");
    if (!list) return;
    const scrollTop = list.scrollTop;
    const filtered = this.#filter === "all"
      ? this.#events
      : this.#events.filter((event) => levelOf(event) === this.#filter);
    if (!filtered.length) {
      list.innerHTML = '<div class="empty">Keine passenden Audit-Einträge vorhanden.</div>';
      list.scrollTop = 0;
      return;
    }
    list.innerHTML = filtered.map((event) => {
      const level = levelOf(event);
      const title = event.message || event.event || event.action || "V6-Ereignis";
      const detail = [event.actor, event.status, event.printer_id, event.job_id]
        .filter((value) => value !== null && value !== undefined && value !== "")
        .map((value) => String(value))
        .join(" · ");
      return `<article class="entry"><time>${escapeHtml(timestampLabel(event.timestamp || event.created_at))}</time><span class="badge ${level}">${escapeHtml(level)}</span><span class="message"><strong>${escapeHtml(title)}</strong>${detail ? `<small>${escapeHtml(detail)}</small>` : ""}</span></article>`;
    }).join("");
    list.scrollTop = Math.min(scrollTop, list.scrollHeight);
  }

  #updateStatus(): void {
    const status = this.#root.querySelector<HTMLElement>("#status");
    if (!status) return;
    status.classList.toggle("error", Boolean(this.#error));
    status.textContent = this.#error
      ? this.#error
      : this.#loading
        ? "Wird geladen …"
        : `${this.#events.length} Einträge · ${new Date().toLocaleTimeString("de-DE")}`;
  }
}

if (!customElements.get("ultimate-3d-audit-log-panel")) {
  customElements.define("ultimate-3d-audit-log-panel", Ultimate3DAuditLogPanelV2);
}
