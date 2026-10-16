import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// Actual production methods, isolated state and explicit I/O doubles. This is
// not visual, provider, hardware, engine or full-file-parser acceptance.
const root = process.env.CAD_SOURCE_ROOT || process.cwd();
const workspace = "frontend/studio-mega-workspace-v2.ts";
const globals = { Map, Set, Float32Array, Uint32Array, Array, Date, Math, Number,
  String, Error, JSON, Promise, File, URLSearchParams, queueMicrotask, console };
const plain = (v: unknown) => JSON.parse(JSON.stringify(v));
function method(file: string, name: string, dependencies: Record<string, unknown> = {}): any {
  const source = ts.createSourceFile(file, readFileSync(join(root, file), "utf8"), ts.ScriptTarget.Latest, true);
  const owners = source.statements.filter(ts.isClassDeclaration).filter(c => c.members.some(m => m.name?.getText(source) === `#${name}`));
  assert.equal(owners.length, 1);
  const member = owners[0]!.members.find(m => m.name?.getText(source) === `#${name}`)!;
  const code = ts.transpileModule(`exports.Subject=class {${member.getText(source)}}`, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
    transformers: { before: [context => {
      const visit: ts.Visitor = n => ts.isPrivateIdentifier(n) ? ts.factory.createIdentifier(n.text.slice(1)) : ts.visitEachChild(n, visit, context);
      return file => ts.visitNode(file, visit) as ts.SourceFile;
    }] },
  }).outputText;
  const exports: any = {};
  runInNewContext(code, { exports, ...globals, ...dependencies });
  return exports.Subject.prototype[name];
}
function functions(names: string[], dependencies: Record<string, unknown> = {}): any {
  const source = ts.createSourceFile(workspace, readFileSync(join(root, workspace), "utf8"), ts.ScriptTarget.Latest, true);
  const parts = names.map(name => {
    const node = source.statements.find(n => ts.isFunctionDeclaration(n) && n.name?.text === name);
    assert.ok(node);return node.getText(source).replace(/^export\s+/, "");
  });
  const code = ts.transpileModule(parts.join("\n") + names.map(n => `\nexports.${n}=${n};`).join(""), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
  }).outputText;
  const exports: any = {};runInNewContext(code, { exports, ...globals, ...dependencies });return exports;
}
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes;reject = no; });
  void promise.catch(() => undefined); // Keep unused fixture rejection handled.
  return { promise, resolve, reject };
}
const tick = () => new Promise<void>(resolve => setImmediate(resolve));
const selection = () => ({ target_printer_id: "printer", printer_profile_id: "a1", nozzle_profile_id: "n", process_profile_id: "p", build_plate_profile_id: "b", filament_profile_ids: ["f"], gcode_preset_ids: { start_sound: "sound" } });
const positions = [0,0,0,1,0,0,0,1,0];
const mesh = () => ({ positions: new Float32Array(positions), normals: new Float32Array(9), triangleCount: 1, boundsMin: [0,0,0], boundsMax: [1,1,0] });
const inspection = (count = 1, color = "#ffffff") => ({ format: "3mf", plate_count: count, plates: Array.from({length:count},(_,i)=>({name:`Plate ${i}`})), objects: [], filaments: [{extruder:1,name:"New",material:"PLA",color}] });
const scene = (index = 0) => ({ plate_size:[256,256], instances:[{part_id:`part-${index}`,object_id:`model-${index}`,name:`New ${index}`,positions:[...positions],extruder:1,visible:true}] });
function fixture(overrides: Record<string, unknown> = {}) {
  const {newPlate} = functions(["newPlateUid","newPlate"]);
  const initial = newPlate(0,"Saved plate",selection());
  initial.instances=[{id:"saved",name:"Saved model",geometry:mesh(),position:[35,45,0],rotation:[0,0,90],scale:[2,2,2],visible:true,color:"#112233"}];
  initial.jobId="saved-job";initial.stage="completed";
  const events: any[] = [], persisted: any[] = [], dismissed: any[] = [];
  const jobs: any = {snapshot:{slicer:{id:"saved-job",status:"completed"}},dismissSlicerJob:(id?: string)=>dismissed.push(id)};
  const makePaint=()=>({marker:{original:true},replace() {},getRegions:()=>[],clear() {}});
  const dependencies: any = { newPlate, createPaintSession:makePaint, jobActivityStore:jobs,
    ACTIVE:new Set(["queued","running","cancelling"]), PREVIEW_FEATURE_KEYS:["outer_wall"],
    NEUTRAL_COLOR:"#6b7785", normalizeColor:(v:string)=>v,
    inspectSliceModel:async()=>inspection(),inspectGallerySliceModel:async()=>inspection(),
    fetchScene:async(_file:File,index:number)=>scene(index),buildMeshGeometryAsync:async()=>mesh(),
    fitImportedGroup:(items:any[])=>items,parseStl:()=>mesh(),
    positionCenteredOnPlate:()=>[128,128,0],positionOnBed:(_g:unknown,t:any)=>t.position,
    ...overrides };
  const value: any = { plates:[initial],activePlate:0,assignments:new Map([["saved","model:1"]]),
    modelMaterials:[{key:"model:1",name:"Old",material:"PLA",color:"#112233",source:"model"}],
    selected:new Set(["saved"]),selectionAnchor:"saved",paintSession:makePaint(),paintLayers:new Map([[0,[{id:"paint",objectId:"saved"}]]]),paintLegacyAmbiguousObjectIds:new Set(["saved"]),
    clipboard:{id:"clipboard"},projectId:"project",projectName:"Saved project",projectRevision:4,
    file:new File(["saved"],"saved.3mf"),inspection:{marker:"saved"},mode:"colors",previewSupportOnly:true,
    previewColorMode:"feature",previewVisibleFeatures:new Set(["infill"]),previewCumulative:false,
    generation:0,projectGeneration:0,nextId:40,recentImportKey:"",recentImportAt:0,recentImportFile:null,operationTraceId:"",
    loading:false,importing:false,workspaceReady:true,historyReady:false,isConnected:true,
    reconcilingJobs:new Set(["saved-job"]),sliceTraceByJob:new Map(),slicePreparationId:"",
    error:"",status:"Saved",nextPaintLayerId:5,
    plate(){return this.plates[this.activePlate];},
    materialColor(key:string){return this.modelMaterials.find((m:any)=>m.key===key)?.color??"#6b7785";},
    collectExtruders(){},audit:(...a:any[])=>events.push(a),traceStudioOperation:(...a:any[])=>events.push(a),
    renderFull(){},renderStatus(){},schedulePersist(){persisted.push(this.plates);},
    viewport:{setPreviewMode(){},setInstances(){}},setSlicePreparation(){},
    invalidatePlate(p:any){p.jobId="";p.stage="prepared";p.layers=[];},
  };
  value.resetWorkspaceForProjectOpen=method(workspace,"resetWorkspaceForProjectOpen",dependencies);
  const load=method(workspace,"load",dependencies),request=method(workspace,"requestImport",dependencies);
  const running:Promise<void>[]=[];
  value.load=function(...args:any[]){const p=load.call(this,...args);running.push(p);return p;};
  return {value,load,request,running,dependencies,events,persisted,dismissed,jobs};
}
function saved(value:any) {
  return {plates:value.plates,plate:value.plate(),instances:value.plate().instances,assignments:value.assignments,
    palette:value.modelMaterials,paint:value.paintSession,layers:value.paintLayers,legacy:value.paintLegacyAmbiguousObjectIds,
    selected:value.selected,clipboard:value.clipboard,file:value.file,inspection:value.inspection,mode:value.mode,
    projectId:value.projectId,projectName:value.projectName,projectRevision:value.projectRevision,
    jobId:value.plate().jobId,nextId:value.nextId};
}
function retained(value:any,before:ReturnType<typeof saved>) {
  const now=saved(value);for(const key of Object.keys(before))assert.equal(now[key as keyof typeof now],before[key as keyof typeof before],key);
}

