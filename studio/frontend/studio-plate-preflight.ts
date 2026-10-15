import { yieldToBrowser } from "./browser-yield.js";
import { transformPoint, transformedBounds } from "./mesh-export.js";
import type { MeshInstance } from "./webgl-studio-viewport.js";

export type PlateBoundsIssue = Readonly<{
  instanceId: string;
  name: string;
  minimum: readonly [number, number, number];
  maximum: readonly [number, number, number];
  overflowLeftMm: number;
  overflowRightMm: number;
  overflowFrontMm: number;
  overflowBackMm: number;
  overflowBelowMm: number;
  overflowTopMm: number;
}>;

const TOLERANCE_MM = 0.01;
const VERTEX_BATCH = 60_000;

function safelyInsideVolume(
  minimum: readonly [number, number, number],
  maximum: readonly [number, number, number],
  width: number,
  depth: number,
  height: number,
): boolean {
  return minimum[0] >= -TOLERANCE_MM
    && minimum[1] >= -TOLERANCE_MM
    && minimum[2] >= -TOLERANCE_MM
    && maximum[0] <= width + TOLERANCE_MM
    && maximum[1] <= depth + TOLERANCE_MM
    && (
      !Number.isFinite(height)
      || maximum[2] <= height + TOLERANCE_MM
    );
}

export async function analyzePlateBounds(
  instances: readonly MeshInstance[],
  plateWidthMm: number,
  plateDepthMm: number,
  buildHeightMm = Infinity,
): Promise<PlateBoundsIssue[]> {
  const issues: PlateBoundsIssue[] = [];
  let processedVertices = 0;

  for (const instance of instances) {
    if (!instance.visible || !instance.geometry.positions.length) continue;

    const fastBounds = transformedBounds(instance.geometry, {
      position: instance.position,
      rotation: instance.rotation,
      scale: instance.scale,
    });
    if (safelyInsideVolume(
      fastBounds.min,
      fastBounds.max,
      plateWidthMm,
      plateDepthMm,
      buildHeightMm,
    )) {
      continue;
    }

    // Only boundary cases need the expensive exact vertex scan. This keeps
    // the preflight exact while avoiding millions of transforms for objects
    // whose transformed bounding box is already safely inside the volume.
    const minimum: [number, number, number] = [Infinity, Infinity, Infinity];
    const maximum: [number, number, number] = [-Infinity, -Infinity, -Infinity];
    const positions = instance.geometry.positions;

    for (let index = 0; index < positions.length; index += 3) {
      const point = transformPoint(
        [positions[index]!, positions[index + 1]!, positions[index + 2]!],
        {
          position: instance.position,
          rotation: instance.rotation,
          scale: instance.scale,
        },
      );
      minimum[0] = Math.min(minimum[0], point[0]);
      minimum[1] = Math.min(minimum[1], point[1]);
      minimum[2] = Math.min(minimum[2], point[2]);
      maximum[0] = Math.max(maximum[0], point[0]);
      maximum[1] = Math.max(maximum[1], point[1]);
      maximum[2] = Math.max(maximum[2], point[2]);
      processedVertices += 1;
      if (processedVertices % VERTEX_BATCH === 0) await yieldToBrowser();
    }

    const overflowLeftMm = Math.max(0, -minimum[0]);
    const overflowRightMm = Math.max(0, maximum[0] - plateWidthMm);
    const overflowFrontMm = Math.max(0, -minimum[1]);
    const overflowBackMm = Math.max(0, maximum[1] - plateDepthMm);
    const overflowBelowMm = Math.max(0, -minimum[2]);
    const overflowTopMm = Number.isFinite(buildHeightMm)
      ? Math.max(0, maximum[2] - buildHeightMm)
      : 0;

    if (Math.max(
      overflowLeftMm,
      overflowRightMm,
      overflowFrontMm,
      overflowBackMm,
      overflowBelowMm,
      overflowTopMm,
    ) <= TOLERANCE_MM) {
      continue;
    }

    issues.push({
      instanceId: instance.id,
      name: instance.name,
      minimum,
      maximum,
      overflowLeftMm,
      overflowRightMm,
      overflowFrontMm,
      overflowBackMm,
      overflowBelowMm,
      overflowTopMm,
    });
  }

  return issues;
}

function overflowParts(issue: PlateBoundsIssue): string[] {
  const parts: string[] = [];
  if (issue.overflowLeftMm > TOLERANCE_MM) {
    parts.push(`${issue.overflowLeftMm.toFixed(2)} mm links`);
  }
  if (issue.overflowRightMm > TOLERANCE_MM) {
    parts.push(`${issue.overflowRightMm.toFixed(2)} mm rechts`);
  }
  if (issue.overflowFrontMm > TOLERANCE_MM) {
    parts.push(`${issue.overflowFrontMm.toFixed(2)} mm vorne`);
  }
  if (issue.overflowBackMm > TOLERANCE_MM) {
    parts.push(`${issue.overflowBackMm.toFixed(2)} mm hinten`);
  }
  if (issue.overflowBelowMm > TOLERANCE_MM) {
    parts.push(
      `${issue.overflowBelowMm.toFixed(2)} mm unterhalb der Platte`,
    );
  }
  if (issue.overflowTopMm > TOLERANCE_MM) {
    parts.push(
      `${issue.overflowTopMm.toFixed(2)} mm oberhalb des Bauraums`,
    );
  }
  return parts;
}

export function plateBoundsErrorMessage(
  issues: readonly PlateBoundsIssue[],
): string {
  const details = issues
    .slice(0, 5)
    .map((issue) => `${issue.name}: ${overflowParts(issue).join(", ")}`)
    .join("; ");
  const suffix = issues.length > 5
    ? `; und ${issues.length - 5} weitere Objekte`
    : "";
  return `Slicing wurde vor dem Upload blockiert. Mindestens ein Objekt liegt außerhalb des Druckraums: ${details}${suffix}. Die betroffenen Objekte wurden markiert. Bitte verschieben, zentrieren oder anordnen und erneut slicen.`;
}
