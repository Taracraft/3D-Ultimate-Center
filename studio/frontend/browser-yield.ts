export async function yieldToBrowser(): Promise<void> {
  const scheduler = (globalThis as typeof globalThis & { scheduler?: { yield?: () => Promise<void> } }).scheduler;
  if (typeof scheduler?.yield === "function") {
    await scheduler.yield();
    return;
  }
  await new Promise<void>((resolve) => globalThis.setTimeout(resolve, 0));
}

export async function waitForBrowserPaint(): Promise<void> {
  const requestFrame = globalThis.requestAnimationFrame;
  if (typeof requestFrame === "function") {
    await new Promise<void>((resolve) => requestFrame(() => resolve()));
    return;
  }
  await yieldToBrowser();
}
