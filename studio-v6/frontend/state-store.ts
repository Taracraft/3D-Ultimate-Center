export type Listener<T> = (state: Readonly<T>) => void;
export type Reducer<T, A> = (state: Readonly<T>, action: Readonly<A>) => T;

export class Store<T, A> {
  #state: T;
  #listeners = new Set<Listener<T>>();

  constructor(initialState: T, private readonly reducer: Reducer<T, A>) {
    this.#state = Object.freeze(initialState);
  }

  getState(): Readonly<T> {
    return this.#state;
  }

  dispatch(action: Readonly<A>): void {
    const next = this.reducer(this.#state, action);
    if (Object.is(next, this.#state)) {
      return;
    }
    this.#state = Object.freeze(next);
    for (const listener of this.#listeners) {
      listener(this.#state);
    }
  }

  subscribe(listener: Listener<T>): () => void {
    this.#listeners.add(listener);
    listener(this.#state);
    return () => this.#listeners.delete(listener);
  }
}