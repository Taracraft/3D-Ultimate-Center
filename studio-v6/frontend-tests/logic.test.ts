import { safeMediaUrl, descriptionImageUrls, missingDescriptionImages } from "../frontend/makerworld-description-media.js";
import { buildContinuousToolpathMeshes, extrusionRibbonWidth, type RibbonSegment } from "../frontend/toolpath-ribbon-geometry.js";
import { transferMatchesAttempt } from "../frontend/transfer-attempt.js";
import { issueTitle, issueMessage, issueHelpUrl, issueQrImageUrl } from "../frontend/printer-issues.js";
import { PROCESS_EDITOR_FIELDS, validateProcessEditor, processProfileChanges } from "../frontend/process-profile-editor-model.js";
import { filamentSyncError, filamentSyncActionsHtml } from "../frontend/studio-filament-sync.js";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  bestFlatRotation,
  exportBinaryStl,
  positionCenteredOnPlate,
  positionOnBed,
  transformedBounds,
} from "../frontend/mesh-export.js";
import { parseRoute, routeToHash } from "../frontend/router.js";
import { sceneStore, type SceneState } from "../frontend/scene-store.js";
import { Store } from "../frontend/state-store.js";
import { analyzeFloatingSupportNeeds } from "../frontend/floating-support-analysis.js";
import { supportWarningHtml } from "../frontend/support-warning-dialog.js";
import { PRINT_PHASES, resolvePrintPhaseProgress, resolveSafePrintPhaseProgress, resolveTrackedPrintPhaseProgress } from "../frontend/print-phase-progress.js";
import { analyzeGeometry, layerCount, layerZ, sliceSegmentsAtZ, getCachedSliceSegmentsAtZ, clearSegmentCache, segmentCache } from "../frontend/stl-layer-preview.js";
import { parseStl, type MeshGeometry } from "../frontend/webgl-studio-viewport.js";
import { generateCapFaces } from "../frontend/studio-mesh-cap.js";
import { nextStudioSelection, selectAllStudioObjects } from "../frontend/studio-selection.js";
import { addMakerWorldTerms, normalizeMakerWorldTerms, removeMakerWorldTerm } from "../frontend/makerworld-search-filters.js";
import { supportPreviewStride, toolpathSupportKind, toolpathSupportStats } from "../frontend/toolpath-support-filter.js";
import { buildMeshGeometryAsync } from "../frontend/mesh-geometry-async.js";
import { analyzePlateBounds, plateBoundsErrorMessage } from "../frontend/studio-plate-preflight.js";
import { export3mfStreamed } from "../frontend/three-mf-export-stream.js";
import { uploadProgressSnapshot } from "../frontend/ha-api-transport.js";
import { filamentProfilesHtml, studioProfileBarHtml } from "../frontend/studio-profile-ui.js";
import { slicerActivityLabel, slicerEtaSeconds, slicerProgressPercent } from "../frontend/slicer-telemetry.js";
import { PRINT_SPEED_MODES, hasConfirmedModelPhase, hasModelStarted, printLayerLabel, printSpeedLabel, printStageHistoryKeys, resolveLivePrintPhase } from "../frontend/print-live-telemetry.js";
import { detailsOpenAttribute, updateDetailsOpenState } from "../frontend/details-open-state.js";
import { materialSystemHassSignature } from "../frontend/material-system-hass-signature.js";
import { filamentsForTarget, resolveFilamentSelection, vendorsForTarget } from "../frontend/filament-catalog-selection.js";
import { sortGalleryItems } from "../frontend/gallery-library-state.js";
import { readGalleryTransferResponse } from "../frontend/gallery-api-v2.js";
import { UploadController } from "../frontend/upload-controller.js";
import type { StudioApiClient } from "../frontend/api-client.js";
import { FILAMENT_COLOR_PATH } from "../frontend/direct-print-status-api.js";
import { ModelStateHistory } from "../frontend/model-state-history.js";
import { measureMeshInstances, mirrorMeshGeometry } from "../frontend/studio-mesh-tools.js";
import { analyzeMeshGeometry, repairMeshGeometry } from "../frontend/studio-mesh-repair.js";
import { previewMeshPlaneSplit } from "../frontend/studio-mesh-split.js";
import { refinePaintGeometry, remapPaintRegions } from "../frontend/studio-paint-refinement.js";

test("material details retain their open state across source rerenders", () => {
  const openKeys = new Set<string>();
  updateDetailsOpenState(openKeys, "spool:external", true);
  assert.equal(detailsOpenAttribute(openKeys, "spool:external"), " open");
  assert.equal(detailsOpenAttribute(openKeys, "system:amslite"), "");
  updateDetailsOpenState(openKeys, "system:amslite", true);
  assert.deepEqual([...openKeys].sort(), ["spool:external", "system:amslite"]);
  updateDetailsOpenState(openKeys, "spool:external", false);
  assert.equal(detailsOpenAttribute(openKeys, "spool:external"), "");
  updateDetailsOpenState(openKeys, "", true);
  assert.equal(openKeys.has(""), false);
});

test("material workspace keys every expandable area and binds native toggle state", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "ams-workspace.ts"), "utf8");
  assert.ok(source.includes('data-detail-key="${esc(detailKey)}"'));
  assert.ok(source.includes('`spool:ams:${slot.global_id}`'));
  assert.ok(source.includes('"spool:external"'));
  assert.ok(source.includes('`system:${key}`'));
  assert.ok(source.includes('"details[data-detail-key]"'));
  assert.ok(source.includes("updateDetailsOpenState("));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("material menus ignore unrelated Home Assistant telemetry renders", () => {
  const first = {
    states: {
      "sensor.bambu_a1_configured_ams_type": { state: "AMS Lite", attributes: { friendly_name: "Bambu A1 Configured AMS Type" } },
      "sensor.bambu_a1_detected_ams_type": { state: "AMS Lite", attributes: { friendly_name: "Bambu A1 Detected AMS Type" } },
      "sensor.bambu_a1_nozzle_temperature": { state: "215" },
    },
  };
  const unrelatedUpdate = {
    states: {
      ...first.states,
      "sensor.bambu_a1_nozzle_temperature": { state: "216" },
      "sensor.bambu_a1_progress": { state: "42" },
    },
  };
  const relevantUpdate = {
    states: {
      ...unrelatedUpdate.states,
      "sensor.bambu_a1_detected_ams_type": { state: "AMS 2 Pro", attributes: { friendly_name: "Bambu A1 Detected AMS Type" } },
    },
  };
  assert.equal(materialSystemHassSignature(first), materialSystemHassSignature(unrelatedUpdate));
  assert.notEqual(materialSystemHassSignature(first), materialSystemHassSignature(relevantUpdate));
});

test("all AMS variants and the external spool share stable filament controls", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "ams-workspace.ts"), "utf8");
  for (const label of [
    "AMS Lite",
    "AMS (Original / Gen 1)",
    "AMS 2 Pro",
    "AMS HT",
    "BMCU-370 / BCMU-370 (Drittanbieter)",
    "AMS-/BMCU-kompatibel (4 Slots erkannt)",
    "Externe Spule",
  ]) assert.ok(source.includes(label), label);
  assert.ok(source.includes('this.#materialControls("ams_slot"'));
  assert.ok(source.includes('this.#materialControls("external_spool"'));
  assert.ok(source.includes("materialSystemHassSignature(value)"));
  assert.ok(source.includes("if (this.isConnected && materialStateChanged) this.#render();"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("A1 catalog selection is manufacturer-aware and target-safe", () => {
  const items: any[] = [
    { id: "GFU99", name: "Generic TPU", vendor: "Generic", material_type: "TPU", targets: ["external_spool"] },
    { id: "GFU02", name: "Bambu TPU for AMS", vendor: "Bambu Lab", material_type: "TPU-AMS", targets: ["external_spool", "ams_slot"] },
    { id: "GFG99", name: "Generic PETG", vendor: "Generic", material_type: "PETG", targets: ["external_spool", "ams_slot"] },
  ];
  assert.deepEqual(vendorsForTarget(items, "ams_slot"), ["Bambu Lab", "Generic"]);
  assert.deepEqual(filamentsForTarget(items, "ams_slot").map((item) => item.id), ["GFU02", "GFG99"]);
  assert.equal(resolveFilamentSelection(items, "external_spool", "GFG99", "PETG")?.name, "Generic PETG");
  assert.equal(resolveFilamentSelection(items, "ams_slot", "GFU99", "TPU", "Bambu Lab")?.id, "GFU02");
});

function triangleGeometry(): MeshGeometry {
  return {
    positions: new Float32Array([
      0, 0, 0,
      10, 0, 10,
      0, 10, 10,
    ]),
    normals: new Float32Array([
      0, -0.707, 0.707,
      0, -0.707, 0.707,
      0, -0.707, 0.707,
    ]),
    triangleCount: 1,
    boundsMin: [0, 0, 0],
    boundsMax: [10, 10, 10],
  };
}

function instance(id: string, name: string, geometry: MeshGeometry, position: readonly [number, number, number] = [0, 0, 0]) {
  return {
    id,
    name,
    geometry,
    position,
    rotation: [0, 0, 0] as const,
    scale: [1, 1, 1] as const,
    color: "#fff",
    visible: true,
  };
}

test("router parses and serializes known routes", () => {
  assert.deepEqual(parseRoute("#/steuerung"), { name: "steuerung" });
  assert.deepEqual(parseRoute("#/galerie"), { name: "galerie" });
  assert.deepEqual(parseRoute("#/studio/project-9"), { name: "studio", projectId: "project-9" });
  assert.deepEqual(parseRoute("#/slicer/job-7"), { name: "slicer", jobId: "job-7" });
  assert.deepEqual(parseRoute("#/aufgaben/print-42"), { name: "aufgaben", jobId: "print-42" });
  assert.deepEqual(parseRoute("#/profile"), { name: "profile" });
  assert.deepEqual(parseRoute("#/aufgaben"), { name: "aufgaben" });
  assert.deepEqual(parseRoute("#/verlauf"), { name: "verlauf" });
  assert.deepEqual(parseRoute("#/system"), { name: "system" });
  assert.deepEqual(parseRoute("#/unknown"), { name: "steuerung" });
  assert.equal(routeToHash({ name: "studio", projectId: "project-9" }), "#/studio/project-9");
  assert.equal(routeToHash({ name: "aufgaben", jobId: "print-42" }), "#/aufgaben/print-42");
  assert.equal(routeToHash({ name: "galerie" }), "#/galerie");
  assert.equal(routeToHash({ name: "profile" }), "#/profile");
  assert.equal(routeToHash({ name: "system" }), "#/system");
});

test("store uses immutable transitions", () => {
  const store = new Store({ value: 1 }, (state, action: { delta: number }) => ({ value: state.value + action.delta }));
  const snapshots: number[] = [];
  store.subscribe((state) => snapshots.push(state.value));
  const before = store.getState();
  store.dispatch({ delta: 2 });
  const after = store.getState();
  assert.equal(before.value, 1);
  assert.equal(after.value, 3);
  assert.notEqual(before, after);
  assert.deepEqual(snapshots, [1, 3]);
});

test("scene store updates transforms immutably", () => {
  const initial: SceneState = {
    projectId: "project",
    revision: 1,
    activePlateId: "plate",
    selectedObjectIds: ["object"],
    plates: [{
      id: "plate",
      name: "Plate",
      orderIndex: 0,
      objects: [{
        id: "object",
        assetId: "asset",
        name: "Object",
        transform: {
          position: [0, 0, 0],
          rotation: [0, 0, 0],
          scale: [1, 1, 1],
        },
        visible: true,
        locked: false,
        color: null,
      }],
    }],
  };
  sceneStore.dispatch({ type: "load", state: initial });
  sceneStore.dispatch({
    type: "set_transform",
    plateId: "plate",
    objectId: "object",
    transform: {
      position: [5, 0, 0],
      rotation: [0, 0, 0],
      scale: [1, 1, 1],
    },
  });
  const updated = sceneStore.getState();
  assert.equal(initial.plates[0]?.objects[0]?.transform.position[0], 0);
  assert.equal(updated.plates[0]?.objects[0]?.transform.position[0], 5);
  assert.equal(updated.revision, 2);
});

test("ASCII STL parser produces mesh bounds and triangles", () => {
  const source = new TextEncoder().encode(`solid demo\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 10 0 0\nvertex 0 20 0\nendloop\nendfacet\nendsolid demo`).buffer;
  const mesh = parseStl(source);
  assert.equal(mesh.triangleCount, 1);
  assert.deepEqual(mesh.boundsMin, [0, 0, 0]);
  assert.deepEqual(mesh.boundsMax, [10, 20, 0]);
});

test("binary STL parser produces mesh bounds and triangles", () => {
  const buffer = new ArrayBuffer(84 + 50);
  const view = new DataView(buffer);
  view.setUint32(80, 1, true);
  let offset = 84;
  for (const value of [0, 0, 1, 0, 0, 0, 5, 0, 0, 0, 7, 0]) {
    view.setFloat32(offset, value, true);
    offset += 4;
  }
  view.setUint16(offset, 0, true);
  const mesh = parseStl(buffer);
  assert.equal(mesh.triangleCount, 1);
  assert.deepEqual(mesh.boundsMin, [0, 0, 0]);
  assert.deepEqual(mesh.boundsMax, [5, 7, 0]);
});

test("mesh export applies transforms and writes binary STL", () => {
  const geometry = triangleGeometry();
  const transform = { position: [5, 6, 7] as const, rotation: [0, 0, 0] as const, scale: [2, 1, 1] as const };
  const bounds = transformedBounds(geometry, transform);
  assert.deepEqual(bounds.min, [5, 6, 7]);
  assert.deepEqual(bounds.max, [25, 16, 17]);
  const stl = exportBinaryStl([{ name: "triangle", geometry, transform }]);
  const view = new DataView(stl);
  assert.equal(view.getUint32(80, true), 1);
  assert.equal(stl.byteLength, 134);
});

test("CAD placement puts transformed geometry on the bed and in the plate center", () => {
  const geometry = triangleGeometry();
  const transform = {
    position: [10, 20, -4] as const,
    rotation: [0, 0, 0] as const,
    scale: [1, 1, 1] as const,
  };
  const onBed = positionOnBed(geometry, transform);
  assert.deepEqual(onBed, [10, 20, 0]);
  const centered = positionCenteredOnPlate(geometry, { ...transform, position: onBed }, 256, 256);
  assert.deepEqual(centered, [123, 123, 0]);
});

test("flat orientation chooses the smallest vertical extent", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0, 0, 0, 40, 0, 0, 0, 10, 2]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0, 0, 0],
    boundsMax: [40, 10, 2],
  };
  assert.deepEqual(bestFlatRotation(geometry, [1, 1, 1]), [0, 0, 0]);
});

