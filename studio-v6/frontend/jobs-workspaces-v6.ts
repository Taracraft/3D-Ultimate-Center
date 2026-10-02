import { openContextMenu, type ContextMenuAction } from "./context-menu.js";
import { errorMessage } from "./ha-api-transport.js";
import { v6Api, type V6Job, type V6Jobs } from "./v6-api.js";

type WorkspaceKind = "tasks" | "history";

abstract class AuftragsArbeitsbereich extends HTMLElement {
  protected readonly root = this.attachShadow({ mode: "open" });
  protected daten: V6Jobs = {};
  protected fehler = "";
  protected meldung = "";
  private timer: number | null = null;
  private busyJobId = "";

  connectedCallback(): void {
    void this.aktualisieren();
    this.timer = window.setInterval(() => void this.aktualisieren(), 10000);
  }

  disconnectedCallback(): void {
    if (this.timer !== null) window.clearInterval(this.timer);
    this.timer = null;
  }

  protected abstract titel(): string;
  protected abstract beschreibung(): string;
  protected abstract eintraege(): V6Job[];
  protected abstract kind(): WorkspaceKind;

  protected async aktualisieren(): Promise<void> {
    try {
      this.daten = await v6Api.getJobs();
      this.fehler = "";
    } catch (error) {
      this.fehler = errorMessage(error);
    }
    this.rendern();
  }

