export {};

declare global {
  interface Math {
    /**
     * Vec3-Grenzberechnung mit dynamischem Index 0..2.
     * Die aufrufende Schleife garantiert, dass beide Tupelwerte vorhanden sind.
     */
    min(a: number | undefined, b: number | undefined): number;
    max(a: number | undefined, b: number | undefined): number;
  }
}