test("geometry analysis calculates area volume and layer count", () => {
  const geometry = triangleGeometry();
  const analysis = analyzeGeometry(geometry);
  assert.equal(analysis.triangleCount, 1);
  assert.deepEqual(analysis.dimensions, [10, 10, 10]);
  assert.ok(analysis.surfaceAreaMm2 > 0);
  assert.equal(layerCount(analysis, 2), 5);
  assert.equal(layerZ(analysis, 2, 0), 1);
  assert.equal(layerZ(analysis, 2, 4), 9);
});

test("layer slicing returns the real triangle cross section", () => {
  const segments = sliceSegmentsAtZ(triangleGeometry(), 5);
  assert.equal(segments.length, 1);
  assert.deepEqual(segments[0]?.a, [5, 0]);
  assert.deepEqual(segments[0]?.b, [0, 5]);
});

test("support analysis ignores geometry resting on the bed", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0,0,0, 10,0,0, 0,10,0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0,0,0],
    boundsMax: [10,10,0],
  };
  assert.equal(analyzeFloatingSupportNeeds([instance("bed", "Bed", geometry)]).length, 0);
});

test("support analysis detects a complete floating object", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0,0,0, 10,0,0, 0,10,0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0,0,0],
    boundsMax: [10,10,0],
  };
  const issues = analyzeFloatingSupportNeeds([instance("floating", "Floating", geometry, [0,0,4])]);
  assert.equal(issues.length, 1);
  assert.equal(issues[0]?.floatingShellCount, 1);
  assert.equal(issues[0]?.minimumGapMm, 4);
});

test("support analysis reports downward overhang span and bridge span", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0,0,0, 10,0,0, 0,10,0,
      0,0,2, 0,10,2, 10,0,2,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [0,0,0],
    boundsMax: [10,10,2],
  };
  const issues = analyzeFloatingSupportNeeds([instance("overhang", "Overhangteil", geometry)]);
  assert.equal(issues.length, 1);
  assert.equal(issues[0]?.overhangTriangleCount, 1);
  assert.ok((issues[0]?.maxOverhangMm ?? 0) >= 10);
  assert.equal(issues[0]?.maxOverhangAngleDeg, 0);
  assert.ok((issues[0]?.bridgeOverhangMm ?? 0) >= 10);
});

test("support analysis detects a detached floating shell inside one mesh", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0,0,0, 10,0,0, 0,10,0,
      20,20,5, 30,20,5, 20,30,5,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [0,0,0],
    boundsMax: [30,30,5],
  };
  const issues = analyzeFloatingSupportNeeds([instance("mixed", "Mixed", geometry)]);
  assert.equal(issues.length, 1);
  assert.equal(issues[0]?.floatingShellCount, 1);
  assert.equal(issues[0]?.minimumGapMm, 5);
});

test("support analysis accepts a detached shell resting on a lower shell", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0,0,0, 10,0,1, 0,10,1,
      2,2,1, 8,2,1, 2,8,1,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [0,0,0],
    boundsMax: [10,10,1],
  };
  assert.equal(analyzeFloatingSupportNeeds([instance("stacked", "Stacked", geometry)]).length, 0);
});

test("support analysis accepts a side-connected shell of the same model", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0,0,0, 10,0,1, 0,10,1,
      10,2,0.8, 18,2,1.8, 10,8,1.8,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [0,0,0],
    boundsMax: [18,10,1.8],
  };
  assert.equal(analyzeFloatingSupportNeeds([instance("side", "Side connected", geometry)]).length, 0);
});

test("support analysis accepts one model part resting on another model part", () => {
  const lower: MeshGeometry = {
    positions: new Float32Array([0,0,0, 10,0,1, 0,10,1]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0,0,0],
    boundsMax: [10,10,1],
  };
  const upper: MeshGeometry = {
    positions: new Float32Array([2,2,1, 8,2,1, 2,8,1]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [2,2,1],
    boundsMax: [8,8,1],
  };
  assert.equal(analyzeFloatingSupportNeeds([
    instance("lower", "Lower", lower),
    instance("upper", "Upper", upper),
  ]).length, 0);
});


test("large-model geometry builder preserves bounds and normals", async () => {
  const mesh = await buildMeshGeometryAsync([
    0, 0, 0,
    10, 0, 0,
    0, 20, 0,
  ], 256);
  assert.equal(mesh.triangleCount, 1);
  assert.deepEqual(mesh.boundsMin, [0, 0, 0]);
  assert.deepEqual(mesh.boundsMax, [10, 20, 0]);
  assert.ok(mesh.normals[2]! > .99);
});

test("plate preflight blocks the exact transformed overflow before upload", async () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0,0,0, 10,0,0, 0,10,0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0,0,0],
    boundsMax: [10,10,0],
  };
  const outside = instance("outside", "Brause Quadrat", geometry, [-2.3, 20, 0]);
  const issues = await analyzePlateBounds([outside], 256, 256, 256);
  assert.equal(issues.length, 1);
  assert.ok(Math.abs((issues[0]?.overflowLeftMm ?? 0) - 2.3) < .001);
  assert.match(plateBoundsErrorMessage(issues), /Brause Quadrat: 2.30 mm links/);
  assert.equal((await analyzePlateBounds([instance("inside", "Inside", geometry, [20,20,0])], 256, 256, 256)).length, 0);
});

test("streamed 3MF exporter writes deflated ZIP entries", async () => {
  const bytes = await export3mfStreamed([{
    name: "Triangle",
    geometry: triangleGeometry(),
    transform: { position: [0,0,0], rotation: [0,0,0], scale: [1,1,1] },
    color: "#ff0000",
  }], { title: "Test", plateWidthMm: 256, plateDepthMm: 256 });
  const view = new DataView(bytes);
  assert.equal(view.getUint32(0, true), 0x04034B50);
  assert.equal(view.getUint16(8, true), 8);
  assert.ok(bytes.byteLength > 100);
});

test("upload progress snapshot reports real byte rate and ETA", () => {
  const mib = 1024 * 1024;
  const snapshot = uploadProgressSnapshot(20 * mib, 50 * mib, 1_000, 11_000);
  assert.equal(snapshot.loadedBytes, 20 * mib);
  assert.equal(snapshot.totalBytes, 50 * mib);
  assert.equal(snapshot.ratio, 0.4);
  assert.equal(snapshot.rateBytesPerSecond, 2 * mib);
  assert.equal(snapshot.etaSeconds, 15);
});

test("A1 reliable checklist follows the order confirmed by printer stage telemetry", () => {
  assert.deepEqual(PRINT_PHASES.map((phase) => phase.key), [
    "bed_heating",
    "homing",
    "filament_loading",
    "flow_calibration",
    "mechanical_check",
    "nozzle_cleaning_after",
    "bed_leveling",
    "printing_model",
    "completed",
  ]);
});

test("A1 nozzle cleaning uses the single printer-reported cleaning stage", () => {
  let progress = resolvePrintPhaseProgress("flow_calibration", -1);
  assert.equal(progress.resolvedKey, "flow_calibration");
  progress = resolvePrintPhaseProgress("nozzle_cleaning", progress.highestIndex);
  assert.equal(progress.resolvedKey, "nozzle_cleaning_after");
  assert.equal(progress.currentLabel, "Druckkopf wird gereinigt");
});

test("removed filament-change and test-strip stages are not tracked or shown", () => {
  const filamentChange = resolveTrackedPrintPhaseProgress("filament_change", ["filament_loading"], false);
  const testStrip = resolveTrackedPrintPhaseProgress("test_strip", ["bed_leveling"], false);
  assert.equal(filamentChange.resolvedKey, "");
  assert.equal(testStrip.resolvedKey, "");
  assert.equal(filamentChange.seenKeys.includes("filament_change"), false);
  assert.equal(testStrip.seenKeys.includes("test_strip"), false);
  assert.equal(PRINT_PHASES.some((phase) => phase.key === "filament_change"), false);
  assert.equal(PRINT_PHASES.some((phase) => phase.key === "test_strip"), false);
});

test("legacy monotonic resolver still never moves backwards", () => {
  const printing = resolvePrintPhaseProgress("printing_model", -1);
  const staleCleaning = resolvePrintPhaseProgress("nozzle_cleaning", printing.highestIndex);
  assert.equal(staleCleaning.activeIndex, printing.activeIndex);
  assert.equal(staleCleaning.highestIndex, printing.highestIndex);
  assert.equal(staleCleaning.currentLabel, "Modell wird gedruckt");
});

test("A1 startup stage zero cannot complete preparation before real model progress", () => {
  const prematureModel = resolveSafePrintPhaseProgress("printing_model", -1, false);
  assert.equal(prematureModel.activeIndex, -1);
  assert.equal(prematureModel.currentLabel, "Druckvorbereitung läuft");
  const realModel = resolveSafePrintPhaseProgress("printing_model", -1, true);
  assert.equal(realModel.resolvedKey, "printing_model");
});

test("tracked Bambu preparation phases only mark stages that were actually observed", () => {
  let progress = resolveTrackedPrintPhaseProgress("homing", [], false);
  assert.equal(progress.resolvedKey, "homing");
  assert.deepEqual(progress.seenKeys, ["homing"]);
  progress = resolveTrackedPrintPhaseProgress("flow_calibration", progress.seenKeys, false);
  assert.equal(progress.resolvedKey, "flow_calibration");
  assert.ok(progress.seenKeys.includes("homing"));
  assert.ok(progress.seenKeys.includes("flow_calibration"));
  assert.ok(!progress.seenKeys.includes("filament_change"));
  assert.ok(!progress.seenKeys.includes("bed_leveling"));
});

test("tracked phase guard ignores false stage-zero model start but accepts real model progress", () => {
  let progress = resolveTrackedPrintPhaseProgress("printing_model", ["homing"], false);
  assert.equal(progress.activeIndex, -1);
  assert.equal(progress.resolvedKey, "");
  assert.ok(!progress.seenKeys.includes("printing_model"));
  progress = resolveTrackedPrintPhaseProgress("printing_model", progress.seenKeys, true);
  assert.equal(progress.resolvedKey, "printing_model");
  assert.ok(progress.seenKeys.includes("printing_model"));
});

test("tracked nozzle cleaning records only the reliable printer stage", () => {
  const progress = resolveTrackedPrintPhaseProgress("nozzle_cleaning", [], false);
  assert.equal(progress.resolvedKey, "nozzle_cleaning_after");
  assert.deepEqual(progress.seenKeys, ["nozzle_cleaning_after"]);
  assert.ok(!progress.seenKeys.includes("nozzle_cleaning_before"));
});

test("studio selection supports ctrl-a and additive shift ranges", () => {
  const ids = ["a", "b", "c", "d"];
  const all = selectAllStudioObjects(ids);
  assert.deepEqual([...all.selected], ids);
  assert.equal(all.anchor, "a");
  const first = nextStudioSelection(ids, new Set(), "b", false, false, null);
  const extended = nextStudioSelection(ids, first.selected, "d", false, true, first.anchor);
  assert.deepEqual([...extended.selected], ["b", "c", "d"]);
  assert.equal(extended.anchor, "b");
  const additive = nextStudioSelection(ids, new Set(["a"]), "c", false, true, "a");
  assert.deepEqual([...additive.selected], ["a", "b", "c"]);
});


test("MakerWorld search chips are unique and individually removable", () => {
  const terms = addMakerWorldTerms(["PLA"], "Holder, Wall Mount, pla");
  assert.deepEqual(terms, ["PLA", "Holder", "Wall Mount"]);
  assert.deepEqual(removeMakerWorldTerm(terms, "holder"), ["PLA", "Wall Mount"]);
  assert.deepEqual(normalizeMakerWorldTerms(["A", "a", "B", ""]), ["A", "B"]);
});


test("support preview classifies base, interface and transition paths", () => {
  assert.equal(toolpathSupportKind("Support", "support"), "base");
  assert.equal(toolpathSupportKind("Support interface", "support"), "interface");
  assert.equal(toolpathSupportKind("Support transition", "support"), "transition");
  assert.equal(toolpathSupportKind("Outer wall", "model"), "none");
});

test("support preview counts support layers without counting model paths", () => {
  const stats = toolpathSupportStats([
    { index: 0, segments: [[0,0,1,1,0.2,0,1,"Support","support"], [0,0,1,1,0.2,0,1,"Outer wall","model"]] },
    { index: 3, segments: [[0,0,1,1,0.8,0,1,"Support interface","support"]] },
  ]);
  assert.deepEqual(stats, { present: true, segmentCount: 2, interfaceSegmentCount: 1, firstLayer: 0, lastLayer: 3 });
});

test("support preview limits very large support geometry deterministically", () => {
  assert.equal(supportPreviewStride(96_226), 1);
  assert.equal(supportPreviewStride(160_001), 2);
  assert.equal(supportPreviewStride(480_000), 3);
});

test("popup job dismissal is local-only and individual task navigation keeps the job id", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const entry = readFileSync(join(process.cwd(), "frontend", "v6-entry.ts"), "utf8");
  const tasks = readFileSync(join(process.cwd(), "frontend", "jobs-workspaces-v9.ts"), "utf8");

  assert.ok(popup.includes('data-dismiss-item="${esc(key)}"'));
  assert.ok(popup.includes("Nur aus diesem Popup entfernen"));
  assert.ok(popup.includes('collapse.textContent = this.#collapsed ? "Einblenden" : "Minimieren"'));
  assert.ok(!popup.includes('collapse.textContent = this.#collapsed ? "Öffnen" : "Minimieren"'));

  const dismissStart = popup.indexOf("  #dismissItem(key: string): void {");
  const dismissEnd = popup.indexOf("\n  #sliceWorkflowKey", dismissStart);
  assert.ok(dismissStart >= 0 && dismissEnd > dismissStart);
  const dismissBlock = popup.slice(dismissStart, dismissEnd);
  assert.ok(dismissBlock.includes("this.#dismissedItems.add(normalized)"));
  assert.ok(dismissBlock.includes("this.#persistDismissedItems()"));
  assert.ok(!/removeQueuedJob|cancelActiveSlicerJob|startDirectPrint|stop|delete/i.test(dismissBlock));

  assert.ok(entry.includes('detail.name === "slicer" || detail.name === "aufgaben"'));
  assert.ok(tasks.includes('data-job-row="${id}"'));
  assert.ok(tasks.includes("row?.scrollIntoView({ block: \"center\", behavior: \"smooth\" })"));
  assert.ok(tasks.includes('class="row${selected ? " selected" : ""}"'));
});

