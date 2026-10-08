export type HistoryState<T> = Readonly<{
  canUndo: boolean;
  canRedo: boolean;
  undoCount: number;
  redoCount: number;
}>;

export class ModelStateHistory<T> {
  readonly #clone: (value: T) => T;
  readonly #signature: (value: T) => string;
  readonly #maximum: number;
  #current: T | null = null;
  #currentSignature = "";
  #undo: T[] = [];
  #redo: T[] = [];

  constructor(options: Readonly<{
    clone: (value: T) => T;
    signature: (value: T) => string;
    maximum?: number;
  }>) {
    this.#clone = options.clone;
    this.#signature = options.signature;
    this.#maximum = Math.max(1, Math.min(50, options.maximum ?? 20));
  }

  get state(): HistoryState<T> {
    return {
      canUndo: this.#undo.length > 0,
      canRedo: this.#redo.length > 0,
      undoCount: this.#undo.length,
      redoCount: this.#redo.length,
    };
  }

  reset(value: T): void {
    this.#current = this.#clone(value);
    this.#currentSignature = this.#signature(value);
    this.#undo = [];
    this.#redo = [];
  }

  checkpoint(value: T): boolean {
    const nextSignature = this.#signature(value);
    if (this.#current === null) {
      this.reset(value);
      return false;
    }
    if (nextSignature === this.#currentSignature) return false;
    this.#undo.push(this.#current);
    this.#undo = this.#undo.slice(-this.#maximum);
    this.#current = this.#clone(value);
    this.#currentSignature = nextSignature;
    this.#redo = [];
    return true;
  }

  undo(): T | null {
    if (this.#current === null || this.#undo.length === 0) return null;
    this.#redo.push(this.#current);
    const previous = this.#undo.pop()!;
    this.#current = this.#clone(previous);
    this.#currentSignature = this.#signature(previous);
    return this.#clone(previous);
  }

  redo(): T | null {
    if (this.#current === null || this.#redo.length === 0) return null;
    this.#undo.push(this.#current);
    const next = this.#redo.pop()!;
    this.#current = this.#clone(next);
    this.#currentSignature = this.#signature(next);
    return this.#clone(next);
  }
}
