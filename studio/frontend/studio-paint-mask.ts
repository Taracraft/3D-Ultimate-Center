/** A captured object-local projection: camera changes never move committed paint. */
export type MaterialPaintMask = Readonly<{
  kind: "rectangle" | "circle" | "text";
  matrix: number[];
  left: number;
  top: number;
  right: number;
  bottom: number;
  width?: number;
  height?: number;
  runs?: number[];
}>;

export function validatePaintMask(mask: MaterialPaintMask): void {
  if (!["rectangle", "circle", "text"].includes(mask.kind) || !Array.isArray(mask.matrix) || mask.matrix.length !== 16 || mask.matrix.some((value) => !Number.isFinite(value))
    || ![mask.left, mask.top, mask.right, mask.bottom].every(Number.isFinite) || mask.right <= mask.left || mask.bottom <= mask.top) {
    throw new Error("Die gespeicherte Malform ist ungültig; die Bemalung wurde nicht verändert.");
  }
  if (mask.kind !== "text") {
    if (mask.runs !== undefined) {
      if (!Array.isArray(mask.runs) || mask.runs.length > 2_000_000 || mask.runs.length % 2 !== 0) throw new Error("Die mitgeführten Maskenbereiche überschreiten das Größenbudget.");
      let previous = 0;
      for (let index = 0; index < mask.runs.length; index += 2) {
        const start = mask.runs[index]!, end = mask.runs[index + 1]!;
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < previous || end <= start || end > 1_000_000) throw new Error("Die mitgeführten Maskenbereiche sind ungültig.");
        previous = end;
      }
    }
    return;
  }
  if (!Number.isInteger(mask.width) || !Number.isInteger(mask.height) || !mask.width || !mask.height || mask.width < 1 || mask.height < 1 || mask.width * mask.height > 1_000_000 || !Array.isArray(mask.runs) || mask.runs.length > mask.width * mask.height * 2 || mask.runs.length % 2 !== 0) {
    throw new Error("Die Textmaske ist unvollständig oder überschreitet das Größenbudget.");
  }
  let previous = 0;
  for (let index = 0; index < mask.runs.length; index += 2) {
    const start = mask.runs[index]!, end = mask.runs[index + 1]!;
    if (!Number.isInteger(start) || !Number.isInteger(end) || start < previous || end <= start || end > mask.width * mask.height) throw new Error("Die Textmaske enthält ungültige Pixelbereiche.");
    previous = end;
  }
}

/** Compress the actual canvas glyph alpha; empty glyphs remain empty, never a fallback dot. */
export function paintMaskRuns(alpha: ArrayLike<number>, width: number, height: number, stride = 4): number[] {
  if (!Number.isInteger(stride) || stride < 1 || stride > 4 || !Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 || width * height > 1_000_000 || alpha.length !== width * height * stride) throw new Error("Die Textmaske überschreitet das Größenbudget oder ist unvollständig.");
  const runs: number[] = [];
  let start = -1;
  for (let pixel = 0; pixel < width * height; pixel += 1) {
    const painted = (alpha[pixel * stride + stride - 1] ?? 0) >= 128;
    if (painted && start < 0) start = pixel;
    if (!painted && start >= 0) { runs.push(start, pixel); start = -1; }
  }
  if (start >= 0) runs.push(start, width * height);
  return runs;
}

export function paintMaskContains(mask: MaterialPaintMask | undefined, x: number, y: number, z: number): boolean {
  if (!mask) return true;
  const m = mask.matrix;
  const w = m[3]! * x + m[7]! * y + m[11]! * z + m[15]!;
  if (!Number.isFinite(w) || w <= 0) return false;
  const depth = (m[2]! * x + m[6]! * y + m[10]! * z + m[14]!) / w;
  if (depth < -1 || depth > 1) return false;
  const px = ((m[0]! * x + m[4]! * y + m[8]! * z + m[12]!) / w + 1) / 2;
  const py = (1 - (m[1]! * x + m[5]! * y + m[9]! * z + m[13]!) / w) / 2;
  if (px < mask.left || px >= mask.right || py < mask.top || py >= mask.bottom) return false;
  const u = (px - mask.left) / (mask.right - mask.left), v = (py - mask.top) / (mask.bottom - mask.top);
  if (mask.kind === "circle") return (u * 2 - 1) ** 2 + (v * 2 - 1) ** 2 <= 1;
  if (mask.kind === "rectangle") return true;
  // Reflection/reprojection can represent the same rational pixel edge on opposite sides
  // of one floating-point ULP. Snap only numerical edge noise, never a visible pixel area.
  const pixelCoordinate = (value: number): number => {
    const integer = Math.round(value);
    return Math.floor(Math.abs(value - integer) <= 1e-9 ? integer : value);
  };
  const column = pixelCoordinate(u * mask.width!), row = pixelCoordinate(v * mask.height!);
  if (column >= mask.width! || row >= mask.height!) return false;
  const pixel = row * mask.width! + column;
  const runs = mask.runs!;
  let low = 0, high = runs.length / 2;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (runs[middle * 2 + 1]! <= pixel) low = middle + 1;
    else high = middle;
  }
  return low * 2 < runs.length && pixel >= runs[low * 2]! && pixel < runs[low * 2 + 1]!;
}

/** Keep point spacing tied to the real projected brush, including zoomed-out models. */
export function paintSamplingStep(matrix: readonly number[], point: readonly number[], radiusMm: number, width: number, height: number): number {
  if (matrix.length !== 16 || !matrix.every(Number.isFinite) || point.length !== 3 || !point.every(Number.isFinite) || ![radiusMm, width, height].every((value) => Number.isFinite(value) && value > 0)) throw new Error("Die Malprojektion ist ungültig.");
  const projected = (position: readonly number[]): number[] => {
    const [x, y, z] = position as readonly [number, number, number];
    const w = matrix[3]! * x + matrix[7]! * y + matrix[11]! * z + matrix[15]!;
    if (w <= 0) throw new Error("Die Malfläche liegt außerhalb der sichtbaren Projektion.");
    return [(matrix[0]! * x + matrix[4]! * y + matrix[8]! * z + matrix[12]!) / w * width / 2, (matrix[1]! * x + matrix[5]! * y + matrix[9]! * z + matrix[13]!) / w * height / 2];
  };
  const origin = projected(point);
  const radii = [0, 1, 2].map((axis) => {
    const moved = [...point]; moved[axis] = moved[axis]! + radiusMm;
    const target = projected(moved);
    return Math.hypot(target[0]! - origin[0]!, target[1]! - origin[1]!);
  }).filter((value) => value > 1e-5);
  const radius = Math.min(...radii);
  if (!Number.isFinite(radius) || radius < .2) throw new Error("Der Pinsel ist in dieser Ansicht zu klein. Bitte näher an das Modell heranzoomen.");
  return Math.max(.1, Math.min(3, radius * .45));
}