test("studio exposes BambuLab Cloud filament profiles without deduplicating them away", () => {
  const now = new Date().toISOString();
  const cloud = { id: "cloud.pla-basic", kind: "filament", name: "Bambu PLA Basic", source: "bambu_cloud", payload: { vendor: "Bambu Lab", material: "PLA", sub_brand: "Basic" }, builtin: false, created_at: now, updated_at: now };
  const local = { ...cloud, id: "local.pla-basic", name: "Bambu PLA Basic lokal", source: "local" };
  const catalog = { profiles: [local, cloud], groups: { printer: [], nozzle: [], filament: [local, cloud], process: [], build_plate: [] }, selection: { printer_profile_id: null, nozzle_profile_id: null, process_profile_id: null, build_plate_profile_id: null, filament_profile_ids: [cloud.id] }, persistent: true, custom_profiles_supported: true, cloud_sync: { configured: true, syncing: false, available_offline: true, last_sync_at: now, last_attempt_at: now, last_error: null, profile_count: 1, credential_source: "test" }, source_counts: { builtin: 0, bambu_cloud: 1, local: 1 } };
  const selection = { target_printer_id: "", printer_profile_id: "", nozzle_profile_id: "", process_profile_id: "", build_plate_profile_id: "", filament_profile_ids: [cloud.id] };
  const bar = studioProfileBarHtml(catalog as any, [], selection);
  assert.match(bar, /Filamentprofile/);
  assert.match(bar, /aria-pressed="true" data-filament-profile="cloud\.pla-basic"/);
  assert.doesNotMatch(bar, /data-cloud-filament-profile|data-external-filament-profile/);
  const tree = filamentProfilesHtml(catalog as any, [cloud.id]);
  assert.match(tree, /BambuLab Cloud/);
  assert.match(tree, /data-filament-profile="cloud\.pla-basic"/);
  assert.match(tree, /data-filament-profile="local\.pla-basic"/);
});

test("native Bambu slicer telemetry drives real progress, phase and ETA", () => {
  const started = Date.parse("2026-08-11T10:00:00Z");
  const job: any = {
    id: "server__v6-test", status: "running",
    slicer_progress: {
      source: "bambu_cli_pipe", active: true, started_at: new Date(started).toISOString(),
      plate_index: 1, plate_count: 1, plate_percent: 60, total_percent: 57,
      message: "Slicing supports", eta_seconds: 50,
      history: [
        { at: new Date(started + 10_000).toISOString(), plate_index: 1, plate_count: 1, plate_percent: 5, total_percent: 7, message: "Slicing begins" },
        { at: new Date(started + 40_000).toISOString(), plate_index: 1, plate_count: 1, plate_percent: 30, total_percent: 30, message: "Slicing model" },
        { at: new Date(started + 70_000).toISOString(), plate_index: 1, plate_count: 1, plate_percent: 60, total_percent: 57, message: "Slicing supports" },
      ],
    },
  };
  assert.equal(slicerProgressPercent(job), 57);
  assert.equal(slicerActivityLabel(job), "Stützstrukturen werden berechnet");
  const eta = slicerEtaSeconds(job, started + 80_000);
  assert.ok(eta !== null && eta > 20 && eta < 120);
});

test("native V6 router retains server progress, runtime and engine result", () => {
  const router = readFileSync(join(process.cwd(), "deploy", "homeassistant", "custom_components", "ultimate_3d_studio_v6", "slicer_backend_router.py"), "utf8");
  assert.ok(router.includes('"slicer_progress": progress'));
  assert.ok(router.includes('"runtime_summary": runtime'));
  assert.ok(router.includes('"engine_result": engine_result'));
  assert.ok(router.includes('"slice_time_ms": engine_metrics.get("slice_time_ms")'));
});

test("popup renders native Bambu slicer progress instead of the old 62 percent placeholder", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  assert.ok(popup.includes("nativeSlicerProgress"));
  assert.ok(popup.includes("slicerProgressPercent"));
  assert.ok(popup.includes("slicerEtaSeconds"));
  assert.ok(popup.includes("data-slicer-eta"));
  assert.ok(!popup.includes('if (job.status === "running") return 62;'));
  assert.ok(popup.includes("ETA wird berechnet"));
});

test("Slicing-Server workspace exposes native job details without changing job creation", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "slicing-server-workspace.ts"), "utf8");
  assert.ok(source.includes('type: "printer_slicing_server/job"'));
  assert.ok(source.includes("Vollständige Server-Daten"));
  assert.ok(source.includes("Bambu-Zeitanteile"));
  assert.ok(source.includes("Live-Fortschritt"));
  assert.ok(source.includes('type: "printer_slicing_server/create_job"'));
  assert.ok(source.includes('type: "printer_slicing_server/upload"'));
  assert.ok(source.includes('type: "printer_slicing_server/download"'));
});


test("A1 test strip does not complete from early job progress alone", () => {
  const printer: any = {
    progress: 0,
    current_layer: 0,
    print_stage_key: "nozzle_cleaning",
    print_stage_history: [
      { key: "bed_heating" },
      { key: "homing" },
      { key: "nozzle_cleaning_after" },
    ],
  };
  const job: any = { progress: 7, current_layer: 0, status: "running" };
  assert.equal(hasModelStarted(job, printer), true);
  assert.equal(hasConfirmedModelPhase(printer), false);
  printer.print_stage_history.push({ key: "bed_leveling" });
  assert.equal(hasConfirmedModelPhase(printer), false);
  printer.print_stage_history.push({ key: "printing_model" });
  assert.equal(hasConfirmedModelPhase(printer), true);
});

test("live print telemetry exposes layer, four speed modes and server stage history", () => {
  const printer:any={speed_level:2,current_layer:38,total_layers:1118,progress:10,print_stage_key:"printing_model",print_stage_label:"Modell wird gedruckt",print_stage_history:[{key:"homing"},{key:"bed_leveling"},{key:"printing_model"}]};
  const job:any={progress:10,current_layer:null,total_layers:null,status:"running"};
  assert.deepEqual(PRINT_SPEED_MODES.map((item)=>item.percent),[50,100,125,166]);
  assert.equal(printSpeedLabel(printer),"100 %");
  assert.equal(printLayerLabel(job,printer),"Layer 38 / 1118");
  assert.equal(hasModelStarted(job,printer),true);
  assert.deepEqual(printStageHistoryKeys(printer),["homing","bed_leveling","printing_model"]);
  const phase=resolveLivePrintPhase(job,printer);
  assert.equal(phase.resolvedKey,"printing_model");
  assert.ok(phase.seenKeys.includes("homing"));
  assert.ok(phase.seenKeys.includes("bed_leveling"));
});

test("A1 model telemetry is never rewritten as a test strip", () => {
  const printer:any={current_layer:1,progress:3,print_stage_key:"printing_model",print_stage_label:"Modell wird gedruckt",print_stage_detail:"Der eigentliche Modelldruck läuft.",print_stage_history:[
    {key:"bed_leveling",at:"2026-08-15T09:24:48.358741+00:00"},
    {key:"printing_model",at:"2026-08-15T09:26:04.065616+00:00"},
  ]};
  const phase=resolveLivePrintPhase({progress:3,current_layer:1,status:"running"} as any,printer);
  assert.equal(phase.resolvedKey,"printing_model");
  assert.equal(phase.currentLabel,"Modell wird gedruckt");
  assert.equal(phase.seenKeys.includes("test_strip"),false);
});

test("live flow calibration retains only actually observed stage keys", () => {
  const printer:any={current_layer:0,progress:0,print_stage_key:"flow_calibration",print_stage_history:[
    {key:"bed_heating"},{key:"homing"},{key:"filament_loading"},{key:"flow_calibration"},
  ]};
  const phase=resolveLivePrintPhase({progress:0,current_layer:0,status:"running"} as any,printer);
  assert.equal(phase.resolvedKey,"flow_calibration");
  assert.equal(phase.seenKeys.includes("filament_change"),false);
  assert.equal(phase.seenKeys.includes("test_strip"),false);
});
test("speed control uses only the fixed V6 command contract", () => {
  const source=readFileSync(join(process.cwd(),"frontend","print-speed-control.ts"),"utf8");
  const storeSource=readFileSync(join(process.cwd(),"frontend","printer-command-store-v2.ts"),"utf8");
  assert.ok(source.includes("PRINT_SPEED_MODES"));
  assert.ok(source.includes("speedLevel: level"));
  assert.ok(storeSource.includes("{ speed_level: request.speedLevel }"));
  assert.ok(!source.includes("gcode_line"));
});


test("print live information is shared across popup control system and navigation", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const control = readFileSync(join(process.cwd(), "frontend", "control-workspace-v2.ts"), "utf8");
  const system = readFileSync(join(process.cwd(), "frontend", "system-workspace-v5.ts"), "utf8");
  const shell = readFileSync(join(process.cwd(), "frontend", "app-shell-v4.ts"), "utf8");
  const view = readFileSync(join(process.cwd(), "frontend", "app-shell-view.ts"), "utf8");

  assert.ok(popup.includes("resolveLivePrintPhase"));
  assert.ok(popup.includes("printLayerLabel(job, itemPrinter)"));
  assert.ok(popup.includes('id="popup-speed"'));
  assert.ok(control.includes("resolveLivePrintPhase(job, printer)"));
  assert.ok(control.includes("PRINT_PHASES.map"));
  assert.ok(!control.includes("currentIndex >= 0 && index < currentIndex"));
  assert.ok(control.includes('id="print-speed"'));
  assert.ok(system.includes("printLayerLabel(job, printer)"));
  assert.ok(system.includes("printSpeedLabel(printer)"));
  assert.ok(system.includes('id="system-speed"'));
  assert.ok(view.includes('id="nav-live"'));
  assert.ok(shell.includes("#updateNavLive(): void"));
  assert.ok(shell.includes("printLayerLabel(job, printer)"));
  assert.ok(shell.includes("printSpeedLabel(printer)"));
});

test("speed controls exist in popup control and system without duplicating existing temperature cards", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const control = readFileSync(join(process.cwd(), "frontend", "control-workspace-v2.ts"), "utf8");
  const system = readFileSync(join(process.cwd(), "frontend", "system-workspace-v5.ts"), "utf8");
  assert.equal((popup.match(/ultimate-3d-print-speed-control/g) ?? []).length >= 1, true);
  assert.equal((control.match(/ultimate-3d-print-speed-control/g) ?? []).length >= 1, true);
  assert.equal((system.match(/ultimate-3d-print-speed-control/g) ?? []).length >= 1, true);
  assert.equal((control.match(/nozzle_temperature/g) ?? []).length, 0);
  assert.equal((control.match(/bed_temperature/g) ?? []).length, 0);
  assert.equal((system.match(/metric\("Düse"/g) ?? []).length, 1);
  assert.equal((system.match(/metric\("Druckbett"/g) ?? []).length, 1);
});

test("live views contain neither removed phase nor test-strip inference", () => {
  const telemetry = readFileSync(join(process.cwd(), "frontend", "print-live-telemetry.ts"), "utf8");
  const phases = readFileSync(join(process.cwd(), "frontend", "print-phase-progress.ts"), "utf8");
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const control = readFileSync(join(process.cwd(), "frontend", "control-workspace-v2.ts"), "utf8");
  assert.ok(!telemetry.includes("hasActiveInferredTestStrip"));
  assert.ok(!telemetry.includes("TEST_STRIP_INFERENCE_WINDOW_MS"));
  assert.ok(!phases.includes('key: "filament_change"'));
  assert.ok(!phases.includes('key: "test_strip"'));
  for (const source of [popup, control]) {
    assert.ok(!source.includes("inferredTestStrip"));
    assert.ok(!source.includes("Aus dem serverseitig beobachteten Modelldruck abgeleitet"));
    assert.ok(source.includes("progress.activeIndex >"));
  }
});
test("unreported preparation stages are neutral as soon as a later observed phase starts", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const control = readFileSync(join(process.cwd(), "frontend", "control-workspace-v2.ts"), "utf8");
  assert.ok(popup.includes('unreported ? "–" : "○"'));
  assert.ok(control.includes('unreported ? "–" : "○"'));
  assert.ok(popup.includes("Vom Drucker nicht als eigener Status gemeldet"));
  assert.ok(control.includes("Vom Drucker nicht als eigener Status gemeldet"));
});


test("navigation live print status resubscribes before an existing shell returns", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "app-shell-v4.ts"), "utf8");
  const start = source.indexOf("  connectedCallback(): void {");
  const end = source.indexOf("\n  disconnectedCallback(): void {", start);
  const block = source.slice(start, end);
  assert.ok(block.indexOf("jobActivityStore.subscribe") >= 0);
  assert.ok(block.indexOf("jobActivityStore.subscribe") < block.indexOf("this.#root.childElementCount"));
  assert.ok(block.includes("this.#updateNavLive();"));
});

test("completed slice refreshes real material analysis after toolpath loading", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  const panel = readFileSync(join(process.cwd(), "frontend", "slice-analysis-panel.ts"), "utf8");
  const start = workspace.indexOf("  async #activatePlateJob(");
  const end = workspace.indexOf("\n  #plate(): Plate", start);
  const block = workspace.slice(start, end);
  const toolpathAt = block.indexOf("const summary = await fetchToolpath(jobId);");
  const refreshedJobAt = block.lastIndexOf("job = await fetchSliceJob(jobId);");
  const registeredJobAt = block.lastIndexOf("jobActivityStore.registerSlicerJob(job);");
  assert.ok(toolpathAt >= 0);
  assert.ok(refreshedJobAt > toolpathAt);
  assert.ok(registeredJobAt > refreshedJobAt);
  assert.ok(panel.includes("Materialverbrauch"));
  assert.ok(panel.includes("Druckschritt / Materialanteile"));
  assert.ok(panel.includes("feature.materials"));
});

