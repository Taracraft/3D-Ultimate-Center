import { STUDIO_BRANDING } from "./branding.js";
import { yieldToBrowser } from "./browser-yield.js";
import { transformPoint } from "./mesh-export.js";
import type { ThreeMfMesh, ThreeMfMetadata } from "./three-mf-export.js";

const encoder = new TextEncoder();
const XML_CHUNK_CHARACTERS = 512 * 1024;

type ZipEntry = Readonly<{
  name: string;
  data: Uint8Array;
  crc: number;
  uncompressedSize: number;
  compressionMethod: number;
}>;

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

function concatenate(chunks: readonly Uint8Array[]): Uint8Array {
  const length = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
  const output = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return output;
}

function crc32Update(current: number, data: Uint8Array): number {
  let crc = current >>> 0;
  for (const byte of data) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ ((crc & 1) ? 0xEDB88320 : 0);
  }
  return crc >>> 0;
}

function dosDateTime(date: Date): { date: number; time: number } {
  const year = Math.max(1980, date.getFullYear());
  return {
    date: ((year - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    time: (date.getHours() << 11) | (date.getMinutes() << 5) | Math.floor(date.getSeconds() / 2),
  };
}

async function compressedEntry(name: string, chunks: AsyncIterable<Uint8Array>): Promise<ZipEntry> {
  const Compression = globalThis.CompressionStream as unknown as (new (format: string) => CompressionStream) | undefined;
  if (typeof Compression !== "function") throw new Error("Dieser Browser unterstützt keinen gestreamten 3MF-Export.");

  const compression = new Compression("deflate-raw");
  const writer = compression.writable.getWriter();
  const outputChunks: Uint8Array[] = [];
  const readerTask = (async () => {
    const reader = compression.readable.getReader();
    try {
      while (true) {
        const result = await reader.read();
        if (result.done) break;
        if (result.value?.byteLength) outputChunks.push(result.value);
      }
    } finally {
      reader.releaseLock();
    }
  })();

  let crc = 0xFFFFFFFF;
  let uncompressedSize = 0;
  try {
    for await (const chunk of chunks) {
      crc = crc32Update(crc, chunk);
      uncompressedSize += chunk.byteLength;
      const writableChunk = chunk.buffer instanceof ArrayBuffer
        ? new Uint8Array(chunk.buffer, chunk.byteOffset, chunk.byteLength)
        : Uint8Array.from(chunk);
      await writer.write(writableChunk);
    }
    await writer.close();
    await readerTask;
  } catch (error) {
    try { await writer.abort(error); } catch {}
    throw error;
  }

  return {
    name,
    data: concatenate(outputChunks),
    crc: (crc ^ 0xFFFFFFFF) >>> 0,
    uncompressedSize,
    compressionMethod: 8,
  };
}

async function* singleChunk(value: string): AsyncGenerator<Uint8Array> {
  yield encoder.encode(value);
}

async function* modelXmlChunks(
  meshes: readonly ThreeMfMesh[],
  metadata: ThreeMfMetadata,
  onProgress?: (progress: number) => void,
): AsyncGenerator<Uint8Array> {
  const materials = metadata.materials?.length
    ? metadata.materials.map((item) => ({ name: String(item.name || "Material"), color: normalizeColor(item.color) }))
    : meshes.map((mesh, index) => ({ name: `Material ${index + 1}`, color: normalizeColor(mesh.color) }));
  const colors = materials.map((item) => item.color);
  const metadataEntries = [
    ["Title", metadata.title],
    ["Description", metadata.description || STUDIO_BRANDING.exportDescription],
    ["Application", STUDIO_BRANDING.exportApplication],
    ["Ultimate3D:BuildPlateProfile", metadata.buildPlateProfileId || ""],
    ["Ultimate3D:BuildPlateName", metadata.buildPlateName || ""],
    ["Ultimate3D:PlateWidthMm", metadata.plateWidthMm ?? ""],
    ["Ultimate3D:PlateDepthMm", metadata.plateDepthMm ?? ""],
  ].filter((entry) => String(entry[1]).length > 0)
    .map(([name, value]) => `<metadata name="${xml(name)}">${xml(value)}</metadata>`)
    .join("");

  const totalTriangles = Math.max(1, meshes.reduce((sum, mesh) => sum + mesh.geometry.triangleCount, 0));
  const totalWork = totalTriangles * 2;
  let completedWork = 0;
  let buffer = `<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="de-DE" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">${metadataEntries}<resources><basematerials id="1">${materials.map((item) => `<base name="${xml(item.name)}" displaycolor="${item.color}"/>`).join("")}</basematerials>`;

  const flush = async (): Promise<Uint8Array | null> => {
    if (!buffer.length) return null;
    const chunk = encoder.encode(buffer);
    buffer = "";
    onProgress?.(Math.min(1, completedWork / totalWork));
    await yieldToBrowser();
    return chunk;
  };

  for (let meshIndex = 0; meshIndex < meshes.length; meshIndex += 1) {
    const mesh = meshes[meshIndex]!;
    const objectId = meshIndex + 2;
    const positions = mesh.geometry.positions;
    const materialIndex = Number.isInteger(mesh.materialIndex) && mesh.materialIndex! >= 0 && mesh.materialIndex! < colors.length ? mesh.materialIndex! : Math.min(meshIndex, colors.length - 1);
    buffer += `<object id="${objectId}" type="model" name="${xml(mesh.name)}" pid="1" pindex="${materialIndex}"><mesh><vertices>`;

    for (let index = 0; index < positions.length; index += 9) {
      const points = [
        transformPoint([positions[index]!, positions[index + 1]!, positions[index + 2]!], mesh.transform),
        transformPoint([positions[index + 3]!, positions[index + 4]!, positions[index + 5]!], mesh.transform),
        transformPoint([positions[index + 6]!, positions[index + 7]!, positions[index + 8]!], mesh.transform),
      ];
      for (const point of points) buffer += `<vertex x="${point[0]}" y="${point[1]}" z="${point[2]}"/>`;
      completedWork += 1;
      if (buffer.length >= XML_CHUNK_CHARACTERS) {
        const chunk = await flush();
        if (chunk) yield chunk;
      }
    }

    buffer += `</vertices><triangles>`;
    let vertexIndex = 0;
    for (let index = 0; index < positions.length; index += 9) {
      const paintedMaterial = mesh.triangleMaterialIndices?.[index / 9];
      const faceMaterial = Number.isInteger(paintedMaterial) && paintedMaterial! >= 0 && paintedMaterial! < colors.length ? paintedMaterial! : materialIndex;
      const materialProperty = faceMaterial === materialIndex ? "" : ` pid="1" p1="${faceMaterial}"`;
      buffer += `<triangle v1="${vertexIndex}" v2="${vertexIndex + 1}" v3="${vertexIndex + 2}"${materialProperty}/>`;
      vertexIndex += 3;
      completedWork += 1;
      if (buffer.length >= XML_CHUNK_CHARACTERS) {
        const chunk = await flush();
        if (chunk) yield chunk;
      }
    }
    buffer += `</triangles></mesh></object>`;
  }

  buffer += `</resources><build>${meshes.map((_mesh, index) => `<item objectid="${index + 2}"/>`).join("")}</build></model>`;
  const finalChunk = await flush();
  if (finalChunk) yield finalChunk;
  onProgress?.(1);
}

function zip(entries: readonly ZipEntry[]): Uint8Array {
  const locals: Uint8Array[] = [];
  const centrals: Uint8Array[] = [];
  let localOffset = 0;
  const stamp = dosDateTime(new Date());

  for (const entry of entries) {
    if (entry.data.byteLength > 0xFFFFFFFF || entry.uncompressedSize > 0xFFFFFFFF || localOffset > 0xFFFFFFFF) {
      throw new Error("Der 3MF-Export überschreitet die unterstützte ZIP-Größe.");
    }
    const name = encoder.encode(entry.name);
    const local = new Uint8Array(30 + name.length + entry.data.byteLength);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034B50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0x0800, true);
    localView.setUint16(8, entry.compressionMethod, true);
    localView.setUint16(10, stamp.time, true);
    localView.setUint16(12, stamp.date, true);
    localView.setUint32(14, entry.crc, true);
    localView.setUint32(18, entry.data.byteLength, true);
    localView.setUint32(22, entry.uncompressedSize, true);
    localView.setUint16(26, name.length, true);
    localView.setUint16(28, 0, true);
    local.set(name, 30);
    local.set(entry.data, 30 + name.length);
    locals.push(local);

    const central = new Uint8Array(46 + name.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014B50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0x0800, true);
    centralView.setUint16(10, entry.compressionMethod, true);
    centralView.setUint16(12, stamp.time, true);
    centralView.setUint16(14, stamp.date, true);
    centralView.setUint32(16, entry.crc, true);
    centralView.setUint32(20, entry.data.byteLength, true);
    centralView.setUint32(24, entry.uncompressedSize, true);
    centralView.setUint16(28, name.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, localOffset, true);
    central.set(name, 46);
    centrals.push(central);
    localOffset += local.byteLength;
  }

  const localData = concatenate(locals);
  const centralData = concatenate(centrals);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054B50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, entries.length, true);
  endView.setUint16(10, entries.length, true);
  endView.setUint32(12, centralData.byteLength, true);
  endView.setUint32(16, localData.byteLength, true);
  endView.setUint16(20, 0, true);
  return concatenate([localData, centralData, end]);
}

export async function export3mfStreamed(
  meshes: readonly ThreeMfMesh[],
  metadata: ThreeMfMetadata,
  onProgress?: (progress: number) => void,
): Promise<ArrayBuffer> {
  if (!meshes.length || !meshes.some((mesh) => mesh.geometry.triangleCount > 0)) {
    throw new Error("Die Szene enthält keine exportierbare Geometrie.");
  }
  const contentTypes = `<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>`;
  const relationships = `<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>`;
  const entries = await Promise.all([
    compressedEntry("[Content_Types].xml", singleChunk(contentTypes)),
    compressedEntry("_rels/.rels", singleChunk(relationships)),
    compressedEntry("3D/3dmodel.model", modelXmlChunks(meshes, metadata, onProgress)),
  ]);
  const bytes = zip(entries);
  const output = new Uint8Array(bytes.byteLength);
  output.set(bytes);
  return output.buffer;
}
