class PrinterSlicingServerPanel extends HTMLElement {
  set hass(value) {
    this._hass = value;
    if (this._built) return;
    this._built = true;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;min-height:100%;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,system-ui)}
        *{box-sizing:border-box}.wrap{max-width:1400px;margin:auto;padding:20px;display:grid;grid-template-columns:380px 1fr;gap:20px}.stack{display:grid;gap:20px}.card{background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:14px;padding:18px;box-shadow:var(--ha-card-box-shadow)}h1,h2{margin-top:0}.status{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}.pill{padding:6px 10px;border-radius:999px;background:var(--secondary-background-color);border:1px solid var(--divider-color)}label{display:block;margin:12px 0 6px;color:var(--secondary-text-color)}input,select,button{width:100%;padding:10px;border-radius:9px;border:1px solid var(--divider-color);background:var(--secondary-background-color);color:var(--primary-text-color);font:inherit}button{cursor:pointer;background:var(--primary-color);color:var(--text-primary-color);font-weight:700;border:0;margin-top:14px}button.secondary{background:var(--secondary-background-color);color:var(--primary-text-color);border:1px solid var(--divider-color)}button.small{width:auto;margin:0;padding:7px 9px;font-size:12px}button:disabled{opacity:.45}.msg{min-height:22px;margin-top:10px}.ok{color:var(--success-color,#2ecc71)}.bad{color:var(--error-color,#e74c3c)}.muted{color:var(--secondary-text-color)}table{width:100%;border-collapse:collapse}th,td{padding:9px 7px;border-bottom:1px solid var(--divider-color);text-align:left;vertical-align:middle}th{color:var(--secondary-text-color)}.completed{color:var(--success-color,#2ecc71)}.failed{color:var(--error-color,#e74c3c)}.queued,.slicing{color:#f4b400}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px;max-height:650px;overflow:auto}.model{display:grid;grid-template-rows:108px auto;border:1px solid var(--divider-color);border-radius:12px;overflow:hidden;background:var(--secondary-background-color)}.preview{display:grid;place-items:center;position:relative;background:radial-gradient(circle at 50% 35%,#35536b,#162635 70%);font-size:34px;font-weight:900;color:#b9def8}.preview small{position:absolute;right:8px;top:8px;padding:3px 7px;border-radius:999px;background:#08111bbb;font-size:10px}.model-body{padding:11px;display:grid;gap:7px}.model-name{font-weight:700;overflow-wrap:anywhere}.model-meta{font-size:11px;color:var(--secondary-text-color)}.model-actions{display:grid;grid-template-columns:1fr 1fr;gap:7px}.model-actions button{margin:0;padding:7px;font-size:11px}.job-actions{display:flex;gap:6px;flex-wrap:wrap}#jobs{max-height:650px;overflow:auto}@media(max-width:900px){.wrap{grid-template-columns:1fr}.card{overflow:auto}}@media(max-width:520px){.gallery{grid-template-columns:1fr}.model-actions{grid-template-columns:1fr}}
      </style>
      <div class="wrap">
        <div class="stack">
          <section class="card"><h1>3D-Printer Slicing Server</h1><div id="status" class="status"></div><div class="muted">Nativer Linux-Worker, gesteuert über Home Assistant</div></section>
          <section class="card"><h2>Modell hochladen</h2><input id="file" type="file" accept=".stl,.3mf,.obj,.amf"><button id="upload">Hochladen</button><div id="uploadMsg" class="msg"></div></section>
          <section class="card" id="slice-card"><h2>Slicing-Auftrag</h2><label>Modell</label><select id="inputFile"></select><label>Druckerprofil</label><select id="printer"></select><label>Engine</label><select id="engine"><option value="auto">Automatisch</option><option value="bambu_studio">Bambu Studio</option><option value="prusaslicer">PrusaSlicer</option><option value="curaengine">CuraEngine</option></select><label>Ausgabeformat</label><select id="format"><option value="gcode">G-Code</option><option value="3mf">3MF</option></select><label>Job-ID (optional)</label><input id="jobId" placeholder="automatisch"><button id="slice">Slicing starten</button><div id="jobMsg" class="msg"></div></section>
        </div>
        <div class="stack">
          <section class="card"><div style="display:flex;justify-content:space-between;align-items:center;gap:12px"><div><h2 style="margin-bottom:4px">Galerie</h2><div class="muted">Modelle auswählen oder direkt mit dem Bambu Lab A1 testen</div></div><button id="refresh" class="secondary small">Aktualisieren</button></div><div id="gallery" class="gallery"></div></section>
          <section class="card"><h2>Aufträge</h2><div class="muted" style="margin-bottom:10px">Kompakte Anzeige: maximal 20 Aufträge · Aktualisierung alle 10 Sekunden</div><div id="jobs"></div></section>
        </div>
      </div>`;
    this.shadowRoot.getElementById("refresh").onclick = () => this.load(true);
    this.shadowRoot.getElementById("upload").onclick = () => this.upload();
    this.shadowRoot.getElementById("slice").onclick = () => this.createJob();
    this.load(true);
    this._timer = setInterval(() => this.load(false), 10000);
  }
  disconnectedCallback(){if(this._timer)clearInterval(this._timer)}
  esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}
  async ws(type,extra={}){return this._hass.callWS({type,...extra})}
  fileType(name){return String(name).split(".").pop().toUpperCase()||"3D"}
  async load(full=true){
    try{
      const data=await this.ws("printer_slicing_server/overview");
      const info=data.info||{},status=data.status||{},printers=(data.printers||{}).printers||[],files=(data.files||{}).files||[],jobs=(data.jobs||{}).jobs||[];
      this.shadowRoot.getElementById("status").innerHTML=`<span class="pill ok">${this.esc(info.status)}</span><span class="pill">Version ${this.esc(info.version)}</span><span class="pill">Engines ${this.esc(info.engine_count)}</span><span class="pill">Queue ${this.esc(status.queued_jobs)}</span>`;
      if(full){
        this.shadowRoot.getElementById("printer").innerHTML=printers.map(p=>`<option value="${this.esc(p.id)}">${this.esc(p.name||p.id)}</option>`).join("");
        this.shadowRoot.getElementById("inputFile").innerHTML=files.length?files.slice(0,12).map(f=>`<option value="${this.esc(f.filename)}">${this.esc(f.filename)}</option>`).join(""):'<option value="">Keine Modelle</option>';
        this.shadowRoot.getElementById("gallery").innerHTML=files.length?files.map(f=>`<article class="model"><div class="preview"><span>⬡</span><small>${this.esc(this.fileType(f.filename))}</small></div><div class="model-body"><div class="model-name">${this.esc(f.filename)}</div><div class="model-meta">${(f.size/1024).toFixed(1)} KB · ${new Date(f.modified*1000).toLocaleString()}</div><div class="model-actions"><button class="secondary choose-model" data-file="${this.esc(f.filename)}">Auswählen</button><button class="test-model" data-file="${this.esc(f.filename)}">A1-Test</button></div></div></article>`).join(""):'<div class="muted">Noch keine Modelle hochgeladen.</div>';
        this.shadowRoot.querySelectorAll(".choose-model").forEach(button=>button.onclick=()=>this.chooseModel(button.dataset.file));
        this.shadowRoot.querySelectorAll(".test-model").forEach(button=>button.onclick=()=>this.testModel(button.dataset.file,button));
      }
      this.shadowRoot.getElementById("jobs").innerHTML=jobs.length?`<table><thead><tr><th>Job</th><th>Status</th><th>Engine</th><th>Datei</th><th></th></tr></thead><tbody>${jobs.slice(0,20).map(j=>`<tr><td>${this.esc(j.job_id)}</td><td class="${this.esc(j.status)}">${this.esc(j.status)}</td><td>${this.esc(j.engine||"-")}</td><td>${this.esc(j.input_file||"-")}</td><td><div class="job-actions">${j.download_url?`<button class="secondary small download-job" data-job="${this.esc(j.job_id)}">Download</button>`:""}</div></td></tr>`).join("")}</tbody></table>`:'<div class="muted">Noch keine Aufträge.</div>';
      this.shadowRoot.querySelectorAll(".download-job").forEach(button=>button.onclick=()=>this.download(button.dataset.job));
    }catch(err){const msg=this.shadowRoot.getElementById("jobMsg");msg.className="msg bad";msg.textContent=err.message||String(err)}
  }
  chooseModel(filename){
    const select=this.shadowRoot.getElementById("inputFile");select.value=filename;
    this.shadowRoot.getElementById("slice-card").scrollIntoView({behavior:"smooth",block:"start"});
    const msg=this.shadowRoot.getElementById("jobMsg");msg.className="msg ok";msg.textContent=`${filename} ist für den nächsten Auftrag ausgewählt.`;
  }
  async testModel(filename,button){
    button.disabled=true;const msg=this.shadowRoot.getElementById("jobMsg");
    try{const result=await this.ws("printer_slicing_server/create_job",{payload:{printer_profile:"bambu_lab_a1_04",input_file:filename,engine:"auto",output_format:"gcode",process_profile:"default",filament_profile:"default"}});msg.className="msg ok";msg.textContent=`A1-Test ${result.job_id} wurde angelegt.`;await this.load(false)}catch(err){msg.className="msg bad";msg.textContent=err.message||String(err)}finally{button.disabled=false}
  }
  async upload(){
    const input=this.shadowRoot.getElementById("file"),file=input.files[0],msg=this.shadowRoot.getElementById("uploadMsg"),btn=this.shadowRoot.getElementById("upload");if(!file)return;
    if(file.size>32*1024*1024){msg.className="msg bad";msg.textContent="Im HA-Panel sind maximal 32 MiB möglich.";return}btn.disabled=true;
    try{const buffer=await file.arrayBuffer();let binary="";const bytes=new Uint8Array(buffer);for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));await this.ws("printer_slicing_server/upload",{filename:file.name,content_base64:btoa(binary)});msg.className="msg ok";msg.textContent="Upload abgeschlossen.";input.value="";await this.load(true)}catch(err){msg.className="msg bad";msg.textContent=err.message||String(err)}finally{btn.disabled=false}
  }
  async createJob(){
    const q=id=>this.shadowRoot.getElementById(id),msg=q("jobMsg"),btn=q("slice");btn.disabled=true;
    const payload={printer_profile:q("printer").value,input_file:q("inputFile").value,engine:q("engine").value,output_format:q("format").value,process_profile:"default",filament_profile:"default"};if(q("jobId").value.trim())payload.job_id=q("jobId").value.trim();
    try{const result=await this.ws("printer_slicing_server/create_job",{payload});msg.className="msg ok";msg.textContent=`Job ${result.job_id} wurde angelegt.`;q("jobId").value="";await this.load(false)}catch(err){msg.className="msg bad";msg.textContent=err.message||String(err)}finally{btn.disabled=false}
  }
  async download(jobId){
    const msg=this.shadowRoot.getElementById("jobMsg");
    try{const result=await this.ws("printer_slicing_server/download",{job_id:jobId});const binary=atob(result.content_base64),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);const url=URL.createObjectURL(new Blob([bytes],{type:"application/octet-stream"})),link=document.createElement("a");link.href=url;link.download=result.filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);msg.className="msg ok";msg.textContent=`${result.filename} wurde heruntergeladen.`}catch(err){msg.className="msg bad";msg.textContent=err.message||String(err)}
  }
}
customElements.define("printer-slicing-server-panel",PrinterSlicingServerPanel);