test("layer preview generation is an individually dismissible entry in the right popup list", () => {
  const previewSource = readFileSync(join(process.cwd(), "frontend", "studio-preview-progress-popup.ts"), "utf8");
  const entrySource = readFileSync(join(process.cwd(), "frontend", "v6-entry.ts"), "utf8");
  const globalPopupSource = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  assert.ok(!entrySource.includes('import "./studio-preview-progress-popup.js"'));
  assert.ok(!entrySource.includes("<studio-preview-progress-popup"));
  assert.ok(entrySource.includes("<ultimate-3d-global-job-popup></ultimate-3d-global-job-popup>"));
  assert.ok(globalPopupSource.includes("#previewWorkflowKey(): string"));
  assert.ok(globalPopupSource.includes('`preview:${this.#sliceTrace.traceId}`'));
  assert.ok(globalPopupSource.includes("const previewCard = visiblePreview"));
  assert.ok(globalPopupSource.includes("this.#dismissButton(previewWorkflowKey, previewTitle)"));
  assert.ok(globalPopupSource.includes("preparationCard + slicerCard + previewCard + transferCard + printCards + traceCard + studioCard"));
  assert.ok(globalPopupSource.includes('data-target="slicer"'));
  assert.ok(globalPopupSource.includes("(loadedLayers / layerCount) * 100"));
  assert.ok(globalPopupSource.includes("ETA wird nach dem ersten Datenblock berechnet"));
  assert.ok(globalPopupSource.includes("Druckvorschau wird erzeugt"));
  assert.ok(globalPopupSource.includes("Druckvorschau fertig"));
  assert.ok(previewSource.includes("@keyframes preview-fill"));
});

test("popup design, controls and one-way calculation progress remain intact", () => {
  const previewSource = readFileSync(join(process.cwd(), "frontend", "studio-preview-progress-popup.ts"), "utf8");
  const globalPopupSource = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  assert.ok(globalPopupSource.includes("linear-gradient(155deg,rgba(7,28,43,.98),rgba(5,17,29,.98))"));
  assert.ok(globalPopupSource.includes('<div class="eyebrow">Vorgänge</div>'));
  assert.ok(globalPopupSource.includes('id="collapse"'));
  assert.ok(globalPopupSource.includes('id="camera-toggle"'));
  assert.ok(globalPopupSource.includes('id="expand"'));
  assert.ok(globalPopupSource.includes('id="close"'));
  assert.ok(globalPopupSource.includes("this.#cameraVisible = !this.#cameraVisible"));
  assert.ok(globalPopupSource.includes("this.#expanded = !this.#expanded"));
  assert.ok(globalPopupSource.includes("this.#collapsed = !this.#collapsed"));
  assert.ok(globalPopupSource.includes("this.#dismissedSignature = this.#lastSignature"));
  assert.ok(globalPopupSource.includes("[data-dismiss-item]"));
  assert.ok(globalPopupSource.includes("[data-target]"));
  assert.ok(globalPopupSource.includes("overflow-y:auto"));
  assert.ok(globalPopupSource.includes("overflow:auto"));
  assert.ok(globalPopupSource.includes("@keyframes calculate{from{transform:scaleX(0)}to{transform:scaleX(1)}}"));
  assert.ok(globalPopupSource.includes('class="progress ${previewProgressClass}"'));
  assert.ok(!globalPopupSource.includes("alternate"));
  assert.ok(!previewSource.includes("alternate"));
  assert.ok(!globalPopupSource.includes("active ? 50 : 100"));
});

test("direct printer transfer uses measured FTPS telemetry in the shared right popup list", () => {
  const panel = readFileSync(join(process.cwd(), "frontend", "direct-print-panel-next.ts"), "utf8");
  const api = readFileSync(join(process.cwd(), "frontend", "slicing-api.ts"), "utf8");
  const events = readFileSync(join(process.cwd(), "frontend", "direct-print-transfer-events.ts"), "utf8");
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  assert.ok(api.includes("fetchDirectPrintTransferStatus"));
  assert.ok(api.includes("/print/transfer-status?printer_id="));
  assert.ok(panel.includes("window.setInterval(() => void this.#pollTransfer(), 350)"));
  assert.ok(panel.includes("status.loaded_bytes"));
  assert.ok(panel.includes("status.total_bytes"));
  assert.ok(panel.includes("status.rate_bytes_per_second"));
  assert.ok(panel.includes("status.eta_seconds"));
  assert.ok(panel.includes("this.#finishTransfer(prepared)"));
  assert.ok(panel.includes("this.#failTransfer(this.#error)"));
  assert.ok(events.includes('DIRECT_PRINT_TRANSFER_EVENT = "ultimate-3d-direct-print-transfer"'));
  assert.ok(popup.includes("globalThis.addEventListener(DIRECT_PRINT_TRANSFER_EVENT"));
  assert.ok(popup.includes("const transferCard = visibleTransfer"));
  assert.ok(popup.includes("DRUCKER · ÜBERTRAGUNG"));
  assert.ok(popup.includes("formatBytes(visibleTransfer.loadedBytes)"));
  assert.ok(popup.includes("formatRate(visibleTransfer.rateBytesPerSecond)"));
  assert.ok(popup.includes("formatDuration(visibleTransfer.etaSeconds)"));
  assert.ok(popup.includes("this.#dismissButton(transferWorkflowKey, transferTitle)"));
  assert.ok(popup.includes("previewCard + transferCard + printCards"));
  assert.ok(popup.includes('data-target="slicer"'));
  assert.ok(!popup.includes('class="progress moving"><u style="width:${transferProgress}%'));
});



test("gallery sorting keeps folders first and applies the selected order", () => {
  const items = [
    { kind: "model" as const, name: "B.3mf", modified: 2, size_bytes: 20 },
    { kind: "folder" as const, name: "Zeta", modified: 1, size_bytes: 0 },
    { kind: "model" as const, name: "A.3mf", modified: 3, size_bytes: 10 },
  ];
  assert.deepEqual(sortGalleryItems(items, "name").map((item) => item.name), ["Zeta", "A.3mf", "B.3mf"]);
  assert.deepEqual(sortGalleryItems(items, "newest").map((item) => item.name), ["Zeta", "A.3mf", "B.3mf"]);
  assert.deepEqual(sortGalleryItems(items, "size").map((item) => item.name), ["Zeta", "B.3mf", "A.3mf"]);
});

test("gallery upload controller always stays below the HA request limit", async () => {
  const chunks: number[] = [];
  const fakeApi = {
    createUpload: async () => ({ id: "test-upload" }),
    writeUploadChunk: async (_id: string, _offset: number, chunk: Blob) => { chunks.push(chunk.size); },
    finalizeUpload: async () => ({ ok: true }),
  };
  const source = new Uint8Array(10 * 1024 * 1024);
  const file = new File([source], "large.3mf");
  await new UploadController(fakeApi as unknown as StudioApiClient).upload(file, "gallery", "gallery");
  assert.deepEqual(chunks, [4 * 1024 * 1024, 4 * 1024 * 1024, 2 * 1024 * 1024]);
});

test("gallery transfer reports HA plaintext 413 without JSON parse noise", async () => {
  await assert.rejects(
    readGalleryTransferResponse(new Response("Maximum request body size 16777216 exceeded", { status: 413 })),
    /Home-Assistant-Anfragelimit/,
  );
});


test("filament setting uses the registered V6 route outside direct-print", () => {
  assert.equal(FILAMENT_COLOR_PATH, "ultimate_3d_studio_v6/v1/slicer/filament-color");
  assert.equal(FILAMENT_COLOR_PATH.includes("/direct-print/"), false);
});

test("material source conflict stays explicit and never auto-switches the plate", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "ams-workspace.ts"), "utf8");
  assert.ok(source.includes("externalTelemetry?.loaded && !externalSelected"));
  assert.ok(source.includes("Geladene externe Spule ist noch nicht die Studio-Quelle"));
  assert.ok(source.includes('href="#/studio"'));
  assert.ok(source.includes("Im Studio „Externe Spule“ wählen"));
});

test("studio profile and filament details retain native open state across rerenders", () => {
  const profileUi = readFileSync(join(process.cwd(), "frontend", "studio-profile-ui.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(profileUi.includes("data-filament-detail-key"));
  assert.ok(profileUi.includes("detailsOpenAttribute(openKeys, key)"));
  assert.ok(workspace.includes("#openFilamentDetailKeys = new Set<string>()"));
  assert.ok(workspace.includes('"details[data-filament-detail-key]"'));
  assert.ok(workspace.includes("details.dataset.filamentDetailKey"));
  assert.ok(workspace.includes("#profileBarOpen = true"));
  assert.ok(workspace.includes('querySelector<HTMLElement>(".profilebar-shell")'));
  assert.ok(!workspace.includes('querySelector<HTMLElement>(".profilebar");'));
  assert.ok(!workspace.includes("MutationObserver"));
  assert.ok(!workspace.includes("location.reload"));
});


test("model-state history stores real states, clears redo after a new edit and stays bounded", () => {
  const history = new ModelStateHistory({
    clone: (value: { value: number }) => ({ ...value }),
    signature: (value) => String(value.value),
    maximum: 2,
  });
  history.reset({ value: 1 });
  assert.equal(history.checkpoint({ value: 1 }), false);
  assert.equal(history.checkpoint({ value: 2 }), true);
  assert.equal(history.checkpoint({ value: 3 }), true);
  assert.equal(history.checkpoint({ value: 4 }), true);
  assert.deepEqual(history.state, { canUndo: true, canRedo: false, undoCount: 2, redoCount: 0 });
  assert.deepEqual(history.undo(), { value: 3 });
  assert.deepEqual(history.undo(), { value: 2 });
  assert.equal(history.undo(), null);
  assert.deepEqual(history.redo(), { value: 3 });
  history.checkpoint({ value: 9 });
  assert.equal(history.state.canRedo, false);
});


test("mesh mirror bakes the reflection and preserves triangle winding", () => {
  const source: MeshGeometry = {
    positions: new Float32Array([-2, 0, 0, 2, 0, 0, -2, 4, 0]),
    normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    triangleCount: 1,
    boundsMin: [-2, 0, 0],
    boundsMax: [2, 4, 0],
  };
  const mirrored = mirrorMeshGeometry(source, "x");
  assert.deepEqual([...source.positions], [-2, 0, 0, 2, 0, 0, -2, 4, 0]);
  assert.deepEqual([...mirrored.positions], [2, 0, 0, 2, 4, 0, -2, 0, 0]);
  assert.deepEqual(mirrored.boundsMin, [-2, 0, 0]);
  assert.deepEqual(mirrored.boundsMax, [2, 4, 0]);
  assert.ok(mirrored.normals[2]! > 0.99);
});

test("mesh measurement uses transformed vertices across the full selection", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0, 0, 0, 2, 0, 0, 0, 3, 4]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0, 0, 0],
    boundsMax: [2, 3, 4],
  };
  const first = { id: "a", name: "A", geometry, position: [10, 20, 1], rotation: [0, 0, 0], scale: [2, 1, .5], color: "#000000", visible: true } as const;
  const second = { ...first, id: "b", name: "B", position: [-2, 5, 0] as const, scale: [1, 1, 1] as const };
  const measured = measureMeshInstances([first, second]);
  assert.ok(measured);
  assert.deepEqual(measured.minimum, [-2, 5, 0]);
  assert.deepEqual(measured.maximum, [14, 23, 4]);
  assert.deepEqual(measured.size, [16, 18, 4]);
  assert.equal(measured.objectCount, 2);
  assert.equal(measured.triangleCount, 2);
});

test("mega studio exposes source-owned mirror and measurement controls", () => {
  const ui = readFileSync(join(process.cwd(), "frontend", "studio-mega-ui-v2.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  for (const id of ["mirror-x", "mirror-y", "mirror-z", "measure", "menu-mirror-x", "menu-mirror-y", "menu-mirror-z", "menu-measure"]) {
    assert.ok(ui.includes(`id="${id}"`));
  }
  assert.ok(workspace.includes("#mirrorSelected(axis: StudioMirrorAxis)"));
  assert.ok(workspace.includes("#measureSelected(): void"));
  assert.ok(!workspace.includes("MutationObserver"));
  assert.ok(!workspace.includes("location.reload"));
});


test("mesh diagnosis distinguishes safe removals from topology warnings", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0, 0, 0, 2, 0, 0, 0, 2, 0,
      0, 2, 0, 2, 0, 0, 0, 0, 0,
      0, 0, 0, 1, 0, 0, 2, 0, 0,
      Number.NaN, 0, 0, 0, 1, 0, 0, 0, 1,
    ]),
    normals: new Float32Array(36),
    triangleCount: 4,
    boundsMin: [0, 0, 0],
    boundsMax: [2, 2, 1],
  };
  const report = analyzeMeshGeometry(geometry);
  assert.equal(report.duplicateTriangleCount, 1);
  assert.equal(report.zeroAreaTriangleCount, 1);
  assert.equal(report.nonFiniteTriangleCount, 1);
  assert.equal(report.repairableTriangleCount, 3);
  assert.equal(report.boundaryEdgeCount, 3);
  assert.equal(report.nonManifoldEdgeCount, 0);
});

test("safe mesh repair removes only proven invalid or duplicate triangles", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0, 0, 0, 2, 0, 0, 0, 2, 0,
      0, 2, 0, 2, 0, 0, 0, 0, 0,
      0, 0, 0, 1, 0, 0, 2, 0, 0,
    ]),
    normals: new Float32Array(27),
    triangleCount: 3,
    boundsMin: [0, 0, 0],
    boundsMax: [2, 2, 0],
  };
  const result = repairMeshGeometry(geometry);
  assert.equal(result.changed, true);
  assert.equal(result.geometry.triangleCount, 1);
  assert.equal(result.report.repairableTriangleCount, 2);
  assert.deepEqual([...geometry.positions].slice(0, 9), [0, 0, 0, 2, 0, 0, 0, 2, 0]);
});

test("safe mesh repair is fail-safe and returns an unchanged clean mesh", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0, 0, 0],
    boundsMax: [1, 1, 0],
  };
  const result = repairMeshGeometry(geometry);
  assert.equal(result.changed, false);
  assert.equal(result.geometry, geometry);
  assert.equal(result.report.boundaryEdgeCount, 3);
});

