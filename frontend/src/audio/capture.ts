/**
 * Microphone capture: one shared getUserMedia stream, and the float32 ->
 * PCM16 conversion the rest of the pipeline needs.
 *
 * Capture itself lives in `recorder.ts` (AudioWorklet + user-controlled
 * start/stop). This module is the shared MediaStream so the orb's analyser
 * and the recorder never open two microphones.
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
 * denied) or `NotFoundError` (F4, no mic present).
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
  if (sharedStream) {
    for (const track of sharedStream.getTracks()) {
      track.stop();
    }
  }
  sharedStream = null;
  sharedStreamPromise = null;
}

/**
 * float32 samples in [-1, 1] -> little-endian PCM16 bytes.
 */
export function floatToPCM16(samples: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]!));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer as ArrayBuffer;
}
