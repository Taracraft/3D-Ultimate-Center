/** Coordinates reads and mutations without allowing an old list to replace a new view. */
export class GalleryOperationState {
  #revision = 0;
  #busy = false;

  get busy(): boolean { return this.#busy; }

  invalidate(): void { this.#revision += 1; }

  async refresh<T>(load: () => Promise<T>, apply: (value: T) => void): Promise<boolean> {
    if (this.#busy) return false;
    const revision = ++this.#revision;
    try {
      const value = await load();
      if (revision !== this.#revision || this.#busy) return false;
      apply(value);
      return true;
    } catch (error) {
      if (revision !== this.#revision || this.#busy) return false;
      throw error;
    }
  }

  async mutate(operation: () => Promise<void>, refresh: () => Promise<unknown>): Promise<boolean> {
    if (this.#busy) return false;
    this.#busy = true;
    this.invalidate();
    try {
      await operation();
      return true;
    } finally {
      // A partially completed batch also changes the library. Unlock before the
      // refresh, otherwise the read guard would silently discard that update.
      this.#busy = false;
      await refresh();
    }
  }
}
