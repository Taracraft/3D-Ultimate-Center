export type WorkspaceRoute =
  | { name: "steuerung" }
  | { name: "galerie" }
  | { name: "studio"; projectId?: string }
  | { name: "slicer"; jobId?: string }
  | { name: "ams" }
  | { name: "profile" }
  | { name: "aufgaben" }
  | { name: "verlauf" }
  | { name: "system" }
  | { name: "slicing-server" };

const ROUTE_SECTIONS = new Set([
  "steuerung",
  "galerie",
  "studio",
  "slicer",
  "ams",
  "profile",
  "aufgaben",
  "verlauf",
  "system",
  "slicing-server",
]);

function routeParts(path: string): string[] {
  const parts = path.replace(/^#?\/?/, "").split("/").filter(Boolean);
  const first = parts[0];
  if (!first || ROUTE_SECTIONS.has(first)) return parts;
  const routeIndex = parts.findIndex((part) => ROUTE_SECTIONS.has(part));
  return routeIndex > 0 ? parts.slice(routeIndex) : parts;
}

export function parseRoute(path: string): WorkspaceRoute {
  const parts = routeParts(path);
  const section = parts[0] ?? "steuerung";

  switch (section) {
    case "galerie":
      return { name: "galerie" };
    case "studio":
      return parts[1] ? { name: "studio", projectId: parts[1] } : { name: "studio" };
    case "slicer":
      return parts[1] ? { name: "slicer", jobId: parts[1] } : { name: "slicer" };
    case "ams":
      return { name: "ams" };
    case "profile":
      return { name: "profile" };
    case "aufgaben":
      return { name: "aufgaben" };
    case "verlauf":
      return { name: "verlauf" };
    case "system":
      return { name: "system" };
    case "slicing-server":
      return { name: "slicing-server" };
    default:
      return { name: "steuerung" };
  }
}

export function routeToHash(route: WorkspaceRoute): string {
  switch (route.name) {
    case "studio":
      return route.projectId ? `#/studio/${route.projectId}` : "#/studio";
    case "slicer":
      return route.jobId ? `#/slicer/${route.jobId}` : "#/slicer";
    default:
      return `#/${route.name}`;
  }
}