export type WorkspaceRoute =
  | { name: "steuerung" }
  | { name: "galerie" }
  | { name: "studio"; projectId?: string }
  | { name: "slicer"; jobId?: string }
  | { name: "ams" }
  | { name: "profile" }
  | { name: "aufgaben"; jobId?: string }
  | { name: "verlauf" }
  | { name: "system" }
  | { name: "slicing-server" };

export function parseRoute(path: string): WorkspaceRoute {
  const parts = path.replace(/^#?\/?/, "").split("/").filter(Boolean);
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
      return parts[1] ? { name: "aufgaben", jobId: parts[1] } : { name: "aufgaben" };
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
    case "aufgaben":
      return route.jobId ? `#/aufgaben/${route.jobId}` : "#/aufgaben";
    default:
      return `#/${route.name}`;
  }
}