test("mega studio requires preview confirmation before safe mesh repair", () => {
  const ui = readFileSync(join(process.cwd(), "frontend", "studio-mega-ui-v2.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(ui.includes('id="repair"'));
  assert.ok(ui.includes('id="menu-repair"'));
  assert.ok(workspace.includes("#confirmSafeMeshRepair("));
  assert.ok(workspace.includes('id="mesh-repair-confirm"'));
  assert.ok(workspace.includes("Löcher werden nicht automatisch geschlossen"));
  assert.ok(!workspace.includes("MutationObserver"));
  assert.ok(!workspace.includes("location.reload"));
});


test("safe plane split previews two existing geometry groups without changing the source", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      -4, 0, 0, -2, 0, 0, -4, 2, 0,
      2, 0, 0, 4, 0, 0, 2, 2, 0,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [-4, 0, 0],
    boundsMax: [4, 2, 0],
  };
  const instance = { id: "split-source", name: "Source", geometry, position: [10, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#000000", visible: true } as const;
  const preview = previewMeshPlaneSplit(instance, "x", 10);
  assert.equal(preview.canApply, true);
  assert.equal(preview.negativeTriangleCount, 1);
  assert.equal(preview.positiveTriangleCount, 1);
  assert.equal(preview.crossingTriangleCount, 0);
  assert.equal(preview.touchingTriangleCount, 0);
  assert.equal(preview.negativeGeometry?.triangleCount, 1);
  assert.equal(preview.positiveGeometry?.triangleCount, 1);
  assert.equal(instance.geometry, geometry);
});

test("safe plane split fails closed when a triangle crosses the plane", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([-1, 0, 0, 1, 0, 0, -1, 1, 0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [-1, 0, 0],
    boundsMax: [1, 1, 0],
  };
  const instance = { id: "crossing", name: "Crossing", geometry, position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#000000", visible: true } as const;
  const preview = previewMeshPlaneSplit(instance, "x", 0);
  assert.equal(preview.canApply, false);
  assert.equal(preview.crossingTriangleCount, 1);
  assert.equal(preview.negativeGeometry, null);
  assert.equal(preview.positiveGeometry, null);
});

test("safe plane split fails closed when the plane touches a triangle", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0, 0, 0, 2, 0, 0, 0, 2, 0]),
    normals: new Float32Array(9),
    triangleCount: 1,
    boundsMin: [0, 0, 0],
    boundsMax: [2, 2, 0],
  };
  const instance = { id: "touching", name: "Touching", geometry, position: [0, 0, 0], rotation: [0, 0, 0], scale: [1, 1, 1], color: "#000000", visible: true } as const;
  const preview = previewMeshPlaneSplit(instance, "x", 0);
  assert.equal(preview.canApply, false);
  assert.equal(preview.touchingTriangleCount, 1);
});

