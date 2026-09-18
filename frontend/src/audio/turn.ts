/**
 * Turn detection. Client-side, because it saves a network round trip on every turn.
 *
 * The silence threshold is a PRODUCT DECISION, not a constant: it trades
 * cutting the user off against making them wait. Expose it while developing,
 * then fix a value and write down why.
 *
 * Gate the VAD during playback. The microphone is live while the speakers play
 * Sarjy's own audio; echoCancellation is necessary and not sufficient.
 *
 * Backchannels — "mhm", "yeah" — must not end a turn.
 */

export const SILENCE_MS = 600; // TODO: tune by feel, then record the reason here.

export async function startTurnDetection(): Promise<void> {
  throw new Error("not implemented");
}