  protected rendern(): void {
    const eintraege = this.eintraege();
    this.root.innerHTML = `
      <style>
        :host{display:block;min-height:calc(100vh - 156px);color:#eef5ff;background:#08101a}
        *{box-sizing:border-box}.inhalt{padding:20px}.kopf{display:flex;justify-content:space-between;gap:16px;margin-bottom:16px}.kopf h1{margin:0}.kopf p{margin:6px 0 0;color:#91a5bb}.liste{display:grid;gap:10px}.eintrag{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center;padding:14px;border:1px solid #2a3c53;border-radius:11px;background:#111b29;cursor:context-menu}.eintrag:hover{border-color:#3d6388}.eintrag small{display:block;margin-top:5px;color:#8fa4bc}.aktionen{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.aktion{padding:8px 10px;border:1px solid #32658b;border-radius:8px;background:#14324b;color:#eef5ff;cursor:pointer;font-weight:700}.aktion.danger{border-color:#8f3f4b;background:#3a171d;color:#ffd7dc}.aktion:disabled{opacity:.4;cursor:not-allowed}.leer,.fehler,.meldung{padding:16px;border:1px solid #2a3c53;border-radius:11px;background:#111b29;color:#91a5bb}.fehler{border-color:#8f3f4b;color:#ffd7dc}.meldung{margin-bottom:10px;border-color:#27734c;color:#8ff0b5}.datum{white-space:nowrap;color:#7890a8;font-size:11px}@media(max-width:700px){.eintrag{grid-template-columns:1fr}.aktionen{justify-content:flex-start}}
      </style>
      <section class="inhalt">
        <div class="kopf"><div><h1>${this.titel()}</h1><p>${this.beschreibung()}</p></div><strong>${eintraege.length}</strong></div>
        ${this.meldung ? `<div class="meldung">${this.maskieren(this.meldung)}</div>` : ""}
        ${this.fehler ? `<div class="fehler">${this.maskieren(this.fehler)}</div>` : ""}
        <div class="liste">${eintraege.length ? eintraege.map((auftrag) => this.zeile(auftrag)).join("") : '<div class="leer">Keine Einträge vorhanden.</div>'}</div>
      </section>`;

    this.root.querySelectorAll<HTMLElement>("[data-job-id]").forEach((row) => {
      const job = this.findJob(String(row.dataset.jobId || ""));
      if (!job) return;
      row.addEventListener("contextmenu", (event) => this.openJobContext(event, job));
      row.addEventListener("keydown", (event) => {
        if (event.key !== "ContextMenu" && !(event.shiftKey && event.key === "F10")) return;
        const bounds = row.getBoundingClientRect();
        this.openJobContext(new MouseEvent("contextmenu", {
          clientX: bounds.left + 24,
          clientY: bounds.top + 24,
        }), job);
      });
    });

    this.root.querySelectorAll<HTMLButtonElement>("[data-action='repeat']").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const job = this.findJob(String(button.dataset.jobId || ""));
        if (job) void this.repeat(job);
      });
    });

    this.root.querySelectorAll<HTMLButtonElement>("[data-action='remove']").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.stopPropagation();
        const job = this.findJob(String(button.dataset.jobId || ""));
        if (job) void this.removeQueued(job);
      });
    });
  }

  private jobId(job: V6Job): string {
    return String(job.job_id || job.id || "");
  }

  private findJob(jobId: string): V6Job | null {
    return this.eintraege().find((job) => this.jobId(job) === jobId) ?? null;
  }

  private isQueued(job: V6Job): boolean {
    return String(job.status || "").toLowerCase() === "queued"
      || String(this.jobId(job)).startsWith("queue:");
  }

  private zeile(auftrag: V6Job): string {
    const id = this.maskieren(this.jobId(auftrag));
    const datei = this.maskieren(String(auftrag.file || auftrag.model_name || "Unbenanntes Modell"));
    const drucker = this.maskieren(String(auftrag.printer_name || auftrag.printer_id || "Kein Drucker"));
    const status = this.maskieren(String(auftrag.status || "unbekannt"));
    const fortschritt = Number(auftrag.progress);
    const fortschrittText = Number.isFinite(fortschritt) ? ` · ${fortschritt}%` : "";
    const datum = this.datum(auftrag.completed_at || auftrag.queued_at || auftrag.started_at);
    const busy = this.busyJobId === this.jobId(auftrag);
    const action = this.kind() === "history"
      ? `<button class="aktion" type="button" data-action="repeat" data-job-id="${id}" ${busy ? "disabled" : ""}>${busy ? "Wird eingereiht …" : "Erneut einreihen"}</button>`
      : this.isQueued(auftrag)
        ? `<button class="aktion danger" type="button" data-action="remove" data-job-id="${id}" ${busy ? "disabled" : ""}>${busy ? "Wird entfernt …" : "Aus Warteschlange"}</button>`
        : "";

    return `
      <article class="eintrag" data-job-id="${id}" tabindex="0">
        <div><b>${datei}</b><small>${drucker} · ${status}${fortschrittText}</small>${datum ? `<div class="datum">${this.maskieren(datum)}</div>` : ""}</div>
        <div class="aktionen">${action}</div>
      </article>`;
  }

  private datum(value: unknown): string {
    if (!value) return "";
    const parsed = new Date(String(value));
    if (Number.isNaN(parsed.getTime())) return "";
    return parsed.toLocaleString("de-DE");
  }

  private openJobContext(event: MouseEvent, job: V6Job): void {
    const name = String(job.file || job.model_name || "Unbenanntes Modell");
    const actions: ContextMenuAction[] = [
      {
        label: "Dateiname kopieren",
        run: async () => {
          await navigator.clipboard?.writeText(name);
          this.meldung = "Dateiname wurde kopiert.";
          this.rendern();
        },
      },
      { label: "Liste aktualisieren", run: () => this.aktualisieren() },
    ];

    if (this.kind() === "history") {
      actions.unshift({
        label: "Druck erneut einreihen",
        run: () => this.repeat(job),
      });
    } else if (this.isQueued(job)) {
      actions.unshift({
        label: "Aus Warteschlange entfernen",
        danger: true,
        run: () => this.removeQueued(job),
      });
    }

    openContextMenu(event, actions);
  }

  private async repeat(job: V6Job): Promise<void> {
    const id = this.jobId(job);
    if (!id || this.busyJobId) return;
    const name = String(job.file || job.model_name || "Unbenanntes Modell");
    if (!window.confirm(`Druck erneut in die Warteschlange stellen?\n\n${name}\n\nDer Druck startet dadurch noch nicht automatisch.`)) return;

    this.busyJobId = id;
    this.fehler = "";
    this.meldung = "";
    this.rendern();
    try {
      await v6Api.repeatJob(id);
      this.meldung = `${name} wurde erneut in die Warteschlange gestellt.`;
      await this.aktualisieren();
    } catch (error) {
      this.fehler = errorMessage(error);
    } finally {
      this.busyJobId = "";
      this.rendern();
    }
  }

  private async removeQueued(job: V6Job): Promise<void> {
    const id = this.jobId(job);
    if (!id || this.busyJobId) return;
    const name = String(job.file || job.model_name || "Unbenanntes Modell");
    if (!window.confirm(`Auftrag aus der Warteschlange entfernen?\n\n${name}`)) return;

    this.busyJobId = id;
    this.fehler = "";
    this.meldung = "";
    this.rendern();
    try {
      await v6Api.removeQueuedJob(id);
      this.meldung = `${name} wurde aus der Warteschlange entfernt.`;
      await this.aktualisieren();
    } catch (error) {
      this.fehler = errorMessage(error);
    } finally {
      this.busyJobId = "";
      this.rendern();
    }
  }

  protected maskieren(wert: string): string {
    return wert.replace(/[&<>"']/g, (zeichen) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[zeichen] || zeichen));
  }
}

class Ultimate3DAufgabenWorkspace extends AuftragsArbeitsbereich {
  protected titel(): string { return "Aufgaben"; }
  protected beschreibung(): string { return "Laufende, pausierte und wartende Druckaufträge."; }
  protected eintraege(): V6Job[] { return [...(this.daten.current || []), ...(this.daten.queue || [])]; }
  protected kind(): WorkspaceKind { return "tasks"; }
}

class Ultimate3DVerlaufWorkspace extends AuftragsArbeitsbereich {
  protected titel(): string { return "Verlauf"; }
  protected beschreibung(): string { return "Abgeschlossene, abgebrochene und fehlgeschlagene Drucke."; }
  protected eintraege(): V6Job[] { return this.daten.history || []; }
  protected kind(): WorkspaceKind { return "history"; }
}

if (!customElements.get("ultimate-3d-aufgaben-workspace")) {
  customElements.define("ultimate-3d-aufgaben-workspace", Ultimate3DAufgabenWorkspace);
}

if (!customElements.get("ultimate-3d-verlauf-workspace")) {
  customElements.define("ultimate-3d-verlauf-workspace", Ultimate3DVerlaufWorkspace);
}