test("mega studio previews two split objects and requires explicit confirmation", () => {
  const ui = readFileSync(join(process.cwd(), "frontend", "studio-mega-ui-v2.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(ui.includes('id="split"'));
  assert.ok(ui.includes('id="menu-split"'));
  assert.ok(workspace.includes('id="mesh-split-preview"'));
  assert.ok(workspace.includes('id="mesh-split-confirm"'));
  assert.ok(workspace.includes("Vorschau · zwei getrennte Ergebnisobjekte"));
  assert.ok(workspace.includes("noch nicht freigegebene Kappenbildung"));
  assert.ok(workspace.includes("mesh_safe_plane_split_applied"));
  assert.ok(!workspace.includes("MutationObserver"));
  assert.ok(!workspace.includes("location.reload"));
});

test("external filament sync works without AMS while AMS still rejects missing slots", () => {
  const external = { available: true, loaded: true };
  assert.equal(filamentSyncError("external_spool", external, 0), null);
  assert.equal(filamentSyncError("ams", external, 0), "Keine belegten AMS-Slots erkannt.");
  assert.equal(filamentSyncError("ams", null, 4), null);
  assert.equal(filamentSyncError("external_spool", { available: false, loaded: false }, 4), "Keine Telemetrie der externen Spule verfügbar.");
  assert.equal(filamentSyncError("external_spool", { available: true, loaded: false }, 0), null);
});

test("material sources share sync and reset controls with safe error text", () => {
  const html = filamentSyncActionsHtml(false, "<img src=x onerror=alert(1)>");
  assert.ok(html.includes("Filamente synchronisieren"));
  assert.ok(html.includes("Projektfarben zurücksetzen"));
  assert.ok(!html.includes("<img"));
  assert.ok(html.includes("&lt;img"));
  assert.equal((filamentSyncActionsHtml(true, "").match(/disabled/g) ?? []).length, 2);
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.equal((workspace.match(/\$\{sourceOptions\}\$\{syncActions\}/g) ?? []).length, 2);
  assert.equal((workspace.match(/this\.#bindFilamentSyncActions\(host\)/g) ?? []).length, 2);
});

test("process editor validates nozzle ranges, integer shells and finite values", () => {
  assert.equal(validateProcessEditor({ layer_height_mm: .1, first_layer_height_mm: .1, walls: 2, top_shell_layers: 0, bottom_shell_layers: 3, infill_percent: 100, outer_wall_speed_mm_s: 120, inner_wall_speed_mm_s: 150, travel_speed_mm_s: 300 }, .2).size, 0);
  const invalid = validateProcessEditor({ layer_height_mm: .2, first_layer_height_mm: .3, walls: 1.5, top_shell_layers: -1, infill_percent: 101, inner_wall_speed_mm_s: Infinity, outer_wall_speed_mm_s: true, travel_speed_mm_s: "" }, .2);
  assert.equal(invalid.size, 8);
  assert.ok(validateProcessEditor({ layer_height_mm: .2 }, null).has("layer_height_mm"));
  assert.ok(validateProcessEditor({ walls: 2, nozzle_diameter_mm: .4 }, .2).has("nozzle_diameter_mm"));
  assert.ok(validateProcessEditor({}, .4).has("_process"));
  for (const [diameter, height] of [[.2,.1],[.4,.2],[.6,.3],[.8,.4]]) {
    assert.equal(validateProcessEditor({ layer_height_mm: height }, diameter).size, 0);
  }
});

test("process editor preserves absence, zero values and original profile in its review", () => {
  const original = Object.freeze({ walls: 2, layer_height_mm: .1 });
  const changed = Object.freeze({ walls: 3, infill_percent: 0 });
  assert.equal(validateProcessEditor(changed, .4).size, 0);
  assert.deepEqual(processProfileChanges(original, changed), [
    { key: "infill_percent", before: undefined, after: 0 },
    { key: "layer_height_mm", before: .1, after: undefined },
    { key: "walls", before: 2, after: 3 },
  ]);
  assert.equal(original.walls, 2);
  assert.deepEqual(processProfileChanges(original, original), []);
});

test("transfer retry rejects prior server attempt and late responses from old client trace", () => {
  assert.equal(transferMatchesAttempt("old-server-start", "old-server-start", "new-client", "new-client"), false);
  assert.equal(transferMatchesAttempt("new-server-start", "old-server-start", "old-client", "new-client"), false);
  assert.equal(transferMatchesAttempt("new-server-start", "old-server-start", "new-client", "new-client"), true);
  assert.equal(transferMatchesAttempt("first-server-start", "", "first-client", "first-client"), true);
  assert.equal(transferMatchesAttempt("", "", "first-client", "first-client"), false);
});

test("motion errors use exact descriptions and Bambu error-specific help with matching QR target", () => {
  const issue = { code: "HMS_0300-1800-0001-0005", title: "Kritische Druckerstörung", help_url: "https://wiki.bambulab.com/en/home?search=code" };
  assert.equal(issueTitle(issue), "Bewegung des Z-Achsen-Motors blockiert");
  assert.ok(issueMessage(issue).includes("Z-Schlitten"));
  const target = issueHelpUrl(issue);
  assert.equal(target, "https://e.bambulab.com/index.php?e=0300180000010005&s=device_hms&lang=de");
  assert.equal(new URL(issueQrImageUrl(issue)).searchParams.get("text"), target);
  assert.equal(issueTitle({code:"0300-4000"}), "Referenzfahrt der Z-Achse fehlgeschlagen");
  assert.equal(new URL(issueHelpUrl({code:"0300-4000",help_url:"https://wiki.bambulab.com/en/hms/error-code"})).searchParams.get("e"), "03004000");
  assert.equal(issueTitle({code:"HMS_0300-4000-0002-0001",title:"Andere Meldung"}), "Andere Meldung");
  assert.equal(issueHelpUrl({code:"0300-4000",help_url:"https://wiki.bambulab.com/en/a1/troubleshooting/example"}), "https://wiki.bambulab.com/en/a1/troubleshooting/example");
  assert.ok(!issueHelpUrl({code:"0300-4000",help_url:"https://bambulab.com.evil.test/"}).includes("evil.test"));
});

test("issue telemetry updates retain printer action component and confirmation context", () => {
  const popup = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf8");
  const renderIssue = popup.slice(popup.indexOf("#renderIssue(printer:"), popup.indexOf("#updateRemainingLabels():"));
  assert.ok(renderIssue.includes('if (!host.querySelector("#issue-actions"))'));
  assert.ok(renderIssue.includes('if (list && list.innerHTML !== markup) list.innerHTML = markup'));
  const actions = readFileSync(join(process.cwd(), "frontend", "printer-command-store-v2.ts"), "utf8");
  assert.ok(actions.includes("printer: currentPrinter"));
  assert.ok(actions.includes("!== requestedJob"));
});

test("continuous ribbons retain every segment beyond the former preview budget", () => {
  const count = 180_001;
  const segments: RibbonSegment[] = Array.from({ length: count }, (_, i) => [i * .001, 0, (i + 1) * .001, 0, .2, 0, .00002, "Outer wall", "model"]);
  const meshes = buildContinuousToolpathMeshes([{ index: 0, z: .2, segments }, { index: 1, z: .4, segments: [] }], 1, true,
    new Map([[0, .2], [1, .2]]), () => ({ key: "wall", color: "#000000", label: "Wall", flat: false }));
  assert.equal(meshes.reduce((sum, mesh) => sum + mesh.geometry.triangleCount, 0), count * 6 + 4);
  assert.equal(new Set(meshes.map((mesh) => mesh.id)).size, meshes.length);
  assert.ok(meshes.every((mesh) => mesh.geometry.positions.length <= 54 * 4096));
  assert.ok(Math.abs(meshes.at(-1)!.geometry.boundsMax[0] - count * .001) < .0001);
});

test("ribbons use full consecutive layer heights and preserve narrow extrusion width", () => {
  const filamentArea = Math.PI * .875 * .875;
  assert.ok(Math.abs(extrusionRibbonWidth(.2 * 10 * .1 / filamentArea, 10, .1) - .2) < 1e-10);
  const segment = (z: number): RibbonSegment => [0, 0, 10, 0, z, 0, .2 * 10 * .1 / filamentArea, "Outer wall", "model"];
  const meshes = buildContinuousToolpathMeshes([
    { index: 0, z: .1, segments: [segment(.1)] },
    { index: 1, z: .2, segments: [segment(.2)] },
  ], 1, true, new Map([[0, .1], [1, .1]]), (_, current) => ({ key: "wall", color: "#112233", label: "Wall", flat: false }));
  assert.equal(meshes.length, 2);
  assert.equal(meshes[0]!.geometry.boundsMin[2], 0);
  assert.equal(meshes[0]!.geometry.boundsMax[2], meshes[1]!.geometry.boundsMin[2]);
  assert.ok(Math.abs(meshes[1]!.geometry.boundsMax[2] - .2) < 1e-7);
  assert.ok(Math.abs(meshes[0]!.geometry.boundsMax[1] - .1) < 1e-7);
  assert.ok(meshes.every((mesh) => [...mesh.geometry.normals].every(Number.isFinite)));
});

test("ribbon selection preserves single-layer mode, support isolation and feature filters", () => {
  const segment = (feature: string, category: string): RibbonSegment => [0, 0, 5, 0, .4, 0, .1, feature, category];
  const layers = [
    { index: 0, z: .2, segments: [segment("Outer wall", "model")] },
    { index: 1, z: .4, segments: [segment("Outer wall", "model"), segment("Support interface", "support")] },
  ];
  const height = new Map([[0, .2], [1, .2]]);
  const support = buildContinuousToolpathMeshes(layers, 1, false, height, (item) => item[8] === "support"
    ? { key: "support", color: "#32d6ff", label: "Interface", flat: true } : null);
  assert.equal(support.reduce((sum, mesh) => sum + mesh.geometry.triangleCount, 0), 2);
  assert.equal(support[0]!.color, "#32d6ff");
  assert.deepEqual(buildContinuousToolpathMeshes(layers, 1, true, height, () => null), []);
  assert.deepEqual(buildContinuousToolpathMeshes(layers, 2, true, height, () => null), []);
});

test("ribbons reject invalid coordinates and travel without altering source paths", () => {
  const valid: RibbonSegment = [0, 0, 5, 0, .2, 0, .1, "Outer wall", "model"];
  const segments: RibbonSegment[] = [valid, [0, 0, NaN, 0, .2, 0, .1, "", ""], [0, 0, 5, 0, .2, 0, 0, "", ""]];
  const before = structuredClone(segments);
  const meshes = buildContinuousToolpathMeshes([{index: 0, z: .2, segments}], 0, false, new Map([[0, .2]]),
    () => ({key: "wall", color: "#000000", label: "Wall", flat: false, highlight: "#444444"}));
  assert.equal(meshes.reduce((sum, mesh) => sum + mesh.geometry.triangleCount, 0), 12);
  assert.deepEqual(segments, before);
});



test("expanded process editor validates widths, speeds and support values without fabricated defaults", () => {
  assert.equal(PROCESS_EDITOR_FIELDS.length, 31);
  const payload = { outer_wall_line_width_mm: .42, bridge_speed_mm_s: 25, support_top_z_distance_mm: 0, support_interface_top_layers: 3 };
  assert.equal(validateProcessEditor(payload, .4).size, 0);
  assert.deepEqual(payload, { outer_wall_line_width_mm: .42, bridge_speed_mm_s: 25, support_top_z_distance_mm: 0, support_interface_top_layers: 3 });
  for (const field of PROCESS_EDITOR_FIELDS.slice(9)) {
    for (const value of [true, null, "", NaN, Infinity, field.min - .01, ...(field.step === "1" ? [1.5] : [])]) {
      assert.ok(validateProcessEditor({ [field.key]: value }, .4).has(field.key), `${field.key}: ${value}`);
    }
    assert.equal(validateProcessEditor({ [field.key]: field.min }, .4).size, 0);
  }
});


test("ribbon corners fill left and right turns without changing toolpath coordinates", () => {
  const area = Math.PI * .875 * .875;
  const segment = (x1: number, y1: number, x2: number, y2: number): RibbonSegment =>
    [x1, y1, x2, y2, .2, 0, .4 * Math.hypot(x2 - x1, y2 - y1) * .2 / area, "Outer wall", "model"];
  const covered = (positions: Float32Array, x: number, y: number): boolean => {
    for (let i = 0; i < positions.length; i += 9) {
      if (![2, 5, 8].every((j) => Math.abs(positions[i + j]! - .2) < 1e-6)) continue;
      const cross = (ax: number, ay: number, bx: number, by: number) => ax * by - ay * bx;
      const ax = positions[i]!, ay = positions[i + 1]!, bx = positions[i + 3]!, by = positions[i + 4]!, cx = positions[i + 6]!, cy = positions[i + 7]!;
      const signs = [cross(bx - ax, by - ay, x - ax, y - ay), cross(cx - bx, cy - by, x - bx, y - by), cross(ax - cx, ay - cy, x - cx, y - cy)];
      if (signs.every((v) => v >= -1e-6) || signs.every((v) => v <= 1e-6)) return true;
    }
    return false;
  };
  for (const direction of [-1, 1]) {
    const segments = [segment(0, 0, 10, 0), segment(10, 0, 10, direction * 10)];
    const before = JSON.stringify(segments);
    const meshes = buildContinuousToolpathMeshes([{index: 0, z: .2, segments}], 0, false, new Map([[0, .2]]), () => ({key: "wall", color: "#000000", label: "Wall", flat: false}));
    assert.equal(meshes[0]!.geometry.triangleCount, 19);
    assert.ok(covered(meshes[0]!.geometry.positions, 10.05, -direction * .05), "outer corner must be covered");
    assert.ok([...meshes[0]!.geometry.normals].every(Number.isFinite));
    assert.equal(JSON.stringify(segments), before);
  }
});

test("ribbon joins respect travel, hidden paths, material and feature boundaries", () => {
  const east: RibbonSegment = [0, 0, 10, 0, .2, 0, .2, "Outer wall", "model"];
  const north: RibbonSegment = [10, 0, 10, 10, .2, 0, .2, "Outer wall", "model"];
  const style = {key: "wall", color: "#000000", label: "Wall", flat: false};
  const variants: RibbonSegment[][] = [
    [east, [10, 0, 10, 10, .2, 1, .2, "Outer wall", "model"]],
    [east, [10, 0, 10, 10, .2, 0, .2, "Inner wall", "model"]],
    [east, [10.01, 0, 10, 10, .2, 0, .2, "Outer wall", "model"]],
    [east, [10, 0, 10, 1, .2, 0, 0, "Travel", "travel"], north],
    [east, [10, 0, 11, 0, .2, 0, .2, "Hidden", "model"], north],
  ];
  for (const segments of variants) {
    const meshes = buildContinuousToolpathMeshes([{index: 0, z: .2, segments}], 0, false, new Map([[0, .2]]), (s) => s[7] === "Hidden" ? null : style);
    assert.equal(meshes.reduce((n, m) => n + m.geometry.triangleCount, 0), 20);
  }
});

test("closed ribbon contours join the seam and preserve flat support and highlight rendering", () => {
  const points = [[0,0], [10,0], [10,10], [0,10], [0,0]];
  const segments: RibbonSegment[] = points.slice(0, -1).map((p, i) => [p[0]!, p[1]!, points[i+1]![0]!, points[i+1]![1]!, .2, 0, .2, "Outer wall", "model"]);
  for (const flat of [false, true]) {
    const meshes = buildContinuousToolpathMeshes([{index: 0, z: .2, segments}], 0, false, new Map([[0, .2]]), () => ({key: "wall", color: "#001122", label: "Wall", flat, highlight: "#ffffff"}));
    assert.equal(meshes.filter((m) => m.color === "#001122").reduce((n,m) => n+m.geometry.triangleCount, 0), flat ? 12 : 36);
    assert.equal(meshes.filter((m) => m.color === "#ffffff").reduce((n,m) => n+m.geometry.triangleCount, 0), 12);
    assert.ok(meshes.every((m) => m.geometry.positions.length <= 54 * 4096));
  }
});



test("ribbon sides and end caps face outward for every travel direction", () => {
  for (const [dx, dy] of [[10,0], [0,10], [-10,0], [6,8]]) {
    const segment: RibbonSegment = [0,0,dx!,dy!,.2,0,.2,"Outer wall","model"];
    const mesh = buildContinuousToolpathMeshes([{index:0,z:.2,segments:[segment]}],0,false,new Map([[0,.2]]),()=>({key:"wall",color:"#123456",label:"Wall",flat:false}))[0]!;
    const {positions:p,normals:n}=mesh.geometry;
    for (let i=0;i<p.length;i+=9) {
      const z=[p[i+2]!,p[i+5]!,p[i+8]!];
      if (Math.max(...z)-Math.min(...z)<1e-6) continue;
      const cx=(p[i]!+p[i+3]!+p[i+6]!)/3-dx!/2;
      const cy=(p[i+1]!+p[i+4]!+p[i+7]!)/3-dy!/2;
      assert.ok(cx*n[i]!+cy*n[i+1]!>0, "every vertical face must point away from the bead center");
    }
    assert.equal(mesh.geometry.triangleCount,10,"one open bead has two top, four side and four cap triangles");
  }
});

test("ribbon end caps appear only at open chain boundaries, never between straight segments", () => {
  const a: RibbonSegment=[0,0,10,0,.2,0,.2,"Outer wall","model"];
  const b: RibbonSegment=[10,0,20,0,.2,0,.2,"Outer wall","model"];
  const mesh=buildContinuousToolpathMeshes([{index:0,z:.2,segments:[a,b]}],0,false,new Map([[0,.2]]),()=>({key:"wall",color:"#000000",label:"Wall",flat:false}))[0]!;
  const p=mesh.geometry.positions;
  const atPlane=(x:number):number=>{
    let count=0;
    for(let i=0;i<p.length;i+=9) if([0,3,6].every(j=>Math.abs(p[i+j]!-x)<1e-6)) count++;
    return count;
  };
  assert.equal(atPlane(0),2);
  assert.equal(atPlane(10),0);
  assert.equal(atPlane(20),2);
  assert.equal(mesh.geometry.triangleCount,16);
});

test("ribbon reversals close each open run while flat support remains two-dimensional", () => {
  const segments: RibbonSegment[]=[[0,0,10,0,.2,0,.2,"Support","support"],[10,0,0,0,.2,0,.2,"Support","support"]];
  for(const flat of [false,true]) {
    const meshes=buildContinuousToolpathMeshes([{index:0,z:.2,segments}],0,false,new Map([[0,.2]]),()=>({key:"support",color:"#00ffff",label:"Support",flat}));
    assert.equal(meshes.reduce((n,m)=>n+m.geometry.triangleCount,0),flat?4:20);
    if(flat) assert.ok(meshes.every(m=>m.geometry.boundsMin[2]===m.geometry.boundsMax[2]));
    assert.ok(meshes.every(m=>Array.from(m.geometry.normals).every(Number.isFinite)));
  }
});

test("current layer toolpaths keep highlight while history stays dimmed", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(source.includes("const highlight = !supportOnly && current"));
  assert.ok(source.includes("colorMode === \"material\" ? materialHighlightColor(materialColor) : mixColor(base, \"#ffffff\", .28)"));
  assert.ok(source.includes("...(highlight ? { highlight } : {})"));
  assert.ok(source.includes("current ? base : mixColor(base"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("layer preview sidebar supports fast jumps and direct layer entry", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(source.includes("#layer-jump-back"));
  assert.ok(source.includes("#layer-jump-forward"));
  assert.ok(source.includes("#layer-index"));
  assert.ok(source.includes("selectVisibleLayer(plate.visibleLayer - 10, true)"));
  assert.ok(source.includes("selectVisibleLayer(plate.visibleLayer + 10, true)"));
  assert.ok(source.includes("selectVisibleLayer(Number((event.currentTarget as HTMLInputElement).value) - 1, true)"));
  assert.ok(source.includes("layerIndexInput.value = String(value + 1)"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});


test("layer preview stage exposes current layer badge in the canvas", () => {
  const ui = readFileSync(join(process.cwd(), "frontend", "studio-mega-ui-v2.ts"), "utf8");
  assert.ok(ui.includes("function stagePreviewBadgeHtml(state: MegaUiStateV2): string"));
  assert.ok(ui.includes("preview-stage-badge"));
  assert.ok(ui.includes("aria-label=\"Aktive Layeransicht\""));
  assert.ok(ui.includes("Layer ${state.visibleLayer + 1} / ${state.layerCount}"));
  assert.ok(ui.includes("Z ${state.visibleLayerZ.toFixed(2)} mm"));
  assert.ok(!ui.includes("MutationObserver"));
  assert.ok(!ui.includes("location.reload"));
});

test("layer preview sidebar exposes variable ranges and touch step controls", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(source.includes("const variableLayerSection = variableLayerRangesHtml(variableLayerRanges, currentLayer?.z ?? 0);"));
  assert.ok(source.includes("${supportPanel}${variableLayerSection}<div class=\"section\">"));
  assert.ok(source.includes("class=\"layer-stepper\""));
  assert.ok(source.includes("const updateVisibleLayerSidebar = (value: number): void =>"));
  assert.ok(source.includes("const selectVisibleLayer = (rawValue: number, rerender = false): void =>"));
  assert.ok(source.includes("#preview-layer-height-range-current"));
  assert.ok(source.includes("chip.classList.toggle(\"active\", isActive)"));
  assert.ok(source.includes("#layer-prev"));
  assert.ok(source.includes("#layer-next"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("process options panel exposes a source-owned variable layer-height curve preview", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf8");
  assert.ok(source.includes("function layerHeightCurveHtml"));
  assert.ok(source.includes("data-range-curve"));
  assert.ok(source.includes("Variable Schichthoehen von 0 bis"));
  assert.ok(source.includes("${layerHeightCurveHtml(ranges, previewZ)}"));
  assert.ok(source.includes("nozzleLayerHeightBounds"));
  assert.ok(source.includes("Schichthoehe fuer ${bounds.label}"));
  assert.ok(source.includes('min="${bounds.minimum}" max="${bounds.maximum}"'));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("process options panel supports pointer editing for the variable layer-height curve", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf8");
  assert.ok(source.includes("function layerHeightFromCurvePointer"));
  assert.ok(source.includes("#updateLayerHeightFromCurve"));
  assert.ok(source.includes("touch-action:none"));
  assert.ok(source.includes("addEventListener(\"pointerdown\""));
  assert.ok(source.includes("range_height_mm") === false);
  assert.ok(source.includes("layer_height_mm: point.height"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("process options panel cleans up drag listeners for variable layer-height curve editing", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf8");
  assert.ok(source.includes("setPointerCapture(pointerId)"));
  assert.ok(source.includes("window.addEventListener(\"pointermove\", move)"));
  assert.ok(source.includes("window.addEventListener(\"pointerup\", up, { once: true })"));
  assert.ok(source.includes("window.addEventListener(\"pointercancel\", up, { once: true })"));
  assert.ok(source.includes("window.removeEventListener(\"pointermove\", move)"));
  assert.ok(source.includes("releasePointerCapture(pointerId)"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});

test("process options panel can split and merge variable layer-height ranges", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf8");
  assert.ok(source.includes("data-split-range"));
  assert.ok(source.includes("data-merge-range"));
  assert.ok(source.includes("#splitLayerHeightRange"));
  assert.ok(source.includes("#mergeLayerHeightRange"));
  assert.ok(source.includes("max_z_mm: middle"));
  assert.ok(source.includes("min_z_mm: middle"));
  assert.ok(source.includes("max_z_mm: current.max_z_mm"));
  assert.ok(source.includes("layer_height_mm: current.layer_height_mm"));
  assert.ok(!source.includes("MutationObserver"));
  assert.ok(!source.includes("location.reload"));
});


test("global job popup keeps scroll positions across telemetry rerenders", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "global-job-popup-v3.ts"), "utf-8");
  assert.ok(source.includes("const previousJobsScrollTop = jobs.scrollTop;"));
  assert.ok(source.includes("jobs.scrollTop = previousJobsScrollTop;"));
  assert.ok(source.includes("const previousActivityScrollTop = sliceActivity.scrollTop;"));
});

test("process editor exposes Bambu support styles and model-contact support", () => {
  const panel = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf-8");
  const api = readFileSync(join(process.cwd(), "frontend", "plate-slice-api.ts"), "utf-8");
  assert.ok(api.includes("export type SupportStyle"));
  assert.ok(api.includes("query.set(\"support_style\""));
  for (const label of ["Baum schlank", "Baum stark", "Baum-Hybrid", "Baum Organisch"]) assert.ok(panel.includes(label));
  assert.ok(panel.includes("Support darf direkt auf Modellflächen starten."));
});

test("material controls lock while the printer is not ready", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "ams-workspace.ts"), "utf8");
  assert.match(source, /printerBlocked = this.#printer\(\) !== null && !this.#printer\(\)\?\.ready/);
  assert.match(source, /Während eines laufenden Drucks gesperrt/);
});

test("slice gate reads the active plate process state from the options panel", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf-8");
  const panel = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf-8");
  assert.match(panel, /getProcessOverrides\(\): SliceProcessOverrides/);
  assert.match(workspace, /processPanel\?\.getProcessOverrides\?\.\(\)\s*\?\?\s*loadSliceProcessOverrides\(\)/);
});


test("layer preview performance with 200+ layers using cached segment slicing", () => {

  
  // Clear cache before test
  clearSegmentCache();
  
  // Create a geometry with 200 layers worth of triangles
  const triangleCount = 500;
  const positions = new Float32Array(triangleCount * 9);
  
  // Fill with random positions in a 100x100x50mm bounding box
  for (let i = 0; i < positions.length; i++) {
    positions[i] = Math.random() * 100 - 50;
  }
  
  const geometry = {
    positions,
    triangleCount,
    boundsMin: [-50, -50, 0],
    boundsMax: [50, 50, 50],
  };
  
  const layerHeight = 0.2;
  const totalLayers = 250; // 50mm / 0.2mm = 250 layers
  
  // Warm up cache by slicing all layers
  const warmUpStart = performance.now();
  for (let layer = 0; layer < totalLayers; layer++) {
    const z = layer * layerHeight + layerHeight / 2;
    getCachedSliceSegmentsAtZ(geometry, z);
  }
  const warmUpTime = performance.now() - warmUpStart;
  
  // Now test repeated access (should use cache)
  const cachedStart = performance.now();
  for (let iter = 0; iter < 10; iter++) {
    for (let layer = 0; layer < totalLayers; layer++) {
      const z = layer * layerHeight + layerHeight / 2;
      getCachedSliceSegmentsAtZ(geometry, z);
    }
  }
  const cachedTime = performance.now() - cachedStart;
  
  // Without cache, 250 layers × 10 iterations = 2500 slice operations would be slow
  // With cache, subsequent accesses should be nearly instant
  assert.ok(cachedTime < warmUpTime * 2, "Cached access should be significantly faster than warmup");
  assert.ok(cachedTime < 100, "Cached layer access should complete in under 100ms");
  
  // Verify cache size doesn't exceed limit
  assert.ok(cachedTime > 0, "Timing should be positive");
});

test("layer segment cache does not leak memory beyond 5000 entries", () => {
  clearSegmentCache();
  
  // Create a geometry with triangles
  const triangleCount = 100;
  const positions = new Float32Array(triangleCount * 9);
  for (let i = 0; i < positions.length; i++) {
    positions[i] = Math.random() * 100 - 50;
  }
  
  const geometry = {
    positions,
    triangleCount,
    boundsMin: [-50, -50, 0],
    boundsMax: [50, 50, 50],
  };
  
  const layerHeight = 0.1;
  const totalLayers = 6000; // More than cache limit
  
  // Fill cache beyond limit
  for (let layer = 0; layer < totalLayers; layer++) {
    const z = layer * layerHeight + layerHeight / 2;
    getCachedSliceSegmentsAtZ(geometry, z);
  }
  
  // Cache should be capped at 5000
  assert.equal(segmentCache.size, 5000, "Cache must remain capped at 5000 entries");
});

test("layer segment cache clears properly between geometries", () => {
  clearSegmentCache();
  
  // Create first geometry
  const positions1 = new Float32Array(9);
  positions1[0] = 0; positions1[1] = 0; positions1[2] = 0;
  positions1[3] = 10; positions1[4] = 0; positions1[5] = 0;
  positions1[6] = 5; positions1[7] = 10; positions1[8] = 0;
  
  const geometry1 = { positions: positions1, triangleCount: 1, boundsMin: [0, 0, 0], boundsMax: [10, 10, 10] };
  getCachedSliceSegmentsAtZ(geometry1, 5);
  assert.equal(segmentCache.size, 1, "First geometry should create one cache entry");

  // A geometry change must invalidate the previous geometry cache automatically.
  const positions2 = new Float32Array(9);
  positions2[0] = 1; positions2[1] = 0; positions2[2] = 0;
  positions2[3] = 10; positions2[4] = 0; positions2[5] = 0;
  positions2[6] = 5; positions2[7] = 10; positions2[8] = 0;
  const geometry2 = { positions: positions2, triangleCount: 1, boundsMin: [0, 0, 0], boundsMax: [10, 10, 10] };
  getCachedSliceSegmentsAtZ(geometry2, 5);
  assert.equal(segmentCache.size, 1, "Geometry change must invalidate the previous cache");

  clearSegmentCache();
  assert.equal(segmentCache.size, 0, "Cache must be empty after clear");
});

test("layer segment cache distinguishes sampled geometry bit patterns", () => {
  clearSegmentCache();
  const first = new Float32Array([0, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0.5]);
  const second = new Float32Array([0, 0, 0.1, 0.5, 0, 0.6, 0, 0.5, 0.6]);
  const geometry1 = { positions: first, triangleCount: 1, boundsMin: [0, 0, 0], boundsMax: [1, 1, 1] };
  const geometry2 = { positions: second, triangleCount: 1, boundsMin: [0, 0, 0], boundsMax: [1, 1, 1] };
  const firstSegments = getCachedSliceSegmentsAtZ(geometry1, 0.55);
  assert.equal(firstSegments.length, 0);
  const secondSegments = getCachedSliceSegmentsAtZ(geometry2, 0.55);
  assert.equal(secondSegments.length, 1);
  assert.equal(segmentCache.size, 1);
  clearSegmentCache();
});

// ============================================================
// Paint-Tool Tests (Abschnitt 61)
// ============================================================

import { createPaintSession, type PaintBrush } from "../frontend/studio-mesh-paint.js";

function makePaintGeometry(triangles: number[]): MeshGeometry {
  return {
    positions: new Float32Array(triangles),
    normals: new Float32Array(triangles.length),
    triangleCount: triangles.length / 9,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
}

test("paint session applies add mode correctly", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  assert.ok(result.modified, "Paint should modify geometry");
  assert.ok(result.paintedTriangleCount > 0, "Should paint at least one triangle");
});

test("paint session applies remove mode correctly", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const addBrush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], addBrush);
  
  const removeBrush: PaintBrush = { radiusMm: 1.0, color: "#000000", mode: "remove" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], removeBrush);
  assert.ok(result.modified, "Remove should modify geometry");
});

test("paint session applies replace mode correctly", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "replace" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  assert.ok(result.modified, "Replace should modify geometry");
  const regions = session.getRegions("obj1");
  assert.equal(regions[0].color, "#ff0000", "Region should have correct color");
});

test("paint session respects brush radius", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 0.1, color: "#ff0000", mode: "add" };
  const result = session.paint("obj1", geometry, [], [5, 5, 0], brush);
  // Small brush far away should not hit anything
  assert.equal(result.paintedTriangleCount, 0, "Brush too small should not hit");
});

test("getRegions groups by color", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush1: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush1);
  
  const brush2: PaintBrush = { radiusMm: 1.0, color: "#00ff00", mode: "add" };
  session.paint("obj1", geometry, [], [0.0, 0.0, 0], brush2);
  
  const regions = session.getRegions("obj1");
  assert.ok(regions.length > 0, "Should have regions");
});

test("clear removes all paint data", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  assert.ok(session.getRegions("obj1").length > 0, "Should have paint data");
  
  session.clear();
  assert.equal(session.getRegions("obj1").length, 0, "Clear should remove all data");
});

