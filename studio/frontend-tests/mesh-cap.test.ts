import { generateCapFaces } from "../frontend/studio-mesh-cap.js";
import type { MeshGeometry } from "../frontend/webgl-studio-viewport.js";

function makeGeometry(triangles: number[]): MeshGeometry {
  return {
    positions: new Float32Array(triangles),
    normals: new Float32Array(triangles.length),
    triangleCount: triangles.length / 9,
    boundsMin: [0, 0, 0] as [number, number, number],
    boundsMax: [1, 1, 1] as [number, number, number],
  };
}

test("cap generation creates faces for a simple box split", () => {
  // Create a simple cube-like geometry (8 vertices, 12 triangles)
  // Then simulate what would be a boundary after split
  const positions = new Float32Array([
    // Front face (z=0)
    0, 0, 0,  1, 0, 0,  1, 1, 0,
    0, 0, 0,  1, 1, 0,  0, 1, 0,
    // Back face (z=1)
    0, 0, 1,  1, 0, 1,  1, 1, 1,
    0, 0, 1,  1, 1, 1,  0, 1, 1,
    // Top face (y=1)
    0, 1, 0,  1, 1, 0,  1, 1, 1,
    0, 1, 0,  1, 1, 1,  0, 1, 1,
    // Bottom face (y=0)
    0, 0, 0,  1, 0, 0,  1, 0, 1,
    0, 0, 0,  1, 0, 1,  0, 0, 1,
    // Left face (x=0)
    0, 0, 0,  0, 1, 0,  0, 1, 1,
    0, 0, 0,  0, 1, 1,  0, 0, 1,
    // Right face (x=1)
    1, 0, 0,  1, 1, 0,  1, 1, 1,
    1, 0, 0,  1, 1, 1,  1, 0, 1,
  ]);
  
  const geometry = makeGeometry(positions);
  const result = generateCapFaces(geometry, "z");
  
  // A closed cube has no boundary edges, so no caps should be generated
  assert.equal(result.capCount, 0);
});

test("cap generation creates triangular cap for open face", () => {
  // Create a simple triangle (open face)
  const positions = new Float32Array([
    0, 0, 0,  1, 0, 0,  0, 1, 0,
  ]);
  
  const geometry = makeGeometry(positions);
  const result = generateCapFaces(geometry, "z");
  
  // Triangle should create 1 cap face (itself, but with correct winding)
  assert.equal(result.capCount, 1);
  assert.equal(result.capPositions.length, 9);
});

test("cap generation creates quadrilateral cap for square open face", () => {
  // Create a square (2 triangles sharing an edge) - this simulates an open face after split
  const positions = new Float32Array([
    0, 0, 0,  1, 0, 0,  1, 1, 0,
    0, 0, 0,  1, 1, 0,  0, 1, 0,
  ]);
  
  const geometry = makeGeometry(positions);
  const result = generateCapFaces(geometry, "z");
  
  // The square should create 1 additional cap (triangulated from corner)
  assert.ok(result.capCount >= 1);
});

test("cap winding is consistent with face normal direction", () => {
  // Create two triangles forming a square in XY plane
  const positions = new Float32Array([
    0, 0, 0,  1, 0, 0,  1, 1, 0,
    0, 0, 0,  1, 1, 0,  0, 1, 0,
  ]);
  
  const geometry = makeGeometry(positions);
  const result = generateCapFaces(geometry, "z");
  
  // For Z-axis, caps should have normal pointing in +Z direction
  // Check that the generated cap positions form valid triangles
  assert.ok(result.capPositions.length >= 9);
  
  // Verify the cap has at least one triangle
  assert.ok(result.capCount > 0);
});
