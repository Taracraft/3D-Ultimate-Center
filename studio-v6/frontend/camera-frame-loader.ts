export interface CameraFrameImage {
  src: string;
  readonly complete: boolean;
  readonly naturalWidth: number;
  addEventListener(type: string, listener: EventListener): void;
  removeEventListener(type: string, listener: EventListener): void;
}

/** Install listeners before starting the image request; abort covers image loading too. */
export function waitForCameraImage(image: CameraFrameImage, url: string, signal: AbortSignal): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    let settled = false;
    const finish = (error?: unknown): void => {
      if (settled) return;
      settled = true;
      image.removeEventListener("load", loaded);
      image.removeEventListener("error", failed);
      signal.removeEventListener("abort", aborted);
      if (error) reject(error); else resolve();
    };
    const loaded = (): void => image.naturalWidth > 0
      ? finish() : finish(new Error("Kamerabild konnte nicht geladen werden."));
    const failed = (): void => finish(new Error("Kamerabild konnte nicht geladen werden."));
    const aborted = (): void => finish(signal.reason ?? new DOMException("Kamerabild abgebrochen.", "AbortError"));
    if (signal.aborted) { aborted(); return; }
    image.addEventListener("load", loaded);
    image.addEventListener("error", failed);
    signal.addEventListener("abort", aborted, { once: true });
    try {
      image.src = url;
      if (image.complete) loaded();
    } catch (error) { finish(error); }
  });
}
