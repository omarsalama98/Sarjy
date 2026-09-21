/**
 * Microphone capture: one shared getUserMedia stream, and the float32 ->
 * PCM16 conversion the rest of the pipeline needs.
 *
 * There is deliberately no second AudioWorklet capture graph here. The VAD
 * (@ricky0123/vad-web) already runs its own capture internally, and
 * `onSpeechEnd` hands back the exact Float32Array segment we want to send
 * -- pre-speech padding included -- at 16 kHz. Building a parallel worklet
 * and slicing a ring buffer by VAD timestamps would produce the same bytes
 * with twice the moving parts (docs/plans/blocks/02-voice-loop.md,
 * "design decision 1"). What IS shared is the underlying MediaStream: the
 * VAD's `getStream` option (turn.ts) is overridden to return the stream
 * this module opens, so there is still only ever one mic prompt and one
 * open microphone, never two.
 *
 * Rules: .claude/rules/voice/browser-audio.md
 */

export const TARGET_SAMPLE_RATE = 16_000;

export const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

let sharedStream: MediaStream | null = null;
let sharedStreamPromise: Promise<MediaStream> | null = null;

/**
 * Opens the microphone once and reuses the same MediaStream for every
 * caller. `getUserMedia` itself is what throws `NotAllowedError` (F3, mic
 * denied) or `NotFoundError` (F4, no mic present) -- turn.ts's caller is
 * where those are caught and turned into visible UI state.
 */
export async function getSharedMicStream(): Promise<MediaStream> {
  if (sharedStream) return sharedStream;
  if (!sharedStreamPromise) {
    // Single-flight for concurrent callers, but a REJECTED promise must not
    // stay cached -- without the .catch() below, denying the mic once left
    // every later call (including the Retry button, F3) re-awaiting the
    // same dead rejection forever, never calling getUserMedia() again even
    // after the user allowed the mic in the address bar.
    sharedStreamPromise = navigator.mediaDevices.getUserMedia({ audio: MIC_CONSTRAINTS }).catch((err: unknown) => {
      sharedStreamPromise = null;
      throw err;
    });
  }
  sharedStream = await sharedStreamPromise;
  return sharedStream;
}

/** F5: permission revoked mid-session, or the device disappearing, both
 * surface as the stream's track ending. Clears the cache so the next call
 * to getSharedMicStream() re-prompts instead of handing back a dead stream. */
export function clearSharedMicStream(): void {
  sharedStream = null;
  sharedStreamPromise = null;
}

/**
 * float32 samples in [-1, 1] -> little-endian PCM16 bytes. Lifted verbatim
 * from the Block 0 spike's worklet (frontend/src/spike/worklet.js, deleted
 * in this same commit) -- the conversion math was already proven correct
 * there; there is nothing to improve by rederiving it.
 */
export function floatToPCM16(samples: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]!));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}