test("project request preserves saved workspace and file while inspection is pending",async()=>{
  const wait=deferred<any>(),f=fixture({inspectSliceModel:()=>wait.promise}),before=saved(f.value);
  f.request.call(f.value,new File(["new"],"next.3mf"),true,"");
  try { retained(f.value,before);assert.equal(f.persisted.length,0);assert.equal(f.dismissed.length,0); }
  finally {wait.reject(Error("blocked"));await Promise.all(f.running);}
});
test("inspection failure retains project geometry paint palette and saved file",async()=>{
  const f=fixture({inspectSliceModel:async()=>{throw Error("inspection blocked");}}),before=saved(f.value);
  f.request.call(f.value,new File(["x"],"bad.3mf"),true,"");await Promise.all(f.running);
  retained(f.value,before);assert.match(f.value.error,/inspection blocked/);assert.equal(f.value.loading,false);assert.equal(f.persisted.length,0);
});
test("second-plate failure retains the whole original project without staged assignments",async()=>{
  const f=fixture({inspectSliceModel:async()=>inspection(2),fetchScene:async(_f:File,i:number)=>{if(i===1)throw Error("second plate failed");return scene(i);}}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"multi.3mf"),true,"");
  retained(f.value,before);assert.match(f.value.error,/second plate failed/);assert.equal(f.persisted.length,0);assert.equal(f.dismissed.length,0);
});
test("append failure cannot leak a new palette or assignment into existing models",async()=>{
  const f=fixture({buildMeshGeometryAsync:async()=>{throw Error("geometry failed");}}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"bad.3mf"),false,"");retained(f.value,before);assert.equal(f.persisted.length,0);
});
test("a late failed import cannot overwrite a newer successful project",async()=>{
  const old=deferred<any>(),f=fixture({inspectSliceModel:(file:File)=>file.name==="old.3mf"?old.promise:Promise.resolve(inspection())});
  const first=f.load.call(f.value,new File(["old"],"old.3mf"),true,"");
  await f.load.call(f.value,new File(["new"],"new.3mf"),true,"");const current=saved(f.value),status=f.value.status;
  old.reject(Error("obsolete failure"));await first;retained(f.value,current);assert.equal(f.value.status,status);assert.equal(f.value.error,"");
});
test("a late successful scene cannot replace the latest imported project",async()=>{
  const old=deferred<any>(),f=fixture({fetchScene:(file:File)=>file.name==="old.3mf"?old.promise:Promise.resolve(scene())});
  const first=f.load.call(f.value,new File(["old"],"old.3mf"),true,"");await tick();
  await f.load.call(f.value,new File(["new"],"new.3mf"),true,"");const current=saved(f.value);
  old.resolve(scene());await first;retained(f.value,current);assert.equal(f.value.error,"");
});
test("failed import can immediately retry the exact same file",async()=>{
  let calls=0;const f=fixture({inspectSliceModel:async()=>{calls++;throw Error("temporary");}}),file=new File(["x"],"retry.3mf");
  f.request.call(f.value,file,true,"");await Promise.all(f.running);f.request.call(f.value,file,true,"");await Promise.all(f.running);assert.equal(calls,2);
});
test("distinct files with identical metadata are not treated as duplicate content",async()=>{
  const waits=[deferred<any>(),deferred<any>()];let calls=0;const f=fixture({inspectSliceModel:()=>waits[calls++]!.promise});
  const a=new File(["AAA"],"same.3mf",{lastModified:1}),b=new File(["BBB"],"same.3mf",{lastModified:1});
  f.request.call(f.value,a,true,"");f.request.call(f.value,b,true,"");
  try {assert.equal(calls,2);}finally{for(const w of waits)w.reject(Error("done"));await Promise.all(f.running);}
});
test("a repeated pending request for the same file is coalesced",async()=>{
  const wait=deferred<any>();let calls=0;const f=fixture({inspectSliceModel:()=>{calls++;return wait.promise;}}),file=new File(["x"],"same.3mf");
  f.request.call(f.value,file,true,"");f.request.call(f.value,file,true,"");assert.equal(calls,1);wait.reject(Error("done"));await Promise.all(f.running);
});
test("append and replacement are distinct operations even for the same file",async()=>{
  const waits=[deferred<any>(),deferred<any>()];let calls=0;const f=fixture({inspectSliceModel:()=>waits[calls++]!.promise}),file=new File(["x"],"same.3mf");
  f.request.call(f.value,file,false,"");f.request.call(f.value,file,true,"");
  try{assert.equal(calls,2);}finally{for(const w of waits)w.reject(Error("done"));await Promise.all(f.running);}
});
test("successful replacement commits complete plates and clears only old workspace state",async()=>{
  const f=fixture({inspectSliceModel:async()=>inspection(2)}),old=f.value.plate(),oldMap=f.value.assignments;
  const file=new File(["x"],"complete.3mf");await f.load.call(f.value,file,true,"");
  assert.equal(f.value.error,"");assert.equal(f.value.plates.length,2);assert.equal(f.value.file,file);assert.equal(f.value.projectId,"");
  assert.equal(f.value.paintLayers.size,0);assert.equal(f.value.paintLegacyAmbiguousObjectIds.size,0);assert.equal(f.value.clipboard,null);
  assert.equal(f.value.assignments.size,2);assert.equal(oldMap.get("saved"),"model:1");assert.equal(old.jobId,"saved-job");assert.equal(f.persisted.length,1);
});
test("successful append preserves previous materials when extruder numbers collide",async()=>{
  const f=fixture(),old=f.value.plate(),oldColor=f.value.modelMaterials[0].color;
  await f.load.call(f.value,new File(["x"],"another.3mf"),false,"");
  assert.equal(f.value.plates[0],old);assert.equal(f.value.assignments.get("saved"),"model:1");
  assert.equal(f.value.modelMaterials.find((m:any)=>m.key==="model:1").color,oldColor);
  const added=f.value.plates[1].instances[0],key=f.value.assignments.get(added.id);
  assert.notEqual(key,"model:1");assert.equal(f.value.modelMaterials.find((m:any)=>m.key===key).color,"#ffffff");
});
test("active backend jobs are not cancelled or dismissed by project replacement",async()=>{
  const f=fixture();f.jobs.snapshot.slicer={id:"running-job",status:"running"};
  await f.load.call(f.value,new File(["x"],"new.3mf"),true,"");assert.equal(f.value.error,"");assert.equal(f.dismissed.length,0);
});
test("an import cannot commit into a structurally replaced workspace",async()=>{
  const wait=deferred<any>(),f=fixture({fetchScene:()=>wait.promise});const pending=f.load.call(f.value,new File(["x"],"late.3mf"),false,"");await tick();
  f.value.plates=[{...f.value.plate(),uid:"changed"}];const now=saved(f.value);wait.resolve(scene());await pending;
  retained(f.value,now);assert.notEqual(f.value.error,"");assert.equal(f.persisted.length,0);
});
test("invalid inspection format is rejected without interpreting it as STL",async()=>{
  const f=fixture({inspectSliceModel:async()=>({...inspection(),format:"unknown"})}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"bad.bin"),true,"");retained(f.value,before);assert.notEqual(f.value.error,"");
});
function shellFixture() {
  const calls:any[]=[];let clears=0,removes=0,consumes=0;
  const studio={isConnected:true,remove(){removes++;},openProject:(...a:any[])=>calls.push(a),openGalleryProject:(...a:any[])=>calls.push(a)};
  const routes:any[]=[];const queue=[new File(["queued"],"queued.3mf")];
  const open=method("frontend/app-shell-v4.ts","openStudioProject",{clearStudioWorkspace:async()=>{clears++;},writeFrontendAudit(){},consumeWorkspaceFiles:()=>{consumes++;return queue.splice(0);}});
  const value:any={projectOpenGeneration:0,studio,source:null,studioNode:()=>studio,navigate:(r:any)=>routes.push(r)};
  return {open,value,studio,calls,routes,queue,counts:()=>({clears,removes,consumes})};
}
test("shell explicit-file handoff preserves the old workspace and unrelated queued files",async()=>{
  const f=shellFixture(),file=new File(["explicit"],"chosen.3mf");await f.open.call(f.value,{file});
  assert.deepEqual(f.counts(),{clears:0,removes:0,consumes:0});assert.equal(f.calls[0][0],file);assert.equal(f.queue.length,1);
});
test("shell empty-source request has no destructive effect",async()=>{
  const f=shellFixture();f.queue.length=0;await f.open.call(f.value,{});assert.equal(f.counts().clears,0);assert.equal(f.counts().removes,0);assert.equal(f.routes.length,0);assert.equal(f.calls.length,0);
});
test("shell gallery-asset handoff never clears a saved project or drains a queued file",async()=>{
  const f=shellFixture();await f.open.call(f.value,{assetId:"asset",fileName:"model.3mf"});
  assert.deepEqual(f.counts(),{clears:0,removes:0,consumes:0});assert.equal(f.calls[0][0],"asset");assert.equal(f.queue.length,1);
});
test("shell only forwards the latest pending explicit project request",async()=>{
  const f=shellFixture(),a=new File(["a"],"a.3mf"),b=new File(["b"],"b.3mf");
  await Promise.all([f.open.call(f.value,{file:a}),f.open.call(f.value,{file:b})]);assert.equal(f.calls.length,1);assert.equal(f.calls[0][0],b);assert.equal(f.counts().clears,0);
});

