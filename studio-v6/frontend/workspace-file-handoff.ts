export type WorkspaceFileTarget = "studio" | "slicer";

const pending: Record<WorkspaceFileTarget, File[]> = {
  studio: [],
  slicer: [],
};

export function queueWorkspaceFile(target: WorkspaceFileTarget, file: File): void {
  pending[target].push(file);
}

export function consumeWorkspaceFiles(target: WorkspaceFileTarget): File[] {
  return pending[target].splice(0, pending[target].length);
}

export function hasWorkspaceFiles(target: WorkspaceFileTarget): boolean {
  return pending[target].length > 0;
}