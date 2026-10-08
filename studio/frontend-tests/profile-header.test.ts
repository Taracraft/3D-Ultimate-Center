import test from "node:test";
import assert from "node:assert/strict";
import { studioProfileBarHtml } from "../frontend/studio-profile-ui.js";
import type { V6Profile, V6ProfileCatalog } from "../frontend/profile-api.js";
import type { StudioPlateProfileSelection } from "../frontend/studio-profile-catalog.js";

function render(payload: Record<string, unknown>, source: V6Profile["source"] = "local", overrides: Record<string, unknown> = {}, diameter = .4): string {
  const process = { id: "test.process", kind: "process", name: "Selected process", source, payload } as V6Profile;
  const nozzle = { id: "test.nozzle", kind: "nozzle", name: "Nozzle", source: "builtin", payload: { diameter_mm: diameter } } as V6Profile;
  const profiles = [process, nozzle];
  const catalog = { profiles, groups: { process: [process], nozzle: [nozzle], filament: [], build_plate: [], printer: [] } } as unknown as V6ProfileCatalog;
  const selection = { process_profile_id: process.id, nozzle_profile_id: nozzle.id, printer_profile_id: "", target_printer_id: "", filament_profile_ids: [], build_plate_profile_id: "" } as StudioPlateProfileSelection;
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", { configurable: true, value: { getItem: () => JSON.stringify(overrides), setItem: () => { throw Error("Rendering must not write process settings"); } } });
  try { return studioProfileBarHtml(catalog, [], selection); }
  finally { if (original) Object.defineProperty(globalThis, "localStorage", original); else Reflect.deleteProperty(globalThis, "localStorage"); }
}
function input(html: string, key: string): string { return html.match(new RegExp(`<input data-process-override="${key}"[^>]*>`))?.[0] || ""; }
const selected = { layer_height_mm: .2, outer_wall_speed_mm_s: 70, inner_wall_speed_mm_s: 150 };

test("profile header shows selected 70/150 rather than generic 200/300 nozzle values", () => {
  const html = render(selected);
  assert.match(input(html,"outer_wall_speed_mm_s"), /placeholder="Standard · 70 mm\/s"/);
  assert.match(input(html,"inner_wall_speed_mm_s"), /placeholder="Standard · 150 mm\/s"/);
  assert.match(input(html,"layer_height_mm"), /placeholder="Standard · 0,2 mm"/);
});
test("selected process height is independent of nozzle default height", () => {
  assert.match(input(render({...selected, layer_height_mm: .12}),"layer_height_mm"), /placeholder="Standard · 0,12 mm"/);
});
test("all supported nozzle diameters keep the selected profile values", () => {
  for (const nozzle of [.2,.4,.6,.8]) assert.match(input(render(selected,"local",{},nozzle),"outer_wall_speed_mm_s"), /placeholder="Standard · 70 mm\/s"/);
});
test("explicit user overrides remain actual input values and do not mutate the profile", () => {
  const payload = {...selected}; const html = render(payload,"local",{outer_wall_speed_mm_s:85});
  assert.match(input(html,"outer_wall_speed_mm_s"), /value="85"/);
  assert.match(input(html,"outer_wall_speed_mm_s"), /placeholder="Standard · 70 mm\/s"/);
  assert.deepEqual(payload, selected);
});
test("cloud native overlay uses its own keys without local alias precedence", () => {
  const html = render({layer_height: ".16", outer_wall_speed:"82.5", inner_wall_speed:161, outer_wall_speed_mm_s:999},"bambu_cloud");
  assert.match(input(html,"outer_wall_speed_mm_s"), /placeholder="Standard · 82,5 mm\/s"/);
  assert.match(input(html,"layer_height_mm"), /placeholder="Standard · 0,16 mm"/);
});
test("missing inherited or invalid values never advertise fabricated defaults", () => {
  for (const value of [undefined,null,"",true,false,NaN,Infinity,-1,0,[],[70],"50%","{speed}","<script>"]){
    const html=render({outer_wall_speed_mm_s:value});
    assert.match(input(html,"outer_wall_speed_mm_s"), /placeholder="Standardprofil"/);
    assert.doesNotMatch(input(html,"outer_wall_speed_mm_s"), /placeholder="[^"]*200/);
  }
  assert.match(input(render({inherits:"native_base"},"bambu_cloud"),"inner_wall_speed_mm_s"), /placeholder="Standardprofil"/);
});
test("switching the selected process refreshes placeholder values", () => {
  assert.match(input(render({...selected,outer_wall_speed_mm_s:40}),"outer_wall_speed_mm_s"), /placeholder="Standard · 40 mm\/s"/);
  assert.match(input(render({...selected,outer_wall_speed_mm_s:90}),"outer_wall_speed_mm_s"), /placeholder="Standard · 90 mm\/s"/);
});
test("unavailable process values and G-code slot profiles do not create defaults", () => {
  assert.match(input(render({...selected,slicing_supported:false}),"outer_wall_speed_mm_s"), /placeholder="Standardprofil"/);
  assert.match(input(render({...selected,gcode_slot:"gcode_1"}),"inner_wall_speed_mm_s"), /placeholder="Standardprofil"/);
});