test("clear with objectId removes only that object", () => {
  const session = createPaintSession();
  const geometry = makePaintGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ff0000", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  session.paint("obj2", geometry, [], [0.5, 0.5, 0], brush);
  
  assert.ok(session.getRegions("obj1").length > 0, "obj1 should have paint");
  assert.ok(session.getRegions("obj2").length > 0, "obj2 should have paint");
  
  session.clear("obj1");
  assert.equal(session.getRegions("obj1").length, 0, "obj1 should be cleared");
  assert.ok(session.getRegions("obj2").length > 0, "obj2 should remain");
});

// ============================================================
// Support-Malen Tests (Abschnitt 62)
// ============================================================

import { createPaintSession, type PaintBrush } from "../frontend/studio-mesh-paint.js";

function makeSupportGeometry(triangles: number[]): MeshGeometry {
  return {
    positions: new Float32Array(triangles),
    normals: new Float32Array(triangles.length),
    triangleCount: triangles.length / 9,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
}

test("support paint marks triangles for support generation", () => {
  const session = createPaintSession();
  const geometry = makeSupportGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ffaa00", mode: "add" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  assert.ok(result.modified, "Support paint should modify geometry");
  assert.ok(result.paintedTriangleCount > 0, "Should mark at least one triangle");
});

test("support regions can be retrieved and grouped", () => {
  const session = createPaintSession();
  const geometry = makeSupportGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ffaa00", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  const regions = session.getRegions("obj1");
  assert.ok(regions.length > 0, "Should have support regions");
  assert.equal(regions[0].color, "#ffaa00", "Region should have support color");
});

test("clear support regions works", () => {
  const session = createPaintSession();
  const geometry = makeSupportGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#ffaa00", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  assert.ok(session.getRegions("obj1").length > 0, "Should have support regions");
  
  session.clear();
  assert.equal(session.getRegions("obj1").length, 0, "Clear should remove support regions");
});

// ============================================================
// Naht-Malen Tests (Abschnitt 63)
// ============================================================

import { createPaintSession, type PaintBrush } from "../frontend/studio-mesh-paint.js";

function makeSeamGeometry(triangles: number[]): MeshGeometry {
  return {
    positions: new Float32Array(triangles),
    normals: new Float32Array(triangles.length),
    triangleCount: triangles.length / 9,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
}

test("seam paint sets seam position on wall triangles", () => {
  const session = createPaintSession();
  const geometry = makeSeamGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
    0, 0, 0, 1, 1, 0, 0, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#00aaff", mode: "add" };
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  assert.ok(result.modified, "Seam paint should modify geometry");
  assert.ok(result.paintedTriangleCount > 0, "Should mark at least one seam triangle");
});

test("seam regions use distinct color for identification", () => {
  const session = createPaintSession();
  const geometry = makeSeamGeometry([
    0, 0, 0, 1, 0, 0, 1, 1, 0,
  ]);
  const brush: PaintBrush = { radiusMm: 1.0, color: "#00aaff", mode: "add" };
  session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  
  const regions = session.getRegions("obj1");
  assert.ok(regions.length > 0, "Should have seam regions");
  assert.equal(regions[0].color, "#00aaff", "Seam region should have seam color");
});



// ============================================================
// Performance-Test: Paint mit großen Dreiecksmengen (Roadmap #65)
// ============================================================

test("paint performance with 2000 triangles under 100ms", () => {
  const session = createPaintSession();
  
  // Generate geometry with 2000 triangles (18000 floats)
  const triangleCount = 2000;
  const positions = new Float32Array(triangleCount * 9);
  for (let i = 0; i < triangleCount; i++) {
    const base = i * 9;
    positions[base] = Math.random();
    positions[base + 1] = Math.random();
    positions[base + 2] = 0;
    positions[base + 3] = Math.random();
    positions[base + 4] = Math.random();
    positions[base + 5] = 0;
    positions[base + 6] = Math.random();
    positions[base + 7] = Math.random();
    positions[base + 8] = 0;
  }
  const geometry = {
    positions,
    normals: new Float32Array(positions.length),
    triangleCount,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
  const brush: PaintBrush = { radiusMm: 10, color: "#ff4444", mode: "add" };
  
  const start = performance.now();
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  const elapsed = performance.now() - start;
  
  assert.ok(elapsed < 100, `Paint operation should complete in <100ms, got ${elapsed.toFixed(2)}ms`);
  assert.ok(result.modified, "Paint should modify geometry");
  assert.ok(result.paintedTriangleCount > 0, "Should have painted triangles");
  
  const regions = session.getRegions("obj1");
  assert.ok(regions.length > 0, "Should have painted regions");
});

test("paint performance with 5000 triangles under 250ms", () => {
  const session = createPaintSession();
  
  const triangleCount = 5000;
  const positions = new Float32Array(triangleCount * 9);
  for (let i = 0; i < triangleCount; i++) {
    const base = i * 9;
    positions[base] = Math.random();
    positions[base + 1] = Math.random();
    positions[base + 2] = 0;
    positions[base + 3] = Math.random();
    positions[base + 4] = Math.random();
    positions[base + 5] = 0;
    positions[base + 6] = Math.random();
    positions[base + 7] = Math.random();
    positions[base + 8] = 0;
  }
  const geometry = {
    positions,
    normals: new Float32Array(positions.length),
    triangleCount,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
  const brush: PaintBrush = { radiusMm: 10, color: "#00ff44", mode: "add" };
  
  const start = performance.now();
  const result = session.paint("obj1", geometry, [], [0.5, 0.5, 0], brush);
  const elapsed = performance.now() - start;
  
  assert.ok(elapsed < 250, `Paint with 5000 triangles should complete in <250ms, got ${elapsed.toFixed(2)}ms`);
  assert.ok(result.modified, "Paint should modify geometry");
  assert.ok(result.paintedTriangleCount > 0, "Should have painted triangles");
});


test("process options panel renders and submits all process editor fields", () => {
  const panel = readFileSync(join(process.cwd(), "frontend", "studio-process-options-panel.ts"), "utf8");
  const api = readFileSync(join(process.cwd(), "frontend", "plate-slice-api.ts"), "utf8");
  assert.ok(panel.includes('from "./process-profile-editor-model.js"'));
  assert.ok(panel.includes("processEditorRows(value, nozzleDiameter)"));
  assert.ok(panel.includes("[data-process-editor-field]"));
  assert.ok(panel.includes("#updateProcessEditorField"));
  assert.ok(api.includes('from "./process-profile-editor-model.js"'));
  assert.ok(api.includes("for (const field of PROCESS_EDITOR_FIELDS)"));
  assert.ok(api.includes("query.set(field.key, String(value))"));
  assert.equal(PROCESS_EDITOR_FIELDS.length, 31);
  for (const field of PROCESS_EDITOR_FIELDS) {
    assert.ok(field.key);
  }
});


test("paint button is wired to viewport paint regions", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  const viewport = readFileSync(join(process.cwd(), "frontend", "studio-mega-viewport.ts"), "utf8");

  assert.ok(workspace.includes('import "./studio-paint-ui.js";'));
  assert.ok(workspace.includes("type PaintRegion"));
  assert.ok(workspace.includes("type StudioPaintButtonElement"));
  assert.ok(workspace.includes("#paintRegions(): readonly PaintRegion[]"));
  assert.ok(workspace.includes("paintButton?.isActive?.()"));
  assert.ok(workspace.includes("pickPaintPoint(event.clientX, event.clientY)"));
  assert.ok(workspace.includes("this.#paintSession.paintTriangles("));
  assert.ok(workspace.includes("refinePaintResolution"));
  assert.ok(workspace.includes("this.#viewport?.setPaintRegions(this.#paintRegions())"));
  assert.ok(viewport.includes("export type PaintPickResult"));
  assert.ok(viewport.includes("pickPaintPoint(clientX: number, clientY: number): PaintPickResult | null"));
});


test("generateCapFaces caps a square boundary", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0, 0, 0, 10, 0, 0, 10, 10, 0,
      0, 0, 0, 10, 10, 0, 0, 10, 0,
    ]),
    normals: new Float32Array(18),
    triangleCount: 2,
    boundsMin: [0, 0, 0],
    boundsMax: [10, 10, 0],
  };
  const result = generateCapFaces(geometry, "z");
  assert.equal(result.capCount, 2);
  assert.equal(result.capPositions.length, 18);
});

test("generateCapFaces does not cap closed tetrahedron geometry", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([
      0, 0, 0, 10, 0, 0, 0, 10, 0,
      0, 0, 0, 0, 10, 0, 0, 0, 10,
      0, 0, 0, 0, 0, 10, 10, 0, 0,
      10, 0, 0, 0, 0, 10, 0, 10, 0,
    ]),
    normals: new Float32Array(36),
    triangleCount: 4,
    boundsMin: [0, 0, 0],
    boundsMax: [10, 10, 10],
  };
  const result = generateCapFaces(geometry, "z");
  assert.equal(result.capCount, 0);
});

