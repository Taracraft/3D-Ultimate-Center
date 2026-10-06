export type HomeAssistantApiHost = Readonly<{
  callApi: <T>(method: string, path: string, parameters?: unknown) => Promise<T>;
  auth?: Readonly<{
    accessToken?: string;
    data?: Readonly<{
      access_token?: string;
    }>;
  }>;
}>;

export type ApiError = Readonly<{
  code?: string;
  message?: string;
  details?: Readonly<Record<string, unknown>> | undefined;
}>;

export type ApiEnvelope<T> = Readonly<{
  data?: T | null;
  error?: ApiError | null;
  request_id?: string;
  version?: string;
}>;

export type FrontendAuditEvent = Readonly<{
  category: string;
  component: string;
  event: string;
  status?: "info" | "success" | "warning" | "error" | "failed" | "cancelled";
  source?: string | undefined;
  correlation_id?: string | undefined;
  job_id?: string | undefined;
  printer_id?: string | undefined;
  duration_ms?: number | undefined;
  details?: Readonly<Record<string, unknown>>;
}>;

let homeAssistant: HomeAssistantApiHost | null = null;
const auditQueue: FrontendAuditEvent[] = [];
const lastGetAudit = new Map<string, number>();
const AUDIT_PATH = "ultimate_3d_studio_v6/v1/system/audit";
const GET_AUDIT_INTERVAL_MS = 60_000;

function record(value: unknown): Readonly<Record<string, unknown>> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Readonly<Record<string, unknown>>
    : null;
}

export function errorMessage(error: unknown, fallback = "API-Anfrage fehlgeschlagen."): string {
  // Home Assistant wraps non-2xx responses in a generic transport error.
  // Keep the server's structured explanation without repeating the request.
  const wrapped = record(error);
  const body = record(wrapped?.body);
  const serverError = record(body?.error);
  const serverMessage = serverError?.message;
  if (typeof serverMessage === "string" && serverMessage.trim()) return serverMessage;
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === "string" && error.trim()) return error;
  const top = record(error);
  if (top) {
    for (const key of ["message", "detail", "description", "reason"] as const) {
      const value = top[key];
      if (typeof value === "string" && value.trim()) return value;
    }
    for (const key of ["error", "body", "response", "data"] as const) {
      const nested = top[key];
      if (nested !== undefined && nested !== error) {
        const message = errorMessage(nested, "");
        if (message) return message;
      }
    }
    try {
      const serialized = JSON.stringify(top);
      if (serialized && serialized !== "{}") return serialized;
    } catch {}
  }
  return fallback;
}