test("pending restore cannot replace a newer imported workspace",async()=>{
  const wait=deferred<any>(),f=fixture();
  const restore=method(workspace,"restoreWorkspace",{loadStudioWorkspace:()=>wait.promise});
  const pending=restore.call(f.value);f.value.generation++;
  const current=saved(f.value);wait.resolve({plates:[{name:"obsolete"}]});await pending;
  retained(f.value,current);assert.equal(f.events.length,0);
});
test("restore does not read saved state during an active import",async()=>{
  let calls=0;const f=fixture();f.value.importing=true;
  const restore=method(workspace,"restoreWorkspace",{loadStudioWorkspace:async()=>{calls++;return null;}});
  await restore.call(f.value);assert.equal(calls,0);
});
test("old failure cannot stop progress or set an error while the next import is pending",async()=>{
  const old=deferred<any>(),latest=deferred<any>();
  const f=fixture({inspectSliceModel:(file:File)=>file.name==="old.3mf"?old.promise:latest.promise});
  const a=f.load.call(f.value,new File(["a"],"old.3mf"),true,"");
  const b=f.load.call(f.value,new File(["b"],"latest.3mf"),true,"");
  old.reject(Error("old failure"));await a;
  assert.equal(f.value.loading,true);assert.equal(f.value.importing,true);assert.equal(f.value.error,"");
  latest.reject(Error("current failure"));await b;assert.match(f.value.error,/current failure/);
});
test("STL parse failure leaves the old project and persisted state untouched",async()=>{
  const f=fixture({inspectSliceModel:async()=>({...inspection(),format:"stl"}),parseStl:()=>{throw Error("broken STL");}}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"broken.stl"),true,"");retained(f.value,before);assert.equal(f.persisted.length,0);
});
test("successful STL append preserves earlier geometry and invalidates only its target job",async()=>{
  const f=fixture({inspectSliceModel:async()=>({...inspection(),format:"stl",filaments:[]})}),old=f.value.plate(),original=old.instances[0];
  const file=new File(["x"],"append.stl");await f.load.call(f.value,file,false,"");
  assert.equal(f.value.error,"");assert.equal(f.value.plates.length,1);assert.equal(f.value.plate(),old);assert.equal(old.instances.length,2);assert.equal(old.instances[0],original);assert.equal(old.jobId,"");assert.equal(f.value.file,file);
});
test("gallery asset import uses its exact id without reading placeholder bytes",async()=>{
  const ids:string[]=[];const f=fixture({inspectGallerySliceModel:async(id:string)=>{ids.push(id);return inspection();},inspectSliceModel:async()=>{throw Error("local path forbidden");},fetchScene:async(_file:File,_i:number,id:string)=>{ids.push(id);return scene();}});
  const file=new File([],"remote.3mf");file.arrayBuffer=async()=>{throw Error("placeholder must not be read");};
  await f.load.call(f.value,file,true,"asset-identity");assert.equal(f.value.error,"");assert.deepEqual(ids,["asset-identity","asset-identity"]);
});
for (const count of [NaN,2.5,true,1001]) test(`invalid plate count ${String(count)} fails before scene transport`,async()=>{
  let calls=0;const f=fixture({inspectSliceModel:async()=>({...inspection(),plate_count:count}),fetchScene:async()=>{calls++;return scene();}}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"bad.3mf"),true,"");

  retained(f.value,before);assert.equal(calls,0);assert.notEqual(f.value.error,"");
});
test("ambiguous duplicate material channels fail before replacing a project",async()=>{
  const info=inspection();info.filaments.push({...info.filaments[0]!,color:"#ff0000"});const f=fixture({inspectSliceModel:async()=>info}),before=saved(f.value);
  await f.load.call(f.value,new File(["x"],"ambiguous.3mf"),true,"");retained(f.value,before);assert.notEqual(f.value.error,"");
});