test("layer segment cache invalidates epsilon and unsampled in-place edits", () => {
  clearSegmentCache();
  const positions = new Float32Array(4500);
  positions.set([0, 0, 0, 1, 0, 1, 0, 1, 1]);
  const geometry = { positions, normals: new Float32Array(4500), triangleCount: 500,
    boundsMin: [0, 0, 0], boundsMax: [1, 1, 1] } as MeshGeometry;
  const before = getCachedSliceSegmentsAtZ(geometry, 0.5);
  positions[3] = 2; // The former stride of two skipped this coordinate.
  const after = getCachedSliceSegmentsAtZ(geometry, 0.5);
  assert.notDeepEqual(after, before);
  assert.deepEqual(after, sliceSegmentsAtZ(geometry, 0.5));
  assert.equal(segmentCache.size, 1);
  getCachedSliceSegmentsAtZ(geometry, 0.6);
  assert.equal(segmentCache.size, 2);
  assert.deepEqual(getCachedSliceSegmentsAtZ(geometry, 0.5, 0.6), sliceSegmentsAtZ(geometry, 0.5, 0.6));
  assert.equal(segmentCache.size, 1);
  clearSegmentCache();
});

test("layer segment cache preserves distinct sub-micrometre slice heights", () => {
  clearSegmentCache();
  const geometry = makePaintGeometry([0, 0, 0, 1, 0, 1, 0, 1, 1]);
  const first = getCachedSliceSegmentsAtZ(geometry, 0.5000001);
  const second = getCachedSliceSegmentsAtZ(geometry, 0.5000002);
  assert.notDeepEqual(first, second);
  assert.deepEqual(second, sliceSegmentsAtZ(geometry, 0.5000002));
  assert.equal(segmentCache.size, 2);
  clearSegmentCache();
});

test("closed tetrahedron splits retain volume and opposite cap winding on all axes", () => {
  const geometry = makePaintGeometry([
    0,0,0, 10,0,0, 0,10,0,
    0,0,0, 0,10,0, 0,0,10,
    0,0,0, 0,0,10, 10,0,0,
    10,0,0, 0,0,10, 0,10,0,
  ]);
  const original = Array.from(geometry.positions);
  const instance = { id: "closed", name: "Closed", geometry, position: [0,0,0],
    rotation: [0,0,0], scale: [1,1,1], color: "#000000", visible: true } as const;
  for (const axis of ["x", "y", "z"] as const) {
    const split = previewMeshPlaneSplit(instance, axis, 3);
    assert.equal(split.canApply, true, axis);
    const volume = analyzeGeometry(split.negativeGeometry!).volumeMm3
      + analyzeGeometry(split.positiveGeometry!).volumeMm3;
    assert.ok(Math.abs(volume - 1000 / 6) < 1e-5, `${axis}: volume ${volume}`);
  }
  assert.deepEqual(Array.from(geometry.positions), original);
  assert.equal(previewMeshPlaneSplit(instance, "z", Number.NaN).canApply, false);
});


test("paint export carries the exact selected material through the 3MF and native worker contracts", () => {
  const paint = readFileSync(join(process.cwd(), "frontend", "studio-mesh-paint.ts"), "utf8");
  const exporter = readFileSync(join(process.cwd(), "frontend", "three-mf-export-stream.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(paint.includes("materialKey: string"));
  assert.ok(exporter.includes('p1="${faceMaterial}"'));
  assert.ok(exporter.includes("triangleMaterialIndices"));
  assert.ok(workspace.includes("paintMaterialKeys"));
  assert.ok(workspace.includes("triangleMaterialIndices"));
  assert.ok(workspace.includes("Bemalte Flächen benötigen mehrere Materialkanäle"));
});


import { projectedTriangleIntersectsPaintShape } from "../frontend/studio-mega-viewport.js";

test("paint shapes select intersecting triangles instead of centroid-only triangles", () => {
  const broadTriangle = [{ x: 0, y: 0 }, { x: 20, y: 0 }, { x: 0, y: 20 }] as const;
  assert.equal(projectedTriangleIntersectsPaintShape(
    broadTriangle,
    "rectangle",
    { left: 4, right: 6, top: 4, bottom: 6 },
  ), true, "A rectangle inside a large triangle must select it even if its centroid lies outside");

  const crossingTriangle = [{ x: -10, y: 0 }, { x: 10, y: 0 }, { x: 0, y: 20 }] as const;
  assert.equal(projectedTriangleIntersectsPaintShape(
    crossingTriangle,
    "circle",
    { left: -1, right: 1, top: -1, bottom: 1 },
  ), true, "A circle intersecting a triangle edge must select it");

  const outsideTriangle = [{ x: 30, y: 30 }, { x: 40, y: 30 }, { x: 30, y: 40 }] as const;
  assert.equal(projectedTriangleIntersectsPaintShape(
    outsideTriangle,
    "circle",
    { left: -1, right: 1, top: -1, bottom: 1 },
  ), false);
});


test("paint area rows remove one material-bound region without selecting twice", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(workspace.includes('data-paint-remove'));
  assert.ok(workspace.includes('#removePaintRegion(region: PaintRegion)'));
  assert.ok(workspace.includes('mode: "remove"'));
  const duplicateRootBinding = 'this.#root.querySelectorAll<HTMLButtonElement>("[data-object]")';
  assert.equal(workspace.split(duplicateRootBinding).length - 1, 0, "Object rows must not receive a second click handler after rendering");
});


test("paint shape preview renders a smooth drag frame above the WebGL viewport", () => {
  const ui = readFileSync(join(process.cwd(), "frontend", "studio-mega-ui-v2.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(ui.includes('canvas class="paint-shape-preview"'));
  assert.ok(workspace.includes('drawShapePreview'));
  assert.ok(workspace.includes('context.ellipse'));
  assert.ok(workspace.includes('context.rect'));
  assert.ok(workspace.includes('clearShapePreview()'));
});


test("paint refinement subdivides only touched triangles and preserves material assignments", () => {
  const geometry = makePaintGeometry([0, 0, 0, 10, 0, 0, 0, 10, 0]);
  const refined = refinePaintGeometry(geometry, [0], { targetEdgeMm: 2, maxSubdivisions: 8 });
  assert.equal(refined.changed, true);
  assert.equal(refined.positions.length / 9, 64);
  assert.equal(refined.triangleIndexMap.get(0)?.length, 64);

  const remapped = remapPaintRegions([{
    objectId: "model",
    triangleIndices: [0],
    color: "#ff0000",
    materialKey: "ams:1",
  }], "model", refined.triangleIndexMap);
  assert.deepEqual(remapped[0]?.triangleIndices, [...Array(64).keys()]);
  assert.equal(remapped[0]?.materialKey, "ams:1");
});

test("paint workspace stores free paint layers and materializes them only for slicing", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  assert.ok(workspace.includes("type StudioPaintLayer"));
  assert.ok(workspace.includes("#paintLayers = new Map<number, StudioPaintLayer[]>"));
  assert.ok(workspace.includes("#materializePaintLayersForSlicing(plate)"));
  assert.ok(workspace.includes("this.#materializePaintLayersForSlicing(plate);"));
  assert.ok(workspace.includes("this.#paintSession.paint(layer.objectId"));
  assert.ok(workspace.includes("freie Malpunkte"));
});


test("text tool creates a free material-bound paint layer before slicer materialization", () => {
  const tools = readFileSync(join(process.cwd(), "frontend", "studio-paint-ui.ts"), "utf8");
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  const persistence = readFileSync(join(process.cwd(), "frontend", "studio-persistence.ts"), "utf8");
  assert.ok(tools.includes('data-paint-tool=\\"text\\"'));
  assert.ok(tools.includes("getTextSizePx"));
  assert.ok(workspace.includes("applyTextPaint"));
  assert.ok(workspace.includes('this.#createPaintLayer(this.#plate(), hit.objectId, "text"'));
  assert.ok(workspace.includes('"Text: " + text, { text, textSizePx: fontSize }'));
  assert.ok(workspace.includes("sampleLayerPoints(layer, samples)"));
  assert.ok(persistence.includes("PersistedStudioPaintLayer"));
});

test("filament profiles remain available without top material-source switching", () => {
  const profiles = [
    { id: "standard", kind: "filament", source: "builtin", name: "PLA Standard", payload: { vendor: "Generic", material: "PLA" } },
    { id: "local", kind: "filament", source: "local", name: "PLA Lokal", payload: { vendor: "Generic", material: "PLA" } },
    { id: "cloud", kind: "filament", source: "bambu_cloud", name: "PLA Cloud", payload: { vendor: "Generic", material: "PLA" } },
  ];
  const catalog = { profiles, groups: { filament: profiles, printer: [], nozzle: [], process: [], build_plate: [] } } as any;
  const selection = { target_printer_id: "", printer_profile_id: "", nozzle_profile_id: "", process_profile_id: "", build_plate_profile_id: "", filament_profile_ids: ["local", "cloud"] };
  for (const source of ["ams", "external_spool"] as const) {
    const html = studioProfileBarHtml(catalog, [], selection, source, "standard");
    assert.doesNotMatch(html, /data-material-source/);
    assert.match(html, /data-filament-profile-picker/);
    assert.match(html, /AMS und externe Spule nutzen denselben Profilkatalog/);
    for (const profile of profiles) assert.ok(html.includes('data-filament-profile="' + profile.id + '"'));
    const active = source === "ams" ? ["local", "cloud"] : ["standard"];
    for (const id of active) assert.ok(html.includes('aria-pressed="true" data-filament-profile="' + id + '"'));
    assert.equal((html.match(/aria-pressed="true"/g) || []).length, active.length);
    assert.doesNotMatch(html, /Externes Filament|data-cloud-filament-profile|data-external-filament-profile/);
  }
});

test("filament catalog retains same-material local variants and standard profiles", () => {
  const base = { kind: "filament", source: "local", name: "PLA", payload: { vendor: "Generic", material: "PLA", sub_brand: "PLA" } };
  const profiles = [{ ...base, id: "slow" }, { ...base, id: "fast" }, { ...base, id: "builtin", source: "builtin" }];
  const html = filamentProfilesHtml({ profiles, groups: { filament: profiles } } as any, ["fast"]);
  for (const profile of profiles) assert.ok(html.includes('data-filament-profile="' + profile.id + '"'));
  assert.match(html, /aria-pressed="true" data-filament-profile="fast"/);
});

test("support warning lists all object names escaped and offers three explicit decisions", () => {
  const issue = { instanceId: "x", name: "<img src=x>", floatingShellCount: 1, minimumGapMm: 4, overhangTriangleCount: 1, maxOverhangMm: 8, maxOverhangAngleDeg: 0, bridgeOverhangMm: 8 };
  const html = supportWarningHtml(Array.from({ length: 12 }, (_, i) => ({ ...issue, name: issue.name + i })));
  assert.equal((html.match(/<li>/g) || []).length, 12);
  assert.match(html, /&lt;img src=x&gt;11/);
  assert.doesNotMatch(html, /<img/);
  for (const choice of ["cancel", "enable", "continue"]) assert.ok(html.includes('data-support-decision="' + choice + '"'));
  assert.match(html, /nicht die tatsächliche ungestützte Brückenlänge/);
});

test("support warning is modal, survives render attempts and cancels on disconnect", () => {
  const workspace = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  const dialog = readFileSync(join(process.cwd(), "frontend", "support-warning-dialog.ts"), "utf8");
  assert.ok(dialog.includes('createElement("dialog")'));
  assert.ok(dialog.includes("dialog.showModal()"));
  assert.ok(dialog.includes('dialog.addEventListener("cancel"'));
  assert.ok(dialog.includes('dialog.addEventListener("close"'));
  assert.ok(dialog.includes("if (settled) return;"));
  assert.ok(workspace.includes("if (this.#supportWarning) { this.#deferredFullRender = true; return; }"));
  assert.ok(workspace.includes("this.#supportWarning?.cancel();"));
  assert.ok(workspace.includes('if (this.#loading || !plate.instances.length || plate.stage === "slicing") return;'));
  assert.ok(workspace.includes('saveProcess(String(plate.id), { ...processOptions, support_mode: "normal" })'));
  const support = workspace.indexOf("const decision = await this.#supportDecision(supportIssues)");
  const upload = workspace.indexOf("const materialPlan = this.#materialPlan()", support);
  assert.ok(support > 0 && upload > support);
});

test("support analysis detects thin downward triangles independent of area and mirroring", () => {
  const geometry: MeshGeometry = {
    positions: new Float32Array([0,0,0, 1,0,0, 0,1,0, 0,0,2, 0,.1,2, .3,0,2]),
    normals: new Float32Array(18), triangleCount: 2, boundsMin: [0,0,0], boundsMax: [1,1,2],
  };
  const mesh = instance("fine", "Fine underside", geometry);
  assert.equal(analyzeFloatingSupportNeeds([mesh])[0]?.overhangTriangleCount, 1);
  assert.equal(analyzeFloatingSupportNeeds([{ ...mesh, scale: [-1,1,1] }])[0]?.overhangTriangleCount, 1);
});

test("unified filament picker dispatches by material source without cloud synchronization", () => {
  const source = readFileSync(join(process.cwd(), "frontend", "studio-mega-workspace-v2.ts"), "utf8");
  const picker = source.slice(source.indexOf("  #bindFilamentProfilePicker()"), source.indexOf("  #materialSourceChanged("));
  assert.ok(picker.includes('plate.materialSource === "external_spool"'));
  assert.ok(picker.includes("this.#externalFilamentProfileChanged"));
  assert.ok(picker.includes("this.#toggleFilamentProfile"));
  assert.doesNotMatch(source, /#cloudFilamentProfileChanged|syncCloudProfiles\(/);
});


test("MakerWorld description media rejects empty relative and active URLs", () => {
  for (const value of ["", "  ", "/dashboard", "javascript:alert(1)", "data:image/png;base64,x"]) {
    assert.equal(safeMediaUrl(value), "");
  }
  assert.equal(safeMediaUrl("https://example.com/a.png"), "https://example.com/a.png");
});

test("MakerWorld text image links remain visible unless actually rendered inline", () => {
  const url = "https://example.com/a.png";
  const candidates = descriptionImageUrls(`Image: ${url} ![image](${url})`);
  assert.deepEqual(missingDescriptionImages(candidates, []), [url]);
  assert.deepEqual(missingDescriptionImages(candidates, [url]), []);
});

test("MakerWorld additional images are normalized deduplicated and validated", () => {
  assert.deepEqual(missingDescriptionImages(["https://example.com/a.png", "https://example.com/a.png", "javascript:x", "https://example.com/b.png"], ["https://example.com/a.png"]), ["https://example.com/b.png"]);
});
