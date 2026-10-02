import { transformPoint, type ExportMesh } from "./mesh-export.js";

export type ThreeMfMesh = ExportMesh & Readonly<{ color?: string }>;
export type ThreeMfMetadata = Readonly<{
  title: string;
  description?: string;
  buildPlateProfileId?: string;
  buildPlateName?: string;
  plateWidthMm?: number;
  plateDepthMm?: number;
}>;

const encoder = new TextEncoder();

function xml(value: unknown): string {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&apos;",
  }[character] || character));
}

function normalizeColor(value: string | undefined): string {
  const raw = String(value || "#38AEE8").trim().replace(/^#/, "").toUpperCase();
  return /^[0-9A-F]{6}$/.test(raw) ? `#${raw}FF` : "#38AEE8FF";
}

function modelXml(meshes: readonly ThreeMfMesh[], metadata: ThreeMfMetadata): string {
  const colors = meshes.map((mesh) => normalizeColor(mesh.color));
  const resources: string[] = [
    `<basematerials id="1">${colors.map((color, index) => `<base name="Material ${index + 1}" displaycolor="${color}"/>`).join("")}</basematerials>`,
  ];
  const build: string[] = [];

  meshes.forEach((mesh, meshIndex) => {
    const vertices: string[] = [];
    const triangles: string[] = [];
    const positions = mesh.geometry.positions;
    let vertexIndex = 0;
    for (let index = 0; index < positions.length; index += 9) {
      const points = [
        transformPoint([positions[index]!, positions[index + 1]!, positions[index + 2]!], mesh.transform),
        transformPoint([positions[index + 3]!, positions[index + 4]!, positions[index + 5]!], mesh.transform),
        transformPoint([positions[index + 6]!, positions[index + 7]!, positions[index + 8]!], mesh.transform),
      ];
      for (const point of points) {
        vertices.push(`<vertex x="${point[0]}" y="${point[1]}" z="${point[2]}"/>`);
      }
      triangles.push(`<triangle v1="${vertexIndex}" v2="${vertexIndex + 1}" v3="${vertexIndex + 2}"/>`);
      vertexIndex += 3;
    }
    const objectId = meshIndex + 2;
    resources.push(`<object id="${objectId}" type="model" name="${xml(mesh.name)}" pid="1" pindex="${meshIndex}"><mesh><vertices>${vertices.join("")}</vertices><triangles>${triangles.join("")}</triangles></mesh></object>`);
    build.push(`<item objectid="${objectId}"/>`);
  });

  const metadataEntries = [
    ["Title", metadata.title],
    ["Description", metadata.description || "Exportiert mit Ultimate 3D Studio V6"],
    ["Application", "Ultimate 3D Studio V6"],
    ["Ultimate3D:BuildPlateProfile", metadata.buildPlateProfileId || ""],
    ["Ultimate3D:BuildPlateName", metadata.buildPlateName || ""],
    ["Ultimate3D:PlateWidthMm", metadata.plateWidthMm ?? ""],
    ["Ultimate3D:PlateDepthMm", metadata.plateDepthMm ?? ""],
  ].filter((entry) => String(entry[1]).length > 0)
    .map(([name, value]) => `<metadata name="${xml(name)}">${xml(value)}</metadata>`)
    .join("");

  return `<?xml version="1.0" encoding="UTF-8"?>` +
    `<model unit="millimeter" xml:lang="de-DE" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">` +
    metadataEntries + `<resources>${resources.join("")}</resources><build>${build.join("")}</build></model>`;
}

function crc32(data: Uint8Array): number {
  let crc = 0xFFFFFFFF;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function dosDateTime(date: Date): { date: number; time: number } {
  const year = Math.max(1980, date.getFullYear());
  return {
    date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    time: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2),
  };
}

function concatenate(chunks: readonly Uint8Array[]): Uint8Array {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const output = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function zipStore(files: ReadonlyArray<Readonly<{ name: string; data: Uint8Array }>>): Uint8Array {
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let localOffset = 0;
  const stamp = dosDateTime(new Date());

  for (const file of files) {
    const name = encoder.encode(file.name);
    const crc = crc32(file.data);
    const local = new Uint8Array(30 + name.length + file.data.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034B50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0x0800, true);
    localView.setUint16(8, 0, true);
    localView.setUint16(10, stamp.time, true);
    localView.setUint16(12, stamp.date, true);
    localView.setUint32(14, crc, true);
    localView.setUint32(18, file.data.length, true);
    localView.setUint32(22, file.data.length, true);
    localView.setUint16(26, name.length, true);
    localView.setUint16(28, 0, true);
    local.set(name, 30);
    local.set(file.data, 30 + name.length);
    locals.push(local);

    const central = new Uint8Array(46 + name.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014B50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0x0800, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, stamp.time, true);
    centralView.setUint16(14, stamp.date, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, file.data.length, true);
    centralView.setUint32(24, file.data.length, true);
    centralView.setUint16(28, name.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, localOffset, true);
    central.set(name, 46);
    centrals.push(central);
    localOffset += local.length;
  }

  const localData = concatenate(locals);
  const centralData = concatenate(centrals);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054B50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, files.length, true);
  endView.setUint16(10, files.length, true);
  endView.setUint32(12, centralData.length, true);
  endView.setUint32(16, localData.length, true);
  endView.setUint16(20, 0, true);
  return concatenate([localData, centralData, end]);
}

export function export3mf(meshes: readonly ThreeMfMesh[], metadata: ThreeMfMetadata): ArrayBuffer {
  if (!meshes.length || !meshes.some((mesh) => mesh.geometry.triangleCount > 0)) {
    throw new Error("Die Szene enthält keine exportierbare Geometrie.");
  }
  const contentTypes = `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>`;
  const relationships = `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>`;
  const bytes = zipStore([
    { name: "[Content_Types].xml", data: encoder.encode(contentTypes) },
    { name: "_rels/.rels", data: encoder.encode(relationships) },
    { name: "3D/3dmodel.model", data: encoder.encode(modelXml(meshes, metadata)) },
  ]);
  const output = new Uint8Array(bytes.byteLength);
  output.set(bytes);
  return output.buffer;
}