test("retired project job reconciliation cannot publish into a new workspace or clear its loading state",async()=>{
  const wait=deferred<any>(),f=fixture();let published=0,rendered=0,toolpaths=0;
  const old=f.value.plate();f.value.traceSliceActivity=()=>{published++;};f.value.renderAfterSliceReconcile=()=>{rendered++;};f.value.persistNow=async()=>{};
  const activate=method(workspace,"activatePlateJob",{ACTIVE:new Set(["running"]),fetchSliceJob:()=>{fetches++;return wait.promise;},fetchToolpath:async()=>{toolpaths++;return {layer_count:0,layers:[],filament_colors:[]};},jobActivityStore:{registerSlicerJob(){published++;}},console:{warn(){}},normalizeToolpathPalette:(v:unknown)=>v});
  let fetches=0;f.value.reconcilingJobs.clear();
  const pending=activate.call(f.value,old);assert.equal(fetches,1);
  await f.load.call(f.value,new File(["next"],"new.3mf"),true,"");
  f.value.loading=true;f.value.importing=true;f.value.status="new import pending";f.value.reconcilingJobs.add(old.jobId);
  wait.resolve({id:old.jobId,status:"succeeded"});await pending;
  assert.equal(published,0);assert.equal(rendered,0);assert.equal(toolpaths,0);
  assert.equal(f.value.loading,true);assert.equal(f.value.status,"new import pending");assert.ok(f.value.reconcilingJobs.has(old.jobId));
});
test("existing job failure cannot end the progress display of a pending import",async()=>{
  const wait=deferred<any>(),f=fixture();let rendered=0;
  f.value.traceSliceActivity=()=>{};f.value.renderAfterSliceReconcile=()=>{rendered++;};
  const activate=method(workspace,"activatePlateJob",{ACTIVE:new Set(["running"]),fetchSliceJob:()=>{fetches++;return wait.promise;},console:{warn(){}}});
  let fetches=0;f.value.reconcilingJobs.clear();
  const pending=activate.call(f.value,f.value.plate());assert.equal(fetches,1);
  f.value.loading=true;f.value.importing=true;f.value.status="import in progress";
  wait.reject(Error("old job failed"));await pending;
  assert.equal(f.value.loading,true);assert.equal(f.value.status,"import in progress");assert.equal(rendered,0);
});
