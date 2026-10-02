import type { WorkspaceFileTarget } from "./workspace-file-handoff.js";

export type WorkspaceSource = "gallery" | "storage" | "makerworld";
export type WorkspaceSourceRequest = Readonly<{
  target: WorkspaceFileTarget;
  source: WorkspaceSource;
}>;

let pendingRequest: WorkspaceSourceRequest | null = null;

export function requestWorkspaceSource(
  host: HTMLElement,
  target: WorkspaceFileTarget,
  source: WorkspaceSource,
): void {
  pendingRequest = { target, source };
  host.dispatchEvent(new CustomEvent<WorkspaceSourceRequest>(
    "workspace-source-request",
    {
      bubbles: true,
      composed: true,
      detail: pendingRequest,
    },
  ));
}

export function consumeWorkspaceSourceRequest(): WorkspaceSourceRequest | null {
  const request = pendingRequest;
  pendingRequest = null;
  return request;
}
