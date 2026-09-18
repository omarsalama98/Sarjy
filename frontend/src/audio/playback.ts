/**
 * Playback: schedule PCM chunks into an AudioContext.
 *
 * Never point an <audio> element at a stream — you get neither low latency nor
 * clean interruption.
 *
 * Barge-in must stop audio NOW: drop scheduled buffers, do not drain the
 * current chunk. See stop().
 *
 * An AudioContext starts suspended until a user gesture — resume it on the
 * first interaction, and make sure the first thing the user does provides one.
 */

export async function enqueue(_pcm: ArrayBuffer): Promise<void> {
  throw new Error("not implemented");
}

/** Immediate. Drops queued buffers rather than letting them drain. */
export function stop(): void {
  throw new Error("not implemented");
}
