/**
 * Microphone capture: getUserMedia -> AudioWorklet -> 16 kHz PCM16.
 *
 * The fiddliest part of the project and where voice demos usually break.
 * It is pure engineering — every bug here is fixable and none are mysterious.
 *
 * Three things that are not optional:
 *   - AudioWorklet, never ScriptProcessor (deprecated, main-thread, janky)
 *   - getUserMedia gives 48 kHz float; STT wants 16 kHz PCM16. Resample explicitly.
 *   - echoCancellation in the constraints, or the assistant hears itself and
 *     interrupts itself. One line; looks like a deep architectural bug without it.
 *
 * Rules: .claude/rules/voice/browser-audio.md
 */

export const TARGET_SAMPLE_RATE = 16_000;

export const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

export async function startCapture(_onFrame: (pcm16: ArrayBuffer) => void): Promise<() => void> {
  throw new Error("Day 1: mic -> worklet -> resample -> onFrame. Test in isolation first.");
}