function normalizedPath(path: string): string {
  return path.replace(/^\/+/, "").replace(/^api\//, "");
}

function auditCategory(path: string): string {
  const value = path.toLocaleLowerCase("de-DE");
  if (value.includes("makerworld")) return "MakerWorld";
  if (value.includes("gallery") || value.includes("galerie")) return "Galerie";
  if (value.includes("profile")) return "Profile";
  if (value.includes("camera")) return "Kamera";
  if (value.includes("ams") || value.includes("filament")) return "AMS";
  if (value.includes("printer_slicing_server") || value.includes("slicing-server")) return "Slicing-Server";
  if (value.includes("slicer") || value.includes("slice") || value.includes("gcode") || value.includes("toolpath")) return "Slicer";
  if (value.includes("direct-print") || value.includes("print") || value.includes("printer")) return "Druck";
  if (value.includes("studio") || value.includes("scene") || value.includes("model")) return "Studio";
  return "API";
}

function auditPath(input: RequestInfo | URL): string {
  try {
    if (input instanceof URL) return input.pathname.replace(/^\/api\//, "");
    if (typeof input === "string") return new URL(input, globalThis.location?.origin || "http://localhost").pathname.replace(/^\/api\//, "");
    return String(input.url || "").replace(/^\/api\//, "");
  } catch {
    return String(input);
  }
}

function shouldAuditGet(path: string): boolean {
  const now = Date.now();
  const previous = lastGetAudit.get(path) || 0;
  if (now - previous < GET_AUDIT_INTERVAL_MS) return false;
  lastGetAudit.set(path, now);
  return true;
}

async function sendAudit(event: FrontendAuditEvent): Promise<void> {
  if (!homeAssistant) {
    auditQueue.push(event);
    if (auditQueue.length > 250) auditQueue.splice(0, auditQueue.length - 250);
    return;
  }
  try {
    await homeAssistant.callApi("post", AUDIT_PATH, event);
  } catch {
    auditQueue.push(event);
    if (auditQueue.length > 250) auditQueue.splice(0, auditQueue.length - 250);
  }
}

async function flushAuditQueue(): Promise<void> {
  if (!homeAssistant || !auditQueue.length) return;
  const pending = auditQueue.splice(0, auditQueue.length);
  for (const event of pending) {
    try {
      await homeAssistant.callApi("post", AUDIT_PATH, event);
    } catch {
      auditQueue.unshift(...pending.slice(pending.indexOf(event)));
      return;
    }
  }
}

export function writeFrontendAudit(event: FrontendAuditEvent): void {
  void sendAudit({
    ...event,
    status: event.status || "info",
    source: event.source || "frontend",
  });
}

export function configureHomeAssistantApi(host: HomeAssistantApiHost | null): void {
  homeAssistant = host;
  if (host) {
    globalThis.dispatchEvent?.(new Event("ultimate-3d-ha-api-ready"));
    writeFrontendAudit({
      category: "Lifecycle",
      component: "ha-api-transport",
      event: "home_assistant_api_ready",
      status: "success",
      details: { queued_events: auditQueue.length },
    });
    void flushAuditQueue();
  }
}

export function hasHomeAssistantApi(): boolean {
  return homeAssistant !== null;
}

export type AuthenticatedUploadProgress = Readonly<{
  loadedBytes: number;
  totalBytes: number;
  ratio: number;
  elapsedSeconds: number;
  rateBytesPerSecond: number;
  etaSeconds?: number | undefined;
}>;

export function uploadProgressSnapshot(
  loadedBytes: number,
  totalBytes: number,
  startedAtMs: number,
  nowMs: number,
): AuthenticatedUploadProgress {
  const loaded = Math.max(0, Number(loadedBytes) || 0);
  const total = Math.max(loaded, Number(totalBytes) || 0);
  const elapsedSeconds = Math.max(.001, (Number(nowMs) - Number(startedAtMs)) / 1000);
  const rateBytesPerSecond = loaded > 0 && elapsedSeconds >= .05 ? loaded / elapsedSeconds : 0;
  const etaSeconds = rateBytesPerSecond > 0 && total > loaded
    ? (total - loaded) / rateBytesPerSecond
    : undefined;
  return {
    loadedBytes: loaded,
    totalBytes: total,
    ratio: total > 0 ? Math.max(0, Math.min(1, loaded / total)) : 0,
    elapsedSeconds,
    rateBytesPerSecond,
    etaSeconds,
  };
}

export async function authenticatedUpload(
  input: RequestInfo | URL,
  init: RequestInit,
  onProgress?: (progress: AuthenticatedUploadProgress) => void,
): Promise<Response> {
  if (!homeAssistant) throw new Error("Home-Assistant-API ist noch nicht initialisiert.");
  const accessToken = homeAssistant.auth?.accessToken ?? homeAssistant.auth?.data?.access_token;
  if (!accessToken) throw new Error("Kein Home-Assistant-Zugriffstoken verfügbar.");
  const body = init.body;
  if (!(body instanceof Blob)) throw new Error("Der authentifizierte Upload erwartet eine Binärdatei.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  const method = String(init.method || "POST").toUpperCase();
  const path = auditPath(input);
  const target = input instanceof URL ? input.toString() : typeof input === "string" ? input : input.url;
  const started = performance.now();

  return await new Promise<Response>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, target, true);
    xhr.responseType = "arraybuffer";
    xhr.withCredentials = true;
    headers.forEach((value, key) => xhr.setRequestHeader(key, value));
    xhr.upload.addEventListener("progress", (event) => {
      const total = Math.max(body.size, event.lengthComputable ? event.total : 0, event.loaded);
      const snapshot = uploadProgressSnapshot(event.loaded, total, started, performance.now());
      try { onProgress?.(snapshot); } catch {}
    });
    xhr.addEventListener("load", () => {
      const responseHeaders = new Headers();
      for (const line of xhr.getAllResponseHeaders().trim().split(/[\r\n]+/)) {
        if (!line) continue;
        const separator = line.indexOf(":");
        if (separator <= 0) continue;
        responseHeaders.append(line.slice(0, separator).trim(), line.slice(separator + 1).trim());
      }
      const duration = Math.round(performance.now() - started);
      if (path !== AUDIT_PATH) {
        writeFrontendAudit({
          category: auditCategory(path),
          component: "frontend_binary_upload",
          event: `${method} ${path}`,
          status: xhr.status >= 200 && xhr.status < 400 ? "success" : "error",
          duration_ms: duration,
          details: { method, path, http_status: xhr.status, body_type: body.constructor.name, size_bytes: body.size },
        });
      }
      resolve(new Response(xhr.response ?? new ArrayBuffer(0), { status: xhr.status, statusText: xhr.statusText, headers: responseHeaders }));
    });
    const fail = (kind: string): void => {
      const message = `Upload fehlgeschlagen (${kind}).`;
      if (path !== AUDIT_PATH) {
        writeFrontendAudit({
          category: auditCategory(path),
          component: "frontend_binary_upload",
          event: `${method} ${path}`,
          status: "error",
          duration_ms: Math.round(performance.now() - started),
          details: { method, path, error: message, size_bytes: body.size },
        });
      }
      reject(new Error(message));
    };
    xhr.addEventListener("error", () => fail("Netzwerkfehler"));
    xhr.addEventListener("abort", () => fail("abgebrochen"));
    xhr.addEventListener("timeout", () => fail("Zeitüberschreitung"));
    xhr.send(body);
  });
}

export async function authenticatedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
): Promise<Response> {
  if (!homeAssistant) throw new Error("Home-Assistant-API ist noch nicht initialisiert.");
  const accessToken = homeAssistant.auth?.accessToken ?? homeAssistant.auth?.data?.access_token;
  if (!accessToken) throw new Error("Kein Home-Assistant-Zugriffstoken verfügbar.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  const method = String(init.method || "GET").toUpperCase();
  const path = auditPath(input);
  const started = performance.now();
  try {
    const response = await fetch(input, { ...init, credentials: "same-origin", headers });
    const duration = Math.round(performance.now() - started);
    if (path !== AUDIT_PATH && (method !== "GET" || !response.ok || shouldAuditGet(path))) {
      writeFrontendAudit({
        category: auditCategory(path),
        component: "frontend_binary_api",
        event: `${method} ${path}`,
        status: response.ok ? "success" : "error",
        duration_ms: duration,
        details: { method, path, http_status: response.status, body_type: init.body?.constructor?.name || null },
      });
    }
    return response;
  } catch (error) {
    if (path !== AUDIT_PATH) {
      writeFrontendAudit({
        category: auditCategory(path),
        component: "frontend_binary_api",
        event: `${method} ${path}`,
        status: "error",
        duration_ms: Math.round(performance.now() - started),
        details: { method, path, error: errorMessage(error) },
      });
    }
    throw error;
  }
}

export async function callHomeAssistantApi<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  parameters?: unknown,
): Promise<T> {
  if (!homeAssistant) throw new Error("Home-Assistant-API ist noch nicht initialisiert.");
  const normalized = normalizedPath(path);
  const started = performance.now();
  try {
    const result = await homeAssistant.callApi<T>(method.toLowerCase(), normalized, parameters);
    if (normalized !== AUDIT_PATH && (method !== "GET" || shouldAuditGet(normalized))) {
      writeFrontendAudit({
        category: auditCategory(normalized),
        component: "frontend_api",
        event: `${method} ${normalized}`,
        status: "success",
        duration_ms: Math.round(performance.now() - started),
        details: { method, path: normalized },
      });
    }
    return result;
  } catch (callApiError) {
    const message = errorMessage(callApiError);
    if (normalized !== AUDIT_PATH) {
      writeFrontendAudit({
        category: auditCategory(normalized),
        component: "frontend_api",
        event: `${method} ${normalized}`,
        status: "error",
        duration_ms: Math.round(performance.now() - started),
        details: { method, path: normalized, error: message },
      });
    }
    throw new Error(message);
  }
}

export async function callEnvelopeApi<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  parameters?: unknown,
  allowNull = false,
): Promise<T | null> {
  const envelope = await callHomeAssistantApi<ApiEnvelope<T>>(method, path, parameters);
  if (envelope.error) throw new Error(errorMessage(envelope.error));
  if (envelope.data === undefined || (!allowNull && envelope.data === null)) {
    throw new Error("Die API hat keine verwertbaren Daten geliefert.");
  }
  return envelope.data ?? null;
}
