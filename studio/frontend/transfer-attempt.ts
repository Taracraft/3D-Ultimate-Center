/** Use server-issued start identities, not clocks on different devices. */
export function transferMatchesAttempt(
  startedAt: string,
  previousStartedAt: string,
  requestedTrace: string,
  activeTrace: string,
): boolean {
  return Boolean(startedAt && requestedTrace && requestedTrace === activeTrace && startedAt !== previousStartedAt);
}
